"""
Production-grade cache service with connection pooling and resilience.
"""

import redis
import json
import hashlib
import logging
from typing import Optional, Any
from app.core.base_service import CacheRepository, Service
from app.core.settings import get_settings
from app.core.exceptions import CacheError

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisCacheService(CacheRepository, Service):
    """
    Redis cache service with connection pooling and automatic fallback.
    """
    
    def __init__(self):
        super().__init__()
        self._pool = None
        self._client = None
        self._initialize_connection_pool()
    
    def _initialize_connection_pool(self):
        """Initialize Redis connection pool."""
        try:
            self._pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password if settings.redis_password else None,
                max_connections=settings.redis_connection_pool_size,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 1,  # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                } if hasattr(redis, 'socket_keepalive_options') else None,
                decode_responses=True,
                health_check_interval=30  # Check connection health every 30s
            )
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            self._client.ping()
            self.logger.info("Redis connection pool initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis connection pool: {e}")
            self._client = None
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate hash-based cache key from text."""
        normalized = text.strip().lower()
        return f"cache:{hashlib.sha256(normalized.encode()).hexdigest()}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if not self._client:
                return None
            
            cache_key = self._generate_cache_key(key)
            data = self._client.get(cache_key)
            
            if data:
                self.logger.debug(f"Cache hit: {cache_key}")
                return json.loads(data)
            
            self.logger.debug(f"Cache miss: {cache_key}")
            return None
        
        except Exception as e:
            self.logger.warning(f"Cache GET failed: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        try:
            if not self._client:
                return
            
            cache_key = self._generate_cache_key(key)
            ttl = ttl or settings.redis_ttl_seconds
            
            serialized = json.dumps(value)
            self._client.setex(cache_key, ttl, serialized)
            
            self.logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
        
        except Exception as e:
            self.logger.warning(f"Cache SET failed: {e}")
    
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        try:
            if not self._client:
                return
            
            cache_key = self._generate_cache_key(key)
            self._client.delete(cache_key)
            self.logger.debug(f"Cache DELETE: {cache_key}")
        
        except Exception as e:
            self.logger.warning(f"Cache DELETE failed: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            if not self._client:
                return False
            
            cache_key = self._generate_cache_key(key)
            return bool(self._client.exists(cache_key))
        
        except Exception as e:
            self.logger.warning(f"Cache EXISTS failed: {e}")
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries matching pattern."""
        try:
            if not self._client:
                return
            
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor, match="cache:*", count=100)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
            
            self.logger.info("Cache cleared")
        
        except Exception as e:
            self.logger.warning(f"Cache CLEAR failed: {e}")
    
    async def ping(self) -> bool:
        """Health check."""
        try:
            if not self._client:
                return False
            
            return bool(self._client.ping())
        
        except Exception as e:
            self.logger.warning(f"Cache PING failed: {e}")
            return False
    
    def close(self):
        """Close connection pool."""
        try:
            if self._pool:
                self._pool.disconnect()
            self.logger.info("Redis connection pool closed")
        except Exception as e:
            self.logger.error(f"Error closing Redis pool: {e}")


# Singleton instance
_cache_service: Optional[RedisCacheService] = None


def get_cache_service() -> CacheRepository:
    """Get or create cache service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = RedisCacheService()
    return _cache_service
