"""
Production-grade error tracking and monitoring.

Features:
- Error categorization
- Error rate tracking
- Error context capture
"""

import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorTracker:
    """Track and categorize errors for monitoring."""

    # Error categories
    CATEGORY_INPUT_VALIDATION = "input_validation"
    CATEGORY_AUTH = "authentication"
    CATEGORY_AUTHORIZATION = "authorization"
    CATEGORY_RATE_LIMIT = "rate_limit"
    CATEGORY_EXTERNAL_SERVICE = "external_service"
    CATEGORY_DATABASE = "database"
    CATEGORY_INTERNAL = "internal_error"

    def __init__(self):
        self.error_counts = {}

    def track_error(
        self,
        category: str,
        message: str,
        request_id: str,
        user_id: Optional[int] = None,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track an error occurrence."""
        
        # Increment counter
        if category not in self.error_counts:
            self.error_counts[category] = 0
        self.error_counts[category] += 1

        # Log as structured event
        log_data = {
            "event": "error",
            "category": category,
            "message": message,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error_count": self.error_counts[category]
        }

        if user_id:
            log_data["user_id"] = user_id

        if context:
            log_data["context"] = context

        if error:
            log_data["error_type"] = type(error).__name__
            log_data["error_message"] = str(error)
            if logger.isEnabledFor(logging.DEBUG):
                log_data["traceback"] = traceback.format_exc()

        log_message = f"[{category.upper()}] {message}"
        
        if category in [
            self.CATEGORY_AUTH,
            self.CATEGORY_AUTHORIZATION,
            self.CATEGORY_EXTERNAL_SERVICE
        ]:
            logger.warning(log_message, extra=log_data)
        elif category == self.CATEGORY_INTERNAL:
            logger.error(log_message, extra=log_data, exc_info=error)
        else:
            logger.info(log_message, extra=log_data)

    def get_error_summary(self) -> Dict[str, int]:
        """Get error counts by category."""
        return dict(self.error_counts)

    def reset(self) -> None:
        """Reset error counters."""
        self.error_counts = {}


# Global error tracker instance
error_tracker = ErrorTracker()


def log_error_event(
    category: str,
    message: str,
    request_id: str,
    user_id: Optional[int] = None,
    error: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """Convenience function to log error events."""
    error_tracker.track_error(category, message, request_id, user_id, error, context)
