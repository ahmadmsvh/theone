from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_auth, require_role, get_role_service
from app.models import User
from app.schemas import (
    RoleCreateRequest,
    RoleCreateResponse,
    RoleResponse,
    RolesListResponse
)
from app.services.role_service import RoleService
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")

router = APIRouter(prefix="/roles", tags=["roles"])


@router.post(
    "",
    response_model=RoleCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Role created successfully"},
        400: {"description": "Bad request - validation error or role already exists"},
        401: {"description": "Unauthorized - authentication required"},
        403: {"description": "Forbidden - admin role required"},
        500: {"description": "Internal server error"}
    }
)
def create_role(
    role_data: RoleCreateRequest,
    current_user: User = Depends(require_auth),
    _: None = Depends(require_role("Admin")),
    role_service: RoleService = Depends(get_role_service)
):
    new_role = role_service.create_role(role_data)
    
    logger.info(f"Role created by admin {current_user.email}: {new_role.name}")
    
    return RoleCreateResponse(
        message="Role created successfully",
        role=role_service.role_to_response(new_role)
    )


@router.get(
    "",
    response_model=RolesListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Roles retrieved successfully"},
        401: {"description": "Unauthorized - authentication required"},
        403: {"description": "Forbidden - admin role required"},
        500: {"description": "Internal server error"}
    }
)
def list_roles(
    current_user: User = Depends(require_auth),
    _: None = Depends(require_role("Admin")),
    role_service: RoleService = Depends(get_role_service)
):
    roles = role_service.get_all_roles()
    
    return RolesListResponse(
        roles=[role_service.role_to_response(role) for role in roles],
        total=len(roles)
    )
