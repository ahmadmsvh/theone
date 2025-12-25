from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import UserRegisterRequest, UserResponse
from app.core.security import hash_password, verify_password
import sys
from pathlib import Path

# Add shared to path
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")

class UserService:
    
    def __init__(self, db: Session):

        self.db = db
        self.user_repository = UserRepository(db)
    
    def register_user(self, user_data: UserRegisterRequest) -> User:
        # Check if email already exists
        if self.user_repository.email_exists(user_data.email):
            logger.warning(f"Registration attempt with existing email: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash the password
        try:
            hashed_password = hash_password(user_data.password)
        except Exception as e:
            logger.error(f"Failed to hash password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process password"
            )
        
        # Create user
        try:
            new_user = self.user_repository.create(
                email=user_data.email,
                password_hash=hashed_password
            )
            logger.info(f"User registered successfully: {new_user.email} (ID: {new_user.id})")
            return new_user
        except IntegrityError as e:
            logger.error(f"Database integrity error during registration: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        except Exception as e:
            logger.error(f"Unexpected error during user registration: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while registering the user"
            )
    
    def get_user_by_id(self, user_id: UUID) -> Optional[User]:

        return self.user_repository.get_by_id(user_id)
    
    def get_user_by_email(self, email: str) -> Optional[User]:

        return self.user_repository.get_by_email(email)
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:

        user = self.get_user_by_email(email)
        if not user:
            logger.warning(f"Login attempt with non-existent email: {email}")
            return None
        
        if not verify_password(password, user.password_hash):
            logger.warning(f"Invalid password attempt for user: {email}")
            return None
        
        logger.info(f"User authenticated successfully: {email} (ID: {user.id})")
        return user
    
    def user_to_response(self, user: User) -> UserResponse:

        return UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
