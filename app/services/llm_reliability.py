import asyncio
import json
import time

from app.services.llm_fallback import llm_fallback
from app.core.metrics import llm_requests_total


class LLMCircuitBreaker:

    def __init__(self):
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

        self.FAILURE_THRESHOLD = 5
        self.RECOVERY_TIMEOUT = 30

    def allow_request(self):

        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.RECOVERY_TIMEOUT:
                self.state = "HALF_OPEN"
                return True
            return False

        return True

    def record_success(self):

        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):

        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.FAILURE_THRESHOLD:
            self.state = "OPEN"


class LLMReliabilityService:

    def __init__(self):

        self.circuit_breaker = LLMCircuitBreaker()

        self.TIMEOUT = 1.2

    async def classify(self, transcript: str):

        if not self.circuit_breaker.allow_request():
            raise Exception("LLM circuit breaker open")

        loop = asyncio.get_event_loop()

        try:
            llm_requests_total.inc()

            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    llm_fallback.classify_and_extract,
                    transcript
                ),
                timeout=self.TIMEOUT
            )

            self.circuit_breaker.record_success()
            return response

        except Exception:
            self.circuit_breaker.record_failure()
            raise


llm_reliability_service = LLMReliabilityService()