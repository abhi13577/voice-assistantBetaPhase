"""
Security middleware for API authentication, rate limiting, and CORS.
"""

import time
import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.core.settings import get_settings
from app.core.exceptions import RateLimitError

settings = get_settings()
logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for identifier."""
        now = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Remove old entries outside window
        self.requests[identifier] = [
            t for t in self.requests[identifier]
            if now - t < self.window_seconds
        ]
        
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(now)
            return True
        
        return False


class APIKeyAuthMiddleware:
    """Simple API Key authentication middleware."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request: Request, call_next):
        # Skip auth for health checks and metrics
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        # Check API key if required
        if settings.require_api_key:
            api_key = request.headers.get("X-API-Key")
            
            if not api_key:
                logger.warning(f"Missing API key: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Missing API key"}
                )
            
            if api_key != settings.api_key:
                logger.warning(f"Invalid API key: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API key"}
                )
        
        return await call_next(request)


class RateLimitMiddleware:
    """Rate limiting middleware."""
    
    def __init__(self, app):
        self.app = app
        self.limiter = RateLimiter(
            max_requests=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds
        )
    
    async def __call__(self, request: Request, call_next):
        # Skip rate limiting for certain endpoints
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        # Skip if disabled
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Get identifier (user_id from body or IP)
        identifier = self._get_identifier(request)
        
        if not self.limiter.is_allowed(identifier):
            logger.warning(f"Rate limit exceeded for: {identifier}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"}
            )
        
        return await call_next(request)
    
    def _get_identifier(self, request: Request) -> str:
        """Get identifier for rate limiting."""
        # Try to get user_id from request body
        if request.method == "POST":
            # Try to extract from path or use IP
            if "user_id" in str(request.url):
                return f"user_{request.url.query}"
        
        # Fall back to client IP
        client_host = request.client.host if request.client else "unknown"
        return f"ip_{client_host}"


class InputSanitizationMiddleware:
    """Sanitize and validate input data."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request: Request, call_next):
        # Validate request size
        content_length = request.headers.get("content-length")
        if content_length:
            max_size = settings.max_request_size_mb * 1024 * 1024
            if int(content_length) > max_size:
                logger.warning(f"Request too large: {content_length}")
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Request too large"}
                )
        
        return await call_next(request)


class SecurityHeadersMiddleware:
    """Add security headers to responses."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


class CORSConfigMiddleware:
    """Configure CORS based on environment."""
    
    @staticmethod
    def get_cors_config() -> dict:
        """Get CORS configuration for environment."""
        return {
            "allow_origins": settings.cors_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-API-Key",
                "X-Request-ID"
            ],
            "max_age": 600,
        }


def apply_security_middlewares(app):
    """Apply all security middlewares to FastAPI app."""
    
    # Order matters: innermost executes first
    app.add_middleware(SecurityHeadersMiddleware)
    
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
    
    if settings.require_api_key:
        app.add_middleware(APIKeyAuthMiddleware)
    
    app.add_middleware(InputSanitizationMiddleware)
