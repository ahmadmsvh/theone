import asyncio
from typing import Optional
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from shared.config import get_settings
from shared.logging_config import get_logger

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


settings = get_settings()
logger = get_logger(__name__, settings.app.service_name)


class PostgreSQLConnection:
    """PostgreSQL connection pool manager"""
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
        if self.settings.database is None:
            raise ValueError(
                "PostgreSQL settings are not configured. "
                "Please set DATABASE_URL environment variable."
            )
        self.connection_url = connection_url or self.settings.database.url
        self._pool: Optional[pool.ThreadedConnectionPool] = None
    
    def create_pool(self):
        """Create connection pool"""
        if self._pool is None:
            try:
                self._pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=self.settings.database.pool_size,
                    dsn=self.connection_url
                )
                logger.info("PostgreSQL connection pool created successfully")
            except Exception as e:
                logger.error(f"Failed to create PostgreSQL connection pool: {e}")
                raise
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        if self._pool is None:
            self.create_pool()
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """Get a cursor from the connection pool"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database cursor error: {e}")
                raise
            finally:
                cursor.close()
    
    def close_pool(self):
        """Close all connections in the pool"""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")


class AsyncMongoDBConnection:
    """Async MongoDB connection manager using Motor"""
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
        if self.settings.mongodb is None:
            raise ValueError(
                "MongoDB settings are not configured. "
                "Please set MONGODB_URL and MONGODB_DATABASE environment variables."
            )
        self.connection_url = connection_url or self.settings.mongodb.url
        self.database_name = self.settings.mongodb.database
        self._client: Optional[AsyncIOMotorClient] = None
        self._database: Optional[AsyncIOMotorDatabase] = None
        self._loop_id = None  # Track the event loop ID
    
    def _is_client_valid_for_current_loop(self) -> bool:
        """Check if the client is valid for the current event loop"""
        if self._client is None:
            return False
        try:
            # Try to get the current event loop
            current_loop = None
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    current_loop = asyncio.get_event_loop()
                except RuntimeError:
                    return False
            
            # If we have a stored loop ID, check if it matches
            if self._loop_id is not None:
                try:
                    stored_loop_id = id(self._loop_id)
                    current_loop_id = id(current_loop)
                    return stored_loop_id == current_loop_id
                except Exception:
                    return False
            
            return True
        except Exception:
            return False
    
    async def connect(self):
        """Connect to MongoDB"""
        # Check if we need to recreate the client for a new event loop
        if not self._is_client_valid_for_current_loop():
            # Close existing client if it exists
            if self._client is not None:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
                self._database = None
        
        if self._client is None:
            try:
                # Get current event loop
                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = asyncio.get_event_loop()
                
                self._client = AsyncIOMotorClient(
                    self.connection_url,
                    serverSelectionTimeoutMS=5000,
                    maxPoolSize=50,
                    minPoolSize=10
                )
                # Store the event loop reference
                self._loop_id = current_loop
                
                # Test connection
                await self._client.admin.command('ping')
                self._database = self._client[self.database_name]
                logger.info(f"MongoDB async connection established to database: {self.database_name}")
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error connecting to MongoDB: {e}")
                raise
    
    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self._database is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._database
    
    @property
    def client(self) -> AsyncIOMotorClient:
        """Get MongoDB client"""
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._client
    
    async def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("MongoDB async connection closed")
    
    async def health_check(self) -> bool:
        """Check MongoDB health"""
        try:
            # Ensure client is connected
            if self._client is None:
                await self.connect()
            
            # Try to ping, and reconnect if we get a "different loop" error
            try:
                await self._client.admin.command('ping')
                logger.debug("MongoDB async health check passed")
                return True
            except (RuntimeError, ValueError) as e:
                # Check if this is the "attached to a different loop" error
                error_msg = str(e)
                if "different loop" in error_msg.lower() or "attached to a different" in error_msg.lower():
                    logger.warning("MongoDB client attached to different event loop, reconnecting...")
                    # Close and reconnect
                    try:
                        if self._client is not None:
                            self._client.close()
                    except Exception:
                        pass
                    self._client = None
                    self._database = None
                    self._loop_id = None
                    await self.connect()
                    # Retry ping
                    await self._client.admin.command('ping')
                    logger.debug("MongoDB async health check passed after reconnection")
                    return True
                else:
                    raise
        except Exception as e:
            error_msg = str(e)
            # Also check for "different loop" in the outer exception
            if "different loop" in error_msg.lower() or "attached to a different" in error_msg.lower():
                logger.warning("MongoDB client attached to different event loop, reconnecting...")
                try:
                    if self._client is not None:
                        self._client.close()
                except Exception:
                    pass
                self._client = None
                self._database = None
                self._loop_id = None
                try:
                    await self.connect()
                    await self._client.admin.command('ping')
                    logger.debug("MongoDB async health check passed after reconnection")
                    return True
                except Exception as reconnect_error:
                    logger.error(f"MongoDB async health check failed after reconnection attempt: {reconnect_error}")
                    return False
            else:
                logger.error(f"MongoDB async health check failed: {e}")
                # Clean up on any other error
                try:
                    if self._client is not None:
                        self._client.close()
                except Exception:
                    pass
                self._client = None
                self._database = None
                self._loop_id = None
                return False


class RedisConnection:
    """Redis connection manager"""
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
        if self.settings.redis is None:
            raise ValueError(
                "Redis settings are not configured. "
                "Please set REDIS_URL environment variable."
            )
        self.connection_url = connection_url or self.settings.redis.url
        self._client: Optional[Redis] = None
    
    def connect(self):
        """Connect to Redis"""
        if self._client is None:
            try:
                self._client = Redis.from_url(
                    self.connection_url,
                    decode_responses=self.settings.redis.decode_responses,
                    socket_timeout=self.settings.redis.socket_timeout,
                    socket_connect_timeout=self.settings.redis.socket_connect_timeout
                )
                # Test connection
                self._client.ping()
                logger.info("Redis connection established successfully")
            except RedisConnectionError as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    @property
    def client(self) -> Redis:
        """Get Redis client"""
        if self._client is None:
            self.connect()
        return self._client
    
    def close(self):
        """Close Redis connection"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Redis connection closed")
    
    def health_check(self) -> bool:
        """Check Redis health"""
        try:
            if self._client is None:
                self.connect()
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global connection instances (singleton pattern)
_postgres_connection: Optional[PostgreSQLConnection] = None
_async_mongo_connection: Optional[AsyncMongoDBConnection] = None
_redis_connection: Optional[RedisConnection] = None


def get_postgres() -> PostgreSQLConnection:
    """Get PostgreSQL connection instance"""
    global _postgres_connection
    if _postgres_connection is None:
        _postgres_connection = PostgreSQLConnection()
    return _postgres_connection


def get_redis() -> RedisConnection:
    """Get Redis connection instance"""
    global _redis_connection
    if _redis_connection is None:
        _redis_connection = RedisConnection()
    return _redis_connection


def get_async_mongo() -> AsyncMongoDBConnection:
    """Get async MongoDB connection instance"""
    global _async_mongo_connection
    if _async_mongo_connection is None:
        _async_mongo_connection = AsyncMongoDBConnection()
    return _async_mongo_connection

