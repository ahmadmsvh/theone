from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Role, User, UserRole
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")


class RoleRepository:   
    
    def __init__(self, db: Session):

        self.db = db
    
    def get_by_id(self, role_id: int) -> Optional[Role]:

        return self.db.query(Role).filter(Role.id == role_id).first()
    
    def get_by_name(self, name: str) -> Optional[Role]:

        return self.db.query(Role).filter(Role.name == name).first()
    
    def get_all(self) -> list[Role]:

        return self.db.query(Role).all()
    
    def create(self, name: str, description: Optional[str] = None) -> Role:

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
   
        role = self.get_by_id(role_id)
        if role:
            self.db.delete(role)
            self.db.commit()
            logger.info(f"Role deleted: {role_id}")
            return True
        return False
    
    def assign_role_to_user(self, user_id: UUID, role_id: int) -> bool:

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
    
    def remove_role_from_user(self, user_id: UUID, role_id: int) -> bool:

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
    
    def get_user_roles(self, user_id: UUID) -> list[Role]:

        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            return user.roles
        return []
