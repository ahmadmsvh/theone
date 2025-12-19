"""
Role repository for database operations
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Role, User, UserRole
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")


class RoleRepository:
    """Repository for role database operations"""
    
    def __init__(self, db: Session):
        """
        Initialize role repository
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_by_id(self, role_id: int) -> Optional[Role]:
        """
        Get role by ID
        
        Args:
            role_id: Role ID
            
        Returns:
            Role object or None if not found
        """
        return self.db.query(Role).filter(Role.id == role_id).first()
    
    def get_by_name(self, name: str) -> Optional[Role]:
        """
        Get role by name
        
        Args:
            name: Role name
            
        Returns:
            Role object or None if not found
        """
        return self.db.query(Role).filter(Role.name == name).first()
    
    def get_all(self) -> List[Role]:
        """
        Get all roles
        
        Returns:
            List of all Role objects
        """
        return self.db.query(Role).all()
    
    def create(self, name: str, description: Optional[str] = None) -> Role:
        """
        Create a new role
        
        Args:
            name: Role name
            description: Optional role description
            
        Returns:
            Created Role object
            
        Raises:
            IntegrityError: If role name already exists
        """
        try:
            new_role = Role(
                name=name,
                description=description
            )
            self.db.add(new_role)
            self.db.commit()
            self.db.refresh(new_role)
            logger.info(f"Role created: {new_role.name} (ID: {new_role.id})")
            return new_role
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create role: {e}")
            raise
    
    def delete(self, role_id: int) -> bool:
        """
        Delete role by ID
        
        Args:
            role_id: Role ID
            
        Returns:
            True if deleted, False if not found
        """
        role = self.get_by_id(role_id)
        if role:
            self.db.delete(role)
            self.db.commit()
            logger.info(f"Role deleted: {role_id}")
            return True
        return False
    
    def assign_role_to_user(self, user_id: UUID, role_id: int) -> bool:
        """
        Assign a role to a user
        
        Args:
            user_id: User UUID
            role_id: Role ID
            
        Returns:
            True if assigned, False if already assigned
        """
        try:
            # Check if assignment already exists
            existing = self.db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            ).first()
            
            if existing:
                logger.warning(f"Role {role_id} already assigned to user {user_id}")
                return False
            
            user_role = UserRole(
                user_id=user_id,
                role_id=role_id
            )
            self.db.add(user_role)
            self.db.commit()
            logger.info(f"Role {role_id} assigned to user {user_id}")
            return True
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to assign role: {e}")
            raise
    
    def remove_role_from_user(self, user_id: str, role_id: int) -> bool:
        """
        Remove a role from a user
        
        Args:
            user_id: User UUID
            role_id: Role ID
            
        Returns:
            True if removed, False if not found
        """
        user_role = self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        ).first()
        
        if user_role:
            self.db.delete(user_role)
            self.db.commit()
            logger.info(f"Role {role_id} removed from user {user_id}")
            return True
        
        logger.warning(f"Role {role_id} not assigned to user {user_id}")
        return False
    
    def get_user_roles(self, user_id: UUID) -> List[Role]:
        """
        Get all roles for a user
        
        Args:
            user_id: User UUID
            
        Returns:
            List of Role objects assigned to the user
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            return user.roles
        return []
