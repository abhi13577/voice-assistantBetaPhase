"""
Production-grade intent engine with better error handling.
"""

from typing import Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.core.base_service import Service
from app.core.exceptions import IntentClassificationError
from app.core.settings import get_settings
from app.services.intent_registry import INTENT_REGISTRY

settings = get_settings()


class IntentEngine(Service):
    """
    TF-IDF based intent classifier with LLM fallback.
    """
    
    def __init__(self):
        super().__init__()
        self.intent_names = []
        self.example_texts = []
        
        # Build training data from registry
        for intent, data in INTENT_REGISTRY.items():
            if "examples" not in data:
                self.logger.warning(f"Intent '{intent}' has no examples")
                continue
            
            for example in data["examples"]:
                self.intent_names.append(intent)
                self.example_texts.append(example)
        
        if not self.example_texts:
            raise IntentClassificationError("No intent examples found in registry")
        
        self.logger.info(f"Initialized intent engine with {len(self.example_texts)} examples")
        
        # TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=1000,
            min_df=1,
            max_df=0.9
        )
        
        try:
            self.example_vectors = self.vectorizer.fit_transform(self.example_texts)
            self.logger.info("TF-IDF vectorizer trained successfully")
        except Exception as e:
            raise IntentClassificationError(f"Failed to train vectorizer: {str(e)}")
        
        # System keywords for exact matching
        self.system_keywords = {
            "hello": "greeting",
            "hi": "greeting",
            "hey": "greeting",
            "help": "help",
            "thanks": "acknowledge",
            "ok": "acknowledge"
        }
    
    def classify(self, transcript: str) -> Tuple[str, float]:
        """
        Classify intent from transcript.
        Returns: (intent, confidence)
        """
        # Input validation
        if not transcript or not isinstance(transcript, str):
            self.logger.warning("Invalid transcript input")
            return "fallback", 0.0
        
        transcript_lower = transcript.strip().lower()
        
        if not transcript_lower:
            return "fallback", 0.0
        
        # Exact match on system keywords
        for keyword, intent in self.system_keywords.items():
            if transcript_lower == keyword:
                self.logger.debug(f"Exact keyword match: '{keyword}' -> {intent}")
                return intent, 1.0
        
        # TF-IDF classification
        try:
            transcript_vector = self.vectorizer.transform([transcript_lower])
            similarities = cosine_similarity(transcript_vector, self.example_vectors)[0]
            
            best_index = similarities.argmax()
            confidence = float(similarities[best_index])
            intent = self.intent_names[best_index]
            
            if confidence < settings.confidence_threshold:
                self.logger.debug(
                    f"Low confidence classification: {intent} ({confidence:.2%})"
                )
                return "fallback", confidence
            
            self.logger.debug(f"Classified: {intent} ({confidence:.2%})")
            return intent, confidence
        
        except Exception as e:
            self.logger.error(f"Classification error: {e}")
            raise IntentClassificationError(f"Failed to classify intent: {str(e)}")
    
    def get_supported_intents(self) -> list:
        """Get list of supported intents."""
        return list(set(self.intent_names))


# Singleton instance
_intent_engine: IntentEngine = None


def get_intent_engine() -> IntentEngine:
    """Get or create intent engine singleton."""
    global _intent_engine
    if _intent_engine is None:
        _intent_engine = IntentEngine()
    return _intent_engine
