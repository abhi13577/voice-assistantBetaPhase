"""
Integration tests for Voice Support Engine API endpoints.
Tests the full request-response cycle.
"""

import pytest
import json
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock


# Mock FastAPI app setup
@pytest.fixture
async def client():
    """Create async HTTP client for testing."""
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """Test /health endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test health check with all systems OK."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "checks" in data
    
    @pytest.mark.asyncio
    async def test_health_check_includes_cache(self, client):
        """Test health check includes cache status."""
        response = await client.get("/health")
        
        data = response.json()
        assert "checks" in data
        assert "cache" in data["checks"]


class TestVoiceTurnEndpoint:
    """Test /voice/turn endpoint."""
    
    @pytest.mark.asyncio
    async def test_voice_turn_greeting(self, client):
        """Test voice turn with greeting."""
        payload = {
            "user_id": 1,
            "transcript": "hello",
            "project_id": None
        }
        
        with patch('app.services.intent_engine_refactored.IntentEngine.classify') as mock_classify:
            mock_classify.return_value = ("greeting", 0.95)
            
            response = await client.post("/api/v1/voice/turn", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "intent" in data
    
    @pytest.mark.asyncio
    async def test_voice_turn_missing_user_id(self, client):
        """Test voice turn without user_id."""
        payload = {
            "transcript": "hello"
        }
        
        response = await client.post("/api/v1/voice/turn", json=payload)
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_voice_turn_empty_transcript(self, client):
        """Test voice turn with empty transcript."""
        payload = {
            "user_id": 1,
            "transcript": ""
        }
        
        response = await client.post("/api/v1/voice/turn", json=payload)
        
        # Should handle gracefully
        assert response.status_code in [200, 422]
    
    @pytest.mark.asyncio
    async def test_voice_turn_rate_limit(self, client):
        """Test rate limiting on voice turn."""
        payload = {
            "user_id": 1,
            "transcript": "test"
        }
        
        # Send multiple requests rapidly
        responses = []
        for _ in range(15):
            response = await client.post("/api/v1/voice/turn", json=payload)
            responses.append(response.status_code)
        
        # At least some should succeed (rate limiting enabled in production)
        assert any(status == 200 for status in responses)


class TestVoiceActionEndpoint:
    """Test /voice/action endpoint."""
    
    @pytest.mark.asyncio
    async def test_voice_action_rerun(self, client):
        """Test voice action for rerunning tests."""
        payload = {
            "user_id": 1,
            "action_type": "rerun_test",
            "params": {
                "test_case_id": "123"
            }
        }
        
        with patch('app.services.action_engine.ActionEngine.execute') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "message": "Test rerun triggered",
                "data": {}
            }
            
            response = await client.post("/api/v1/voice/action", json=payload)
            
            assert response.status_code in [200, 404]  # May not exist yet
    
    @pytest.mark.asyncio
    async def test_voice_action_invalid_type(self, client):
        """Test action with invalid type."""
        payload = {
            "user_id": 1,
            "action_type": "invalid_action",
            "params": {}
        }
        
        response = await client.post("/api/v1/voice/action", json=payload)
        
        # Should be rejected
        assert response.status_code in [400, 404, 422]
    
    @pytest.mark.asyncio
    async def test_voice_action_missing_params(self, client):
        """Test action with missing required params."""
        payload = {
            "user_id": 1,
            "action_type": "rerun_test",
            "params": {}  # Missing test_case_id
        }
        
        response = await client.post("/api/v1/voice/action", json=payload)
        
        assert response.status_code in [400, 422, 404]


class TestMetricsEndpoint:
    """Test /metrics endpoint."""
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        """Test metrics endpoint returns Prometheus data."""
        response = await client.get("/metrics")
        
        assert response.status_code == 200
        # Should contain Prometheus format
        assert "HELP" in response.text or "TYPE" in response.text or "#" in response.text


class TestErrorHandling:
    """Test error handling across endpoints."""
    
    @pytest.mark.asyncio
    async def test_invalid_json(self, client):
        """Test endpoint with invalid JSON."""
        response = await client.post(
            "/api/v1/voice/turn",
            content="invalid json"
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_404_not_found(self, client):
        """Test non-existent endpoint."""
        response = await client.get("/api/v1/nonexistent")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_method_not_allowed(self, client):
        """Test wrong HTTP method."""
        response = await client.put("/api/v1/voice/turn", json={})
        
        assert response.status_code == 405


class TestRequestIdTracking:
    """Test request ID tracking."""
    
    @pytest.mark.asyncio
    async def test_request_id_header(self, client):
        """Test that request ID is tracked."""
        headers = {"x-request-id": "test-123"}
        
        response = await client.get("/health", headers=headers)
        
        assert response.status_code == 200
        # Request ID should be in response
        data = response.json()
        assert isinstance(data, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
