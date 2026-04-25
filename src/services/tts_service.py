from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path

import edge_tts
import vlc


class TTSService:
    def __init__(self, voice: str = "en-US-BrianNeural", rate="-1%"):
        self.voice = voice
        self.rate = rate
        self.cache_dir = Path(tempfile.gettempdir()) / "podium_tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._vlc = vlc.Instance()
        self._player = self._vlc.media_player_new()

    def _cache_path(self, cache_key: str) -> Path:
        digest = hashlib.sha256(
            f"{self.voice}|{self.rate}|{cache_key}".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{digest}.mp3"

    def prepare(self, text: str, cache_key: str) -> Path:
        output_path = self._cache_path(cache_key)
        if output_path.exists():
            return output_path

        communicate = edge_tts.Communicate(text=text, voice=self.voice, rate=self.rate)
        communicate.save_sync(str(output_path))
        return output_path
    def debug_double_play(self, audio_path: Path) -> None:
        print("First play")
        self.play_file(audio_path)
        print("Second play")
        self.play_file(audio_path)
        
    def play_file(self, audio_path: Path) -> None:
        t0 = time.perf_counter()
        print(f"[DEBUG] play_file start: {audio_path}")

        media = self._vlc.media_new(str(audio_path))
        t1 = time.perf_counter()
        print(f"[DEBUG] media_new: {(t1 - t0):.3f}s")

        self._player.set_media(media)
        t2 = time.perf_counter()
        print(f"[DEBUG] set_media: {(t2 - t1):.3f}s")

        try:
            rc = self._player.play()
            t3 = time.perf_counter()
            print(f"[DEBUG] play() returned {rc} after {(t3 - t2):.3f}s")

            seen_states = set()
            while True:
                state = self._player.get_state()
                if state not in seen_states:
                    print(f"[DEBUG] state -> {state} at {time.perf_counter() - t0:.3f}s")
                    seen_states.add(state)
                print(f"[DEBUG] time={self._player.get_time()} ms")
                if state in {vlc.State.Ended, vlc.State.Error, vlc.State.Stopped}:
                    break
                time.sleep(0.02)

            t4 = time.perf_counter()
            print(f"[DEBUG] playback finished after {(t4 - t0):.3f}s")

            if self._player.get_state() == vlc.State.Error:
                raise RuntimeError(f"VLC playback failed for: {audio_path}")
        finally:
            self._player.stop()
            media.release()

    def speak(self, text: str, cache_key: str) -> None:
        audio_path = self.prepare(text, cache_key)
        self.play_file(audio_path)

    def close(self) -> None:
        self._player.release()
