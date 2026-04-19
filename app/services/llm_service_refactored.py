"""
Production-grade LLM service with retry logic and circuit breaker.
"""

import os
import redis
import hashlib
import json
import asyncio
from typing import Tuple, Optional
from google import genai
from app.core.base_service import Service
from app.core.settings import get_settings
from app.core.exceptions import LLMError
from app.core.resilience import RetryPolicy, CircuitBreaker

settings = get_settings()


class LLMService(Service):
    """
    LLM provider with caching, retry logic, and circuit breaker.
    """
    
    def __init__(self):
        super().__init__()
        
        # LLM Client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            self.logger.warning("GOOGLE_API_KEY not set, LLM fallback disabled")
        
        self.client = genai.Client(api_key=api_key) if api_key else None
        
        # Cache
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password if settings.redis_password else None,
            decode_responses=True,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
        )
        
        # Retry policy
        self.retry_policy = RetryPolicy(
            max_retries=settings.llm_max_retries,
            backoff_factor=settings.llm_backoff_factor,
            max_backoff_seconds=settings.llm_timeout_seconds,
            jitter=True
        )
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            name="LLM",
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=settings.circuit_breaker_recovery_seconds,
            expected_exception=Exception
        )
        
        self.logger.info("LLM service initialized")
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key for LLM query."""
        normalized = text.strip().lower()
        hash_val = hashlib.sha256(normalized.encode()).hexdigest()
        return f"llm_cache:{hash_val}"
    
    def _try_get_from_cache(self, query: str) -> Optional[dict]:
        """Try to get result from cache."""
        try:
            cache_key = self._generate_cache_key(query)
            cached = self.redis_client.get(cache_key)
            
            if cached:
                self.logger.debug(f"LLM cache hit: {cache_key}")
                return json.loads(cached)
            
            return None
        
        except Exception as e:
            self.logger.warning(f"LLM cache read failed: {e}")
            return None
    
    def _try_set_in_cache(self, query: str, result: dict, ttl: int = 86400) -> None:
        """Try to cache LLM result."""
        try:
            cache_key = self._generate_cache_key(query)
            self.redis_client.setex(cache_key, ttl, json.dumps(result))
            self.logger.debug(f"LLM result cached: {cache_key}")
        
        except Exception as e:
            self.logger.warning(f"LLM cache write failed: {e}")
    
    async def get_intent(self, transcript: str) -> Tuple[str, float]:
        """
        Get intent from LLM with caching and fallback.
        Returns: (intent, confidence)
        """
        if not self.client:
            self.logger.warning("LLM service not available")
            raise LLMError("LLM service not configured")
        
        # Check cache first
        cached_result = self._try_get_from_cache(transcript)
        if cached_result:
            return cached_result["intent"], cached_result["confidence"]
        
        # Build prompt
        prompt = f"""
        Classify the following user transcript into one of these intents:
        - greeting: General greetings
        - check_run_status: Asking about test run status
        - list_projects: Asking to list projects
        - list_runs: Asking to list test runs
        - help: Asking for help
        - fallback: Anything else
        
        User transcript: "{transcript}"
        
        Respond with JSON: {{"intent": "...", "confidence": 0.0-1.0}}
        """
        
        # LLM call with retry and circuit breaker
        try:
            async def call_llm():
                # Use retry policy for transient failures
                def sync_call():
                    return self.client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=prompt
                    )
                
                # Execute with retry
                response = await asyncio.to_thread(
                    self.retry_policy.retry_sync,
                    sync_call,
                    retryable_exceptions=(TimeoutError, ConnectionError, Exception)
                )
                
                return response
            
            # Execute with circuit breaker
            response = await self.circuit_breaker.call_async(call_llm)
            
            # Parse response
            response_text = response.text
            parsed = json.loads(response_text)
            
            intent = parsed.get("intent", "fallback")
            confidence = float(parsed.get("confidence", 0.5))
            
            result = {"intent": intent, "confidence": confidence}
            self._try_set_in_cache(transcript, result)
            
            self.logger.info(f"LLM classified '{transcript}' -> {intent} ({confidence:.2%})")
            return intent, confidence
        
        except Exception as e:
            self.logger.error(f"LLM classification failed: {e}")
            raise LLMError(f"Failed to classify intent: {str(e)}")


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
