import os
import redis
import hashlib
import json
import logging
import asyncio
from google import genai

from app.core.metrics import redis_cache_hits_total, redis_cache_misses_total
from app.core.config import REDIS_HOST, REDIS_PORT, LLM_TIMEOUT_SECONDS
from app.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class LLMFallback:

    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1
        )
        
        # ✅ PRODUCTION: Circuit breaker for LLM API
        # Opens after 5 failures, tries recovery after 60 seconds
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=3,
            name="LLM-Fallback"
        )

    def _generate_key(self, text: str):
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def _call_llm(self, transcript: str) -> dict:
        """
        Internal method to call LLM API.
        Returns: {"intent": str, "confidence": float}
        """
        prompt = f"""
You are an enterprise QA voice assistant intent classifier.

Map user requests to closest intent even if wording is different.

Examples:

User: show last regression result
Intent: check_run_status

User: did my regression pass
Intent: check_run_status

User: list my executions
Intent: list_runs

User: what projects do I have
Intent: list_projects

Allowed intents:
- check_run_status
- list_projects
- list_runs
- greeting

Return ONLY JSON like:
{{"intent": "list_runs", "confidence": 0.9}}

User input:
"{transcript}"
"""

        response = await asyncio.wait_for(
            asyncio.to_thread(
                self.client.models.generate_content,
                model="models/gemini-2.5-flash",
                contents=prompt
            ),
            timeout=LLM_TIMEOUT_SECONDS
        )

        result_text = response.text.strip()
        parsed = json.loads(result_text)

        return {
            "intent": parsed.get("intent", "fallback"),
            "confidence": float(parsed.get("confidence", 0.5))
        }

    async def get_intent(self, transcript: str):
        """
        Get intent from transcript using LLM with circuit breaker protection.
        Returns: (intent, confidence)
        """

        cache_key = self._generate_key(transcript)

        # ✅ Try cache first
        cached = None
        try:
            cached = self.redis_client.get(cache_key)
        except Exception as exc:
            logger.warning("LLM cache read failed: %s", exc)
            cached = None

        if cached:
            redis_cache_hits_total.inc()
            try:
                parsed = json.loads(cached)
                return parsed["intent"], parsed["confidence"]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                return "fallback", 0.0

        redis_cache_misses_total.inc()

        # ✅ CIRCUIT BREAKER: Call LLM with protection
        success, result, error = await self.circuit_breaker.call(
            self._call_llm,
            transcript
        )

        if success:
            intent = result["intent"]
            confidence = result["confidence"]
            logger.info(f"LLM fallback used: intent={intent}")
        else:
            logger.warning(f"LLM fallback failed (circuit breaker): {error}")
            intent = "fallback"
            confidence = 0.0

        # ✅ Cache the result
        try:
            self.redis_client.set(
                cache_key,
                json.dumps({
                    "intent": intent,
                    "confidence": confidence
                }),
                ex=3600
            )
        except Exception:
            # Cache write failures should never fail the request
            pass

        return intent, confidence

    def get_circuit_breaker_state(self) -> dict:
        """Get circuit breaker state for monitoring."""
        return self.circuit_breaker.get_state()



llm_fallback = LLMFallback()