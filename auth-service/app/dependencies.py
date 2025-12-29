from typing import Generator, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User
from app.services.user_service import UserService
from app.services.role_service import RoleService
from app.services.session_service import SessionService
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")

security = HTTPBearer()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def get_role_service(db: Session = Depends(get_db)) -> RoleService:
    return RoleService(db)


def get_session_service() -> SessionService:
    return SessionService()



async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:

    token = credentials.credentials
    
    payload = decode_token(token)
    if not payload:
        logger.warning("Invalid or expired token in require_auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if payload.get("type") != "access":
        logger.warning("Token provided is not an access token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
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
    
    session_service = get_session_service()
    cached_user_data = session_service.get_user_data(user_id)
    
    if cached_user_data:
        logger.debug(f"Found cached user data for user: {user_id}")
        user_service = get_user_service(db)
        user = user_service.get_user_by_id(user_id)
        if not user:
            session_service.invalidate_user_cache(user_id)
            logger.warning(f"User not found in database (cache was stale): {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    else:
        user_service = get_user_service(db)
        user = user_service.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User not found for authenticated token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
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
