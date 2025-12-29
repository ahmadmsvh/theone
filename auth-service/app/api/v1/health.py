from fastapi import APIRouter

from app.core.database import get_db_manager
from shared.database import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    db_manager = get_db_manager()
    db_healthy = db_manager.health_check()
    
    redis_connection = get_redis()
    redis_healthy = redis_connection.health_check()
    
    overall_healthy = db_healthy and redis_healthy
    
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "disconnected"
    }
