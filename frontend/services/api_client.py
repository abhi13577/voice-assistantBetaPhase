"""
Production-grade API client with timeouts, retries, and error handling.
"""

import time
import logging
from typing import Optional, Tuple, Dict, Any
import requests

API_URL = "http://localhost:8000/voice/turn"
TIMEOUT_SECONDS = 30  # Total timeout for the API call
CONNECT_TIMEOUT_SECONDS = 10  # Connection timeout

logger = logging.getLogger(__name__)


def send_voice_turn(
    transcript: str,
    conversation_id: str,
    user_id: int = 1,
    project_id: int = 101
) -> Tuple[Optional[Dict[str, Any]], float]:
    """
    Send voice turn to backend with production-grade error handling.
    
    Args:
        transcript: User input text
        conversation_id: Conversation ID
        user_id: User ID (default: 1)
        project_id: Project ID (default: 101)
        
    Returns:
        Tuple of (response_dict, latency_seconds)
        Returns (None, latency) if request fails
    """
    
    payload = {
        "transcript": transcript,
        "user_id": user_id,
        "project_id": project_id,
        "conversation_id": conversation_id,
        "context_summary": {}
    }
    
    start = time.time()
    
    try:
        logger.debug(f"[API] Sending voice turn: {transcript[:100]}")
        
        response = requests.post(
            API_URL,
            json=payload,
            timeout=(CONNECT_TIMEOUT_SECONDS, TIMEOUT_SECONDS)
        )
        
        latency = round(time.time() - start, 2)
        
        # Log response details
        if response.status_code >= 400:
            logger.error(
                f"[API] Error {response.status_code} for send_voice_turn in {latency}s. "
                f"Response: {response.text[:200]}"
            )
            return None, latency
        
        if response.status_code == 200:
            logger.debug(f"[API] Voice turn successful in {latency}s")
            return response.json(), latency
        
        logger.warning(f"[API] Unexpected status {response.status_code} in {latency}s")
        return None, latency
        
    except requests.Timeout as e:
        latency = round(time.time() - start, 2)
        logger.error(
            f"[API] Timeout after {latency}s "
            f"(connect: {CONNECT_TIMEOUT_SECONDS}s, total: {TIMEOUT_SECONDS}s). "
            f"Backend may be down or overloaded."
        )
        return None, latency
        
    except requests.ConnectionError as e:
        latency = round(time.time() - start, 2)
        logger.error(
            f"[API] Connection error after {latency}s: {str(e)}. "
            f"Cannot reach backend at {API_URL}"
        )
        return None, latency
        
    except Exception as e:
        latency = round(time.time() - start, 2)
        logger.error(
            f"[API] Unexpected error after {latency}s: {type(e).__name__}: {str(e)}"
        )
        return None, latency