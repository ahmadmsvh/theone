"""
Authentication utilities for reading user information from nginx gateway headers.
Nginx validates tokens and sets X-User-Id, X-User-Email, and X-User-Roles headers.
"""
import os
from functools import wraps
from typing import Optional, Dict, Any, List
from flask import request, jsonify
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from shared.logging_config import get_logger

logger = get_logger(__name__, os.getenv("SERVICE_NAME", "product-service"))


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Extract user information from headers set by nginx auth_request module.
    Nginx validates tokens and sets X-User-Id, X-User-Email, and X-User-Roles headers.
    """
    user_id = request.headers.get("X-User-Id")
    user_email = request.headers.get("X-User-Email", "")
    user_roles_str = request.headers.get("X-User-Roles", "")
    
    if not user_id:
        # If headers are missing, it means nginx didn't validate the token
        # This should not happen if nginx is configured correctly
        logger.warning("Missing X-User-Id header - request may have bypassed nginx auth")
        return None
    
    # Parse roles from comma-separated string
    roles = [role.strip() for role in user_roles_str.split(",") if role.strip()] if user_roles_str else []
    
    return {
        "sub": user_id,
        "email": user_email,
        "roles": roles
    }


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
        
        # Add user data to kwargs for use in route
        kwargs["current_user"] = user_data
        logger.debug(f"Authenticated user: {user_data.get('sub')} (roles: {user_data.get('roles', [])})")
        # Return the function call (may be coroutine if async)
        # The async_route decorator will handle execution
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

