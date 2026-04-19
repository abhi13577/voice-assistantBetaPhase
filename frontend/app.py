"""
Production-Grade FAANG-Level Streamlit Voice Support Interface

Architecture:
- Persistent input field (always visible, never disappears)
- Instant message rendering (no render cycle delays)
- Async TTS processing (non-blocking)
- Proper session state management
- Optimized performance metrics
- Enterprise error handling
"""

import streamlit as st
import logging
import time
import threading
from datetime import datetime

from state.session_manager import init_session
from components.chat_timeline import render_chat_instant
from components.voice_input import record_voice
from components.analytics_panel import render_metrics

from services.api_client import send_voice_turn
from services.text_to_speech import speak_async
from utils.error_handler import (
    error_handler,
    api_error_handler,
    user_feedback,
    perf_monitor
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ PAGE CONFIGURATION ============
st.set_page_config(
    page_title="Voice Support Console",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============ CSS STYLING ============
st.markdown("""
    <style>
        /* Clean chat message styling */
        .stChatMessage { 
            font-size: 16px;
            margin-bottom: 12px;
        }
        
        /* Input container always visible and accessible */
        .stChatInputContainer {
            position: sticky;
            bottom: 0;
            background: white;
            z-index: 999;
            padding: 10px 0;
            box-shadow: 0 -2px 4px rgba(0,0,0,0.1);
        }
        
        /* Make spinner less intrusive */
        .stSpinner > div { 
            font-size: 14px;
        }
        
        /* Clean title styling */
        h1 {
            color: #1f77b4;
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🎙️ Voice Support Assistant")

# ============ SESSION STATE INITIALIZATION ============
init_session()

# ============ PERSISTENT INPUT STATE ============
if "last_query" not in st.session_state:
    st.session_state.last_query = ""

if "query_processing" not in st.session_state:
    st.session_state.query_processing = False

# ============ MAIN LAYOUT ============
# Use columns for better layout control
main_col = st.container()

# ============ CHAT DISPLAY AREA ============
with main_col:
    st.subheader("💬 Conversation")
    
    # Display chat with proper spacing
    chat_area = st.container()
    with chat_area:
        render_chat_instant(st.session_state.messages)
        
        # Show processing indicator if needed
        if st.session_state.query_processing:
            with st.spinner("⏳ Processing your request..."):
                time.sleep(0.1)  # Brief pause for visual feedback

# ============ INPUT SECTION (ALWAYS VISIBLE) ============
st.divider()  # Visual separator

# Create two columns: voice input + text input
voice_col, text_col = st.columns([1, 4])

with voice_col:
    st.write("**Voice Input:**")
    if st.button("🎤 Speak", use_container_width=True, key="voice_btn"):
        try:
            logger.info("[INPUT] Voice button clicked")
            voice_text = error_handler.safe_execute(
                record_voice,
                error_message="Failed to process voice input",
                error_code="VOICE_INPUT_ERROR"
            )
            
            if voice_text:
                st.session_state.last_query = voice_text
                logger.info(f"[INPUT] Voice input captured: {voice_text[:50]}")
                st.rerun()
            
        except Exception as e:
            logger.error(f"[INPUT] Voice error: {e}")
            st.error(f"❌ Voice input failed: {e}")

with text_col:
    st.write("**Text Input:**")
    # ✅ CRITICAL FIX: Use stable key (not changing) so input field persists
    user_text = st.chat_input(
        "💬 Type your message or use voice...",
        key="persistent_chat_input"  # STABLE KEY - never changes!
    )

# ============ PROCESS INPUT (TEXT OR VOICE) ============
query = None

if user_text and user_text.strip():
    query = user_text
    logger.info(f"[INPUT] Text input: {query[:100]}")

elif st.session_state.last_query and not st.session_state.query_processing:
    query = st.session_state.last_query
    st.session_state.last_query = ""  # Clear for next voice input
    logger.info(f"[INPUT] Processing voice input: {query[:100]}")

# ============ HANDLE QUERY PROCESSING ============
if query and query.strip():
    st.session_state.query_processing = True
    logger.info(f"[PROCESS] Starting query processing: {query[:100]}")
    
    # Add user message immediately (instant UI feedback)
    st.session_state.messages.append({
        "role": "user",
        "text": query.strip(),
        "timestamp": time.time()
    })
    
    start_time = time.time()
    
    # ============ CALL BACKEND API ============
    try:
        logger.debug(f"[API] Calling backend...")
        
        response, latency = error_handler.safe_execute(
            send_voice_turn,
            query.strip(),
            st.session_state.conversation_id,
            error_message="Failed to reach backend service",
            error_code="API_ERROR"
        )
    except Exception as e:
        logger.error(f"[API] Unexpected error: {e}")
        response = None
        latency = 0
    
    duration_ms = (time.time() - start_time) * 1000
    
    # ============ HANDLE RESPONSE ============
    if response:
        try:
            # Extract and validate response
            reply = response.get("reply_text", "").strip()
            if not reply:
                reply = "I didn't understand that. Could you please rephrase?"
            
            intent = response.get("intent", "unknown")
            confidence = response.get("confidence", 0.0)
            
            logger.info(
                f"[RESPONSE] ✅ Success | Intent: {intent} | "
                f"Confidence: {confidence:.2f} | Latency: {latency:.3f}s"
            )
            
            # Log metrics
            perf_monitor.log_operation(
                "send_voice_turn",
                duration_ms,
                success=True,
                details=f"Latency: {latency}s"
            )
            api_error_handler.log_api_call(
                "POST", "/voice/turn", 200, latency * 1000, success=True
            )
            
            # Create polished assistant message
            assistant_message = {
                "role": "assistant",
                "text": reply,
                "audio_html": None,
                "audio_error": False,
                "intent": intent,
                "confidence": confidence,
                "timestamp": time.time()
            }
            
            # Add to messages
            st.session_state.messages.append(assistant_message)
            logger.debug(f"[STATE] Message added. Total: {len(st.session_state.messages)}")
            
            # ============ ASYNC TTS (Non-blocking) ============
            def synthesize_and_update():
                try:
                    logger.debug(f"[TTS] Generating audio...")
                    audio_html = speak_async(reply)
                    
                    if audio_html:
                        st.session_state.messages[-1]["audio_html"] = audio_html
                        logger.info("[TTS] ✅ Audio ready")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.session_state.messages[-1]["audio_error"] = True
                        logger.warning("[TTS] No audio generated")
                        
                except Exception as tts_error:
                    st.session_state.messages[-1]["audio_error"] = True
                    logger.error(f"[TTS] Failed: {tts_error}")
            
            # Start TTS in background (daemon thread)
            tts_thread = threading.Thread(target=synthesize_and_update, daemon=True)
            tts_thread.start()
            logger.debug("[TTS] Background thread started")
            
            # Display metrics
            try:
                st.session_state.latency = latency
                render_metrics(intent, confidence, latency)
            except Exception as e:
                logger.error(f"[METRICS] Failed: {e}")
            
        except KeyError as e:
            logger.error(f"[RESPONSE] Missing field: {e}")
            user_feedback.show_error("Backend response incomplete", f"Missing: {e}", "RESPONSE_ERROR")
        except Exception as e:
            logger.error(f"[RESPONSE] Processing error: {type(e).__name__}: {e}")
            user_feedback.show_error("Failed to process response", str(e), "RESPONSE_PARSING_ERROR")
    else:
        logger.error("[API] Backend unreachable")
        user_feedback.show_error(
            "Backend not responding",
            "AI service is temporarily unavailable. Please try again.",
            "BACKEND_UNREACHABLE"
        )
        perf_monitor.log_operation("send_voice_turn", duration_ms, success=False)
        api_error_handler.log_api_call("POST", "/voice/turn", 0, latency * 1000, success=False)
    
    # ✅ Processing complete
    st.session_state.query_processing = False
    
    # Ensure chat is still visible after processing
    with chat_area:
        st.empty()
        render_chat_instant(st.session_state.messages)

# ============ ALWAYS ENSURE INPUT IS VISIBLE ============
# This renders the input area at the bottom, always accessible
st.write("")  # Add spacing
