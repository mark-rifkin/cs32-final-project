from __future__ import annotations

"""Small sound-effects service for GUI feedback.

This service keeps sound-effect logic out of the controller so the controller
can stay focused on round state and timing.

Implementation notes:
- Uses the existing pygame mixer already initialized for clue playback.
- Plays short effects on a normal mixer channel, while clue narration continues
  using pygame.mixer.music.
- Generates simple WAV files once and caches them in a temp directory.
"""

import math
import struct
import tempfile
import wave
from pathlib import Path

import pygame


class SFXService:
    """Generate and play simple built-in UI sound effects."""

    SAMPLE_RATE = 22050
    VOLUME = 0.28

    def __init__(self):
        self.cache_dir = Path(tempfile.gettempdir()) / "podium_sfx_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Be defensive in case this service is ever created before TTSService.
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        # Reserve enough channels for effects.
        pygame.mixer.set_num_channels(8)

        # Use one dedicated channel for UI sound effects.
        self.channel = pygame.mixer.Channel(0)

        # Preload all effects once.
        self.sounds = {
            "buzz_ok": self._load_or_create(
                "buzz_ok.wav",
                [
                    (880.0, 0.05),
                    (None, 0.02),
                    (1175.0, 0.10),
                ],
            ),
            "negative_triplet": self._load_or_create(
                "negative_triplet.wav",
                [
                    (220.0, 0.09),
                    (None, 0.04),
                    (220.0, 0.09),
                    (None, 0.04),
                    (220.0, 0.09),
                ],
            ),
            "correct": self._load_or_create(
                "correct.wav",
                [
                    (784.0, 0.06),
                    (None, 0.02),
                    (1047.0, 0.14),
                ],
            ),
            "incorrect": self._load_or_create(
                "incorrect.wav",
                [
                    (196.0, 0.30),
                ],
            ),
        }

    def _load_or_create(
        self,
        filename: str,
        pattern: list[tuple[float | None, float]],
    ) -> pygame.mixer.Sound:
        """Load a cached WAV sound, creating it if needed."""
        path = self.cache_dir / filename
        if not path.exists():
            self._write_pattern_wav(path, pattern)
        return pygame.mixer.Sound(str(path))

    def _write_pattern_wav(
        self,
        path: Path,
        pattern: list[tuple[float | None, float]],
    ) -> None:
        """Generate a mono 16-bit PCM WAV from a sequence of tones and silences.

        Each pattern item is:
            (frequency_hz, duration_seconds)

        A frequency of None means silence for that duration.
        """
        frames = bytearray()
        amplitude = int(32767 * self.VOLUME)

        for frequency, duration_s in pattern:
            sample_count = int(self.SAMPLE_RATE * duration_s)

            if frequency is None:
                for _ in range(sample_count):
                    frames.extend(struct.pack("<h", 0))
                continue

            for i in range(sample_count):
                sample = int(
                    amplitude
                    * math.sin(2.0 * math.pi * frequency * i / self.SAMPLE_RATE)
                )
                frames.extend(struct.pack("<h", sample))

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit PCM
            wav_file.setframerate(self.SAMPLE_RATE)
            wav_file.writeframes(frames)

    def _play(self, sound_name: str) -> None:
        """Play one sound effect immediately.

        We stop any previous effect on the SFX channel so feedback is crisp and
        does not become muddy if several events happen close together.
        """
        self.channel.stop()
        self.channel.play(self.sounds[sound_name])

    def play_buzz_success(self) -> None:
        """Short affirmative chime when the buzz is accepted."""
        self._play("buzz_ok")

    def play_negative_triplet(self) -> None:
        """Three low tones for skip / timeout events."""
        self._play("negative_triplet")

    def play_correct(self) -> None:
        """Positive chime when the user marks an answer correct."""
        self._play("correct")

    def play_incorrect(self) -> None:
        """Single low tone when the user marks an answer incorrect."""
        self._play("incorrect")

    def close(self) -> None:
        """Nothing to clean up right now, but keep a symmetric API."""
        return