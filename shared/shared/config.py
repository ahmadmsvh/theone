from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path
import os
from dotenv import load_dotenv
import logging
import json

logger = logging.getLogger(__name__)

try:
    from google.cloud import secretmanager
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    logger.warning("google-cloud-secret-manager not installed. GCP Secret Manager will not be available.")


class AuthDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_AUTH_")
    
    url: str
    pool_size: int
    max_overflow: int
    pool_timeout: int

class OrderDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_ORDER_")
    
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

def load_gcp_secrets(project_id: str, secret_names: Optional[list[str]] = None, secret_prefix: Optional[str] = None) -> dict[str, str]:

    if not GCP_AVAILABLE:
        raise ImportError("google-cloud-secret-manager is not installed")
    
    secrets = {}
    try:
        client = secretmanager.SecretManagerServiceClient()
        logger.info("Successfully initialized GCP Secret Manager client")
    except Exception as e:    
        error_msg = str(e)
        logger.error(f"Failed to initialize GCP Secret Manager client: {error_msg}")
        
        # Check for common authentication issues
        gac_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not gac_path:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set")
            logger.error("For Docker: Mount service account key and set GOOGLE_APPLICATION_CREDENTIALS")
            logger.error("For local: Run 'gcloud auth application-default login'")
        elif not os.path.exists(gac_path):
            logger.error(f"GOOGLE_APPLICATION_CREDENTIALS points to non-existent file: {gac_path}")
        
        raise Exception(f"Failed to initialize GCP Secret Manager client: {error_msg}")
    parent = f"projects/{project_id}"

    if secret_prefix:

        try:
            for secret in client.list_secrets(request={"parent": parent}):
                if secret.name.split("/")[-1].startswith(secret_prefix):
                    secret_name = secret.name.split("/")[-1]
                    try:
                        name = f"{secret.name}/versions/latest"
                        response = client.access_secret_version(request={"name": name})
                        secrets[secret_name] = response.payload.data.decode("UTF-8")
                        logger.debug(f"Loaded secret: {secret_name}")
                    except Exception as e:
                        logger.debug(f"Could not load secret {secret_name}: {e}")
        except Exception as e:
            logger.warning(f"Could not list secrets with prefix {secret_prefix}: {e}")

        return secrets

    # If secret_names provided, fetch each individual secret
    if secret_names:
        for secret_name in secret_names:
            try:
                name = f"{parent}/secrets/{secret_name}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                secrets[secret_name] = response.payload.data.decode("UTF-8")
                logger.debug(f"Loaded secret: {secret_name}")
            except Exception as e:
                error_msg = str(e)
                # Log at warning level for authentication/permission errors, debug for missing secrets
                if "permission" in error_msg.lower() or "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                    logger.warning(f"Could not load secret '{secret_name}': {error_msg}")
                else:
                    logger.debug(f"Could not load secret '{secret_name}': {error_msg}")
    
    return secrets


def load_environment_variables():

    environment = os.getenv("ENVIRONMENT", "development").lower()
    gcp_project_id = os.getenv("GCP_PROJECT_ID")

    use_gcp = (
        environment == "production" or 
        (gcp_project_id and os.getenv("USE_GCP_SECRETS", "false").lower() == "true")
    )
    
    if use_gcp and gcp_project_id and GCP_AVAILABLE:
        try:
            logger.info(f"Loading secrets from GCP Secret Manager for project: {gcp_project_id}")
            
            secret_prefix = os.getenv("GCP_SECRET_PREFIX")
            secret_names_str = os.getenv("GCP_SECRET_NAMES")
            secret_names = secret_names_str.split(",") if secret_names_str else None
            if secret_names:
                secret_names = [name.strip() for name in secret_names]

            secrets = load_gcp_secrets(
                project_id=gcp_project_id,
                secret_names=secret_names,
                secret_prefix=secret_prefix
            )
            
            if not secrets:
                logger.warning(f"No secrets found in GCP Secret Manager. Check project_id: {gcp_project_id}, secret_names: {secret_names}, secret_prefix: {secret_prefix}")
            
            parsed_secrets = {}
            for secret_name, secret_value in secrets.items():
                try:
                    json_data = json.loads(secret_value)
                    if isinstance(json_data, dict):
                        logger.debug(f"Parsing JSON secret: {secret_name}")
                        for key, value in json_data.items():
                            parsed_secrets[key] = str(value)
                    else:
                        parsed_secrets[secret_name] = secret_value
                except (json.JSONDecodeError, ValueError):
                    parsed_secrets[secret_name] = secret_value
            
            if not parsed_secrets:
                logger.warning("No secrets were loaded from GCP Secret Manager. Check secret names and authentication.")
            else:
                for key, value in parsed_secrets.items():
                    os.environ[key] = value
                logger.info(f"Loaded {len(parsed_secrets)} secrets from GCP Secret Manager")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to load secrets from GCP Secret Manager: {error_msg}")
            
            if "credentials were not found" in error_msg.lower() or "authentication" in error_msg.lower():
                logger.error("GCP Authentication Error: Set up Application Default Credentials (ADC)")
                logger.error("For Docker: Mount a service account key file and set GOOGLE_APPLICATION_CREDENTIALS")
                logger.error("For local: Run 'gcloud auth application-default login'")
            
            logger.warning("Falling back to .env file or existing environment variables")
            raise Exception(f"Failed to load secrets from GCP Secret Manager: {error_msg}")
    else:
        _env_file = Path(__file__).parent / ".env"
        if _env_file.exists():
            logger.debug(f"Loading environment variables from .env file: {_env_file}")
            load_dotenv(dotenv_path=_env_file)
        else:
            logger.debug(".env file not found, using existing environment variables")


class Settings(BaseSettings):
    model_config = SettingsConfigDict()
    
    authDatabase: Optional[AuthDatabaseSettings] = None
    orderDatabase: Optional[OrderDatabaseSettings] = None
    mongodb: Optional[MongoSettings] = None
    redis: Optional[RedisSettings] = None
    rabbitmq: Optional[RabbitMQSettings] = None
    app: AppSettings = Field(default_factory=AppSettings)
    
    def __init__(self, **kwargs):
        if "USE_GCP_SECRETS" not in os.environ:
            os.environ["USE_GCP_SECRETS"] = "false"
        if "GCP_PROJECT_ID" not in os.environ:
            os.environ["GCP_PROJECT_ID"] = "theone-35860"
        if "GCP_SECRET_NAMES" not in os.environ:
            os.environ["GCP_SECRET_NAMES"] = "theone_secrets"
        if "GCP_SECRET_PREFIX" not in os.environ:
            os.environ["GCP_SECRET_PREFIX"] = ""

        load_environment_variables()

        super().__init__(**kwargs)
    
    @model_validator(mode='after')
    def create_nested_settings(self):

        if os.getenv("POSTGRES_AUTH_URL"):
            try:
                self.authDatabase = AuthDatabaseSettings()
            except Exception:
                pass
        
        if os.getenv("POSTGRES_ORDER_URL"):
            try:
                self.orderDatabase = OrderDatabaseSettings()
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
    return Settings()

