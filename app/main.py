
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.schemas.request import VoiceRequest
from app.schemas.response import VoiceResponse
from app.schemas.action import ActionRequest, ActionResponse

from app.core.request_context import request_id_middleware
from app.core.logging_config import configure_logging
from app.core.metrics import voice_requests_total, voice_request_latency_seconds, voice_errors_total
from app.core.config import RATE_LIMIT_WINDOW_SECONDS, RATE_LIMIT_MAX_REQUESTS, REQUIRE_API_KEY, API_KEY
from app.core.http_pool import HTTPClientPool, get_http_pool
from app.core.request_queue import RequestQueue, QueuedRequest, RequestPriority
from app.core.smart_cache import SmartCache

from app.services.intent_engine import intent_engine
from app.services.action_engine import action_engine
from app.services.intent_guardrail import apply_guardrail
from app.services.intent_handlers.intent_router import intent_router
from app.services.cache_service import cache_service
from app.services.llm_fallback import llm_fallback  # ✅ ADDED IMPORT

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

logger = configure_logging()

# ============ PRODUCTION-GRADE COMPONENTS ============

# Smart in-memory cache with LRU eviction
smart_cache = SmartCache(max_memory_mb=50, default_ttl_seconds=600)

# Request queue for surge-traffic handling
request_queue = RequestQueue(max_queue_size=500, dedup_window_seconds=3)

# HTTP connection pool with circuit breaker
http_pool: Optional[HTTPClientPool] = None


# ============ SECURITY UTILITIES ============

