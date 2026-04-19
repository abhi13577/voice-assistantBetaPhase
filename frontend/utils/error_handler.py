"""
Production-grade logging and error handling for Streamlit frontend.
Windows-compatible UTF-8 logging configuration.
"""

import logging
import streamlit as st
from datetime import datetime
from typing import Optional, Callable, Any
from functools import wraps
import traceback
import sys
import io

# Fix Windows UTF-8 encoding for console output
if sys.platform == 'win32':
    try:
        # Try to reconfigure stdout to use UTF-8
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        # Fallback: use UTF-8 with error replacement
        pass

# Configure logging with detailed format and UTF-8 encoding
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('frontend.log', encoding='utf-8'),
        logging.StreamHandler(stream=sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class FrontendErrorHandler:
    """Production-grade error handler for frontend operations."""
    
    @staticmethod
    def log_error(
        error: Exception,
        context: str,
        severity: str = "ERROR"
    ) -> None:
        """
        Log error with context and full traceback.
        
        Args:
            error: The exception
            context: What was happening when error occurred
            severity: ERROR, WARNING, or CRITICAL
        """
        tb = traceback.format_exc()
        log_msg = (
            f"[{severity}] {context}\n"
            f"Error Type: {type(error).__name__}\n"
            f"Error Message: {str(error)}\n"
            f"Traceback:\n{tb}"
        )
        
        if severity == "CRITICAL":
            logger.critical(log_msg)
        elif severity == "WARNING":
            logger.warning(log_msg)
        else:
            logger.error(log_msg)

    @staticmethod
    def show_error_to_user(
        message: str,
        error_details: Optional[str] = None,
        error_code: Optional[str] = None
    ) -> None:
        """
        Display user-friendly error message in Streamlit.
        
        Args:
            message: User-friendly error message
            error_details: Technical details for advanced users
            error_code: Error code for support team
        """
        display_msg = f"ERROR: {message}"
        if error_code:
            display_msg += f" (Code: {error_code})"
        
        st.error(display_msg)
        
        if error_details:
            with st.expander("Technical Details"):
                st.code(error_details, language="text")

    @staticmethod
    def safe_execute(
        func: Callable,
        *args,
        error_message: str = "An error occurred",
        error_code: Optional[str] = None,
        **kwargs
    ) -> Optional[Any]:
        """
        Execute function safely with error handling.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            error_message: Message if error occurs
            error_code: Error code for debugging
            **kwargs: Keyword arguments
            
        Returns:
            Function result or None if error
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            FrontendErrorHandler.log_error(e, f"Error in {func.__name__}", "ERROR")
            FrontendErrorHandler.show_error_to_user(
                error_message,
                str(e),
                error_code
            )
            return None


def production_safe(error_message: str = "Operation failed", error_code: Optional[str] = None):
    """
    Decorator for production-safe functions.
    Catches exceptions and displays user-friendly errors.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                FrontendErrorHandler.log_error(e, f"In {func.__name__}", "ERROR")
                FrontendErrorHandler.show_error_to_user(
                    error_message,
                    str(e),
                    error_code or func.__name__
                )
                return None
        return wrapper
    return decorator


class APIErrorHandler:
    """Handle API-specific errors with proper retry logic."""
    
    @staticmethod
    def handle_api_error(
        response_data: Any,
        endpoint: str,
        operation: str
    ) -> tuple[bool, Optional[Any], str]:
        """
        Handle API response errors gracefully.
        
        Args:
            response_data: API response or None if request failed
            endpoint: API endpoint name
            operation: What operation was being performed
            
        Returns:
            (success: bool, data: Any, error_message: str)
        """
        if response_data is None:
            error_msg = f"No response from {endpoint}. Please check your connection."
            logger.error(f"API Error: {endpoint} returned None for {operation}")
            return False, None, error_msg
        
        if isinstance(response_data, dict):
            if "error" in response_data:
                error_msg = response_data.get("error", "Unknown error")
                logger.error(f"API Error ({endpoint}): {error_msg}")
                return False, None, f"Server error: {error_msg}"
        
        return True, response_data, ""

    @staticmethod
    def log_api_call(
        method: str,
        endpoint: str,
        status_code: int,
        latency_ms: float,
        success: bool
    ) -> None:
        """Log API call for monitoring."""
        status = "[OK]" if success else "[FAIL]"
        logger.info(
            f"API {status} {method} {endpoint} - Status: {status_code}, "
            f"Latency: {latency_ms}ms"
        )


class UserFeedback:
    """Display user feedback and operation status."""
    
    @staticmethod
    def show_success(message: str, duration: float = 3) -> None:
        """Show success message."""
        logger.info(f"Success: {message}")
        st.success(f"SUCCESS: {message}", icon="✓")

    @staticmethod
    def show_warning(message: str) -> None:
        """Show warning message."""
        logger.warning(f"Warning: {message}")
        st.warning(f"WARNING: {message}", icon="⚠️")

    @staticmethod
    def show_info(message: str) -> None:
        """Show info message."""
        logger.info(f"Info: {message}")
        st.info(f"INFO: {message}", icon="ℹ️")

    @staticmethod
    def show_loading(message: str = "Processing...") -> None:
        """Show loading spinner."""
        with st.spinner(f"LOADING: {message}"):
            logger.debug(f"Loading: {message}")
            return


class PerformanceMonitor:
    """Monitor and log performance metrics."""
    
    @staticmethod
    def log_operation(
        operation_name: str,
        duration_ms: float,
        success: bool,
        details: Optional[str] = None
    ) -> None:
        """Log operation performance."""
        status = "[OK]" if success else "[FAIL]"
        msg = f"Operation {status} {operation_name} - {duration_ms:.0f}ms"
        if details:
            msg += f" - {details}"
        
        if duration_ms > 5000:  # More than 5 seconds
            logger.warning(f"SLOW: {msg}")
        else:
            logger.debug(msg)


# Export main handler
error_handler = FrontendErrorHandler()
api_error_handler = APIErrorHandler()
user_feedback = UserFeedback()
perf_monitor = PerformanceMonitor()
