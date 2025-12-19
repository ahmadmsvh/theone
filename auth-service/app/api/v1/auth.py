"""
Authentication API endpoints
"""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add shared to path
# sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token, REFRESH_TOKEN_EXPIRE_DAYS
from app.schemas import (
    UserRegisterRequest, 
    UserRegisterResponse, 
    UserResponse,
    LoginRequest,
    LoginResponse,
    TokenResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
    LogoutResponse
)
from app.services.user_service import UserService
from app.repositories.refresh_token_repository import RefreshTokenRepository
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    # response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User successfully registered"},
        400: {"description": "Bad request - validation error or email already exists"},
        500: {"description": "Internal server error"}
    }
)
def register_user(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user
    
    - **email**: User's email address (must be unique)
    - **password**: User's password (min 8 characters, must contain uppercase, lowercase, and digit)
    
    Returns the created user information.
    """
    user_service = UserService(db)
    new_user = user_service.register_user(user_data)
    
    return UserRegisterResponse(
        message="User registered successfully",
        user=user_service.user_to_response(new_user)
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        500: {"description": "Internal server error"}
    }
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and generate JWT tokens
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns access token (15 minutes expiry) and refresh token (7 days expiry).
    Refresh token is stored in the database for persistence and validation.
    """
    user_service = UserService(db)
    
    # Authenticate user credentials
    user = user_service.authenticate_user(login_data.email, login_data.password)
    if not user:
        logger.warning(f"Failed login attempt for email: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    try:
        # Generate JWT tokens
        token_data = {
            "sub": str(user.id),
            "email": user.email
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Calculate expiration datetime
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Store refresh token in database
        refresh_token_repo = RefreshTokenRepository(db)
        refresh_token_repo.create(
            token=refresh_token,
            user_id=user.id,
            expires_at=expires_at
        )
        
        logger.info(f"User logged in successfully: {user.email} (ID: {user.id})")
        
        return LoginResponse(
            message="Login successful",
            user=user_service.user_to_response(user),
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer"
            )
        )
    except Exception as e:
        logger.error(f"Error during login process: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "Invalid or expired refresh token"},
        500: {"description": "Internal server error"}
    }
)
def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using a valid refresh token
    
    - **refresh_token**: Valid JWT refresh token
    
    Returns a new access token. The refresh token must be valid and exist in the database.
    """
    try:
        # Decode and verify the refresh token
        payload = decode_token(refresh_data.refresh_token)
        if not payload:
            logger.warning("Invalid or expired refresh token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            logger.warning("Token provided is not a refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Extract user information from token
        user_id = payload.get("sub")
        user_email = payload.get("email")
        
        if not user_id or not user_email:
            logger.warning("Refresh token missing required claims")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Verify user still exists in database
        user_service = UserService(db)
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            logger.warning(f"Invalid user ID format in refresh token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        user = user_service.get_user_by_id(user_uuid)
        if not user:
            logger.warning(f"User not found for refresh token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check if refresh token exists and is valid in database
        refresh_token_repo = RefreshTokenRepository(db)
        if not refresh_token_repo.is_valid(refresh_data.refresh_token):
            logger.warning(f"Refresh token not valid in database for user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been invalidated or does not exist"
            )
        
        # Generate new access token
        token_data = {
            "sub": str(user.id),
            "email": user.email
        }
        
        new_access_token = create_access_token(token_data)
        
        logger.info(f"Token refreshed successfully for user: {user.email} (ID: {user.id})")
        
        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_data.refresh_token,  # Keep the same refresh token
            token_type="bearer"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during token refresh: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while refreshing token"
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Logout successful"},
        401: {"description": "Invalid refresh token"},
        500: {"description": "Internal server error"}
    }
)
def logout(
    logout_data: LogoutRequest,
    db: Session = Depends(get_db)
):
    """
    Logout user by invalidating refresh token
    
    - **refresh_token**: JWT refresh token to invalidate
    
    Revokes the refresh token in the database, effectively logging out the user.
    Always returns success to avoid information leakage about token validity.
    """
    try:
        # Decode the refresh token to get user information
        payload = decode_token(logout_data.refresh_token)
        
        if not payload:
            # Token is invalid/expired, but we still return success
            logger.warning("Invalid or expired refresh token provided for logout")
            return LogoutResponse(
                message="Logout successful"
            )
        
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            logger.warning("Token provided is not a refresh token")
            return LogoutResponse(
                message="Logout successful"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Refresh token missing user ID")
            return LogoutResponse(
                message="Logout successful"
            )
        
        # Revoke refresh token in database
        refresh_token_repo = RefreshTokenRepository(db)
        revoked = refresh_token_repo.revoke(logout_data.refresh_token)
        
        if revoked:
            logger.info(f"User logged out successfully: {user_id}")
        else:
            logger.warning(f"Refresh token not found for logout: {user_id}")
            # Still return success to avoid information leakage
        
        return LogoutResponse(
            message="Logout successful"
        )
    except Exception as e:
        logger.error(f"Error during logout: {e}", exc_info=True)
        # Always return success to avoid information leakage about token validity
        return LogoutResponse(
            message="Logout successful"
        )
