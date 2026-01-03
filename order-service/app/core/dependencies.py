from uuid import UUID
from typing import Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_token
from shared.logging_config import get_logger

logger = get_logger(__name__, "order-service")

security = HTTPBearer()


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
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
    
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "roles": payload.get("roles", [])
    }


def require_role(role_name: str):
    async def role_checker(current_user: Dict[str, Any] = Depends(require_auth)) -> None:
        user_roles = current_user.get("roles", [])
        if role_name not in user_roles:
            logger.warning(
                f"User {current_user.get('user_id')} attempted to access {role_name}-only resource. "
                f"User roles: {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {role_name}"
            )
        return None
    
    return role_checker


def require_any_role(*role_names: str):
    async def role_checker(current_user: Dict[str, Any] = Depends(require_auth)) -> None:
        user_roles = current_user.get("roles", [])
        if not any(role in user_roles for role in role_names):
            logger.warning(
                f"User {current_user.get('user_id')} attempted to access resource requiring one of {role_names}. "
                f"User roles: {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: one of {', '.join(role_names)}"
            )
        return None
    
    return role_checker

