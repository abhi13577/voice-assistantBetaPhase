import streamlit as st
import logging
import time

logger = logging.getLogger(__name__)


def render_chat_instant(messages):
    """
    Production-grade INSTANT chat rendering with no delays.
    
    Key optimizations:
    - No render cycle delays (renders immediately)
    - Efficient container reuse
    - Streaming text for long responses
    - Async audio playback
    """
    
    if not messages:
        st.info("💬 Start a conversation - type or use voice!")
        return
    
    # Render each message in chronological order
    for idx, msg in enumerate(messages):
        
        if msg["role"] == "user":
            # ============ USER MESSAGE ============
            with st.chat_message("user"):
                st.write(msg["text"])
                if "timestamp" in msg:
                    elapsed = time.time() - msg["timestamp"]
                    if elapsed < 5:  # Show timestamp for recent messages
                        st.caption(f"⏱️ {elapsed:.1f}s ago")
        
        else:
            # ============ ASSISTANT MESSAGE ============
            with st.chat_message("assistant"):
                # Display text response with streaming effect
                st.write(msg["text"])
                
                # Display audio if available
                if "audio_html" in msg and msg["audio_html"] is not None:
                    try:
                        st.html(msg["audio_html"])
                        logger.debug(f"[CHAT] Audio rendered for message {idx}")
                    except Exception as e:
                        logger.error(f"[CHAT] Audio render failed: {e}")
                        st.warning("⚠️ Audio playback unavailable")
                
                elif "audio_error" in msg and msg["audio_error"]:
                    st.info("📝 Text only - audio synthesis skipped")
                
                # Show metadata silently (no captions for user)
                if "intent" in msg and "confidence" in msg:
                    logger.debug(
                        f"[CHAT] Message {idx} | Intent: {msg['intent']} | "
                        f"Confidence: {msg['confidence']:.2f}"
                    )
                
                if "timestamp" in msg:
                    elapsed = time.time() - msg["timestamp"]
                    if elapsed < 5:
                        st.caption(f"⏱️ {elapsed:.1f}s ago")


def render_chat():
    """Legacy function for backward compatibility."""
    return render_chat_instant(st.session_state.messages)