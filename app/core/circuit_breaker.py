"""
Circuit Breaker pattern implementation for LLM fallback service.

States:
- CLOSED: Normal operation, requests go through
- OPEN: Circuit broken, requests fail fast
- HALF_OPEN: Testing if service recovered, limited requests allowed
"""

import time
import logging
from enum import Enum
from typing import Callable, Any
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker for external service calls (e.g., LLM API).
    
    Configuration:
    - failure_threshold: Number of failures before opening circuit  
    - recovery_timeout: Seconds before attempting recovery
    - half_open_max_calls: Max calls in half_open state
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        name: str = "CircuitBreaker"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_call_count = 0

    def is_open(self) -> bool:
        """Check if circuit is open and needs recovery timeout."""
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"{self.name}: Recovery timeout passed, moving to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_call_count = 0
                return False  # Attempt next request
            return True
        return False

    def record_success(self):
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"{self.name}: Success in HALF_OPEN state, closing circuit")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"{self.name}: Failure in HALF_OPEN state, reopening circuit")
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"{self.name}: Failure threshold reached ({self.failure_count}/"
                    f"{self.failure_threshold}), opening circuit"
                )
                self.state = CircuitState.OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Returns: (success: bool, result: Any, error: str|None)
        """
        # Check if circuit is open
        if self.is_open():
            error_msg = f"{self.name}: Circuit is OPEN, request rejected"
            logger.warning(error_msg)
            return False, None, error_msg

        # Limit calls in HALF_OPEN state
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_call_count >= self.half_open_max_calls:
                error_msg = f"{self.name}: HALF_OPEN call limit reached"
                logger.warning(error_msg)
                return False, None, error_msg
            self.half_open_call_count += 1

        # Execute function
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self.record_success()
            return True, result, None
        except Exception as e:
            self.record_failure()
            error_msg = f"{self.name}: Call failed with error: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def get_state(self) -> dict:
        """Get circuit breaker state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "half_open_calls": self.half_open_call_count,
            "last_failure_time": self.last_failure_time
        }
