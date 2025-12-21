from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from typing import Generator, Optional
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from shared.config import get_settings
from shared.logging_config import get_logger
from app.models import Base

logger = get_logger(__name__, "auth-service")


class DatabaseManager:
    """SQLAlchemy database connection manager with connection pooling"""
    
    def __init__(self, database_url: Optional[str] = None):

        self.settings = get_settings()
        self.database_url = database_url or self.settings.database.url
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
    
    def create_engine(self) -> Engine:
        """Create SQLAlchemy engine with connection pooling"""
        if self._engine is None:
            try:
                self._engine = create_engine(
                    self.database_url,
                    poolclass=QueuePool,
                    pool_size=self.settings.database.pool_size,
                    max_overflow=self.settings.database.max_overflow,
                    pool_timeout=self.settings.database.pool_timeout,
                    pool_pre_ping=True,  # Verify connections before using
                    pool_recycle=3600,  # Recycle connections after 1 hour
                    echo=False,  # Set to True for SQL query logging
                )
                
                # Add connection pool event listeners
                @event.listens_for(self._engine, "connect")
                def set_sqlite_pragma(dbapi_conn, connection_record):
                    """Set connection-level settings"""
                    pass
                
                @event.listens_for(self._engine, "checkout")
                def receive_checkout(dbapi_conn, connection_record, connection_proxy):
                    """Log connection checkout"""
                    logger.debug("Connection checked out from pool")
                
                @event.listens_for(self._engine, "checkin")
                def receive_checkin(dbapi_conn, connection_record):
                    """Log connection checkin"""
                    logger.debug("Connection returned to pool")
                
                logger.info(
                    f"Database engine created with pool_size={self.settings.database.pool_size}, "
                    f"max_overflow={self.settings.database.max_overflow}"
                )
            except Exception as e:
                logger.error(f"Failed to create database engine: {e}")
                raise
        
        return self._engine
    
    @property
    def engine(self) -> Engine:
        """Get database engine (creates if not exists)"""
        if self._engine is None:
            self.create_engine()
        return self._engine
    
    def create_session_factory(self) -> sessionmaker:
        """Create session factory"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
                expire_on_commit=False,
            )
            logger.info("Session factory created")
        return self._session_factory
    
    @property
    def session_factory(self) -> sessionmaker:
        """Get session factory (creates if not exists)"""
        if self._session_factory is None:
            self.create_session_factory()
        return self._session_factory
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()
    
    @contextmanager
    def get_session_context(self):

        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error, rolling back: {e}")
            raise
        finally:
            session.close()
    
    def health_check(self) -> bool:

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.scalar()  # Consume the result
            logger.debug("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def get_pool_status(self) -> dict:

        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
        }
    
    def close(self):
        """Close all database connections and dispose of the engine"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connections closed")
    
    def init_db(self):
        """Initialize database - create all tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_db(self):
        """Drop all tables - use with caution!"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise


# Global database manager instance (singleton pattern)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db() -> Generator[Session, None, None]:

    db_manager = get_db_manager()
    session = db_manager.get_session()
    try:
        yield session
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


# Backward compatibility - expose engine and SessionLocal
def get_engine() -> Engine:
    """Get database engine (for backward compatibility)"""
    return get_db_manager().engine


def get_session_local() -> sessionmaker:
    """Get session factory (for backward compatibility)"""
    return get_db_manager().session_factory


# Initialize engine and session factory on module import
db_manager = get_db_manager()
engine = db_manager.engine
SessionLocal = db_manager.session_factory


def init_db():
    """Initialize database - create all tables (for backward compatibility)"""
    db_manager.init_db()


def drop_db():
    """Drop all tables - use with caution! (for backward compatibility)"""
    db_manager.drop_db()
