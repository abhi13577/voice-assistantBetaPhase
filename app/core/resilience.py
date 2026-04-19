"""
Resilience patterns: retry logic and circuit breaker.
Used to handle transient failures and protect against cascading failures.
"""

import asyncio
import time
import logging
from typing import Callable, TypeVar, Any, Optional
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    Protects external service calls from repeated failures.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"[CircuitBreaker:{self.name}] Attempting recovery (HALF_OPEN)")
            else:
                from app.core.exceptions import CircuitBreakerOpenError
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            logger.warning(
                f"[CircuitBreaker:{self.name}] Failure #{self.failure_count}: {str(e)}"
            )
            raise
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"[CircuitBreaker:{self.name}] Attempting recovery (HALF_OPEN)")
            else:
                from app.core.exceptions import CircuitBreakerOpenError
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            logger.warning(
                f"[CircuitBreaker:{self.name}] Failure #{self.failure_count}: {str(e)}"
            )
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 2:
                self.state = CircuitBreakerState.CLOSED
                self.success_count = 0
                logger.info(f"[CircuitBreaker:{self.name}] Recovered (CLOSED)")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        self.success_count = 0
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.error(
                f"[CircuitBreaker:{self.name}] Threshold reached, opening circuit"
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if not self.last_failure_time:
            return True
        time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout_seconds


class RetryPolicy:
    """Exponential backoff retry policy."""
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff_seconds: float = 10.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff_seconds = max_backoff_seconds
        self.jitter = jitter
    
    def calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff time with exponential strategy."""
        backoff = min(
            self.backoff_factor * (2 ** attempt),
            self.max_backoff_seconds
        )
        
        if self.jitter:
            import random
            backoff *= random.uniform(0.5, 1.0)
        
        return backoff
    
    def retry_sync(
        self,
        func: Callable,
        *args,
        retryable_exceptions: tuple = (Exception,),
        **kwargs
    ) -> Any:
        """Retry function synchronously with exponential backoff."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    backoff = self.calculate_backoff(attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} after {backoff}s: {str(e)}"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"All {self.max_retries + 1} retry attempts exhausted")
        
        raise last_exception
    
    async def retry_async(
        self,
        func: Callable,
        *args,
        retryable_exceptions: tuple = (Exception,),
        **kwargs
    ) -> Any:
        """Retry async function with exponential backoff."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    backoff = self.calculate_backoff(attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} after {backoff}s: {str(e)}"
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"All {self.max_retries + 1} retry attempts exhausted")
        
        raise last_exception
