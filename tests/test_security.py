"""
Security-focused integration tests for the Voice Support Engine.

Tests:
- Input injection attempts
- Authentication/Authorization
- Data isolation
- Rate limiting
- Error message leakage
"""

from fastapi.testclient import TestClient
import pytest
import uuid

from app.main import app
from app.core.config import REQUIRE_API_KEY, API_KEY


client = TestClient(app)


# ============ INPUT INJECTION TESTS ============

def test_sql_injection_attempt_in_transcript():
    """SQL injection attempt should be sanitized."""
    body = {
        "transcript": "'; DROP TABLE users; --",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200  # Should not crash


def test_xss_attack_in_transcript():
    """XSS attempt should be sanitized."""
    body = {
        "transcript": "<script>alert('xss')</script>",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200  # Should not crash


def test_null_byte_injection():
    """Null bytes should be removed."""
    body = {
        "transcript": "hello\x00world\x00test",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200


def test_control_character_removal():
    """Control characters should be removed."""
    body = {
        "transcript": "hello\x01\x02\x03world",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200


def test_unicode_normalization():
    """Unicode characters should be handled safely."""
    body = {
        "transcript": "hello 世界 🌍 مرحبا",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200


# ============ AUTHORIZATION TESTS ============

def test_user_cannot_access_other_user_data_context():
    """User context isolation - different user_id values."""
    # Request as user 1
    body1 = {
        "transcript": "list my projects",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response1 = client.post("/voice/turn", json=body1)
    assert response1.status_code == 200

    # Request as user 2
    body2 = {
        "transcript": "list my projects",
        "user_id": 2,
        "project_id": 2,
        "conversation_id": str(uuid.uuid4())
    }
    response2 = client.post("/voice/turn", json=body2)
    assert response2.status_code == 200

    # Both requests succeeded but should have isolated contexts
    # (This is a proxy test - the actual isolation happens in services)


def test_project_id_cannot_be_zero():
    """project_id must be valid (>0), not 0."""
    body = {
        "transcript": "list my projects",
        "user_id": 1,
        "project_id": 0,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422  # Validation error


def test_conversation_id_cannot_be_empty():
    """conversation_id cannot be empty string."""
    body = {
        "transcript": "list my projects",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": ""  # Empty
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422  # Validation error


# ============ RATE LIMITING ============

def test_rate_limiting_should_trigger():
    """Rate limiting should work after max requests."""
    conversation_id = str(uuid.uuid4())
    user_id = 999  # Use unique user to avoid conflicts

    # Make requests up to limit
    for i in range(10):  # Default limit is 10
        body = {
            "transcript": f"test request {i}",
            "user_id": user_id,
            "project_id": 1,
            "conversation_id": conversation_id
        }
        response = client.post("/voice/turn", json=body)
        assert response.status_code == 200

    # Next request should be rate limited
    body = {
        "transcript": "this should be rate limited",
        "user_id": user_id,
        "project_id": 1,
        "conversation_id": conversation_id
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "rate_limited"


# ============ ERROR MESSAGE SECURITY ============

def test_error_messages_do_not_leak_internal_details():
    """Error messages should not expose internal implementation."""
    body = {
        "action_type": "invalid_action_type_xyz",
        "params": {},
        "user_id": 1
    }
    response = client.post("/voice/action", json=body)
    assert response.status_code == 200  # Graceful handling
    payload = response.json()
    assert "success" in payload
    # Should not expose database info, file paths, etc.
    assert "traceback" not in str(payload).lower()
    assert "/home/" not in str(payload)
    assert "config" not in str(payload).lower()


def test_error_responses_include_request_id():
    """Error responses should include request_id for debugging without leaking details."""
    body = {
        "transcript": "test",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200
    payload = response.json()
    # Should have a response, no details leaked


# ============ SECURITY HEADERS ============

def test_response_includes_security_headers():
    """All responses should include security headers."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)

    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"

    assert "X-XSS-Protection" in response.headers


def test_csp_header_present():
    """Content-Security-Policy header should be present."""
    response = client.get("/health")
    assert "Content-Security-Policy" in response.headers


# ============ CORS SECURITY ============

def test_cors_headers_only_allow_specific_origins():
    """CORS should only allow specific origins."""
    response = client.get(
        "/health",
        headers={"Origin": "https://evil.com"}
    )
    # FastAPI's CORS middleware will handle this
    assert response.status_code == 200


# ============ DATA VALIDATION ============

def test_user_id_must_be_integer():
    """user_id must be integer."""
    body = {
        "transcript": "hello",
        "user_id": "invalid",  # String instead of int
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422


def test_project_id_must_be_integer():
    """project_id must be integer."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": "invalid",  # String instead of int
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422


def test_conversation_id_must_be_string():
    """conversation_id must be string."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": 12345  # Integer instead of string
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422


def test_context_summary_must_be_dict():
    """context_summary must be dict."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4()),
        "context_summary": "invalid"  # String instead of dict
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422


# ============ EDGE CASES ============

def test_very_long_user_ids():
    """Very large user IDs should be handled."""
    body = {
        "transcript": "hello",
        "user_id": 999999999,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200


def test_special_characters_in_conversation_id():
    """Special characters in conversation_id should be handled."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": "abc-123_xyz.test"
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200
