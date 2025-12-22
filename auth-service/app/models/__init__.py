from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    roles = relationship("Role", secondary="user_roles", back_populates="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class Role(Base):
    """Role model"""
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    users = relationship("User", secondary="user_roles", back_populates="roles")
    
    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


class UserRole(Base):
    """User-Role junction table"""
    __tablename__ = "user_roles"
    
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


class RefreshToken(Base):
    """Refresh token model"""
    __tablename__ = "refresh_tokens"
    
    token = Column(Text, primary_key=True)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked = Column(Boolean, default=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
    
    def __repr__(self):
        return f"<RefreshToken(token={self.token[:10]}..., user_id={self.user_id}, expires_at={self.expires_at})>"
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        now = datetime.now(timezone.utc)
        # Normalize expires_at to timezone-aware (SQLite may return naive datetimes)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            # Assume UTC if timezone-naive (common with SQLite)
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return now >= expires_at
    
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)"""
        return not self.revoked and not self.is_expired()
