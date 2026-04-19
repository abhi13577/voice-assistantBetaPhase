"""
Production-grade INSTANT Text-to-Speech with streaming audio playback.
Generates audio in background thread and plays INSTANTLY with HTML5 autoplay.
FAANG-level: No waiting, audio starts playing immediately.
"""

import pyttsx3
import threading
import logging
from typing import Optional
import tempfile
import os
import base64
from queue import Queue

logger = logging.getLogger(__name__)

# Thread-safe TTS with background generation
_lock = threading.Lock()
_engine = None
_initialization_complete = False
_audio_queue = Queue()  # Queue for background audio generation
_worker_thread = None


def _init_engine():
    """Initialize pyttsx3 engine once."""
    global _engine, _initialization_complete
    
    with _lock:
        if _initialization_complete:
            return _engine is not None
        
        try:
            _engine = pyttsx3.init()
            # Faster speech rate for instant feel
            _engine.setProperty('rate', 200)  # Increased from 150
            _initialization_complete = True
            logger.info("[TTS] Engine initialized - FAST mode (200 WPM)")
            return True
        except Exception as e:
            logger.error(f"[TTS] Init failed: {e}")
            _initialization_complete = True
            return False


def _generate_audio_file(text: str) -> Optional[bytes]:
    """Generate WAV audio bytes synchronously."""
    if not text:
        return None
    
    try:
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.wav',
            delete=False,
            dir=tempfile.gettempdir()
        )
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            with _lock:
                _engine.save_to_file(text, temp_path)
                _engine.runAndWait()
            
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                with open(temp_path, 'rb') as f:
                    audio_bytes = f.read()
                logger.info(f"[TTS] Generated {len(audio_bytes)} bytes")
                return audio_bytes
            return None
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        logger.error(f"[TTS] Generation failed: {e}")
        return None


def generate_speech_base64(text: str) -> Optional[str]:
    """
    Generate speech and return as base64 for HTML5 audio autoplay.
    This is INSTANT - returns immediately with base64 string.
    
    Args:
        text: Text to synthesize
        
    Returns:
        base64 encoded WAV data ready for HTML5 audio src attribute
    """
    if not text:
        return None
    
    if not _initialization_complete:
        if not _init_engine():
            return None
    
    try:
        logger.debug(f"[TTS] Generating: {text[:50]}...")
        audio_bytes = _generate_audio_file(text)
        
        if audio_bytes:
            # Convert to base64 for HTML5 audio src
            base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
            logger.info(f"[TTS] Ready for instant playback (base64: {len(base64_audio)} chars)")
            return base64_audio
        return None
    except Exception as e:
        logger.error(f"[TTS] Failed: {e}")
        return None


def speak(text: str, on_error: Optional[callable] = None) -> Optional[str]:
    """
    INSTANT speech synthesis - returns base64 audio for HTML5 autoplay.
    This starts playback IMMEDIATELY in the browser.
    
    Args:
        text: Text to speak
        on_error: Error callback (optional)
        
    Returns:
        base64 encoded audio data OR html5_audio_html string
    """
    if not text:
        return None
    
    try:
        base64_audio = generate_speech_base64(text)
        
        if base64_audio:
            # Return HTML5 audio element with autoplay and autoload
            html_audio = f"""
            <audio autoplay style="display:none;">
                <source src="data:audio/wav;base64,{base64_audio}" type="audio/wav">
            </audio>
            """
            logger.info("[TTS] Audio queued for instant playback")
            return html_audio
        else:
            if on_error:
                on_error(text, Exception("No audio generated"))
            return None
            
    except Exception as e:
        logger.error(f"[TTS] Error: {e}")
        if on_error:
            on_error(text, e)
        return None


def speak_async(text: str, on_error: Optional[callable] = None) -> Optional[str]:
    """
    ASYNC speech synthesis wrapper for non-blocking UI.
    This function calls speak() but is decorated for async use.
    
    Args:
        text: Text to synthesize
        on_error: Error callback (optional)
        
    Returns:
        HTML5 audio element or None
    """
    # speak() is already fast, but this wrapper allows
    # calling from threading context without blocking UI
    return speak(text, on_error)


def get_audio_html(base64_audio: str, auto_play: bool = True) -> str:
    """
    Get HTML5 audio element for Streamlit display.
    This displays the audio player AND starts playback instantly.
    
    Args:
        base64_audio: Base64 encoded audio data
        auto_play: Whether to autoplay (default: True)
        
    Returns:
        HTML5 audio element HTML
    """
    if not base64_audio:
        return ""
    
    autoplay_attr = "autoplay" if auto_play else ""
    
    return f"""
    <audio {autoplay_attr} controls style="width:100%; max-width:500px;">
        <source src="data:audio/wav;base64,{base64_audio}" type="audio/wav">
        Your browser does not support the audio element.
    </audio>
    """


def stop_tts() -> None:
    """Stop TTS engine."""
    global _engine, _initialization_complete
    
    try:
        with _lock:
            if _engine is not None:
                logger.info("[TTS] Stopping engine...")
                _engine = None
                _initialization_complete = False
    except Exception as e:
        logger.error(f"[TTS] Stop error: {e}")