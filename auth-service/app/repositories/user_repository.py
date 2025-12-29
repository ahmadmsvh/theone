from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import User
import sys
from pathlib import Path

from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")


class UserRepository:

    def __init__(self, db: Session):

        self.db = db
    
    def get_by_id(self, user_id: UUID) -> Optional[User]:

        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_email(self, email: str) -> Optional[User]:

        return self.db.query(User).filter(User.email == email).first()
    
    def email_exists(self, email: str) -> bool:

        return self.db.query(User).filter(User.email == email).first() is not None
    
    def create(self, email: str, password_hash: str) -> User:

        try:
            new_user = User(
                email=email,
                password_hash=password_hash
            )
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            logger.info(f"User created: {new_user.email} (ID: {new_user.id})")
            return new_user
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create user: {e}")
            raise
    
    def update(self, user: User) -> User:

        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User updated: {user.email} (ID: {user.id})")
        return user
    
    def delete(self, user_id: UUID) -> bool:

        user = self.get_by_id(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()
            logger.info(f"User deleted: {user_id}")
            return True
        return False
