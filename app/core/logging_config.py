import logging
import sys
import json
from datetime import datetime

from app.core.config import LOG_LEVEL, ENV


class JSONFormatter(logging.Formatter):
    """Production-grade JSON formatter for structured logging."""

    def format(self, record):
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
        }

        # Add request_id if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class StructuredLogger(logging.LoggerAdapter):
    """Logger adapter for adding structured context."""

    def process(self, msg, kwargs):
        """Add context to log messages."""
        if self.extra:
            # Add extra data to message for JSON formatter
            for key, value in self.extra.items():
                setattr(self.logger, key, value)
        return msg, kwargs


def configure_logging():
    """Configure production-grade logging."""
    logger = logging.getLogger("voice-assistant")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Remove existing handlers
    logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Use JSON formatter in production, text formatter in dev
    if ENV == "prod":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set specific log levels for external libraries
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    return logger