"""
VAD Handler

Silero VAD-based voice activity detection with pre-buffering support.
"""

from typing import Tuple, Optional, List
import time
import os

import torch
import numpy as np

from config import (
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
        utils = (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks)
    """
    global _silero_model, _silero_utils

    if _silero_model is None:
        log("VAD", "Loading Silero VAD model...")
        _silero_model, _silero_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            trust_repo=True
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
    - Audio file processing to remove silent parts (supports MP3, WAV, FLAC, etc.)
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

    def process_audio_file(self, input_path: str, output_path: str,
                          min_silence_len_ms: int = 300,
                          keep_silence_ms: int = 100) -> dict:
        """
        Process an audio file and remove silent parts.
        Supports MP3, WAV, FLAC, OGG and other formats using librosa.

        Args:
            input_path: Path to input audio file
            output_path: Path to save the output WAV file
            min_silence_len_ms: Minimum length of silence to be removed (in ms)
            keep_silence_ms: Amount of silence to keep at boundaries (in ms)

        Returns:
            Dictionary with processing statistics:
            - original_duration_ms: Original audio duration
            - processed_duration_ms: Duration after removing silence
            - removed_duration_ms: Amount of silence removed
            - speech_segments: Number of speech segments found
        """
        try:
            import librosa
            import soundfile as sf
        except ImportError:
            raise ImportError("librosa and soundfile are required. Install with: pip install librosa soundfile")
        
        log("VAD", f"Processing audio file: {input_path}")

        # Load audio using librosa (supports MP3, WAV, FLAC, etc.)
        audio_float32, sample_rate = librosa.load(input_path, sr=self.sample_rate, mono=True)
        
        # Convert to torch tensor
        wav = torch.from_numpy(audio_float32)

        # Unpack Silero utilities
        get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks = self.utils

        # Get speech timestamps using Silero VAD
        speech_timestamps = get_speech_timestamps(
            wav,
            self.model,
            sampling_rate=self.sample_rate,
            threshold=self.threshold,
            min_silence_duration_ms=min_silence_len_ms,
            min_speech_duration_ms=self.min_speech_duration_ms,
        )

        log("VAD", f"Found {len(speech_timestamps)} speech segments")

        if not speech_timestamps:
            duration_ms = len(wav) / self.sample_rate * 1000
            log("VAD", "No speech detected in audio file")
            return {
                "original_duration_ms": duration_ms,
                "processed_duration_ms": 0,
                "removed_duration_ms": duration_ms,
                "speech_segments": 0,
            }

        # Collect speech chunks with padding
        keep_silence_samples = int(keep_silence_ms * self.sample_rate / 1000)
        chunks = []
        
        # Create a silence gap of 100ms to insert between segments
        # This ensures speech is not tightly stitched, which helps STT models
        silence_gap_samples = int(100 * self.sample_rate / 1000)
        silence_gap = torch.zeros(silence_gap_samples, dtype=wav.dtype)

        for i, ts in enumerate(speech_timestamps):
            start = max(0, ts["start"] - keep_silence_samples)
            end = min(len(wav), ts["end"] + keep_silence_samples)
            
            # Add the speech chunk
            chunks.append(wav[start:end])
            
            # Add silence gap between segments (but not after the last one)
            if i < len(speech_timestamps) - 1:
                chunks.append(silence_gap)

        # Concatenate all speech segments
        processed_wav = torch.cat(chunks, dim=0)

        # Save using soundfile
        sf.write(output_path, processed_wav.numpy(), self.sample_rate)

        # Calculate statistics
        original_duration_ms = len(wav) / self.sample_rate * 1000
        processed_duration_ms = len(processed_wav) / self.sample_rate * 1000
        removed_duration_ms = original_duration_ms - processed_duration_ms

        log("VAD", f"Original duration: {original_duration_ms:.0f}ms")
        log("VAD", f"Processed duration: {processed_duration_ms:.0f}ms")
        log("VAD", f"Removed silence: {removed_duration_ms:.0f}ms ({removed_duration_ms/original_duration_ms*100:.1f}%)")
        log("VAD", f"Output saved to: {output_path}")

        return {
            "original_duration_ms": original_duration_ms,
            "processed_duration_ms": processed_duration_ms,
            "removed_duration_ms": removed_duration_ms,
            "speech_segments": len(speech_timestamps),
        }

    def batch_process_audio_files(self, input_dir: str, output_dir: str,
                                  file_extensions: List[str] = ['.wav', '.mp3', '.flac'],
                                  min_silence_len_ms: int = 300,
                                  keep_silence_ms: int = 100) -> dict:
        """
        Batch process multiple audio files in a directory.

        Args:
            input_dir: Directory containing input audio files
            output_dir: Directory to save processed files
            file_extensions: List of file extensions to process
            min_silence_len_ms: Minimum length of silence to be removed (in ms)
            keep_silence_ms: Amount of silence to keep at boundaries (in ms)

        Returns:
            Dictionary with batch processing statistics
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        processed_files = []
        failed_files = []
        total_removed_ms = 0

        # Find all audio files
        audio_files = []
        for ext in file_extensions:
            for root, _, files in os.walk(input_dir):
                for file in files:
                    if file.lower().endswith(ext):
                        audio_files.append(os.path.join(root, file))

        log("VAD", f"Found {len(audio_files)} audio files to process")

        for input_path in audio_files:
            try:
                # Generate output filename
                filename = os.path.basename(input_path)
                name, ext = os.path.splitext(filename)
                output_filename = f"{name}_no_silence{ext}"
                output_path = os.path.join(output_dir, output_filename)

                # Process file
                stats = self.process_audio_file(
                    input_path,
                    output_path,
                    min_silence_len_ms=min_silence_len_ms,
                    keep_silence_ms=keep_silence_ms
                )

                processed_files.append({
                    'input': input_path,
                    'output': output_path,
                    'stats': stats
                })
                total_removed_ms += stats['removed_duration_ms']

            except Exception as e:
                log("VAD", f"Error processing {input_path}: {str(e)}")
                failed_files.append({'file': input_path, 'error': str(e)})

        return {
            'total_files': len(audio_files),
            'processed': len(processed_files),
            'failed': len(failed_files),
            'total_removed_ms': total_removed_ms,
            'processed_files': processed_files,
            'failed_files': failed_files
        }


# Helper function to convert MP3 to WAV
def convert_mp3_to_wav(mp3_path: str, wav_path: str) -> bool:
    """
    Convert MP3 file to WAV using pydub (requires ffmpeg).
    
    Args:
        mp3_path: Path to input MP3 file
        wav_path: Path to output WAV file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(mp3_path)
        audio = audio.set_channels(1)  # Convert to mono
        audio = audio.set_frame_rate(16000)  # Set to 16kHz
        audio.export(wav_path, format="wav")
        log("CONVERT", f"Converted {mp3_path} to {wav_path}")
        return True
    except Exception as e:
        log("CONVERT", f"Failed to convert MP3: {e}")
        return False


# Convenience function for quick file processing
def remove_silence_from_audio(input_path: str, output_path: str,
                              threshold: float = SILERO_THRESHOLD,
                              min_silence_len_ms: int = 300,
                              keep_silence_ms: int = 100) -> dict:
    """
    Convenience function to remove silence from an audio file.
    Supports WAV files directly. For MP3/FLAC, convert to WAV first.

    Args:
        input_path: Path to input WAV file
        output_path: Path to save output WAV file
        threshold: VAD threshold (0.0-1.0)
        min_silence_len_ms: Minimum silence duration to remove (ms)
        keep_silence_ms: Silence padding to keep at boundaries (ms)

    Returns:
        Processing statistics dictionary

    Example:
        >>> stats = remove_silence_from_audio('input.wav', 'output.wav')
        >>> print(f"Removed {stats['removed_duration_ms']:.0f}ms of silence")
    """
    vad = VADHandler(threshold=threshold)
    return vad.process_audio_file(
        input_path,
        output_path,
        min_silence_len_ms=min_silence_len_ms,
        keep_silence_ms=keep_silence_ms
    )


# Example usage
if __name__ == "__main__":
    # Single file processing - works with MP3, WAV, FLAC, etc.
    stats = remove_silence_from_audio(
        input_path=r"D:\Harsh\Projects-Working\SingleInterface - HyperX\call_analytics\vad\audio\input\sample1_vad.mp3",
        output_path=r"D:\Harsh\Projects-Working\SingleInterface - HyperX\call_analytics\vad\audio\output\sample1_vad_no_silence.wav",
        threshold=0.5,  # Adjust based on your needs
        min_silence_len_ms=300,  # Remove silences longer than 300ms
        keep_silence_ms=100  # Keep 100ms of silence at boundaries
    )

    print(f"\nProcessing complete!")
    print(f"Original duration: {stats['original_duration_ms']:.0f}ms")
    print(f"Processed duration: {stats['processed_duration_ms']:.0f}ms")
    print(f"Removed {stats['removed_duration_ms']:.0f}ms ({stats['removed_duration_ms']/stats['original_duration_ms']*100:.1f}%)")
    print(f"Speech segments found: {stats['speech_segments']}")
