from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path

import edge_tts
import pygame


class TTSService:
    def __init__(self, voice: str = "en-US-BrianNeural", rate: str = "-1%"):
        self.voice = voice
        self.rate = rate
        self.cache_dir = Path(tempfile.gettempdir()) / "podium_tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # initialize audio engine
        pygame.mixer.init() 

    
    def _cache_path(self, cache_key: str) -> Path:
        '''Converts a clue key into a filepath for an audio file
        '''
        digest = hashlib.sha256(
            f"{self.voice}|{self.rate}|{cache_key}".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{digest}.mp3"

    def prepare(self, text: str, cache_key: str) -> Path:
        '''Creates audio file for clue if not already cached, 
        returns path
        '''
        output_path = self._cache_path(cache_key)
        if output_path.exists():
            return output_path

        communicate = edge_tts.Communicate(text=text, voice=self.voice, rate=self.rate)
        communicate.save_sync(str(output_path))
        return output_path

    def play_file(self, audio_path: Path) -> None:
        '''Plays generated audio file
        '''
        #print(f"[DEBUG] pygame play start: {audio_path}")
        start = time.perf_counter()

        try:
            pygame.mixer.music.load(str(audio_path))
            loaded = time.perf_counter()
            #print(f"[DEBUG] pygame load: {loaded - start:.3f}s")

            pygame.mixer.music.play()
            played = time.perf_counter()
            #print(f"[DEBUG] pygame play call: {played - loaded:.3f}s")

            # loop until playback complete
            while pygame.mixer.music.get_busy(): 
                time.sleep(0.02)

            # finished = time.perf_counter()
            #print(f"[DEBUG] pygame total playback block: {finished - start:.3f}s")
        except pygame.error as exc:
            raise RuntimeError(f"pygame playback failed for {audio_path}: {exc}") from exc

    def speak(self, text: str, cache_key: str) -> None:
        '''Play audio for a clue (will also generate if not already cached)
        '''
        audio_path = self.prepare(text, cache_key)
        self.play_file(audio_path)

    def stop_playback(self) -> None:
        pygame.mixer.music.stop()
        
    def close(self) -> None:
        pygame.mixer.quit()