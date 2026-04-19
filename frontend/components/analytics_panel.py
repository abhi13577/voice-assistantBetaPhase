import streamlit as st
import logging

logger = logging.getLogger(__name__)

def render_metrics(intent, confidence, latency):
    """
    Log metrics silently for monitoring/analytics.
    Do NOT display to end user (production-grade: metrics hidden from UI).
    """
    logger.info(f"[METRICS] intent={intent} | confidence={confidence:.3f} | latency_s={latency:.3f}")
    
    # Metrics silently tracked for internal monitoring
    # No UI display - user only sees text reply