"""
Structured logging configuration with JSON output for production.
Includes correlation IDs, latency tracking, and OpenTelemetry integration.
"""

import logging
import json
import sys
from typing import Optional
from datetime import datetime
from pythonjsonlogger import jsonlogger
from app.core.settings import get_settings

settings = get_settings()


class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record["timestamp"] = datetime.utcnow().isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["message"] = message_dict.get("message", "")
        
        # Add context from extra if available
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id
        if hasattr(record, "latency_ms"):
            log_record["latency_ms"] = record.latency_ms
        if hasattr(record, "service"):
            log_record["service"] = record.service
        
        # Stack trace for exceptions
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def configure_structured_logging(name: Optional[str] = None) -> logging.Logger:
    """Configure structured logging for production."""
    logger = logging.getLogger(name or __name__)
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    if settings.is_production():
        # JSON formatted logs to stdout
        handler = logging.StreamHandler(sys.stdout)
        formatter = StructuredFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        # Pretty format for development
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


class Logger:
    """Wrapper for structured logging with context support."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        """Set logging context (request_id, user_id, etc)."""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear logging context."""
        self.context.clear()
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging with context."""
        extra = {**self.context, **kwargs}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        self.logger.exception(message, extra={**self.context, **kwargs})
