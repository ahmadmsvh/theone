from typing import Generator, List, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User
from app.services.user_service import UserService
from app.services.session_service import SessionService
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")

security = HTTPBearer()



async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:

    token = credentials.credentials
    
    # Decode and verify token
    payload = decode_token(token)
    if not payload:
        logger.warning("Invalid or expired token in require_auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify it's an access token
    if payload.get("type") != "access":
        logger.warning("Token provided is not an access token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user ID
    user_id_str = payload.get("sub")
    if not user_id_str:
        logger.warning("Token missing user ID")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.warning(f"Invalid user ID format in token: {user_id_str}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Try to get user from cache first, then fallback to database
    session_service = SessionService()
    cached_user_data = session_service.get_user_data(user_id)
    
    if cached_user_data:
        # Reconstruct User object from cached data
        # Note: We still need a User object, but we'll create a minimal one
        # For full functionality, we still query DB but cache reduces most queries
        logger.debug(f"Found cached user data for user: {user_id}")
        # Still verify user exists in DB (for security, but cache reduces load)
        user_service = UserService(db)
        user = user_service.get_user_by_id(user_id)
        if not user:
            # Cache might be stale, invalidate it
            session_service.invalidate_user_cache(user_id)
            logger.warning(f"User not found in database (cache was stale): {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    else:
        # Cache miss - get from database and cache it
        user_service = UserService(db)
        user = user_service.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User not found for authenticated token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Cache user data for future requests
        roles = [role.name for role in user.roles]
        session_service.cache_user_data(
            user_id=user.id,
            email=user.email,
            roles=roles
        )
        logger.debug(f"Cached user data for authenticated user: {user_id}")
        
        return user


def require_role(role_name: str):

    async def role_checker(current_user: User = Depends(require_auth)) -> None:

        user_roles = [role.name for role in current_user.roles]
        if role_name not in user_roles:
            logger.warning(
                f"User {current_user.id} attempted to access {role_name}-only resource. "
                f"User roles: {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {role_name}"
            )
        return None
    
    return role_checker


def require_any_role(*role_names: str):

    async def any_role_checker(current_user: User = Depends(require_auth)) -> None:

        user_roles = [role.name for role in current_user.roles]
        if not any(role_name in user_roles for role_name in role_names):
            logger.warning(
                f"User {current_user.id} attempted to access resource requiring one of "
                f"{role_names}. User roles: {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required one of the following roles: {', '.join(role_names)}"
            )
        return None
    
    return any_role_checker
