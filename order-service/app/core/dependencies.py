from uuid import UUID
from typing import Dict, Any
from fastapi import Depends, HTTPException, status, Request

from shared.logging_config import get_logger

logger = get_logger(__name__, "order-service")


async def require_auth(request: Request) -> Dict[str, Any]:

    user_id_header = request.headers.get("X-User-Id")
    user_email_header = request.headers.get("X-User-Email", "")
    user_roles_header = request.headers.get("X-User-Roles", "")
    
    if not user_id_header:
        logger.warning("Missing X-User-Id header - request may have bypassed nginx auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = UUID(user_id_header)
    except ValueError:
        logger.warning(f"Invalid user ID format in header: {user_id_header}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user information",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    roles = [role.strip() for role in user_roles_header.split(",") if role.strip()] if user_roles_header else []
    
    return {
        "user_id": user_id,
        "email": user_email_header,
        "roles": roles
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

