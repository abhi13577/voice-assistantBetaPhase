"""
Production-grade request queue manager for handling surge traffic.
Implements backpressure, priority queuing, and request deduplication
to maintain system stability under high load.

FAANG-level considerations:
- Request prioritization (user requests > health checks)
- Backpressure mechanism (reject if queue too full)
- Request deduplication (avoid duplicate processing)
- Histogram metrics for queue depth
- Graceful degradation under load
"""

import asyncio
import logging
import hashlib
import time
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RequestPriority(Enum):
    """Request priority levels."""
    LOW = 3
    MEDIUM = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class QueuedRequest:
    """Represents a queued request with metadata."""
    request_id: str
    priority: RequestPriority
    transcript: str
    user_id: int
    conversation_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 300  # Request timeout
    
    def is_expired(self) -> bool:
        """Check if request has expired."""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds
    
    def get_dedup_key(self) -> str:
        """Generate deduplication key."""
        key_data = f"{self.user_id}:{self.transcript}:{self.conversation_id}"
        return hashlib.sha256(key_data.encode()).hexdigest()


class RequestQueue:
    """
    Production-grade asynchronous request queue with deduplication,
    backpressure, and priority handling.
    """
    
    def __init__(
        self,
        max_queue_size: int = 1000,
        dedup_window_seconds: int = 5,
        high_water_mark: float = 0.8,  # 80% capacity
    ):
        self.max_queue_size = max_queue_size
        self.dedup_window_seconds = dedup_window_seconds
        self.high_water_mark = high_water_mark
        
        # Priority queue (by priority then FIFO)
        self.requests: List[QueuedRequest] = []
        self.processed_requests: Dict[str, datetime] = {}  # Dedup tracking
        self.lock = asyncio.Lock()
        
        # Metrics
        self.total_enqueued = 0
        self.total_processed = 0
        self.total_deduplicated = 0
        self.total_rejected = 0
        self.max_depth = 0
    
    async def enqueue(
        self,
        request: QueuedRequest
    ) -> bool:
        """
        Enqueue a request with deduplication and backpressure.
        
        Returns:
            True if enqueued, False if rejected
        """
        async with self.lock:
            # Check if queue is too full (backpressure)
            if len(self.requests) >= int(self.max_queue_size * self.high_water_mark):
                self.total_rejected += 1
                logger.warning(
                    f"[QUEUE] BACKPRESSURE: Queue at {len(self.requests)}/{self.max_queue_size} | "
                    f"Rejecting request {request.request_id}"
                )
                return False
            
            # Check for duplicates
            dedup_key = request.get_dedup_key()
            if dedup_key in self.processed_requests:
                last_seen = self.processed_requests[dedup_key]
                elapsed = (datetime.utcnow() - last_seen).total_seconds()
                
                if elapsed < self.dedup_window_seconds:
                    self.total_deduplicated += 1
                    logger.debug(
                        f"[QUEUE] DEDUP: Rejected duplicate within {self.dedup_window_seconds}s | "
                        f"request_id={request.request_id}"
                    )
                    return False
            
            # Remove expired requests
            self.requests = [r for r in self.requests if not r.is_expired()]
            
            # Enqueue with priority
            self.requests.append(request)
            self.requests.sort(key=lambda r: r.priority.value)  # Sort by priority
            
            self.total_enqueued += 1
            self.max_depth = max(self.max_depth, len(self.requests))
            
            logger.debug(
                f"[QUEUE] Enqueued request_id={request.request_id} | "
                f"Priority={request.priority.name} | Queue depth={len(self.requests)}"
            )
            
            return True
    
    async def dequeue(self) -> Optional[QueuedRequest]:
        """
        Dequeue the highest priority request.
        
        Returns:
            Next request to process or None if queue empty
        """
        async with self.lock:
            if not self.requests:
                return None
            
            # Get highest priority (lowest priority value)
            request = self.requests.pop(0)
            
            # Record in dedup tracking
            dedup_key = request.get_dedup_key()
            self.processed_requests[dedup_key] = datetime.utcnow()
            
            # Cleanup old dedup entries
            cutoff = datetime.utcnow() - timedelta(seconds=self.dedup_window_seconds * 2)
            self.processed_requests = {
                k: v for k, v in self.processed_requests.items()
                if v > cutoff
            }
            
            self.total_processed += 1
            logger.debug(
                f"[QUEUE] Dequeued request_id={request.request_id} | "
                f"Queue depth={len(self.requests)}"
            )
            
            return request
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics for monitoring."""
        return {
            "current_depth": len(self.requests),
            "max_depth": self.max_depth,
            "total_enqueued": self.total_enqueued,
            "total_processed": self.total_processed,
            "total_deduplicated": self.total_deduplicated,
            "total_rejected_backpressure": self.total_rejected,
            "utilization": len(self.requests) / self.max_queue_size,
            "backpressure_active": len(self.requests) >= int(
                self.max_queue_size * self.high_water_mark
            )
        }


class QueueWorkerPool:
    """
    Worker pool for processing queued requests.
    Configurable concurrency for optimal throughput.
    """
    
    def __init__(
        self,
        queue: RequestQueue,
        num_workers: int = 10,
        process_handler: Optional[Callable] = None
    ):
        self.queue = queue
        self.num_workers = num_workers
        self.process_handler = process_handler
        self.workers: List[asyncio.Task] = []
        self.running = False
    
    async def start(self):
        """Start worker pool."""
        self.running = True
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker_loop(i))
            self.workers.append(task)
        logger.info(f"[QUEUE_WORKERS] Started {self.num_workers} workers")
    
    async def stop(self):
        """Stop worker pool gracefully."""
        self.running = False
        for task in self.workers:
            task.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("[QUEUE_WORKERS] All workers stopped")
    
    async def _worker_loop(self, worker_id: int):
        """Main worker loop."""
        while self.running:
            try:
                request = await self.queue.dequeue()
                
                if request is None:
                    await asyncio.sleep(0.1)  # Brief sleep if queue empty
                    continue
                
                if self.process_handler:
                    await self.process_handler(request)
                    
            except asyncio.CancelledError:
                logger.info(f"[QUEUE_WORKERS] Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.exception(f"[QUEUE_WORKERS] Worker {worker_id} error: {e}")
                await asyncio.sleep(0.5)  # Back off on error
