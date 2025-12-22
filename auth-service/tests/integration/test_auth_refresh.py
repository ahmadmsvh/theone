from fastapi import status
from freezegun import freeze_time
from datetime import timedelta


class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh"""
    
    def test_refresh_success(self, client, refresh_token):
        """Test successful token refresh"""
        refresh_data = {
            "refresh_token": refresh_token
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0
        # Refresh token should remain the same
        assert data["refresh_token"] == refresh_token
    
    def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token"""
        refresh_data = {
            "refresh_token": "invalid.token.here"
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        assert "Invalid or expired refresh token" in data["detail"]
    
    def test_refresh_expired_token(self, client, test_db, sample_user):
        """Test refresh with expired token"""
        from app.core.security import create_refresh_token
        from datetime import datetime, timedelta, timezone
        from app.repositories.refresh_token_repository import RefreshTokenRepository
        from app.core.security import REFRESH_TOKEN_EXPIRE_DAYS
        
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
        
        refresh_data = {
            "refresh_token": expired_token
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_refresh_access_token_instead_of_refresh(self, client, access_token):
        """Test refresh with access token instead of refresh token"""
        refresh_data = {
            "refresh_token": access_token
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        assert "Invalid token type" in data["detail"]
    
    def test_refresh_revoked_token(self, client, test_db, refresh_token):
        """Test refresh with revoked token"""
        from app.repositories.refresh_token_repository import RefreshTokenRepository
        
        # Revoke the token
        refresh_token_repo = RefreshTokenRepository(test_db)
        refresh_token_repo.revoke(refresh_token)
        
        refresh_data = {
            "refresh_token": refresh_token
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        assert "Refresh token has been invalidated" in data["detail"]
    
    def test_refresh_missing_token(self, client):
        """Test refresh with missing token field"""
        refresh_data = {}
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_refresh_empty_token(self, client):
        """Test refresh with empty token"""
        refresh_data = {
            "refresh_token": ""
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_refresh_user_not_found(self, client, test_db):
        """Test refresh when user doesn't exist"""
        from app.core.security import create_refresh_token
        from uuid import uuid4
        from datetime import datetime, timedelta, timezone
        from app.repositories.refresh_token_repository import RefreshTokenRepository
        from app.core.security import REFRESH_TOKEN_EXPIRE_DAYS
        
        # Create token for non-existent user
        non_existent_user_id = uuid4()
        token_data = {
            "sub": str(non_existent_user_id),
            "email": "nonexistent@example.com"
        }
        token = create_refresh_token(token_data)
        
        # Store in database
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token_repo = RefreshTokenRepository(test_db)
        refresh_token_repo.create(
            token=token,
            user_id=non_existent_user_id,
            expires_at=expires_at
        )
        
        refresh_data = {
            "refresh_token": token
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        assert "User not found" in data["detail"]
    
    def test_refresh_returns_new_access_token(self, client, refresh_token):
        """Test that refresh returns a new valid access token"""
        from app.core.security import decode_token
        
        refresh_data = {
            "refresh_token": refresh_token
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify new access token
        new_access_token = data["access_token"]
        payload = decode_token(new_access_token)
        assert payload is not None
        assert payload["type"] == "access"
        assert "exp" in payload
    
    def test_refresh_token_not_in_database(self, client, sample_user):
        """Test refresh with token not in database"""
        from app.core.security import create_refresh_token
        
        # Create a valid refresh token but don't store it in database
        token_data = {
            "sub": str(sample_user.id),
            "email": sample_user.email
        }
        token = create_refresh_token(token_data)
        
        refresh_data = {
            "refresh_token": token
        }
        
        response = client.post(
            "/api/v1/auth/refresh",
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "detail" in data
        assert "Refresh token has been invalidated" in data["detail"]
