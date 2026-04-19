"""
Application-wide exceptions and error handling.
Used throughout the codebase for consistent error handling.
"""

from typing import Optional, Any


class VoiceAssistantException(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: int = 500,
        details: Optional[dict] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


class IntentClassificationError(VoiceAssistantException):
    """Error during intent classification."""
    status_code = 422


class LLMError(VoiceAssistantException):
    """Error from LLM provider."""
    status_code = 503


class CacheError(VoiceAssistantException):
    """Error accessing cache backend."""
    status_code = 503


class ExternalAPIError(VoiceAssistantException):
    """Error calling external API."""
    status_code = 503


class ValidationError(VoiceAssistantException):
    """Input validation error."""
    status_code = 400


class AuthenticationError(VoiceAssistantException):
    """Authentication failed."""
    status_code = 401


class AuthorizationError(VoiceAssistantException):
    """Authorization failed."""
    status_code = 403


class RateLimitError(VoiceAssistantException):
    """Rate limit exceeded."""
    status_code = 429


class CircuitBreakerOpenError(VoiceAssistantException):
    """Circuit breaker is open."""
    status_code = 503
