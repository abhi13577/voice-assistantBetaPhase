"""
Unit tests for ResponseBuilder - Response generation and formatting.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.response_builder_refactored import ResponseBuilder
from app.core.exceptions import ValidationError


@pytest.fixture
def response_builder():
    """Create response builder instance."""
    return ResponseBuilder()


class TestResponseBuilderGreeting:
    """Test greeting intent response."""
    
    @pytest.mark.asyncio
    async def test_greeting_response(self, response_builder):
        """Test greeting response generation."""
        response, actions, followups = await response_builder.build(
            intent="greeting",
            user_id=1,
            transcript="hello"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert "hello" in response.lower() or "help" in response.lower()
        assert isinstance(actions, list)
        assert isinstance(followups, list)
    
    @pytest.mark.asyncio
    async def test_greeting_has_suggestions(self, response_builder):
        """Test that greeting includes suggestions."""
        response, actions, followups = await response_builder.build(
            intent="greeting",
            user_id=1,
            transcript="hi"
        )
        
        # Should include suggested actions
        assert len(actions) > 0 or len(followups) > 0


class TestResponseBuilderHelp:
    """Test help intent response."""
    
    @pytest.mark.asyncio
    async def test_help_response(self, response_builder):
        """Test help response generation."""
        response, actions, followups = await response_builder.build(
            intent="help",
            user_id=1,
            transcript="help"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0


class TestResponseBuilderValidation:
    """Test input validation."""
    
    @pytest.mark.asyncio
    async def test_missing_intent(self, response_builder):
        """Test response with missing intent."""
        response, _, _ = await response_builder.build(
            intent="",
            user_id=1,
            transcript="test"
        )
        
        # Should return error response
        assert "error" in response.lower() or response == ""
    
    @pytest.mark.asyncio
    async def test_invalid_user_id(self, response_builder):
        """Test response with invalid user ID."""
        response, _, _ = await response_builder.build(
            intent="greeting",
            user_id=0,
            transcript="test"
        )
        
        # Should handle gracefully
        assert isinstance(response, str)
    
    @pytest.mark.asyncio
    async def test_negative_user_id(self, response_builder):
        """Test response with negative user ID."""
        response, _, _ = await response_builder.build(
            intent="greeting",
            user_id=-1,
            transcript="test"
        )
        
        # Should handle gracefully
        assert isinstance(response, str)


class TestResponseBuilderSlots:
    """Test slot resolution."""
    
    @pytest.mark.asyncio
    async def test_build_with_llm_slots(self, response_builder):
        """Test response building with LLM-extracted slots."""
        llm_slots = {
            "project": "test_project",
            "run_id": "123"
        }
        
        response, actions, followups = await response_builder.build(
            intent="check_run_status",
            user_id=1,
            transcript="check status of my test",
            llm_slots=llm_slots
        )
        
        assert isinstance(response, str)


class TestResponseBuilderProjectResolution:
    """Test project name resolution."""
    
    def test_resolve_project_id_found(self, response_builder):
        """Test resolving existing project."""
        projects = [
            {"id": 1, "name": "TestProject"},
            {"id": 2, "name": "ProductionTests"}
        ]
        
        project_id = response_builder._resolve_project_id("TestProject", projects)
        
        assert project_id == 1
    
    def test_resolve_project_id_case_insensitive(self, response_builder):
        """Test case-insensitive project resolution."""
        projects = [
            {"id": 1, "name": "TestProject"}
        ]
        
        project_id = response_builder._resolve_project_id("testproject", projects)
        
        assert project_id == 1
    
    def test_resolve_project_id_not_found(self, response_builder):
        """Test project not found."""
        projects = [
            {"id": 1, "name": "TestProject"}
        ]
        
        project_id = response_builder._resolve_project_id("NonExistent", projects)
        
        assert project_id is None
    
    def test_resolve_project_id_empty_list(self, response_builder):
        """Test with empty project list."""
        project_id = response_builder._resolve_project_id("TestProject", [])
        
        assert project_id is None


class TestResponseBuilderTemplates:
    """Test response templates."""
    
    def test_templates_exist(self, response_builder):
        """Test that templates are defined."""
        assert len(response_builder.TEMPLATES) > 0
    
    def test_error_template_exists(self, response_builder):
        """Test that error template exists."""
        assert "error" in response_builder.TEMPLATES
        assert len(response_builder.TEMPLATES["error"]) > 0
    
    def test_greeting_template_exists(self, response_builder):
        """Test that greeting template exists."""
        assert "greeting" in response_builder.TEMPLATES


class TestResponseBuilderErrorHandling:
    """Test error handling in response building."""
    
    @pytest.mark.asyncio
    async def test_unknown_intent(self, response_builder):
        """Test handling of unknown intent."""
        response, actions, followups = await response_builder.build(
            intent="unknown_intent",
            user_id=1,
            transcript="test"
        )
        
        # Should return error or fallback
        assert isinstance(response, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
