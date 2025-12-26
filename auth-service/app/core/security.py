import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import sys
from pathlib import Path

from dotenv import load_dotenv
from shared.logging_config import get_logger
from shared.config import get_settings

settings = get_settings()
logger = get_logger(__name__, "auth-service")

# Load .env file from shared directory
shared_dir = Path(__file__).parent.parent.parent.parent / "shared"/"shared"
env_path = shared_dir / ".env"
load_dotenv(dotenv_path=env_path)

# JWT Configuration
JWT_SECRET_KEY = settings.app.jwt_secret_key
JWT_ALGORITHM = settings.app.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = int(settings.app.access_token_expire_minutes)
REFRESH_TOKEN_EXPIRE_DAYS = int(settings.app.refresh_token_expire_days)


def hash_password(password: str) -> str:

    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)  # 12 rounds is a good balance between security and performance
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:

    try:

        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def create_access_token(data: Dict[str, Any]) -> str:

    try:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e}")
        raise


def create_refresh_token(data: Dict[str, Any]) -> str:

    try:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating refresh token: {e}")
        raise


def decode_token(token: str) -> Optional[Dict[str, Any]]:

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return None
