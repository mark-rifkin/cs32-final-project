from __future__ import annotations

""" Service that handles: 
1. Generating/caching clue audio with edge-tts
2. Playing cached clue audio with pygame-ce
"""

import hashlib
import tempfile
import time
from pathlib import Path

import edge_tts
import pygame


class TTSService:
    def __init__(self, voice: str = "en-US-BrianNeural", rate: str = "-1%"):
        '''
        '''
        self.voice = voice
        self.rate = rate
        self.cache_dir = Path(tempfile.gettempdir()) / "podium_tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # initialize audio backend
        pygame.mixer.init()

    def _cache_path(self, cache_key: str) -> Path:
        """Map a clue key to a stable cache filename."""
        digest = hashlib.sha256(
            f"{self.voice}|{self.rate}|{cache_key}".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{digest}.mp3"

    def prepare(self, text: str, cache_key: str) -> Path:
        """Generate clue audio if needed, then return the cached path."""
        output_path = self._cache_path(cache_key)
        if output_path.exists():
            return output_path

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
        )
        communicate.save_sync(str(output_path))
        return output_path

    def play_file(self, audio_path: Path) -> None:
        """Play a prepared audio file synchronously.

        This blocks until playback finishes. In the GUI, it is called from a
        worker thread, so the UI remains responsive.
        """
        try:
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                time.sleep(0.02)

        except pygame.error as exc:
            raise RuntimeError(
                f"pygame playback failed for {audio_path}: {exc}"
            ) from exc

    def stop_playback(self) -> None:
        """Stop current clue playback immediately."""
        pygame.mixer.music.stop()

    def close(self) -> None:
        """Shut down pygame audio on application exit."""
        pygame.mixer.quit()