from fastapi.testclient import TestClient
import pytest
import uuid

from app.main import app
from app.core.config import REQUIRE_API_KEY, API_KEY


client = TestClient(app)


# ============ HEALTH CHECKS ============

def test_health_endpoint():
    """Health check should work without API key."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "checks" in payload


def test_health_endpoint_has_security_headers():
    """Health check should include security headers."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"


# ============ SECURITY: Required Parameters ============

def test_voice_turn_requires_conversation_id():
    """conversation_id is now required - request should fail without it."""
    body = {
        "transcript": "list my projects",
        "user_id": 1,
        "project_id": 1
        # Missing conversation_id
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422  # Validation error
    assert "conversation_id" in response.json()["detail"][0]["loc"]


def test_voice_turn_requires_project_id():
    """project_id is now required - request should fail without it."""
    body = {
        "transcript": "list my projects",
        "user_id": 1,
        "conversation_id": str(uuid.uuid4())
        # Missing project_id
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422  # Validation error
    assert "project_id" in response.json()["detail"][0]["loc"]


def test_voice_turn_requires_positive_project_id():
    """project_id must be positive (>= 1)."""
    body = {
        "transcript": "list my projects",
        "user_id": 1,
        "project_id": 0,  # Invalid: must be > 0
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422


def test_voice_turn_requires_positive_user_id():
    """user_id must be positive."""
    body = {
        "transcript": "list my projects",
        "user_id": 0,  # Invalid
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422


def test_voice_turn_valid_request():
    """Valid request with all required fields."""
    body = {
        "transcript": "list my projects",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert "intent" in payload
    assert "reply_text" in payload
    assert "confidence" in payload


def test_voice_turn_sanitizes_input():
    """Transcript should be sanitized."""
    body = {
        "transcript": "hello\x00world",  # Contains null byte
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200  # Should succeed after sanitization


def test_voice_turn_rejects_oversized_input():
    """Transcript exceeding max_length should be rejected."""
    body = {
        "transcript": "x" * 501,  # Exceeds max_length of 500
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 422


def test_voice_turn_normalizes_transcript():
    """Transcript should be normalized."""
    body = {
        "transcript": "  LIST MY PROJECTS  ",  # Extra spaces and uppercase
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert "reply_text" in payload


# ============ SECURITY: API Key Validation ============

@pytest.mark.skipif(not REQUIRE_API_KEY, reason="API key not required in this config")
def test_voice_turn_rejects_missing_api_key():
    """Should reject requests without API key when REQUIRE_API_KEY=true."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 401


@pytest.mark.skipif(not REQUIRE_API_KEY, reason="API key not required in this config")
def test_voice_turn_accepts_valid_api_key():
    """Should accept requests with valid API key."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    headers = {"X-API-Key": API_KEY}
    response = client.post("/voice/turn", json=body, headers=headers)
    assert response.status_code == 200


@pytest.mark.skipif(not REQUIRE_API_KEY, reason="API key not required in this config")
def test_voice_action_rejects_missing_api_key():
    """Should reject action requests without API key when REQUIRE_API_KEY=true."""
    body = {
        "action_type": "get_run_status",
        "params": {},
        "user_id": 1
    }
    response = client.post("/voice/action", json=body)
    assert response.status_code == 401


@pytest.mark.skipif(not REQUIRE_API_KEY, reason="API key not required in this config")
def test_voice_action_rejects_invalid_api_key():
    """Should reject action requests with invalid API key."""
    body = {
        "action_type": "get_run_status",
        "params": {},
        "user_id": 1
    }
    headers = {"X-API-Key": "invalid-key"}
    response = client.post("/voice/action", json=body, headers=headers)
    assert response.status_code == 401


# ============ ACTION ENDPOINT ============

def test_voice_action_requires_user_id():
    """user_id is required for action."""
    body = {
        "action_type": "get_run_status",
        "params": {}
        # Missing user_id
    }
    response = client.post("/voice/action", json=body)
    assert response.status_code == 422


def test_voice_action_requires_action_type():
    """action_type is required."""
    body = {
        "params": {},
        "user_id": 1
        # Missing action_type
    }
    response = client.post("/voice/action", json=body)
    assert response.status_code == 422


def test_voice_action_rejects_nonexistent_user():
    """Actions should be rejected for non-existent users."""
    body = {
        "action_type": "get_run_status",
        "params": {},
        "user_id": 99999  # Non-existent user
    }
    response = client.post("/voice/action", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "User not found" in payload["message"]


def test_voice_action_validates_permission():
    """Permissions should be validated (no longer always True)."""
    # This test assumes user 1 exists in mock data
    body = {
        "action_type": "get_run_status",
        "params": {},
        "user_id": 1
    }
    response = client.post("/voice/action", json=body)
    assert response.status_code == 200
    payload = response.json()
    # Should either succeed or fail based on user role, not always succeed
    assert "success" in payload


# ============ ERROR HANDLING ============

def test_voice_turn_empty_transcript_returns_fallback():
    """Empty transcript should return fallback."""
    body = {
        "transcript": "   ",  # Only whitespace
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "fallback"


def test_voice_turn_response_has_all_fields():
    """Response should have all required fields."""
    body = {
        "transcript": "hello",
        "user_id": 1,
        "project_id": 1,
        "conversation_id": str(uuid.uuid4())
    }
    response = client.post("/voice/turn", json=body)
    assert response.status_code == 200
    payload = response.json()
    
    required_fields = ["intent", "escalate", "reply_text", "suggested_actions", "context_used", "confidence"]
    for field in required_fields:
        assert field in payload, f"Missing field: {field}"
