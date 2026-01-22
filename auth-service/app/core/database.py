from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from typing import Generator, Optional
from shared.config import get_settings
from shared.logging_config import get_logger, setup_logging
from app.models import Base

settings = get_settings()
setup_logging(service_name=settings.app.service_name, log_level=settings.app.log_level)

logger = get_logger(__name__, "auth-service")
logger.setLevel("DEBUG")

class DatabaseManager:
    
    def __init__(self, database_url: Optional[str] = None):
        self.settings = get_settings()
        self.database_url = database_url or self.settings.authDatabase.url
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
    
    def create_engine(self) -> Engine:
        if self._engine is None:
            try:
                self._engine = create_engine(
                    self.database_url,
                    poolclass=QueuePool,
                    pool_size=self.settings.authDatabase.pool_size,
                    max_overflow=self.settings.authDatabase.max_overflow,
                    pool_timeout=self.settings.authDatabase.pool_timeout,
                    pool_pre_ping=True, 
                    pool_recycle=3600,
                    echo=False,
                )
                
                @event.listens_for(self._engine, "connect")
                def set_sqlite_pragma(dbapi_conn, connection_record):
                    pass
                
                @event.listens_for(self._engine, "checkout")
                def receive_checkout(dbapi_conn, connection_record, connection_proxy):
                    logger.debug("Connection checked out from pool")
                
                @event.listens_for(self._engine, "checkin")
                def receive_checkin(dbapi_conn, connection_record):
                    logger.debug("Connection returned to pool")
                
                logger.info(
                    f"Database engine created with pool_size={self.settings.authDatabase.pool_size}, "
                    f"max_overflow={self.settings.authDatabase.max_overflow}"
                )
            except Exception as e:
                logger.error(f"Failed to create database engine: {e}")
                raise
        
        return self._engine
    
    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self.create_engine()
        return self._engine
    
    def create_session_factory(self) -> sessionmaker:
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
        if self._session_factory is None:
            self.create_session_factory()
        return self._session_factory
    
    def get_session(self) -> Session:
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
                result.scalar()
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
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connections closed")
    
    def init_db(self):
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_db(self):  
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise

                
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
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


def get_engine() -> Engine:
    return get_db_manager().engine


def get_session_local() -> sessionmaker:
    return get_db_manager().session_factory


db_manager = get_db_manager()
engine = db_manager.engine
SessionLocal = db_manager.session_factory


def init_db():
    db_manager.init_db()


def drop_db():
    db_manager.drop_db()
