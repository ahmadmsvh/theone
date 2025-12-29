from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import RefreshToken
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")


class RefreshTokenRepository:
    
    def __init__(self, db: Session):

        self.db = db
    
    def get_by_token(self, token: str) -> Optional[RefreshToken]:

        return self.db.query(RefreshToken).filter(RefreshToken.token == token).first()
    
    def get_by_user_id(self, user_id: UUID) -> list[RefreshToken]:

        return self.db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()
    
    def create(self, token: str, user_id: UUID, expires_at: datetime) -> RefreshToken:

        try:
            new_token = RefreshToken(
                token=token,
                user_id=user_id,
                expires_at=expires_at,
                revoked=False
            )
            self.db.add(new_token)
            self.db.commit()
            self.db.refresh(new_token)
            logger.info(f"Refresh token created for user: {user_id}")
            return new_token
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create refresh token: {e}")
            raise
    
    def revoke(self, token: str) -> bool:

        refresh_token = self.get_by_token(token)
        if refresh_token:
            refresh_token.revoked = True
            self.db.commit()
            logger.info(f"Refresh token revoked: {token[:10]}...")
            return True
        return False
    
    def revoke_all_for_user(self, user_id: UUID) -> int:

        tokens = self.get_by_user_id(user_id)
        count = 0
        for token in tokens:
            if not token.revoked:
                token.revoked = True
                count += 1
        if count > 0:
            self.db.commit()
            logger.info(f"Revoked {count} refresh tokens for user: {user_id}")
        return count
    
    def delete(self, token: str) -> bool:

        refresh_token = self.get_by_token(token)
        if refresh_token:
            self.db.delete(refresh_token)
            self.db.commit()
            logger.info(f"Refresh token deleted: {token[:10]}...")
            return True
        return False
    
    def is_valid(self, token: str) -> bool:

        refresh_token = self.get_by_token(token)
        if refresh_token:
            return refresh_token.is_valid()
        return False
