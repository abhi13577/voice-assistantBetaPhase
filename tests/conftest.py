"""
Pytest configuration and shared fixtures for test suite.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client():
    """Create async HTTP client for API testing."""
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_redis():
    """Create mocked Redis client."""
    redis_mock = MagicMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.exists.return_value = False
    
    return redis_mock


@pytest.fixture
def mock_llm_client():
    """Create mocked LLM client."""
    llm_mock = MagicMock()
    llm_mock.models.generate_content.return_value = MagicMock(
        text='{"intent": "greeting", "confidence": 0.95}'
    )
    
    return llm_mock


@pytest.fixture
def mock_settings():
    """Create mock settings object."""
    from app.core.settings import Settings
    
    return Settings(
        env="dev",
        debug=True,
        log_level="DEBUG",
        redis_host="localhost",
        redis_port=6379,
        confidence_threshold=0.65,
        rate_limit_enabled=False,
        circuit_breaker_enabled=True
    )


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    from app.core.structured_logging import Logger
    
    logger = Logger("test")
    logger.logger = MagicMock()
    
    return logger


@pytest.fixture
def sample_voice_request():
    """Sample voice request payload."""
    return {
        "user_id": 1,
        "transcript": "hello",
        "project_id": None
    }


@pytest.fixture
def sample_action_request():
    """Sample action request payload."""
    return {
        "user_id": 1,
        "action_type": "rerun_test",
        "params": {
            "test_case_id": "123"
        }
    }


@pytest.fixture
def sample_projects():
    """Sample project data."""
    return [
        {"id": 1, "name": "TestProject", "status": "active"},
        {"id": 2, "name": "ProductionTests", "status": "active"}
    ]


@pytest.fixture
def sample_runs():
    """Sample run data."""
    return [
        {"id": 101, "project_id": 1, "name": "Run 1", "status": "passed"},
        {"id": 102, "project_id": 1, "name": "Run 2", "status": "failed"},
        {"id": 103, "project_id": 2, "name": "Run 3", "status": "passed"}
    ]


@pytest.fixture(autouse=True)
def reset_singleton_services():
    """Reset singleton service instances between tests."""
    # This ensures tests don't interfere with each other
    # Import and reset service singletons
    import app.services.intent_engine_refactored as intent_mod
    import app.services.cache_service_refactored as cache_mod
    import app.services.response_builder_refactored as builder_mod
    
    intent_mod._intent_engine = None
    cache_mod._cache_service = None
    builder_mod._response_builder = None
    
    yield
    
    # Cleanup after test
    intent_mod._intent_engine = None
    cache_mod._cache_service = None
    builder_mod._response_builder = None


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
