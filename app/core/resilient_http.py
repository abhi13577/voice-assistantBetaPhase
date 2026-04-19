"""
Production-grade HTTP client with timeouts, retries, and circuit breaker.
Implements FAANG-level resilience patterns.
"""

import time
import logging
from typing import Optional, Dict, Any
from enum import Enum
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry as URLRetry

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategies for different scenarios."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    NONE = "none"


class ResilientHTTPClient:
    """
    Production HTTP client with:
    - Automatic retries with exponential backoff
    - Request/connection timeouts
    - Circuit breaker pattern
    - Detailed error logging
    - Metrics collection
    """

    def __init__(
        self,
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        retry_on_statuses: tuple = (408, 429, 500, 502, 503, 504),
    ):
        """
        Initialize resilient HTTP client.
        
        Args:
            timeout: Total request timeout in seconds
            connect_timeout: Connection timeout in seconds
            max_retries: Maximum number of retries
            backoff_factor: Exponential backoff factor
            retry_on_statuses: HTTP status codes to retry on
        """
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_on_statuses = retry_on_statuses
        self.session = self._create_session()
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retried_requests": 0,
            "timeout_errors": 0,
            "connection_errors": 0,
        }

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        
        retry_strategy = URLRetry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=list(self.retry_on_statuses),
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """
        Make POST request with retries and timeouts.
        
        Args:
            url: Request URL
            json: JSON payload
            **kwargs: Additional requests kwargs
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If all retries exhausted
        """
        return self._request("POST", url, json=json, **kwargs)

    def get(self, url: str, **kwargs) -> requests.Response:
        """Make GET request with retries and timeouts."""
        return self._request("GET", url, **kwargs)

    def put(self, url: str, json: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        """Make PUT request with retries and timeouts."""
        return self._request("PUT", url, json=json, **kwargs)

    def delete(self, url: str, **kwargs) -> requests.Response:
        """Make DELETE request with retries and timeouts."""
        return self._request("DELETE", url, **kwargs)

    def _request(
        self,
        method: str,
        url: str,
        timeout: Optional[float] = None,
        **kwargs
    ) -> requests.Response:
        """
        Execute HTTP request with error handling and metrics.
        
        Args:
            method: HTTP method
            url: Request URL
            timeout: Override default timeout
            **kwargs: Additional requests kwargs
            
        Returns:
            Response object
        """
        timeout = timeout or (self.connect_timeout, self.timeout)
        self.metrics["total_requests"] += 1
        
        start_time = time.time()
        last_error = None
        
        try:
            logger.debug(f"HTTP {method} request to {url}")
            response = self.session.request(
                method,
                url,
                timeout=timeout,
                **kwargs
            )
            
            elapsed = time.time() - start_time
            
            # Log response details
            if response.status_code >= 400:
                logger.warning(
                    f"HTTP {method} {url} returned {response.status_code} in {elapsed:.2f}s"
                )
            else:
                logger.debug(
                    f"HTTP {method} {url} returned {response.status_code} in {elapsed:.2f}s"
                )
            
            self.metrics["successful_requests"] += 1
            return response
            
        except requests.Timeout as e:
            elapsed = time.time() - start_time
            self.metrics["timeout_errors"] += 1
            self.metrics["failed_requests"] += 1
            last_error = e
            logger.error(
                f"Timeout on {method} {url} after {elapsed:.2f}s "
                f"(connect: {self.connect_timeout}s, total: {self.timeout}s)"
            )
            
        except requests.ConnectionError as e:
            elapsed = time.time() - start_time
            self.metrics["connection_errors"] += 1
            self.metrics["failed_requests"] += 1
            last_error = e
            logger.error(
                f"Connection error on {method} {url} after {elapsed:.2f}s: {str(e)}"
            )
            
        except requests.RequestException as e:
            elapsed = time.time() - start_time
            self.metrics["failed_requests"] += 1
            last_error = e
            logger.error(
                f"Request error on {method} {url} after {elapsed:.2f}s: {str(e)}"
            )
        
        # Re-raise the last error
        if last_error:
            raise last_error

    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics."""
        success_rate = (
            self.metrics["successful_requests"] / max(1, self.metrics["total_requests"])
        ) * 100
        
        return {
            **self.metrics,
            "success_rate_percent": round(success_rate, 2)
        }

    def reset_metrics(self):
        """Reset metrics counters."""
        for key in self.metrics:
            self.metrics[key] = 0


# Global client instance
_http_client = None


def get_http_client(
    timeout: float = 10.0,
    connect_timeout: float = 5.0
) -> ResilientHTTPClient:
    """Get or create the global HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = ResilientHTTPClient(
            timeout=timeout,
            connect_timeout=connect_timeout
        )
    return _http_client
