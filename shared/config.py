from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class DatabaseSettings(BaseSettings):
    """PostgreSQL database settings"""
    model_config = SettingsConfigDict(env_prefix="DATABASE_")
    
    url: str = "postgresql://postgres:postgres@localhost:5432/theone_db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30


class MongoSettings(BaseSettings):
    """MongoDB database settings"""
    model_config = SettingsConfigDict(env_prefix="MONGODB_")
    
    url: str = "mongodb://admin:admin@localhost:27017/theone_db?authSource=admin"
    database: str = "theone_db"


class RedisSettings(BaseSettings):
    """Redis cache settings"""
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    url: str = "redis://localhost:6379"
    decode_responses: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


class RabbitMQSettings(BaseSettings):
    """RabbitMQ message queue settings"""
    model_config = SettingsConfigDict(env_prefix="RABBITMQ_")
    
    url: str = "amqp://admin:admin@localhost:5672/"
    exchange: str = "theone_exchange"
    queue_prefix: str = "theone"
    prefetch_count: int = 10


class AppSettings(BaseSettings):
    """Application settings"""
    model_config = SettingsConfigDict(env_prefix="")
    
    app_name: str = "theone-service"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    service_name: str = "unknown"


class Settings(BaseSettings):
    """Main settings class combining all configurations"""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    database: DatabaseSettings = DatabaseSettings()
    mongodb: MongoSettings = MongoSettings()
    redis: RedisSettings = RedisSettings()
    rabbitmq: RabbitMQSettings = RabbitMQSettings()
    app: AppSettings = AppSettings()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Override with environment variables if provided
        if "DATABASE_URL" in kwargs:
            self.database.url = kwargs["DATABASE_URL"]
        if "MONGODB_URL" in kwargs:
            self.mongodb.url = kwargs["MONGODB_URL"]
        if "REDIS_URL" in kwargs:
            self.redis.url = kwargs["REDIS_URL"]
        if "RABBITMQ_URL" in kwargs:
            self.rabbitmq.url = kwargs["RABBITMQ_URL"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

