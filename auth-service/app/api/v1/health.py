from fastapi import APIRouter
import sys
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

from app.core.database import get_db_manager
from shared.database import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Health check endpoint that verifies database and Redis connections"""
    # Check database connection
    db_manager = get_db_manager()
    db_healthy = db_manager.health_check()
    
    # Check Redis connection
    redis_connection = get_redis()
    redis_healthy = redis_connection.health_check()
    
    # Overall status is healthy only if both are healthy
    overall_healthy = db_healthy and redis_healthy
    
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "disconnected"
    }
