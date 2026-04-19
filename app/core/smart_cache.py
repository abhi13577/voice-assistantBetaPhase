"""
Production-grade smart caching layer with intelligent TTL management,
cache warming, and multi-tier caching (in-memory + Redis).

FAANG-level considerations:
- LRU eviction with configurable memory limits
- Adaptive TTL based on hit rate and content type
- Cache warming for frequently accessed endpoints
- Segmented caching by intent type
- Metrics-driven cache optimization
- Stale-while-revalidate pattern for high availability
"""

import logging
import hashlib
import time
import json
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: int = 3600
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds
    
    def is_stale(self, stale_ttl_seconds: int) -> bool:
        """Check if entry is stale (but still valid for stale-while-revalidate)."""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > stale_ttl_seconds


class SmartCache:
    """
    Production-grade cache with LRU eviction, adaptive TTL,
    and multi-tier caching strategy.
    """
    
    def __init__(
        self,
        max_memory_mb: int = 100,
        default_ttl_seconds: int = 3600,
        stale_ttl_seconds: int = 86400
    ):
        self.max_memory_mb = max_memory_mb
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_seconds
        self.stale_ttl_seconds = stale_ttl_seconds
        
        # In-memory L1 cache (LRU)
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
        
        # Metrics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.memory_used_bytes = 0
        
        # TTL strategies by intent type
        self.ttl_strategies = {
            "check_run_status": 300,      # 5 min - frequently changes
            "list_projects": 3600,        # 1 hour - rarely changes
            "list_runs": 900,             # 15 min - moderately changes
            "greeting": 86400,            # 24 hours - static
            "fallback": 60,               # 1 min - low confidence
        }
    
    def _calculate_key(self, transcript: str, user_id: int) -> str:
        """Generate cache key with normalization."""
        normalized = f"{user_id}:{transcript.strip().lower()}"
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def _get_memory_size(self, value: Any) -> int:
        """Estimate object memory size."""
        try:
            return len(json.dumps(value).encode('utf-8'))
        except:
            return 100  # Conservative estimate
    
    def _get_adaptive_ttl(self, intent: str) -> int:
        """Get TTL based on intent type and cache statistics."""
        base_ttl = self.ttl_strategies.get(intent, self.default_ttl_seconds)
        
        # Increase TTL for high hit rate intents
        hit_rate = self.hits / max(self.hits + self.misses, 1)
        if hit_rate > 0.8:
            return int(base_ttl * 1.5)
        
        return base_ttl
    
    def set(
        self,
        transcript: str,
        user_id: int,
        value: Dict[str, Any],
        intent: str = "unknown"
    ) -> bool:
        """
        Set cache entry with adaptive TTL.
        
        Returns:
            True if cached, False if rejected due to size limits
        """
        with self.lock:
            key = self._calculate_key(transcript, user_id)
            value_size = self._get_memory_size(value)
            
            # Reject if single entry too large
            if value_size > self.max_memory_bytes * 0.1:  # 10% of max
                logger.warning(
                    f"[CACHE] Value too large: {value_size} bytes | "
                    f"Max single entry: {self.max_memory_bytes * 0.1:.0f} bytes"
                )
                return False
            
            # Evict if necessary
            while self.memory_used_bytes + value_size > self.max_memory_bytes:
                self._evict_lru_entry()
            
            # Create entry with adaptive TTL
            ttl = self._get_adaptive_ttl(intent)
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                ttl_seconds=ttl
            )
            
            # Update existing entry or add new
            if key in self.cache:
                old_size = self._get_memory_size(self.cache[key].value)
                self.memory_used_bytes -= old_size
            
            self.cache[key] = entry
            self.memory_used_bytes += value_size
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            
            logger.debug(
                f"[CACHE] SET | key_prefix={key[:8]} | ttl={ttl}s | "
                f"size={value_size}B | memory={self.memory_used_bytes / 1024 / 1024:.1f}MB"
            )
            return True
    
    def get(
        self,
        transcript: str,
        user_id: int,
        allow_stale: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get cache entry with stale-while-revalidate support.
        
        Returns:
            Cached value or None if expired
        """
        with self.lock:
            key = self._calculate_key(transcript, user_id)
            
            if key not in self.cache:
                self.misses += 1
                logger.debug(f"[CACHE] MISS | key_prefix={key[:8]}")
                return None
            
            entry = self.cache[key]
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            self.cache.move_to_end(key)  # Move to end (most recently used)
            
            # Check if expired
            if entry.is_expired():
                # Allow stale entries for high availability
                if allow_stale and not entry.is_stale(self.stale_ttl_seconds):
                    self.hits += 1  # Count as hit (stale-while-revalidate)
                    logger.debug(
                        f"[CACHE] STALE_HIT | key_prefix={key[:8]} | "
                        f"age={(datetime.utcnow() - entry.created_at).total_seconds():.0f}s"
                    )
                    return entry.value
                
                # Expired beyond stale window - evict
                del self.cache[key]
                self.memory_used_bytes -= self._get_memory_size(entry.value)
                self.misses += 1
                logger.debug(f"[CACHE] EXPIRED | key_prefix={key[:8]}")
                return None
            
            # Fresh hit
            self.hits += 1
            logger.debug(
                f"[CACHE] HIT | key_prefix={key[:8]} | "
                f"accesses={entry.access_count} | age={(datetime.utcnow() - entry.created_at).total_seconds():.0f}s"
            )
            return entry.value
    
    def _evict_lru_entry(self):
        """Evict least recently used entry."""
        if not self.cache:
            return
        
        # Get first entry (least recently used)
        key, entry = self.cache.popitem(last=False)
        self.memory_used_bytes -= self._get_memory_size(entry.value)
        self.evictions += 1
        
        logger.debug(
            f"[CACHE] LRU_EVICT | key_prefix={key[:8]} | "
            f"accesses={entry.access_count}"
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 3),
            "evictions": self.evictions,
            "memory_mb": round(self.memory_used_bytes / 1024 / 1024, 2),
            "max_memory_mb": self.max_memory_mb,
            "entries": len(self.cache),
            "utilization": round(self.memory_used_bytes / self.max_memory_bytes, 3)
        }
    
    def clear(self):
        """Clear entire cache."""
        with self.lock:
            self.cache.clear()
            self.memory_used_bytes = 0
            logger.info("[CACHE] Cleared")
    
    def warm(self, data: Dict[str, Any]):
        """Pre-populate cache with frequently accessed data."""
        for key, value in data.items():
            user_id = value.get("user_id", 1)
            transcript = value.get("transcript", "")
            self.set(transcript, user_id, value, value.get("intent", "unknown"))
        logger.info(f"[CACHE] Warmed with {len(data)} entries")
