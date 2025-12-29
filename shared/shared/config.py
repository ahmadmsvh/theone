from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path
import os
from dotenv import load_dotenv



class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")
    
    url: str
    pool_size: int
    max_overflow: int
    pool_timeout: int


class MongoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MONGODB_")
    
    url: str
    database: str


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    url: str
    decode_responses: bool
    socket_timeout: int
    socket_connect_timeout: int


class RabbitMQSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RABBITMQ_")
    
    url: str
    exchange: str
    queue_prefix: str
    prefetch_count: int


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")
    
    app_name: str
    environment: str
    debug: bool
    log_level: str
    service_name: str 
    json_output: bool
    log_file: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int

class Settings(BaseSettings):
    _env_file = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_env_file)

    model_config = SettingsConfigDict()
    
    database: Optional[DatabaseSettings] = None
    mongodb: Optional[MongoSettings] = None
    redis: Optional[RedisSettings] = None
    rabbitmq: Optional[RabbitMQSettings] = None
    app: AppSettings = Field(default_factory=AppSettings)
    
    @model_validator(mode='after')
    def create_nested_settings(self):

        if os.getenv("DATABASE_URL"):
            try:
                self.database = DatabaseSettings()
            except Exception:
                pass
        
        if os.getenv("MONGODB_URL") and os.getenv("MONGODB_DATABASE"):
            try:
                self.mongodb = MongoSettings()
            except Exception:
                pass
        
        if os.getenv("REDIS_URL"):
            try:
                self.redis = RedisSettings()
            except Exception:
                pass
        
        if os.getenv("RABBITMQ_URL"):
            try:
                self.rabbitmq = RabbitMQSettings()
            except Exception:
                pass
        
        return self


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

