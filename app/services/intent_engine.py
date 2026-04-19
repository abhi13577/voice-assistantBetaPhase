from typing import Tuple
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.services.intent_registry import INTENT_REGISTRY

CONFIDENCE_THRESHOLD = 0.4 
logger = logging.getLogger(__name__)

class IntentEngine:

    def __init__(self):
        self.intent_names = []
        self.example_texts = []

        for intent, data in INTENT_REGISTRY.items():
            for example in data["examples"]:
                self.intent_names.append(intent)
                self.example_texts.append(example)

        logger.info("Intent engine initialized with %s examples", len(self.example_texts))

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2)
        )

        self.example_vectors = self.vectorizer.fit_transform(self.example_texts)

        self.system_keywords = ["hello", "hi", "hey", "help"]

    def classify(self, transcript: str) -> Tuple[str, float]:

        if not transcript or not transcript.strip():
            return "fallback", 0.0

        transcript_lower = transcript.lower().strip()

        # ✅ strict greeting match
        if transcript_lower in self.system_keywords:
            return "greeting", 1.0

        transcript_vector = self.vectorizer.transform([transcript])
        similarities = cosine_similarity(transcript_vector, self.example_vectors)[0]

        best_index = similarities.argmax()
        best_score = similarities[best_index]
        best_intent = self.intent_names[best_index]

        # ✅ simple and stable decision
        if best_score < CONFIDENCE_THRESHOLD:
            return "fallback", float(best_score)

        return best_intent, float(min(best_score, 0.95))

intent_engine = IntentEngine()