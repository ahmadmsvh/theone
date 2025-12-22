import pytest
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from uuid import UUID

# Set test environment variables before importing app modules
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["JWT_ALGORITHM"] = "HS256"

from app.main import app
from app.core.database import get_db
from app.models import Base, User, Role, RefreshToken
from app.core.security import hash_password


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Create a test database in memory for each test function.
    """
    # Create in-memory SQLite database for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create a session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with database override.
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """Sample user registration data"""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!"
    }


@pytest.fixture
def sample_user(test_db: Session, sample_user_data: dict) -> User:
    """Create a sample user in the test database"""
    user = User(
        email=sample_user_data["email"],
        password_hash=hash_password(sample_user_data["password"])
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_role(test_db: Session) -> Role:
    """Create a sample role in the test database"""
    role = Role(
        name="admin",
        description="Administrator role"
    )
    test_db.add(role)
    test_db.commit()
    test_db.refresh(role)
    return role


@pytest.fixture
def user_with_role(test_db: Session, sample_user: User, sample_role: Role) -> User:
    """Create a user with a role assigned"""
    sample_user.roles.append(sample_role)
    test_db.commit()
    test_db.refresh(sample_user)
    return sample_user


@pytest.fixture
def access_token(sample_user: User) -> str:
    """Create a valid access token for testing"""
    from app.core.security import create_access_token
    
    token_data = {
        "sub": str(sample_user.id),
        "email": sample_user.email,
        "roles": [role.name for role in sample_user.roles]
    }
    return create_access_token(token_data)


@pytest.fixture
def refresh_token(test_db: Session, sample_user: User) -> str:
    """Create a valid refresh token for testing"""
    from app.core.security import create_refresh_token, REFRESH_TOKEN_EXPIRE_DAYS
    from datetime import datetime, timedelta, timezone
    from app.repositories.refresh_token_repository import RefreshTokenRepository
    
    token_data = {
        "sub": str(sample_user.id),
        "email": sample_user.email,
        "roles": [role.name for role in sample_user.roles]
    }
    token = create_refresh_token(token_data)
    
    # Store in database
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_repo = RefreshTokenRepository(test_db)
    refresh_token_repo.create(
        token=token,
        user_id=sample_user.id,
        expires_at=expires_at
    )
    
    return token