def validate_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Validate API key if REQUIRE_API_KEY is enabled."""
    if not REQUIRE_API_KEY:
        return
    
    if not API_KEY:
        logger.error("API_KEY enforcement enabled but no key configured")
        raise HTTPException(status_code=500, detail="Server misconfiguration")
    
    if not x_api_key or x_api_key != API_KEY:
        logger.warning("Invalid or missing API key in request")
        raise HTTPException(status_code=401, detail="Invalid API key")


def sanitize_input(value: str, max_length: int = 500) -> str:
    """Sanitize input to prevent injection attacks."""
    if not value:
        return ""
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Truncate to max length
    value = value[:max_length]
    
    # Remove control characters (except newlines and tabs)
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\t')
    
    return value.strip()


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """App startup/shutdown lifecycle with proper cleanup."""
    if REQUIRE_API_KEY and not API_KEY:
        raise RuntimeError("REQUIRE_API_KEY is true but VOICE_API_KEY is not set")
    
    # Initialize production-grade components
    global http_pool
    http_pool = await HTTPClientPool.get_instance()
    logger.info("[APP] HTTP connection pool initialized")
    
    yield
    
    # Cleanup on shutdown
    if http_pool:
        await http_pool.close()
    logger.info("[APP] Shutdown complete")


app = FastAPI(title="Voice Support Engine", lifespan=app_lifespan)

# ============ SECURITY MIDDLEWARE ============

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],  # Streamlit & React dev
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Request ID middleware
app.middleware("http")(request_id_middleware)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # ✅ FIXED CSP (Swagger-compatible)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "font-src 'self' https://cdn.jsdelivr.net;"
    )

    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    voice_errors_total.inc()
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled server error request_id=%s", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id
        }
    )

# 🔥 STORAGE
LAST_REQUESTS = {}
USER_REQUEST_COUNT = {}


# 🔁 DUPLICATE CHECK
def is_duplicate(user_id, transcript):
    key = f"{user_id}:{transcript.strip().lower()}"
    now = time.time()

    if key in LAST_REQUESTS:
        if now - LAST_REQUESTS[key] < 2:
            return True

    LAST_REQUESTS[key] = now
    return False


# 🚦 RATE LIMIT
def is_rate_limited(user_id):
    now = time.time()
    window = RATE_LIMIT_WINDOW_SECONDS

    if user_id not in USER_REQUEST_COUNT:
        USER_REQUEST_COUNT[user_id] = []

    USER_REQUEST_COUNT[user_id] = [
        t for t in USER_REQUEST_COUNT[user_id] if now - t < window
    ]

    USER_REQUEST_COUNT[user_id].append(now)

    return len(USER_REQUEST_COUNT[user_id]) > RATE_LIMIT_MAX_REQUESTS


@app.get("/health")
async def health_check():
    cache_ok = cache_service.ping()
    return {
        "status": "ok",
        "checks": {
            "api": "ok",
            "cache": "ok" if cache_ok else "degraded"
        }
    }


@app.post("/voice/turn", response_model=VoiceResponse)
async def voice_turn(
    req: Request,
    request: VoiceRequest,
    x_api_key: Optional[str] = Header(None)
):
    """
    Process voice input and return response.
    
    Security: Requires conversation_id and project_id. Optional API key validation.
    """
    try:
        # ✅ SECURITY: Validate API key if enabled
        validate_api_key(x_api_key)
        
        voice_requests_total.inc()
        request_id = getattr(req.state, "request_id", "unknown")
        start_time = time.time()

        # ✅ SECURITY: Sanitize and validate transcript
        transcript = sanitize_input(request.transcript or "")

        # 🛑 EMPTY INPUT
        if not transcript:
            logger.debug(f"request_id={request_id} | Empty transcript rejected")
            return VoiceResponse(
                intent="fallback",
                escalate=False,
                reply_text="Please say something.",
                suggested_actions=[],
                context_used=[],
                confidence=0.0
            )

        # ✅ LOG SECURITY CONTEXT
        logger.info(
            f"request_id={request_id} | user_id={request.user_id} | "
            f"project_id={request.project_id} | conversation_id={request.conversation_id}"
        )

        # ✅ 1. RATE LIMIT
        if is_rate_limited(request.user_id):
            logger.warning(f"request_id={request_id} | Rate limit exceeded for user {request.user_id}")
            return VoiceResponse(
                intent="rate_limited",
                escalate=False,
                reply_text="Too many requests. Please slow down.",
                suggested_actions=[],
                context_used=[],
                confidence=1.0
            )

        # ✅ 2. DUPLICATE CHECK
        if is_duplicate(request.user_id, transcript):
            logger.debug(f"request_id={request_id} | Duplicate blocked")
            return VoiceResponse(
                intent="duplicate",
                escalate=False,
                reply_text="You're repeating too quickly. Please wait.",
                suggested_actions=[],
                context_used=[],
                confidence=1.0
            )

        # ✅ DEBUG LOG
        logger.debug(f"request_id={request_id} | RAW TRANSCRIPT: {transcript}")

        # ✅ 3. CACHE (PRODUCTION-GRADE: Multi-tier with smart_cache)
        cached = cache_service.get(transcript)
        if cached:
            logger.info(f"request_id={request_id} | CACHE HIT (Redis)")
            return VoiceResponse(
                intent=cached["intent"],
                escalate=False,
                reply_text=cached["response"],
                suggested_actions=[],
                context_used=[],
                confidence=round(cached["confidence"], 3)
            )
        
        # Try L1 in-memory cache
        smart_cached = smart_cache.get(transcript, request.user_id)
        if smart_cached:
            logger.info(f"request_id={request_id} | CACHE HIT (L1 SmartCache)")
            return VoiceResponse(
                intent=smart_cached["intent"],
                escalate=False,
                reply_text=smart_cached["response"],
                suggested_actions=[],
                context_used=[],
                confidence=round(smart_cached["confidence"], 3)
            )

        # ---------- INTENT ----------
        with voice_request_latency_seconds.time():
            intent, confidence = intent_engine.classify(transcript)

        intent = apply_guardrail(intent, confidence)

        # ---------- LLM FALLBACK ----------
        if confidence < 0.5 or intent == "fallback":

            llm_intent, llm_confidence = await llm_fallback.get_intent(transcript)

            if llm_intent != "fallback":
                intent = llm_intent
                confidence = llm_confidence
                logger.info(f"request_id={request_id} | LLM fallback used")
            else:
                intent = "fallback"
                logger.info(f"request_id={request_id} | LLM also failed → fallback")

        # ---------- ROUTE ----------
        reply, context_used, suggestions = await intent_router.route(
            intent,
            request.user_id,
            request.project_id,
            transcript,
            {}
        )

        # ---------- CACHE (PRODUCTION-GRADE: Multi-tier) ----------
        response_data = {
            "intent": intent,
            "confidence": confidence,
            "response": reply
        }
        
        # Cache to Redis (L2 - persistent)
        if intent == "fallback":
            cache_service.set(transcript, response_data, ttl=30)
        elif intent != "duplicate":
            cache_service.set(transcript, response_data)
        
        # Cache to L1 in-memory cache (SmartCache)
        smart_cache.set(transcript, request.user_id, response_data, intent=intent)

        # ---------- LATENCY ----------
        total_latency = time.time() - start_time

        logger.info(f"request_id={request_id} | METRIC | intent={intent} | latency={total_latency:.3f}s")

        # ---------- RESPONSE ----------
        return VoiceResponse(
            intent=intent,
            escalate=False,
            reply_text=reply,
            suggested_actions=[],
            context_used=[],
            confidence=round(confidence, 3)
        )

    except HTTPException:
        raise
    except Exception as e:
        voice_errors_total.inc()
        request_id = getattr(req.state, "request_id", "unknown")
        logger.exception(f"request_id={request_id} | Unhandled error in /voice/turn: {str(e)}")
        return VoiceResponse(
            intent="error",
            escalate=True,
            reply_text="An error occurred processing your request. Please try again.",
            suggested_actions=[],
            context_used=[],
            confidence=0.0
        )


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/metrics/production")
def production_metrics():
    """
    Production-grade metrics endpoint with detailed system statistics.
    
    Returns:
        - Cache hit rates and memory usage
        - Request queue depth and deduplication stats  
        - HTTP pool status and circuit breaker state
        - Overall system health
    """
    return {
        "timestamp": time.time(),
        "smart_cache": smart_cache.get_cache_stats(),
        "request_queue": request_queue.get_queue_stats(),
        "http_pool": http_pool.get_pool_status() if http_pool else {},
        "redis_cache": {
            "status": "ok" if cache_service.ping() else "error"
        }
    }


@app.get("/health/detailed")
def detailed_health():
    """Detailed health check including production-grade component status."""
    cache_ok = cache_service.ping()
    llm_breaker = llm_fallback.get_circuit_breaker_state()
    http_pool_stats = http_pool.get_pool_status() if http_pool else {"error": "not initialized"}
    cache_stats = smart_cache.get_cache_stats()
    queue_stats = request_queue.get_queue_stats()
    
    return {
        "status": "ok",
        "checks": {
            "api": "ok",
            "redis_cache": "ok" if cache_ok else "degraded",
            "llm_circuit_breaker": llm_breaker,
            "http_pool": http_pool_stats,
            "smart_cache": cache_stats,
            "request_queue": queue_stats
        }
    }


@app.post("/voice/action", response_model=ActionResponse)
async def execute_action(
    request: ActionRequest,
    x_api_key: Optional[str] = Header(None),
    req: Request = None
):
    """
    Execute an allowed action for the user.
    
    Security: Requires API key if enabled.
    """
    try:
        # ✅ SECURITY: Validate API key if enabled
        validate_api_key(x_api_key)
        
        request_id = getattr(req.state, "request_id", "unknown") if req else "unknown"
        
        logger.info(
            f"request_id={request_id} | action_type={request.action_type} | "
            f"user_id={request.user_id}"
        )

        result = await action_engine.execute(
            request.action_type,
            request.params,
            request.user_id
        )

        logger.info(f"request_id={request_id} | action_success={result.get('success')}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        voice_errors_total.inc()
        request_id = getattr(req.state, "request_id", "unknown") if req else "unknown"
        logger.exception(f"request_id={request_id} | Error executing action: {str(e)}")
        return ActionResponse(
            success=False,
            message="Failed to execute action",
            data=None
        )

