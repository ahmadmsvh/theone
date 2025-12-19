"""
Role service for business logic
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models import Role, User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas import RoleCreateRequest, RoleResponse
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")


class RoleService:
    """Service for role business logic"""
    
    def __init__(self, db: Session):
        """
        Initialize role service
        
        Args:
            db: Database session
        """
        self.db = db
        self.role_repository = RoleRepository(db)
        self.user_repository = UserRepository(db)
    
    def create_role(self, role_data: RoleCreateRequest) -> Role:
        """
        Create a new role
        
        Args:
            role_data: Role creation request data
            
        Returns:
            Created Role object
            
        Raises:
            HTTPException: If role name already exists
        """
        # Check if role name already exists
        if self.role_repository.get_by_name(role_data.name):
            logger.warning(f"Role creation attempt with existing name: {role_data.name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role with name '{role_data.name}' already exists"
            )
        
        try:
            new_role = self.role_repository.create(
                name=role_data.name,
                description=role_data.description
            )
            logger.info(f"Role created successfully: {new_role.name} (ID: {new_role.id})")
            return new_role
        except IntegrityError as e:
            logger.error(f"Database integrity error during role creation: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role with name '{role_data.name}' already exists"
            )
        except Exception as e:
            logger.error(f"Unexpected error during role creation: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while creating the role"
            )
    
    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """
        Get role by ID
        
        Args:
            role_id: Role ID
            
        Returns:
            Role object or None if not found
        """
        return self.role_repository.get_by_id(role_id)
    
    def get_role_by_name(self, name: str) -> Optional[Role]:
        """
        Get role by name
        
        Args:
            name: Role name
            
        Returns:
            Role object or None if not found
        """
        return self.role_repository.get_by_name(name)
    
    def get_all_roles(self) -> List[Role]:
        """
        Get all roles
        
        Returns:
            List of all Role objects
        """
        return self.role_repository.get_all()
    
    def assign_role_to_user(self, user_id: UUID, role_id: int) -> User:
        """
        Assign a role to a user
        
        Args:
            user_id: User UUID
            role_id: Role ID
            
        Returns:
            Updated User object
            
        Raises:
            HTTPException: If user or role not found, or role already assigned
        """
        # Verify user exists
        user = self.user_repository.get_by_id(user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify role exists
        role = self.role_repository.get_by_id(role_id)
        if not role:
            logger.warning(f"Role not found: {role_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        # Check if role is already assigned
        user_roles = self.role_repository.get_user_roles(str(user_id))
        if role in user_roles:
            logger.warning(f"Role {role_id} already assigned to user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{role.name}' is already assigned to this user"
            )
        
        # Assign role
        try:
            self.role_repository.assign_role_to_user(str(user_id), role_id)
            # Refresh user to get updated roles
            self.db.refresh(user)
            logger.info(f"Role {role_id} assigned to user {user_id}")
            return user
        except IntegrityError as e:
            logger.error(f"Database integrity error during role assignment: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to assign role"
            )
        except Exception as e:
            logger.error(f"Unexpected error during role assignment: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while assigning the role"
            )
    
    def remove_role_from_user(self, user_id: UUID, role_id: int) -> User:
        """
        Remove a role from a user
        
        Args:
            user_id: User UUID
            role_id: Role ID
            
        Returns:
            Updated User object
            
        Raises:
            HTTPException: If user or role not found, or role not assigned
        """
        # Verify user exists
        user = self.user_repository.get_by_id(user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify role exists
        role = self.role_repository.get_by_id(role_id)
        if not role:
            logger.warning(f"Role not found: {role_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        # Check if role is assigned
        user_roles = self.role_repository.get_user_roles(user_id)
        if role not in user_roles:
            logger.warning(f"Role {role_id} not assigned to user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{role.name}' is not assigned to this user"
            )
        
        # Remove role
        removed = self.role_repository.remove_role_from_user(user_id, role_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove role"
            )
        
        # Refresh user to get updated roles
        self.db.refresh(user)
        logger.info(f"Role {role_id} removed from user {user_id}")
        return user
    
    def role_to_response(self, role: Role) -> RoleResponse:
        """
        Convert Role model to RoleResponse schema
        
        Args:
            role: Role model object
            
        Returns:
            RoleResponse schema object
        """
        return RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            created_at=role.created_at
        )
