"""
Configuration for Modular Agent

Handles all environment-based configuration for the modular voice agent pipeline.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Audio Configuration
# =============================================================================

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30

# =============================================================================
# VAD Configuration
# =============================================================================

# How long silence must persist to trigger end of speech
SILENCE_DURATION_MS = int(os.getenv("SILENCE_DURATION_MS", "300"))

# Minimum speech duration to be considered valid (filters noise)
# Lower values allow shorter utterances like "Hello?" or "Yes"
MIN_SPEECH_DURATION_MS = int(os.getenv("MIN_SPEECH_DURATION_MS", "200"))

# Silero VAD threshold (0.0-1.0). Higher = less sensitive to noise
SILERO_THRESHOLD = float(os.getenv("SILERO_THRESHOLD", "0.75"))

# Pre-buffer duration in ms to capture speech start that VAD may miss
VAD_PRE_BUFFER_MS = int(os.getenv("VAD_PRE_BUFFER_MS", "300"))

# =============================================================================
# Interruption Configuration
# =============================================================================

# How long user must speak to trigger interruption (in ms)
# Higher values prevent false interrupts from TTS echo/feedback
INTERRUPTION_DURATION_MS = int(os.getenv("INTERRUPTION_DURATION_MS", "600"))

# Threshold converted to frames (each frame is FRAME_DURATION_MS)
INTERRUPTION_THRESHOLD = INTERRUPTION_DURATION_MS // FRAME_DURATION_MS

# Voice energy threshold for interruption detection (RMS value, 0.0-1.0)
# Note: RMS is legacy, VAD probability is now used for more reliable detection
INTERRUPTION_VOICE_THRESHOLD = float(os.getenv("INTERRUPTION_VOICE_THRESHOLD", "0.02"))

# VAD probability threshold for interrupt detection (0.0-1.0)
# Higher than normal VAD threshold to avoid triggering on TTS echo
# Default 0.7 means 70% probability of speech triggers interrupt counting
INTERRUPTION_VAD_THRESHOLD = float(os.getenv("INTERRUPTION_VAD_THRESHOLD", "0.7"))

# =============================================================================
# STT Configuration
# =============================================================================

# STT Provider: "groq_whisper", "google_chirp", or "deepgram"
STT_PROVIDER = os.getenv("STT_PROVIDER", "deepgram")

# Force language for STT (e.g., "en", "hi", "es"). None for auto-detect
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "hi")

# Google Cloud STT region (Chirp 3 requires regional endpoint)
GOOGLE_STT_REGION = os.getenv("GOOGLE_STT_REGION", "us")

# Google credentials path
GOOGLE_STT_APPLICATION_CREDENTIALS = os.getenv(
    "GOOGLE_STT_APPLICATION_CREDENTIALS",
    "stt-client.json"
)

# =============================================================================
# TTS Configuration
# =============================================================================

# TTS Provider: "gemini" or "google_chirp"
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "google_chirp")

# Gemini TTS settings
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Kore")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Google TTS settings
GOOGLE_TTS_VOICE = os.getenv("GOOGLE_TTS_VOICE", "Kore")
GOOGLE_TTS_LANGUAGE = os.getenv("GOOGLE_TTS_LANGUAGE", "hi-IN")

# Google Chirp 3 HD TTS advanced settings
# Speaking rate: 0.25 (very slow) to 2.0 (very fast), 1.0 is normal speed
GOOGLE_TTS_SPEAKING_RATE = float(os.getenv("GOOGLE_TTS_SPEAKING_RATE", "1.0"))

# =============================================================================
# LLM Configuration
# =============================================================================

# LLM model for chat completions
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.5"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# =============================================================================
# API Keys
# =============================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# =============================================================================
# Logging
# =============================================================================

# Directory for session logs
LOG_DIR = os.getenv("MODULAR_LOG_DIR", "modular_logs")

# Enable/disable verbose logging for components
VERBOSE_VAD = os.getenv("VERBOSE_VAD", "true").lower() == "true"
VERBOSE_STT = os.getenv("VERBOSE_STT", "true").lower() == "true"
VERBOSE_TTS = os.getenv("VERBOSE_TTS", "true").lower() == "true"
VERBOSE_LLM = os.getenv("VERBOSE_LLM", "true").lower() == "true"


# =============================================================================
# Centralized Logger
# =============================================================================

from datetime import datetime
from typing import Optional


def get_timestamp() -> str:
    """Get current timestamp in HH:MM:SS.mmm format."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(
    component: str,
    message: str,
    level: str = "INFO",
    timestamp: bool = True
) -> None:
    """
    Centralized logging function for consistent output across all modules.

    Args:
        component: Component name (e.g., "VAD", "STT-DEEPGRAM", "TTS-CHIRP", "LLM")
        message: Log message
        level: Log level (INFO, WARNING, ERROR, DEBUG)
        timestamp: Whether to include timestamp prefix
    """
    if timestamp:
        ts = get_timestamp()
        print(f"[{ts}] [{component}] [{level}] {message}", flush=True)
    else:
        print(f"[{component}] {message}", flush=True)