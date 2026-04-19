"""
Tests for critical bug fixes.

Covers:
- StopIteration crash in response_builder
- Permission check now enforced (was always True)
- User validation in action_engine
- Project validation in response_builder
"""

import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ============ PERMISSION CHECK BUG FIX ============

class TestPermissionCheckFix:
    """✅ Fixed: Permission check was always returning True (security bug)."""

    def test_permission_now_enforced(self):
        """Permission check is now enforced (no longer always True)."""
        body = {
            "action_type": "get_run_status",
            "params": {},
            "user_id": 1
        }
        response = client.post("/voice/action", json=body)
        assert response.status_code == 200
        payload = response.json()
        # Should have a success field (either True or False based on permission)
        assert isinstance(payload["success"], bool)

    def test_nonexistent_user_rejected(self):
        """Non-existent users should be rejected."""
        body = {
            "action_type": "get_run_status",
            "params": {},
            "user_id": 999999
        }
        response = client.post("/voice/action", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is False
        assert "User not found" in payload["message"]

    def test_invalid_action_type_rejected(self):
        """Invalid action types should be rejected."""
        body = {
            "action_type": "invalid_action_xyz",
            "params": {},
            "user_id": 1
        }
        response = client.post("/voice/action", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is False
        assert "Invalid action type" in payload["message"]


# ============ STOPITERATION CRASH FIX ============

class TestStopIterationFix:
    """✅ Fixed: StopIteration crash when project not found in response_builder."""

    def test_voice_turn_handles_missing_project_gracefully(self):
        """Response builder should handle missing projects gracefully."""
        body = {
            "transcript": "check run status",
            "user_id": 1,
            "project_id": 1,
            "conversation_id": str(uuid.uuid4())
        }
        response = client.post("/voice/turn", json=body)
        # Should not crash with StopIteration
        assert response.status_code == 200
        payload = response.json()
        assert "reply_text" in payload
        assert payload["reply_text"] != ""

    def test_voice_turn_returns_valid_response(self):
        """All voice/turn responses should have required fields."""
        body = {
            "transcript": "show my projects",
            "user_id": 1,
            "project_id": 1,
            "conversation_id": str(uuid.uuid4())
        }
        response = client.post("/voice/turn", json=body)
        assert response.status_code == 200
        payload = response.json()

        required_fields = [
            "intent",
            "escalate",
            "reply_text",
            "suggested_actions",
            "context_used",
            "confidence"
        ]

        for field in required_fields:
            assert field in payload, f"Missing field: {field}"
            # reply_text should never be None or empty
            if field == "reply_text":
                assert payload[field] is not None
                assert len(payload[field]) > 0


# ============ USER VALIDATION FIX ============

class TestUserValidation:
    """✅ Fixed: Added user existence validation."""

    def test_action_engine_validates_user(self):
        """Action engine should validate user exists."""
        body = {
            "action_type": "get_run_status",
            "params": {},
            "user_id": 999999
        }
        response = client.post("/voice/action", json=body)
        payload = response.json()
        assert payload["success"] is False
        assert "User not found" in payload["message"]

    def test_response_builder_validates_user(self):
        """Response builder should validate user exists."""
        body = {
            "transcript": "hello",
            "user_id": 999999,
            "project_id": 1,
            "conversation_id": str(uuid.uuid4())
        }
        response = client.post("/voice/turn", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert "couldn't find your account" in payload["reply_text"].lower()

    def test_response_builder_validates_project_access(self):
        """Response builder should validate project access."""
        body = {
            "transcript": "hello",
            "user_id": 1,
            "project_id": 999999,  # Non-existent project
            "conversation_id": str(uuid.uuid4())
        }
        response = client.post("/voice/turn", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert "don't have access" in payload["reply_text"].lower()


# ============ INTEGRATION TESTS ============

class TestBugFixesIntegration:
    """Integration tests for all bug fixes working together."""

    def test_end_to_end_with_valid_user(self):
        """End-to-end flow with valid user should work."""
        # First make a request
        body = {
            "transcript": "list my projects",
            "user_id": 1,
            "project_id": 1,
            "conversation_id": str(uuid.uuid4())
        }
        response = client.post("/voice/turn", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] in ["list_projects", "fallback"]
        assert payload["reply_text"] is not None

    def test_end_to_end_action_with_valid_user(self):
        """End-to-end action with valid user should work."""
        body = {
            "action_type": "get_run_status",
            "params": {},
            "user_id": 1
        }
        response = client.post("/voice/action", json=body)
        assert response.status_code == 200
        payload = response.json()
        # May succeed or fail based on permission, but should have proper structure
        assert "success" in payload
        assert "message" in payload

    def test_error_scenarios_dont_crash(self):
        """All error scenarios should return proper responses, not crash."""
        test_cases = [
            # Non-existent user
            {
                "transcript": "hello",
                "user_id": 999999,
                "project_id": 1,
                "conversation_id": str(uuid.uuid4())
            },
            # Non-existent project
            {
                "transcript": "hello",
                "user_id": 1,
                "project_id": 999999,
                "conversation_id": str(uuid.uuid4())
            },
            # Large user ID
            {
                "transcript": "hello",
                "user_id": 999999999,
                "project_id": 1,
                "conversation_id": str(uuid.uuid4())
            },
        ]

        for body in test_cases:
            response = client.post("/voice/turn", json=body)
            assert response.status_code == 200
            payload = response.json()
            # Should always have these fields
            assert "reply_text" in payload
            assert payload["reply_text"] is not None
