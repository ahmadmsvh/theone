import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies import require_auth, require_role, require_any_role


class TestRequireAuth:
    """Tests for require_auth dependency"""
    
    @pytest.mark.asyncio
    async def test_require_auth_valid_token(self, test_db, sample_user, access_token):
        """Test require_auth with valid access token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=access_token
        )
        
        user = await require_auth(credentials, test_db)
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.email == sample_user.email
    
    @pytest.mark.asyncio
    async def test_require_auth_invalid_token(self, test_db):
        """Test require_auth with invalid token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid.token.here"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(credentials, test_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired token" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_require_auth_refresh_token_instead_of_access(self, test_db, sample_user):
        """Test require_auth rejects refresh token"""
        from app.core.security import create_refresh_token
        
        token_data = {
            "sub": str(sample_user.id),
            "email": sample_user.email
        }
        refresh_token = create_refresh_token(token_data)
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=refresh_token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(credentials, test_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token type" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_require_auth_expired_token(self, test_db, sample_user):
        """Test require_auth with expired token"""
        from app.core.security import create_access_token
        from freezegun import freeze_time
        
        with freeze_time("2024-01-01"):
            token_data = {
                "sub": str(sample_user.id),
                "email": sample_user.email
            }
            token = create_access_token(token_data)
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(credentials, test_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_require_auth_user_not_found(self, test_db):
        """Test require_auth when user doesn't exist in database"""
        from app.core.security import create_access_token
        from uuid import uuid4
        
        token_data = {
            "sub": str(uuid4()),  # Non-existent user ID
            "email": "nonexistent@example.com"
        }
        token = create_access_token(token_data)
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(credentials, test_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_require_auth_missing_user_id(self, test_db):
        """Test require_auth with token missing user ID"""
        from app.core.security import create_access_token
        
        token_data = {
            "email": "test@example.com"
            # Missing "sub" field
        }
        token = create_access_token(token_data)
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(credentials, test_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token payload" in exc_info.value.detail


class TestRequireRole:
    """Tests for require_role dependency"""
    
    @pytest.mark.asyncio
    async def test_require_role_user_has_role(self, test_db, user_with_role):
        """Test require_role when user has the required role"""
        role_checker = require_role("admin")
        
        # Call the role checker directly with the user
        result = await role_checker(current_user=user_with_role)
        assert result is None  # Should pass without exception
    
    @pytest.mark.asyncio
    async def test_require_role_user_lacks_role(self, test_db, sample_user):
        """Test require_role when user doesn't have the required role"""
        role_checker = require_role("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(current_user=sample_user)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in exc_info.value.detail
        assert "admin" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_require_role_user_has_different_role(self, test_db, user_with_role):
        """Test require_role when user has different role"""
        role_checker = require_role("manager")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(current_user=user_with_role)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestRequireAnyRole:
    """Tests for require_any_role dependency"""
    
    @pytest.mark.asyncio
    async def test_require_any_role_user_has_one_role(self, test_db, user_with_role):
        """Test require_any_role when user has one of the required roles"""
        role_checker = require_any_role("admin", "manager", "user")
        
        result = await role_checker(current_user=user_with_role)
        assert result is None  # Should pass without exception
    
    @pytest.mark.asyncio
    async def test_require_any_role_user_has_none(self, test_db, sample_user):
        """Test require_any_role when user has none of the required roles"""
        role_checker = require_any_role("manager", "editor")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(current_user=sample_user)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_require_any_role_empty_list(self, test_db, user_with_role):
        """Test require_any_role with empty role list"""
        role_checker = require_any_role()
        
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(current_user=user_with_role)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
