"""
VAD Handler

Silero VAD-based voice activity detection with pre-buffering support.
"""

from typing import Tuple, Optional
import time

import torch
import numpy as np

from app.agent.modular.config import (
    SAMPLE_RATE,
    FRAME_DURATION_MS,
    SILENCE_DURATION_MS,
    MIN_SPEECH_DURATION_MS,
    SILERO_THRESHOLD,
    VAD_PRE_BUFFER_MS,
    VERBOSE_VAD,
    log,
)


# Global model cache
_silero_model = None
_silero_utils = None


def get_silero_vad():
    """
    Load and cache the Silero VAD model.

    Returns:
        Tuple of (model, utils) from Silero VAD
    """
    global _silero_model, _silero_utils

    if _silero_model is None:
        log("VAD", "Loading Silero VAD model...")
        _silero_model, _silero_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        log("VAD", "Silero VAD model loaded")
        log("VAD", f"Config: threshold={SILERO_THRESHOLD}, min_speech={MIN_SPEECH_DURATION_MS}ms, "
              f"silence_trigger={SILENCE_DURATION_MS}ms, pre_buffer={VAD_PRE_BUFFER_MS}ms")

    return _silero_model, _silero_utils


class VADHandler:
    """
    Silero VAD-based voice activity detection.

    Features:
    - Configurable speech probability threshold
    - Pre-buffer to capture speech onset that VAD may miss
    - Minimum speech duration filtering to reject noise
    - Configurable silence duration for end-of-speech detection
    - Hangover mechanism to prevent premature cutoff during brief pauses
    """

    def __init__(self, threshold: float = SILERO_THRESHOLD):
        """
        Initialize the VAD handler.

        Args:
            threshold: Speech probability threshold (0.0-1.0).
                       Higher values = less sensitive to noise.
        """
        self.model, self.utils = get_silero_vad()
        self.threshold = threshold
        self.sample_rate = SAMPLE_RATE

        # Silero requires exactly 512 samples per inference
        self.silero_samples_required = 512
        self.silero_bytes_required = self.silero_samples_required * 2  # 16-bit audio

        # Frame accumulator for Silero's sliding window
        self.frame_accumulator = bytearray()

        # Pre-buffer configuration
        self.pre_buffer_ms = VAD_PRE_BUFFER_MS
        self.pre_buffer_frames = self.pre_buffer_ms // FRAME_DURATION_MS
        self.pre_buffer = []

        # Silence duration required to trigger end of speech
        self.silence_duration_ms = SILENCE_DURATION_MS
        self.min_speech_duration_ms = MIN_SPEECH_DURATION_MS

        # State
        self.reset()

    def reset(self):
        """Reset all state for a new utterance."""
        self.audio_buffer = bytearray()
        self.frame_accumulator = bytearray()  # Critical: reset Silero's sliding window
        self.silence_frames = 0
        self.speech_frames = 0
        self.speech_detected = False
        self.last_is_speech = False
        self.pre_buffer = []
        self.speech_start_time = None
        self._last_speech_prob = 0.0  # Reset cached probability
        self.model.reset_states()

    def _get_speech_probability(self, frame_bytes: bytes) -> float:
        """
        Get speech probability for an audio frame.

        Uses a sliding window approach to accumulate enough samples
        for Silero's 512-sample requirement.

        Args:
            frame_bytes: Raw PCM audio bytes (16-bit, mono)

        Returns:
            Speech probability between 0.0 and 1.0
        """
        self.frame_accumulator.extend(frame_bytes)

        if len(self.frame_accumulator) < self.silero_bytes_required:
            return getattr(self, '_last_speech_prob', 0.0)

        # Extract window for Silero
        window_bytes = bytes(self.frame_accumulator[:self.silero_bytes_required])

        # Slide the window by removing the current frame's worth of bytes
        bytes_to_remove = len(frame_bytes)
        self.frame_accumulator = self.frame_accumulator[bytes_to_remove:]

        # Convert to float32 tensor
        audio_int16 = np.frombuffer(window_bytes, dtype=np.int16)
        if len(audio_int16) != self.silero_samples_required:
            return getattr(self, '_last_speech_prob', 0.0)

        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(audio_float32)

        # Run inference
        speech_prob = self.model(audio_tensor, self.sample_rate).item()
        self._last_speech_prob = speech_prob

        return speech_prob

    def process_frame(self, frame_bytes: bytes) -> Tuple[bool, Optional[bytes], bool, bool]:
        """
        Process an audio frame and detect speech boundaries.

        Args:
            frame_bytes: Raw PCM audio bytes for one frame

        Returns:
            Tuple of:
            - should_transcribe: True if a complete utterance is ready
            - audio_data: The complete utterance audio (or None)
            - state_changed: True if speech state just changed
            - is_speech: Current frame is speech
        """
        speech_prob = self._get_speech_probability(frame_bytes)
        is_speech = speech_prob >= self.threshold

        state_changed = is_speech != self.last_is_speech
        self.last_is_speech = is_speech

        if is_speech:
            if not self.speech_detected:
                # Speech just started - prepend pre-buffer to capture onset
                self.speech_start_time = time.time()
                log("VAD", f"Voice detected (prob: {speech_prob:.3f}), "
                    f"prepending {len(self.pre_buffer)} frames "
                    f"({len(self.pre_buffer) * FRAME_DURATION_MS}ms) from pre-buffer",
                    timestamp=False)
                for buffered_frame in self.pre_buffer:
                    self.audio_buffer.extend(buffered_frame)
                self.pre_buffer = []

            self.speech_detected = True
            self.silence_frames = 0  # Reset silence counter when speech detected
            self.speech_frames += 1
            self.audio_buffer.extend(frame_bytes)

        elif self.speech_detected:
            # In speech mode but current frame is silence
            self.silence_frames += 1
            self.audio_buffer.extend(frame_bytes)  # Keep buffering during silence

            silence_duration = self.silence_frames * FRAME_DURATION_MS
            # Calculate actual speech duration from start time, not just high-probability frames
            # This accounts for natural pauses, breathing, and softer sounds within the utterance
            speech_duration = int((time.time() - self.speech_start_time) * 1000) if self.speech_start_time else 0

            # Check if enough silence to trigger end of speech
            if silence_duration >= self.silence_duration_ms:
                if speech_duration >= self.min_speech_duration_ms:
                    log("VAD", f"Complete: {speech_duration}ms speech + {silence_duration}ms silence",
                        timestamp=False)
                    audio_data = bytes(self.audio_buffer)
                    self.reset()
                    return True, audio_data, state_changed, is_speech
                else:
                    log("VAD", f"Too short: {speech_duration}ms < {self.min_speech_duration_ms}ms",
                        timestamp=False)
                    self.reset()
                    return False, None, state_changed, is_speech
        else:
            # No speech detected yet - maintain rolling pre-buffer
            self.pre_buffer.append(frame_bytes)
            if len(self.pre_buffer) > self.pre_buffer_frames:
                self.pre_buffer.pop(0)

        return False, None, state_changed, is_speech

    def get_status(self) -> dict:
        """Get current VAD status for debugging."""
        speech_ms = int((time.time() - self.speech_start_time) * 1000) if self.speech_start_time else 0
        return {
            "speech_detected": self.speech_detected,
            "speech_frames": self.speech_frames,
            "speech_ms": speech_ms,
            "silence_frames": self.silence_frames,
            "silence_ms": self.silence_frames * FRAME_DURATION_MS,
            "buffer_size": len(self.audio_buffer),
            "pre_buffer_frames": len(self.pre_buffer),
        }

    def check_speech_probability(self, frame_bytes: bytes) -> float:
        """
        Check if a frame contains speech without updating internal state.

        Used for interrupt detection during TTS playback where we only
        need the speech probability, not full utterance boundary detection.

        Args:
            frame_bytes: Raw PCM audio bytes for one frame

        Returns:
            Speech probability between 0.0 and 1.0
        """
        # Silero requires exactly 512 samples, so we need to accumulate
        # Use a separate accumulator to avoid affecting the main state
        if not hasattr(self, '_interrupt_accumulator'):
            self._interrupt_accumulator = bytearray()

        self._interrupt_accumulator.extend(frame_bytes)

        if len(self._interrupt_accumulator) < self.silero_bytes_required:
            return getattr(self, '_last_interrupt_prob', 0.0)

        # Extract window for Silero
        window_bytes = bytes(self._interrupt_accumulator[:self.silero_bytes_required])

        # Slide the window
        bytes_to_remove = len(frame_bytes)
        self._interrupt_accumulator = self._interrupt_accumulator[bytes_to_remove:]

        # Convert to float32 tensor
        audio_int16 = np.frombuffer(window_bytes, dtype=np.int16)
        if len(audio_int16) != self.silero_samples_required:
            return getattr(self, '_last_interrupt_prob', 0.0)

        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(audio_float32)

        # Run inference
        speech_prob = self.model(audio_tensor, self.sample_rate).item()
        self._last_interrupt_prob = speech_prob

        return speech_prob

    def reset_interrupt_state(self):
        """Reset the interrupt detection state (separate from main VAD state)."""
        self._interrupt_accumulator = bytearray()
        self._last_interrupt_prob = 0.0
        self.model.reset_states()