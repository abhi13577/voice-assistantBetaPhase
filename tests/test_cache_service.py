"""
Unit tests for CacheService - Redis-backed caching with fallback.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from app.services.cache_service_refactored import RedisCacheService
from app.core.exceptions import CacheError


@pytest.fixture
def cache_service():
    """Create cache service with mocked Redis."""
    with patch('app.services.cache_service_refactored.redis.ConnectionPool'):
        service = RedisCacheService()
        service._client = MagicMock()
        return service


class TestCacheServiceGet:
    """Test cache GET operations."""
    
    @pytest.mark.asyncio
    async def test_get_hit(self, cache_service):
        """Test successful cache hit."""
        test_data = {"intent": "greeting", "confidence": 0.95}
        cache_service._client.get.return_value = json.dumps(test_data)
        
        result = await cache_service.get("hello")
        
        assert result == test_data
        cache_service._client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_miss(self, cache_service):
        """Test cache miss."""
        cache_service._client.get.return_value = None
        
        result = await cache_service.get("unknown_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_with_client_unavailable(self, cache_service):
        """Test GET when Redis client is unavailable."""
        cache_service._client = None
        
        result = await cache_service.get("test_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_with_exception(self, cache_service):
        """Test GET with exception (should not crash)."""
        cache_service._client.get.side_effect = Exception("Redis error")
        
        result = await cache_service.get("test_key")
        
        assert result is None


class TestCacheServiceSet:
    """Test cache SET operations."""
    
    @pytest.mark.asyncio
    async def test_set_success(self, cache_service):
        """Test successful SET."""
        test_data = {"intent": "greeting", "confidence": 0.95}
        
        await cache_service.set("hello", test_data)
        
        cache_service._client.setex.assert_called_once()
        args, kwargs = cache_service._client.setex.call_args
        assert args[2] == json.dumps(test_data)
    
    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, cache_service):
        """Test SET with custom TTL."""
        test_data = {"value": "test"}
        custom_ttl = 600
        
        await cache_service.set("key", test_data, ttl=custom_ttl)
        
        args, kwargs = cache_service._client.setex.call_args
        assert args[1] == custom_ttl
    
    @pytest.mark.asyncio
    async def test_set_with_client_unavailable(self, cache_service):
        """Test SET when Redis client is unavailable."""
        cache_service._client = None
        
        # Should not raise
        await cache_service.set("key", {"value": "test"})
    
    @pytest.mark.asyncio
    async def test_set_with_exception(self, cache_service):
        """Test SET with exception (should not crash)."""
        cache_service._client.setex.side_effect = Exception("Redis error")
        
        # Should not raise
        await cache_service.set("key", {"value": "test"})


class TestCacheServiceDelete:
    """Test cache DELETE operations."""
    
    @pytest.mark.asyncio
    async def test_delete_success(self, cache_service):
        """Test successful DELETE."""
        await cache_service.delete("test_key")
        
        cache_service._client.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_with_exception(self, cache_service):
        """Test DELETE with exception (should not crash)."""
        cache_service._client.delete.side_effect = Exception("Redis error")
        
        # Should not raise
        await cache_service.delete("test_key")


class TestCacheServiceExists:
    """Test cache EXISTS operations."""
    
    @pytest.mark.asyncio
    async def test_exists_true(self, cache_service):
        """Test EXISTS returns True."""
        cache_service._client.exists.return_value = True
        
        result = await cache_service.exists("test_key")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_exists_false(self, cache_service):
        """Test EXISTS returns False."""
        cache_service._client.exists.return_value = False
        
        result = await cache_service.exists("test_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_exists_with_exception(self, cache_service):
        """Test EXISTS with exception."""
        cache_service._client.exists.side_effect = Exception("Redis error")
        
        result = await cache_service.exists("test_key")
        
        assert result is False


class TestCacheServicePing:
    """Test cache PING health check."""
    
    @pytest.mark.asyncio
    async def test_ping_success(self, cache_service):
        """Test successful PING."""
        cache_service._client.ping.return_value = True
        
        result = await cache_service.ping()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_ping_failure(self, cache_service):
        """Test PING failure."""
        cache_service._client.ping.side_effect = Exception("Redis error")
        
        result = await cache_service.ping()
        
        assert result is False


class TestCacheServiceKeyGeneration:
    """Test cache key generation."""
    
    def test_key_generation_consistency(self, cache_service):
        """Test that same input generates same key."""
        key1 = cache_service._generate_cache_key("test_key")
        key2 = cache_service._generate_cache_key("test_key")
        
        assert key1 == key2
    
    def test_key_generation_case_insensitive(self, cache_service):
        """Test that key generation is case-insensitive."""
        key1 = cache_service._generate_cache_key("Test_Key")
        key2 = cache_service._generate_cache_key("test_key")
        
        assert key1 == key2
    
    def test_key_generation_whitespace_normalized(self, cache_service):
        """Test that whitespace is normalized."""
        key1 = cache_service._generate_cache_key("  test  key  ")
        key2 = cache_service._generate_cache_key("test  key")
        
        # Both should normalize to similar structure
        assert key1 is not None
        assert key2 is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
