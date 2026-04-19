import logging

logger = logging.getLogger(__name__)


def apply_guardrail(intent: str, confidence: float) -> str:
    logger.debug("Guardrail input intent=%s confidence=%.3f", intent, confidence)

    if not intent:
        logger.info("Guardrail fallback: empty intent")
        return "fallback"

    if confidence < 0.2:
        logger.info("Guardrail fallback: low confidence %.3f", confidence)
        return "fallback"

    logger.debug("Guardrail pass intent=%s", intent)
    return intent