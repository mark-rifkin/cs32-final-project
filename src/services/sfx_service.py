from __future__ import annotations

"""Sound-effects service for GUI feedback.
Stores WAV files in a permanent project folder:
    assets/sfx/
If a file is missing, a default version is generated once.
Files can be edited manually if needed. 
"""

import math
import struct
import wave
from pathlib import Path

import pygame


class SFXService:
    """Generate default WAV assets once, then always load from disk."""

    SAMPLE_RATE = 22050
    BASE_VOLUME = 0.28

    ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "sfx"

    # dictionary defining default sound effects. If modified, need to delete 
    # from assets/sfx to regenerate
    DEFAULT_SOUNDS = {
         "intro_theme": {
            "filename": "intro_theme.wav",
            # Jeopardy theme startup, first four notes
            "pattern":  [
                (440, 0.5), # A4
                (587.33, 0.5), # D5
                (440, 0.5),
                (293.66, 10), # D4
            ],
            "level": 1.00,
        },
        "buzz_ok": {
            "filename": "buzz_ok.wav",
            "pattern": [
                (880.0, 0.05), # A5
                (None, 0.02),
                (1174.66, 0.10), # D6
            ],
            "level": 1.00,
        },
        "negative_triplet": {
            "filename": "negative_triplet.wav",
            "pattern": [
                (220.0, 0.09), # A3
                (None, 0.04),
                (220.0, 0.09),
                (None, 0.04),
                (220.0, 0.09),
            ],
            "level": 1.40,
        },
        "reveal": {
            "filename": "reveal.wav",
            "pattern": [
                (329.63, 0.08),   # E4
                (392.00, 0.08),   # G4
                (523.25, 0.12),   # C5
            ] ,
            "level": 0.95,
        },
        "correct": {
            "filename": "correct.wav",
            "pattern": [
                (1046.50, 0.1), # C6

            ],
            "level": 1.00,
        },
        "incorrect": {
            "filename": "incorrect.wav",
            "pattern": [
                (220.0, 0.3), # A3
            ],
            "level": 1.40,
        },
    }

    def __init__(self, asset_dir: Path | None = None):
        self.asset_dir = asset_dir or self.ASSET_DIR
        self.asset_dir.mkdir(parents=True, exist_ok=True)

        # In case service is created before TTS
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.set_num_channels(8)
        self.channel = pygame.mixer.Channel(0)

        self._ensure_default_assets()
        self.sounds = self._load_sounds()

        # print(f"[DEBUG] SFX assets loaded from: {self.asset_dir}")

    def _ensure_default_assets(self) -> None:
        """Create WAVs if they do not already exist."""
        for spec in self.DEFAULT_SOUNDS.values():
            path = self.asset_dir / spec["filename"]
            if not path.exists():
                self._write_pattern_wav(
                    path=path,
                    pattern=spec["pattern"],
                    level=spec["level"],
                )
                # print(f"[DEBUG] Created default SFX: {path.name}")

    def _load_sounds(self) -> dict[str, pygame.mixer.Sound]:
        """Load all sound effects from the permanent asset folder."""
        loaded: dict[str, pygame.mixer.Sound] = {}
        for name, spec in self.DEFAULT_SOUNDS.items():
            path = self.asset_dir / spec["filename"]
            loaded[name] = pygame.mixer.Sound(str(path))
        return loaded

    def _write_pattern_wav(
        self,
        path: Path,
        pattern: list[tuple[float | None, float]],
        level: float = 1.0,
    ) -> None:
        """Generate a mono 16-bit PCM WAV from tones and silences."""
        frames = bytearray()
        amplitude_scale = min(1.0, self.BASE_VOLUME * level)
        amplitude = int(32767 * amplitude_scale)

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
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.SAMPLE_RATE)
            wav_file.writeframes(frames)

    def _play(self, sound_name: str) -> None:
        """Stop any currently playing sound effects and play specified effect"""
        self.channel.stop()
        self.channel.play(self.sounds[sound_name])

    def stop(self) -> None:
        """Stop any currently playing UI sound effect."""
        self.channel.stop()
    
    def play_intro_theme(self) -> None:
        self._play("intro_theme")


    def play_buzz_success(self) -> None:
        self._play("buzz_ok")

    def play_negative_triplet(self) -> None:
        self._play("negative_triplet")

    def play_reveal(self) -> None:
        self._play("reveal")

    def play_correct(self) -> None:
        self._play("correct")

    def play_incorrect(self) -> None:
        self._play("incorrect")

    def close(self) -> None:
        return
    
    def reset_assets(self) -> None:
        """Delete and recreate all default SFX WAV files, for testing
        """
        # Stop any currently playing effect before touching files.
        self.channel.stop()

        # Delete the known default asset files.
        for spec in self.DEFAULT_SOUNDS.values():
            path = self.asset_dir / spec["filename"]
            if path.exists():
                path.unlink()
                # print(f"[DEBUG] Deleted SFX: {path.name}")

        # Recreate defaults and load
        self._ensure_default_assets()
        self.sounds = self._load_sounds()
        
    