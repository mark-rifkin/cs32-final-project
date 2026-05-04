from __future__ import annotations

"""Background workers for the GUI.

LoadRoundWorker:
    fetches the next question and prepares cached clue audio

PlayAudioWorker:
    plays an already-prepared clue audio file without blocking the GUI thread
"""

import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from src.models import Question
from src.services.question_service import QuestionService
from src.services.tts_service import TTSService


class LoadRoundWorker(QObject):
    """Fetch a question and prepare its audio off the UI thread."""

    finished = Signal(object, str)
    error = Signal(str)

    def __init__(self, questions: QuestionService, tts: TTSService):
        super().__init__()
        self.questions = questions
        self.tts = tts

    @Slot()
    def run(self) -> None:
        try:
            t0 = time.perf_counter()
            question: Question = self.questions.get_random_question()
            t1 = time.perf_counter()

            cache_key = question.clue_id or question.clue_text
            audio_path = self.tts.prepare(question.clue_text, cache_key)
            t2 = time.perf_counter()

            print(
                f"[DEBUG] fetch question: {(t1 - t0):.3f}s | "
                f"prepare audio: {(t2 - t1):.3f}s"
            )
            self.finished.emit(question, str(audio_path))

        except Exception as exc:
            self.error.emit(str(exc))


class PlayAudioWorker(QObject):
    """Play one already-prepared audio file off the UI thread."""

    finished = Signal()
    error = Signal(str)

    def __init__(self, tts: TTSService, audio_path: Path):
        super().__init__()
        self.tts = tts
        self.audio_path = audio_path

    @Slot()
    def run(self) -> None:
        try:
            self.tts.play_file(self.audio_path)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))
