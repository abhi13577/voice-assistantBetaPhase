"""
Production-grade voice input with comprehensive error handling.
"""

import streamlit as st
import speech_recognition as sr
import logging

logger = logging.getLogger(__name__)


def record_voice():
    """
    Record audio from microphone and transcribe it.
    Returns transcribed text or None if recording fails.
    """
    
    try:
        recognizer = sr.Recognizer()
        
        try:
            with sr.Microphone() as source:
                st.info("🎵 Listening...")
                logger.info("[VOICE] Microphone activated, listening for speech...")
                
                # Adjust for ambient noise
                try:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    logger.debug("[VOICE] Ambient noise adjustment complete")
                except Exception as noise_error:
                    logger.warning(f"[VOICE] Could not adjust for ambient noise: {noise_error}")
                
                # Record audio with timeout
                try:
                    audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
                    logger.info("[VOICE] Audio capture complete")
                except sr.UnknownValueError:
                    st.error("❌ No speech detected. Please try again.")
                    logger.warning("[VOICE] No speech detected in audio")
                    return None
                except sr.RequestError as req_error:
                    st.error(f"❌ Audio capture failed: {req_error}")
                    logger.error(f"[VOICE] Microphone error: {req_error}")
                    return None
                except Exception as audio_error:
                    st.error(f"❌ Unexpected audio error: {audio_error}")
                    logger.error(f"[VOICE] Unexpected audio error: {type(audio_error).__name__}: {audio_error}")
                    return None
        
        except sr.MicrophoneError as mic_error:
            st.error(f"❌ Microphone not found or not accessible: {mic_error}")
            logger.error(f"[VOICE] Microphone error: {mic_error}")
            return None
        except Exception as mic_setup_error:
            st.error(f"❌ Could not access microphone: {mic_setup_error}")
            logger.error(f"[VOICE] Failed to initialize microphone: {type(mic_setup_error).__name__}: {mic_setup_error}")
            return None
        
        # Transcribe audio
        try:
            st.info("🔄 Transcribing...")
            logger.info("[VOICE] Starting speech-to-text transcription...")
            
            try:
                text = recognizer.recognize_google(audio)
                logger.info(f"[VOICE] Transcription successful: {text[:100]}")
                st.success(f"✓ You said: {text}")
                return text
                
            except sr.UnknownValueError:
                st.error("❌ Speech not recognized. Please try again or rephrase.")
                logger.warning("[VOICE] Could not understand the speech")
                return None
                
            except sr.RequestError as api_error:
                st.error(f"❌ Google API error. Check your internet: {api_error}")
                logger.error(f"[VOICE] Google API error: {api_error}")
                return None
                
            except Exception as transcribe_error:
                st.error(f"❌ Transcription failed: {transcribe_error}")
                logger.error(f"[VOICE] Transcription error: {type(transcribe_error).__name__}: {transcribe_error}")
                return None
        
        except Exception as transcribe_setup_error:
            st.error(f"❌ Could not start transcription: {transcribe_setup_error}")
            logger.error(f"[VOICE] Failed to start transcription: {transcribe_setup_error}")
            return None
    
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")
        logger.error(f"[VOICE] Unexpected error: {type(e).__name__}: {e}")
        return None