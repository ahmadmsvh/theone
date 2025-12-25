from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta, timezone
import sys
import os
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
from app.services.session_service import SessionService
from app.repositories.refresh_token_repository import RefreshTokenRepository
from shared.logging_config import get_logger

logger = get_logger(__name__, os.getenv("SERVICE_NAME"))


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
            "email": user.email,
            "roles": [role.name for role in user.roles]
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Calculate expiration datetime
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Store refresh token in database
        refresh_token_repo = RefreshTokenRepository(db)
        refresh_token_repo.create(
            token=refresh_token,
            user_id=user.id,
            expires_at=expires_at
        )
        
        # Cache user data in Redis (with TTL matching refresh token expiry)
        session_service = SessionService()
        roles = [role.name for role in user.roles]
        session_service.cache_user_data(
            user_id=user.id,
            email=user.email,
            roles=roles
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
        
        # Check if token is blacklisted (early check for performance)
        session_service = SessionService()
        if session_service.is_blacklisted(refresh_data.refresh_token):
            logger.warning("Blacklisted refresh token attempted to be used")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked"
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
        
        # Try to get user from cache first, then fallback to database
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            logger.warning(f"Invalid user ID format in refresh token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Check cache first
        cached_user_data = session_service.get_user_data(user_uuid)
        
        if cached_user_data:
            # Use cached data
            user_email = cached_user_data["email"]
            user_roles = cached_user_data["roles"]
            logger.debug(f"Using cached user data for refresh token: {user_id}")
        else:
            # Fallback to database
            user_service = UserService(db)
            user = user_service.get_user_by_id(user_uuid)
            if not user:
                logger.warning(f"User not found for refresh token: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            user_email = user.email
            user_roles = [role.name for role in user.roles]
            
            # Cache the user data for future requests
            session_service.cache_user_data(
                user_id=user.id,
                email=user.email,
                roles=user_roles
            )
            logger.debug(f"Cached user data during refresh token: {user_id}")
        
        # Check if refresh token exists and is valid in database
        refresh_token_repo = RefreshTokenRepository(db)
        refresh_token_record = refresh_token_repo.get_by_token(refresh_data.refresh_token)
        
        if not refresh_token_record or not refresh_token_record.is_valid():
            # If token exists but is expired, revoke it for cleanup
            if refresh_token_record and refresh_token_record.is_expired() and not refresh_token_record.revoked:
                refresh_token_repo.revoke(refresh_data.refresh_token)
                logger.info(f"Revoked expired refresh token for user: {user_id}")
            
            logger.warning(f"Refresh token not valid in database for user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been invalidated or does not exist"
            )
        
        # Generate new access token
        token_data = {
            "sub": user_id,
            "email": user_email,
            "roles": user_roles
        }
        
        new_access_token = create_access_token(token_data)
        
        logger.info(f"Token refreshed successfully for user: {user_email} (ID: {user_id})")
        
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
        
        # Add token to blacklist and invalidate session cache
        session_service = SessionService()
        session_service.blacklist_token(logout_data.refresh_token)
        
        # Revoke refresh token in database
        refresh_token_repo = RefreshTokenRepository(db)
        revoked = refresh_token_repo.revoke(logout_data.refresh_token)
        
        # Invalidate user session cache
        try:
            user_uuid = UUID(user_id)
            session_service.invalidate_user_cache(user_uuid)
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to invalidate cache during logout for user {user_id}: {e}")
        
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
