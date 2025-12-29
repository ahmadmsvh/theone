from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


class UserRegisterRequest(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!",
            }
        }
    )
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="User password (min 8 characters)"
    )
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(..., description="User unique identifier")
    email: str = Field(..., description="User email address")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: datetime = Field(..., description="User last update timestamp")


class UserRegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    message: str = Field(..., description="Success message")
    user: UserResponse = Field(..., description="Created user information")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")
    details: Optional[dict] = Field(None, description="Additional error details")


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123!",
            }
        }
    )
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password", min_length=1)


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token (15 minutes expiry)")
    refresh_token: str = Field(..., description="JWT refresh token (7 days expiry)")
    token_type: str = Field(default="bearer", description="Token type")


class LoginResponse(BaseModel):
    message: str = Field(..., description="Success message")
    user: UserResponse = Field(..., description="User information")
    tokens: TokenResponse = Field(..., description="Access and refresh tokens")


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )
    
    refresh_token: str = Field(..., min_length=1, description="JWT refresh token")


class RefreshTokenResponse(BaseModel):
    access_token: str = Field(..., description="New JWT access token (15 minutes expiry)")
    refresh_token: str = Field(..., description="JWT refresh token (same or new)")
    token_type: str = Field(default="bearer", description="Token type")


class LogoutRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )
    
    refresh_token: str = Field(..., min_length=1, description="JWT refresh token to invalidate")


class LogoutResponse(BaseModel):
    message: str = Field(..., description="Success message")


class RoleCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Manager",
                "description": "Manager role with elevated permissions",
            }
        }
    )
    
    name: str = Field(..., description="Role name", min_length=1, max_length=50)
    description: Optional[str] = Field(None, description="Role description")


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="Role unique identifier")
    name: str = Field(..., description="Role name")
    description: Optional[str] = Field(None, description="Role description")
    created_at: datetime = Field(..., description="Role creation timestamp")


class RoleCreateResponse(BaseModel):
    message: str = Field(..., description="Success message")
    role: RoleResponse = Field(..., description="Created role information")


class RolesListResponse(BaseModel):
    roles: list[RoleResponse] = Field(..., description="List of roles")
    total: int = Field(..., description="Total number of roles")


class AssignRoleRequest(BaseModel):
    role_id: int = Field(..., description="Role ID to assign")


class AssignRoleResponse(BaseModel):
    message: str = Field(..., description="Success message")
    user: UserResponse = Field(..., description="User with updated roles")
    role: RoleResponse = Field(..., description="Assigned role")


class RemoveRoleResponse(BaseModel):
    message: str = Field(..., description="Success message")
    user: UserResponse = Field(..., description="User with updated roles")
