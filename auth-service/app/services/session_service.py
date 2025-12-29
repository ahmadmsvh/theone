import json
import hashlib
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from shared.database import get_redis
from shared.logging_config import get_logger
from app.core.security import REFRESH_TOKEN_EXPIRE_DAYS, decode_token

logger = get_logger(__name__, "auth-service")


class SessionService:
    
    SESSION_CACHE_PREFIX = "session:user:"
    BLACKLIST_PREFIX = "blacklist:refresh_token:"
    
    def __init__(self):
        self.redis = get_redis()
        self.default_ttl_seconds = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    
    def _get_session_key(self, user_id: UUID) -> str:
        return f"{self.SESSION_CACHE_PREFIX}{str(user_id)}"
    
    def cache_user_data(
        self, 
        user_id: UUID, 
        email: str, 
        roles: list[str]
    ) -> bool:
        try:
            cache_key = self._get_session_key(user_id)
            user_data = {
                "id": str(user_id),
                "email": email,
                "roles": roles
            }
            
            user_data_json = json.dumps(user_data)
            self.redis.client.setex(
                cache_key,
                self.default_ttl_seconds,
                user_data_json
            )
            
            logger.debug(f"Cached user data for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache user data for user {user_id}: {e}", exc_info=True)
            return False
    
    def get_user_data(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        try:
            cache_key = self._get_session_key(user_id)
            cached_data = self.redis.client.get(cache_key)
            
            if cached_data is None:
                logger.debug(f"No cached data found for user: {user_id}")
                return None
            
            user_data = json.loads(cached_data)
            logger.debug(f"Retrieved cached user data for user: {user_id}")
            return user_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached user data for user {user_id}: {e}")
            self.invalidate_user_cache(user_id)
            return None
        except Exception as e:
            logger.error(f"Failed to get cached user data for user {user_id}: {e}", exc_info=True)
            return None
    
    def invalidate_user_cache(self, user_id: UUID) -> bool:
        try:
            cache_key = self._get_session_key(user_id)
            deleted = self.redis.client.delete(cache_key)
            
            if deleted:
                logger.debug(f"Invalidated cache for user: {user_id}")
            else:
                logger.debug(f"No cache entry found to invalidate for user: {user_id}")
            
            return bool(deleted)
        except Exception as e:
            logger.error(f"Failed to invalidate cache for user {user_id}: {e}", exc_info=True)
            return False
    
    # ========== Token Blacklist Methods ==========
    
    def _get_blacklist_key(self, token: str) -> str:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return f"{self.BLACKLIST_PREFIX}{token_hash}"
    
    def _calculate_token_ttl(self, token: str) -> int:
        try:
            payload = decode_token(token)
            if payload and "exp" in payload:
                exp_timestamp = payload["exp"]
                now_timestamp = datetime.now(timezone.utc).timestamp()
                remaining_seconds = int(exp_timestamp - now_timestamp)
                return max(0, min(remaining_seconds, self.default_ttl_seconds))
        except Exception as e:
            logger.warning(f"Failed to calculate TTL from token, using default: {e}")
        
        return self.default_ttl_seconds
    
    def blacklist_token(self, token: str) -> bool:
        try:
            blacklist_key = self._get_blacklist_key(token)
            ttl = self._calculate_token_ttl(token)
            
            if ttl <= 0:
                logger.debug("Token is already expired, skipping blacklist")
                return True
            
            self.redis.client.setex(blacklist_key, ttl, "1")
            logger.info(f"Token blacklisted (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}", exc_info=True)
            return False
    
    def is_blacklisted(self, token: str) -> bool:
        try:
            blacklist_key = self._get_blacklist_key(token)
            exists = self.redis.client.exists(blacklist_key)
            
            if exists:
                logger.debug("Token found in blacklist")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}", exc_info=True)
            return False
    
    def remove_from_blacklist(self, token: str) -> bool:
        try:
            blacklist_key = self._get_blacklist_key(token)
            deleted = self.redis.client.delete(blacklist_key)
            
            if deleted:
                logger.debug("Token removed from blacklist")
            
            return bool(deleted)
        except Exception as e:
            logger.error(f"Failed to remove token from blacklist: {e}", exc_info=True)
            return False
    
    def refresh_user_cache(
        self, 
        user_id: UUID, 
        email: str, 
        roles: list[str]
    ) -> bool:
        return self.cache_user_data(user_id, email, roles)

