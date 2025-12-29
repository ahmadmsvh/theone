from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Role, User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas import RoleCreateRequest, RoleResponse
from app.core.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationError,
    InternalServerError
)
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")


class RoleService:
    
    def __init__(self, db: Session):

        self.db = db
        self.role_repository = RoleRepository(db)
        self.user_repository = UserRepository(db)
    
    def create_role(self, role_data: RoleCreateRequest) -> Role:

        if self.role_repository.get_by_name(role_data.name):
            logger.warning(f"Role creation attempt with existing name: {role_data.name}")
            raise ConflictError(
                message=f"Role with name '{role_data.name}' already exists",
                error_code="ROLE_ALREADY_EXISTS"
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
            raise ConflictError(
                message=f"Role with name '{role_data.name}' already exists",
                error_code="ROLE_ALREADY_EXISTS"
            )
        except Exception as e:
            logger.error(f"Unexpected error during role creation: {e}", exc_info=True)
            raise InternalServerError(
                message="An error occurred while creating the role",
                error_code="ROLE_CREATION_ERROR"
            )
    
    def get_role_by_id(self, role_id: int) -> Optional[Role]:

        return self.role_repository.get_by_id(role_id)
    
    def get_role_by_name(self, name: str) -> Optional[Role]:

        return self.role_repository.get_by_name(name)
    
    def get_all_roles(self) -> list[Role]:

        return self.role_repository.get_all()
    
    def assign_role_to_user(self, user_id: UUID, role_id: int) -> User:

        user = self.user_repository.get_by_id(user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise NotFoundError(
                message="User not found",
                error_code="USER_NOT_FOUND"
            )
        
        role = self.role_repository.get_by_id(role_id)
        if not role:
            logger.warning(f"Role not found: {role_id}")
            raise NotFoundError(
                message="Role not found",
                error_code="ROLE_NOT_FOUND"
            )
        
        user_roles = self.role_repository.get_user_roles(user_id)
        if role in user_roles:
            logger.warning(f"Role {role_id} already assigned to user {user_id}")
            raise ConflictError(
                message=f"Role '{role.name}' is already assigned to this user",
                error_code="ROLE_ALREADY_ASSIGNED"
            )
        
        try:
            self.role_repository.assign_role_to_user(user_id, role_id)
            self.db.refresh(user)
            logger.info(f"Role {role_id} assigned to user {user_id}")
            return user
        except IntegrityError as e:
            logger.error(f"Database integrity error during role assignment: {e}")
            raise ValidationError(
                message="Failed to assign role",
                error_code="ROLE_ASSIGNMENT_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error during role assignment: {e}", exc_info=True)
            raise InternalServerError(
                message="An error occurred while assigning the role",
                error_code="ROLE_ASSIGNMENT_ERROR"
            )
    
    def remove_role_from_user(self, user_id: UUID, role_id: int) -> User:

        user = self.user_repository.get_by_id(user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise NotFoundError(
                message="User not found",
                error_code="USER_NOT_FOUND"
            )
        
        role = self.role_repository.get_by_id(role_id)
        if not role:
            logger.warning(f"Role not found: {role_id}")
            raise NotFoundError(
                message="Role not found",
                error_code="ROLE_NOT_FOUND"
            )
        
        user_roles = self.role_repository.get_user_roles(user_id)
        if role not in user_roles:
            logger.warning(f"Role {role_id} not assigned to user {user_id}")
            raise ValidationError(
                message=f"Role '{role.name}' is not assigned to this user",
                error_code="ROLE_NOT_ASSIGNED"
            )
        
        removed = self.role_repository.remove_role_from_user(user_id, role_id)
        if not removed:
            raise InternalServerError(
                message="Failed to remove role",
                error_code="ROLE_REMOVAL_ERROR"
            )
        
        self.db.refresh(user)
        logger.info(f"Role {role_id} removed from user {user_id}")
        return user
    
    def role_to_response(self, role: Role) -> RoleResponse:

        return RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            created_at=role.created_at
        )
