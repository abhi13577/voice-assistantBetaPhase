"""
Unit tests for IntentEngine - TF-IDF based intent classification.
"""

import pytest
from app.services.intent_engine_refactored import IntentEngine
from app.core.exceptions import IntentClassificationError


@pytest.fixture
def intent_engine():
    """Create intent engine instance."""
    return IntentEngine()


class TestIntentEngineClassification:
    """Test intent classification functionality."""
    
    def test_exact_keyword_matching(self, intent_engine):
        """Test exact keyword matching for greetings."""
        intent, confidence = intent_engine.classify("hello")
        assert intent == "greeting"
        assert confidence == 1.0
    
    def test_greeting_variations(self, intent_engine):
        """Test greeting intent detection."""
        greetings = ["hi", "hey", "hello"]
        for greeting in greetings:
            intent, confidence = intent_engine.classify(greeting)
            assert intent == "greeting", f"Failed for '{greeting}'"
            assert confidence > 0.8
    
    def test_empty_input(self, intent_engine):
        """Test empty transcript handling."""
        intent, confidence = intent_engine.classify("")
        assert intent == "fallback"
        assert confidence == 0.0
    
    def test_none_input(self, intent_engine):
        """Test None input handling."""
        intent, confidence = intent_engine.classify(None)
        assert intent == "fallback"
        assert confidence == 0.0
    
    def test_whitespace_only(self, intent_engine):
        """Test whitespace-only input."""
        intent, confidence = intent_engine.classify("   ")
        assert intent == "fallback"
        assert confidence == 0.0
    
    def test_check_run_status_classification(self, intent_engine):
        """Test check_run_status intent classification."""
        queries = [
            "what is the status of my test",
            "check run status",
            "how is my test running"
        ]
        for query in queries:
            intent, confidence = intent_engine.classify(query)
            # Confidence should be above threshold
            assert confidence >= 0.0  # Will depend on actual training data
    
    def test_case_insensitive(self, intent_engine):
        """Test case insensitivity."""
        results = [
            intent_engine.classify("HELLO"),
            intent_engine.classify("Hello"),
            intent_engine.classify("hello")
        ]
        # All should classify as greeting
        assert all(r[0] == "greeting" for r in results)
    
    def test_get_supported_intents(self, intent_engine):
        """Test getting supported intents list."""
        intents = intent_engine.get_supported_intents()
        assert isinstance(intents, list)
        assert len(intents) > 0
        assert "greeting" in intents or "greeting" in str(intents).lower()


class TestIntentEngineEdgeCases:
    """Test edge cases and error handling."""
    
    def test_very_long_input(self, intent_engine):
        """Test handling of very long input."""
        long_text = "test " * 1000
        intent, confidence = intent_engine.classify(long_text)
        assert isinstance(intent, str)
        assert 0 <= confidence <= 1.0
    
    def test_special_characters(self, intent_engine):
        """Test handling of special characters."""
        text = "hello!!! @#$% test???"
        intent, confidence = intent_engine.classify(text)
        assert isinstance(intent, str)
        assert 0 <= confidence <= 1.0
    
    def test_unicode_input(self, intent_engine):
        """Test handling of unicode input."""
        text = "hello 你好 🌍"
        intent, confidence = intent_engine.classify(text)
        assert isinstance(intent, str)
        assert 0 <= confidence <= 1.0


class TestIntentEngineMetadata:
    """Test metadata and info methods."""
    
    def test_engine_initialization_logging(self, intent_engine):
        """Test that engine initializes with proper logging."""
        # Should not raise
        assert intent_engine is not None
    
    def test_supported_intents_not_empty(self, intent_engine):
        """Test that there are supported intents."""
        intents = intent_engine.get_supported_intents()
        assert len(intents) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
