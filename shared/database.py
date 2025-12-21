import logging
from typing import Optional
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
from pymongo.database import Database
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from .config import get_settings

logger = logging.getLogger(__name__)


class PostgreSQLConnection:
    """PostgreSQL connection pool manager"""
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
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


class MongoDBConnection:
    """MongoDB connection manager"""
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
        self.connection_url = connection_url or self.settings.mongodb.url
        self._client: Optional[MongoClient] = None
        self._database: Optional[Database] = None
    
    def connect(self):
        """Connect to MongoDB"""
        if self._client is None:
            try:
                self._client = MongoClient(
                    self.connection_url,
                    serverSelectionTimeoutMS=5000
                )
                # Test connection
                self._client.server_info()
                self._database = self._client[self.settings.mongodb.database]
                logger.info("MongoDB connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
    
    @property
    def database(self) -> Database:
        """Get database instance"""
        if self._database is None:
            self.connect()
        return self._database
    
    @property
    def client(self) -> MongoClient:
        """Get MongoDB client"""
        if self._client is None:
            self.connect()
        return self._client
    
    def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("MongoDB connection closed")


class RedisConnection:
    """Redis connection manager"""
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
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
_mongo_connection: Optional[MongoDBConnection] = None
_redis_connection: Optional[RedisConnection] = None


def get_postgres() -> PostgreSQLConnection:
    """Get PostgreSQL connection instance"""
    global _postgres_connection
    if _postgres_connection is None:
        _postgres_connection = PostgreSQLConnection()
    return _postgres_connection


def get_mongo() -> MongoDBConnection:
    """Get MongoDB connection instance"""
    global _mongo_connection
    if _mongo_connection is None:
        _mongo_connection = MongoDBConnection()
    return _mongo_connection


def get_redis() -> RedisConnection:
    """Get Redis connection instance"""
    global _redis_connection
    if _redis_connection is None:
        _redis_connection = RedisConnection()
    return _redis_connection

