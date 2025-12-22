import pytest
from fastapi import status


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout"""
    
    def test_logout_success(self, client, refresh_token):
        """Test successful logout"""
        logout_data = {
            "refresh_token": refresh_token
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert data["message"] == "Logout successful"
    
    def test_logout_revokes_token(self, client, test_db, refresh_token):
        """Test that logout revokes the refresh token in database"""
        from app.repositories.refresh_token_repository import RefreshTokenRepository
        
        logout_data = {
            "refresh_token": refresh_token
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify token is revoked
        refresh_token_repo = RefreshTokenRepository(test_db)
        token_record = refresh_token_repo.get_by_token(refresh_token)
        assert token_record is not None
        assert token_record.revoked is True
    
    def test_logout_invalid_token(self, client):
        """Test logout with invalid token (should still return success)"""
        logout_data = {
            "refresh_token": "invalid.token.here"
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        # Logout should always return success to avoid information leakage
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logout successful"
    
    def test_logout_expired_token(self, client, test_db, sample_user):
        """Test logout with expired token (should still return success)"""
        from app.core.security import create_refresh_token
        from datetime import datetime, timedelta, timezone
        from app.repositories.refresh_token_repository import RefreshTokenRepository
        from app.core.security import REFRESH_TOKEN_EXPIRE_DAYS
        from freezegun import freeze_time
        
        # Create expired token
        with freeze_time("2024-01-01"):
            token_data = {
                "sub": str(sample_user.id),
                "email": sample_user.email
            }
            expired_token = create_refresh_token(token_data)
            
            # Store in database with expired time
            expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            refresh_token_repo = RefreshTokenRepository(test_db)
            refresh_token_repo.create(
                token=expired_token,
                user_id=sample_user.id,
                expires_at=expires_at
            )
        
        logout_data = {
            "refresh_token": expired_token
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        # Should still return success
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logout successful"
    
    def test_logout_access_token_instead_of_refresh(self, client, access_token):
        """Test logout with access token instead of refresh token"""
        logout_data = {
            "refresh_token": access_token
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        # Should still return success
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logout successful"
    
    def test_logout_missing_token(self, client):
        """Test logout with missing token field"""
        logout_data = {}
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_logout_empty_token(self, client):
        """Test logout with empty token"""
        logout_data = {
            "refresh_token": ""
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_logout_already_revoked_token(self, client, test_db, refresh_token):
        """Test logout with already revoked token"""
        from app.repositories.refresh_token_repository import RefreshTokenRepository
        
        # Revoke token first
        refresh_token_repo = RefreshTokenRepository(test_db)
        refresh_token_repo.revoke(refresh_token)
        
        logout_data = {
            "refresh_token": refresh_token
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        # Should still return success
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logout successful"
    
    def test_logout_token_not_in_database(self, client, sample_user):
        """Test logout with token not in database"""
        from app.core.security import create_refresh_token
        
        # Create a valid refresh token but don't store it in database
        token_data = {
            "sub": str(sample_user.id),
            "email": sample_user.email
        }
        token = create_refresh_token(token_data)
        
        logout_data = {
            "refresh_token": token
        }
        
        response = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        
        # Should still return success
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logout successful"
    
    def test_logout_multiple_times_same_token(self, client, refresh_token):
        """Test logging out multiple times with the same token"""
        logout_data = {
            "refresh_token": refresh_token
        }
        
        # First logout
        response1 = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Second logout with same token
        response2 = client.post(
            "/api/v1/auth/logout",
            json=logout_data
        )
        assert response2.status_code == status.HTTP_200_OK
        data = response2.json()
        assert data["message"] == "Logout successful"