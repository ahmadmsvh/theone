import os
import jwt
from functools import wraps
from typing import Optional, Dict, Any, List
from flask import request, jsonify
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from shared.logging_config import get_logger
from shared.config import get_settings

logger = get_logger(__name__, os.getenv("SERVICE_NAME", "product-service"))

settings = get_settings()
JWT_SECRET_KEY = settings.app.jwt_secret_key
JWT_ALGORITHM = settings.app.jwt_algorithm


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


def get_current_user() -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.debug("No Authorization header found")
        return None
    
    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "bearer":
            logger.warning(f"Invalid authorization scheme: {scheme}")
            return None
    except ValueError:
        logger.warning("Malformed Authorization header")
        return None
    
    payload = decode_token(token)
    if not payload:
        logger.warning("Failed to decode token")
        return None
    
    if payload.get("type") != "access":
        logger.warning(f"Invalid token type: {payload.get('type')}. Expected 'access' token.")
        return None
    
    if not payload.get("sub"):
        logger.warning("Token missing user ID (sub)")
        return None
    
    return payload


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_data = get_current_user()
        if not user_data:
            logger.warning("Unauthenticated access attempt")
            response = jsonify({
                "error": "Invalid or expired token",
                "detail": "Authentication required. Please provide a valid access token."
            })
            response.headers["WWW-Authenticate"] = "Bearer"
            return response, 401
        
        kwargs["current_user"] = user_data
        logger.debug(f"Authenticated user: {user_data.get('sub')} (roles: {user_data.get('roles', [])})")
        return f(*args, **kwargs)
    
    return decorated_function


def require_role(role_name: str):
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated_function(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                return jsonify({"error": "Authentication required"}), 401
            
            user_roles: List[str] = current_user.get("roles", [])
            if role_name not in user_roles:
                logger.warning(
                    f"User {current_user.get('sub')} attempted to access {role_name}-only resource. "
                    f"User roles: {user_roles}"
                )
                response = jsonify({
                    "error": f"Access denied. Required role: {role_name}"
                })
                response.headers["WWW-Authenticate"] = "Bearer"
                return response, 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_any_role(*role_names: str):
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated_function(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                return jsonify({"error": "Authentication required"}), 401
            
            user_roles: List[str] = current_user.get("roles", [])
            if not any(role_name in user_roles for role_name in role_names):
                logger.warning(
                    f"User {current_user.get('sub')} attempted to access resource requiring one of "
                    f"{role_names}. User roles: {user_roles}"
                )
                response = jsonify({
                    "error": f"Access denied. Required one of the following roles: {', '.join(role_names)}"
                })
                response.headers["WWW-Authenticate"] = "Bearer"
                return response, 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator