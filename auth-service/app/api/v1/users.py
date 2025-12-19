"""
User role management API endpoints (Admin only)
"""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from uuid import UUID
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from app.core.database import get_db
from app.dependencies import require_auth, require_role
from app.models import User
from app.schemas import (
    AssignRoleRequest,
    AssignRoleResponse,
    RemoveRoleResponse,
    UserResponse
)
from app.services.role_service import RoleService
from app.services.user_service import UserService
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/{user_id}/roles",
    response_model=AssignRoleResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Role assigned successfully"},
        400: {"description": "Bad request - role already assigned or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        403: {"description": "Forbidden - admin role required"},
        404: {"description": "User or role not found"},
        500: {"description": "Internal server error"}
    }
)
def assign_role_to_user(
    user_id: UUID,
    role_data: AssignRoleRequest,
    current_user: User = Depends(require_auth),
    _: None = Depends(require_role("Admin")),
    db: Session = Depends(get_db)
):
    """
    Assign a role to a user (Admin only)
    
    - **user_id**: User UUID
    - **role_id**: Role ID to assign
    
    Returns the updated user information with the assigned role.
    """
    role_service = RoleService(db)
    user_service = UserService(db)
    
    updated_user = role_service.assign_role_to_user(user_id, role_data.role_id)
    role = role_service.get_role_by_id(role_data.role_id)
    
    logger.info(
        f"Role {role_data.role_id} assigned to user {user_id} by admin {current_user.email}"
    )
    
    return AssignRoleResponse(
        message=f"Role '{role.name}' assigned successfully",
        user=user_service.user_to_response(updated_user),
        role=role_service.role_to_response(role)
    )


@router.delete(
    "/{user_id}/roles/{role_id}",
    response_model=RemoveRoleResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Role removed successfully"},
        400: {"description": "Bad request - role not assigned"},
        401: {"description": "Unauthorized - authentication required"},
        403: {"description": "Forbidden - admin role required"},
        404: {"description": "User or role not found"},
        500: {"description": "Internal server error"}
    }
)
def remove_role_from_user(
    user_id: UUID,
    role_id: int,
    current_user: User = Depends(require_auth),
    _: None = Depends(require_role("Admin")),
    db: Session = Depends(get_db)
):
    """
    Remove a role from a user (Admin only)
    
    - **user_id**: User UUID
    - **role_id**: Role ID to remove
    
    Returns the updated user information.
    """
    role_service = RoleService(db)
    user_service = UserService(db)
    
    role = role_service.get_role_by_id(role_id)
    updated_user = role_service.remove_role_from_user(user_id, role_id)
    
    logger.info(
        f"Role {role_id} removed from user {user_id} by admin {current_user.email}"
    )
    
    return RemoveRoleResponse(
        message=f"Role '{role.name}' removed successfully",
        user=user_service.user_to_response(updated_user)
    )
