from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models import Attempt, Question
from src.services.question_service import QuestionService
from src.services.stats_store import StatsStore
from src.services.tts_service import TTSService


class LoadRoundWorker(QObject):
    finished = Signal(object, str)
    error = Signal(str)

    def __init__(self, questions: QuestionService, tts: TTSService):
        super().__init__()
        self.questions = questions
        self.tts = tts

    @Slot()
    def run(self) -> None:
        try:
            question = self.questions.get_random_question()
            cache_key = question.clue_id or question.clue_text
            audio_path = self.tts.prepare(question.clue_text, cache_key)
            self.finished.emit(question, str(audio_path))
        except Exception as exc:
            self.error.emit(str(exc))


class PlayAudioWorker(QObject):
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


class MainWindow(QMainWindow):
    EARLY_LOCKOUT_MS = 250
    NO_BUZZ_TIMEOUT_S = 5
    ANSWER_TIME_S = 5

    def __init__(self):
        super().__init__()

        self.questions = QuestionService()
        self.tts = TTSService()
        self.stats = StatsStore()
        self.stats.start_session()

        self.question: Question | None = None
        self.audio_path: Path | None = None
        self.state = "IDLE"
        self.early_buzzed = False
        self.unlock_time: float | None = None
        self.buzz_time: float | None = None
        self.current_buzz_delta_ms: float | None = None
        self.locked_until = 0.0

        self.phase_deadline: float | None = None
        self.phase_label = ""

        self.load_thread: QThread | None = None
        self.play_thread: QThread | None = None

        self.phase_timer = QTimer(self)
        self.phase_timer.setSingleShot(True)
        self.phase_timer.timeout.connect(self._on_phase_timeout)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(100)
        self.countdown_timer.timeout.connect(self._update_countdown)

        self._build_ui()
        self.buzz_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.buzz_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.buzz_shortcut.activated.connect(self.handle_buzz)

        self.skip_shortcut = QShortcut(QKeySequence("S"), self)
        self.skip_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.skip_shortcut.activated.connect(self.handle_skip)

    def _build_ui(self) -> None:
        self.setWindowTitle("Podium - Jeopardy Trainer")
        self.resize(800, 500)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        top_row = QHBoxLayout()
        self.left_light = QLabel()
        self.right_light = QLabel()
        for light in (self.left_light, self.right_light):
            light.setFixedSize(24, 24)
        self._set_lights(False)

        self.category_label = QLabel("Category")
        self.category_label.setStyleSheet("font-size: 22px; font-weight: bold;")

        top_row.addWidget(self.left_light)
        top_row.addStretch()
        top_row.addWidget(self.category_label)
        top_row.addStretch()
        top_row.addWidget(self.right_light)

        self.clue_label = QLabel("Click 'Next clue' to begin.")
        self.clue_label.setWordWrap(True)
        self.clue_label.setStyleSheet("font-size: 18px;")

        buzz_row = QHBoxLayout()
        buzz_row.addStretch()

        self.buzz_button = QPushButton("BUZZ")
        self.buzz_button.setMinimumWidth(180)
        self.buzz_button.setFixedHeight(48)
        self.buzz_button.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.buzz_button.clicked.connect(self.handle_buzz)
        self.buzz_button.setEnabled(False)

        buzz_row.addWidget(self.buzz_button)
        buzz_row.addStretch()

        self.status_label = QLabel("Idle")
        self.countdown_label = QLabel("")
        self.buzz_label = QLabel("")
        self.response_label = QLabel("")
        self.response_label.setWordWrap(True)
        self.response_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        button_row = QHBoxLayout()
        self.next_button = QPushButton("Next clue")
        self.skip_button = QPushButton("Skip clue")
        self.correct_button = QPushButton("Correct")
        self.incorrect_button = QPushButton("Incorrect")
        self.skip_grade_button = QPushButton("Skip grading")
        self.stats_button = QPushButton("Show stats")

        self.skip_button.setEnabled(False)
        self.correct_button.setEnabled(False)
        self.incorrect_button.setEnabled(False)
        self.skip_grade_button.setEnabled(False)

        self.next_button.clicked.connect(self.load_next_round)
        self.skip_button.clicked.connect(self.skip_clue)
        self.correct_button.clicked.connect(lambda: self.grade_attempt(True))
        self.incorrect_button.clicked.connect(lambda: self.grade_attempt(False))
        self.skip_grade_button.clicked.connect(lambda: self.grade_attempt(None))
        self.stats_button.clicked.connect(self.show_stats)

        button_row.addWidget(self.next_button)
        button_row.addWidget(self.skip_button)
        button_row.addWidget(self.correct_button)
        button_row.addWidget(self.incorrect_button)
        button_row.addWidget(self.skip_grade_button)
        button_row.addWidget(self.stats_button)

        # Add layouts in order
        layout.addLayout(top_row)
        layout.addSpacing(16)
        layout.addWidget(self.clue_label)
        layout.addLayout(buzz_row)
        layout.addSpacing(16)
        layout.addWidget(self.status_label)
        layout.addWidget(self.countdown_label)
        layout.addWidget(self.buzz_label)
        layout.addWidget(self.response_label)
        layout.addStretch()
        layout.addLayout(button_row)

        # Buttons should not take keyboard focus
        for button in [
            self.next_button,
            self.skip_button,
            self.correct_button,
            self.incorrect_button,
            self.skip_grade_button,
            self.stats_button,
            self.buzz_button,
        ]:
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _set_lights(self, on: bool) -> None:
        color = "#cc0000" if on else "#444444"
        style = f"background-color: {color}; border-radius: 12px;"
        self.left_light.setStyleSheet(style)
        self.right_light.setStyleSheet(style)

    def _set_grading_enabled(self, enabled: bool) -> None:
        self.correct_button.setEnabled(enabled)
        self.incorrect_button.setEnabled(enabled)
        self.skip_grade_button.setEnabled(enabled)

    def _stop_phase(self) -> None:
        self.phase_timer.stop()
        self.countdown_timer.stop()
        self.phase_deadline = None
        self.phase_label = ""
        self.countdown_label.clear()

    def _start_phase(self, seconds: int, label: str) -> None:
        self.phase_deadline = time.perf_counter() + seconds
        self.phase_label = label
        self.phase_timer.start(seconds * 1000)
        self.countdown_timer.start()
        self._update_countdown()

    def _update_countdown(self) -> None:
        if self.phase_deadline is None:
            self.countdown_label.clear()
            return

        remaining = self.phase_deadline - time.perf_counter()
        if remaining <= 0:
            self.countdown_label.clear()
            return

        shown = int(remaining + 0.999)
        self.countdown_label.setText(f"{self.phase_label}: {shown}")

    def _reset_round_display(self) -> None:
        self.response_label.clear()
        self.countdown_label.clear()
        self.buzz_label.clear()
        self._set_lights(False)
        self._set_grading_enabled(False)
        self.skip_button.setEnabled(False)
        self.buzz_button.setEnabled(False)

        self.early_buzzed = False
        self.unlock_time = None
        self.buzz_time = None
        self.current_buzz_delta_ms = None
        self.locked_until = 0.0

    def load_next_round(self) -> None:
        if self.state in {"LOADING", "READING", "UNLOCKED", "ANSWERING"}:
            return

        self._stop_phase()
        self._reset_round_display()
        self.state = "LOADING"
        self.next_button.setEnabled(False)
        self.status_label.setText("Loading clue and preparing audio...")
        self.clue_label.setText("Loading...")
        self.category_label.setText("Category")

        self.load_thread = QThread(self)
        self.load_worker = LoadRoundWorker(self.questions, self.tts)
        self.load_worker.moveToThread(self.load_thread)

        self.load_thread.started.connect(self.load_worker.run)
        self.load_worker.finished.connect(self._on_round_loaded)
        self.load_worker.error.connect(self._on_worker_error)

        self.load_worker.finished.connect(self.load_thread.quit)
        self.load_worker.error.connect(self.load_thread.quit)
        self.load_worker.finished.connect(self.load_worker.deleteLater)
        self.load_worker.error.connect(self.load_worker.deleteLater)
        self.load_thread.finished.connect(self.load_thread.deleteLater)
        self.load_thread.finished.connect(self._clear_load_thread)

        self.load_thread.start()

    def _clear_load_thread(self) -> None:
        self.load_thread = None

    @Slot(object, str)
    def _on_round_loaded(self, question: Question, audio_path: str) -> None:
        self.question = question
        self.audio_path = Path(audio_path)

        self.category_label.setText(question.category)
        self.clue_label.setText(question.clue_text)
        self.status_label.setText("Playing clue... Press Space to buzz early.")
        self.state = "READING"

        self.buzz_button.setEnabled(True)

        self.play_thread = QThread(self)
        self.play_worker = PlayAudioWorker(self.tts, self.audio_path)
        self.play_worker.moveToThread(self.play_thread)

        self.play_thread.started.connect(self.play_worker.run)
        self.play_worker.finished.connect(self._on_audio_finished)
        self.play_worker.error.connect(self._on_worker_error)

        self.play_worker.finished.connect(self.play_thread.quit)
        self.play_worker.error.connect(self.play_thread.quit)
        self.play_worker.finished.connect(self.play_worker.deleteLater)
        self.play_worker.error.connect(self.play_worker.deleteLater)
        self.play_thread.finished.connect(self.play_thread.deleteLater)
        self.play_thread.finished.connect(self._clear_play_thread)

        self.play_thread.start()

    def _clear_play_thread(self) -> None:
        self.play_thread = None

    @Slot()
    def _on_audio_finished(self) -> None:
        if self.state != "READING":
            return

        self.state = "UNLOCKED"
        self.unlock_time = time.perf_counter()
        self._set_lights(True)
        self.skip_button.setEnabled(True)
        self.status_label.setText("Buzzer unlocked. Press Space to buzz.")
        self._start_phase(self.NO_BUZZ_TIMEOUT_S, "Buzz window")

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self.state = "IDLE"
        self.next_button.setEnabled(True)
        self.skip_button.setEnabled(False)
        self.buzz_button.setEnabled(False)
        self._stop_phase()
        self._set_lights(False)
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Error", message)

    def _accept_buzz(self) -> None:
        assert self.unlock_time is not None

        self.buzz_time = time.perf_counter()
        self.current_buzz_delta_ms = (self.buzz_time - self.unlock_time) * 1000.0

        self._stop_phase()
        self._set_lights(False)
        self.skip_button.setEnabled(False)
        self.buzz_button.setEnabled(False)

        self.buzz_label.setText(f"Buzz time: {self.current_buzz_delta_ms:.1f} ms")
        self.status_label.setText("Buzz accepted. Answer now.")
        self.state = "ANSWERING"
        self._start_phase(self.ANSWER_TIME_S, "Answer time")

    def _finish_without_buzz(self, reason: str) -> None:
        self._stop_phase()
        self._set_lights(False)
        self.skip_button.setEnabled(False)
        self.buzz_button.setEnabled(False)

        self.response_label.setText(
            f"Correct response: What is {self.question.correct_response}?"
        )
        self.status_label.setText(reason)

        attempt = Attempt(
            clue_id=self.question.clue_id,
            category=self.question.category,
            clue_text=self.question.clue_text,
            correct_response=self.question.correct_response,
            buzz_delta_ms=None,
            early_buzz=self.early_buzzed,
            correct=None,
        )
        self.stats.save_attempt(attempt)

        self.state = "REVEAL"
        self.next_button.setEnabled(True)

    def _reveal_for_grading(self) -> None:
        self._stop_phase()
        self._set_lights(False)
        self.skip_button.setEnabled(False)
        self.buzz_button.setEnabled(False)

        self.response_label.setText(
            f"Correct response: What is {self.question.correct_response}?"
        )
        self.status_label.setText("Time up. Grade your response.")
        self._set_grading_enabled(True)

        self.state = "REVEAL"

    def grade_attempt(self, correct: bool | None) -> None:
        if self.question is None or self.current_buzz_delta_ms is None:
            return

        attempt = Attempt(
            clue_id=self.question.clue_id,
            category=self.question.category,
            clue_text=self.question.clue_text,
            correct_response=self.question.correct_response,
            buzz_delta_ms=self.current_buzz_delta_ms,
            early_buzz=self.early_buzzed,
            correct=correct,
        )
        self.stats.save_attempt(attempt)

        self._set_grading_enabled(False)
        self.status_label.setText("Saved. Click 'Next clue' for another round.")
        self.next_button.setEnabled(True)

    def skip_clue(self) -> None:
        if self.state == "UNLOCKED":
            self._finish_without_buzz("Clue skipped.")

    def _on_phase_timeout(self) -> None:
        if self.state == "UNLOCKED":
            self._finish_without_buzz("No buzz within 5 seconds.")
        elif self.state == "ANSWERING":
            self._reveal_for_grading()

    def handle_buzz(self) -> None:
        now = time.perf_counter()

        if self.state == "READING":
            self.early_buzzed = True
            self.locked_until = now + self.EARLY_LOCKOUT_MS / 1000.0
            self.status_label.setText(
                f"Too early. Locked out for {self.EARLY_LOCKOUT_MS} ms."
            )
            return

        if self.state == "UNLOCKED":
            if now < self.locked_until:
                remaining_ms = (self.locked_until - now) * 1000.0
                self.status_label.setText(
                    f"Still locked out for {remaining_ms:.0f} ms."
                )
                return

            self._accept_buzz()


    def handle_skip(self) -> None:
        if self.state == "UNLOCKED":
            self.skip_clue()

    def show_stats(self) -> None:
        text = self.stats.summary_text("current") + "\n\n" + self.stats.summary_text("overall")
        QMessageBox.information(self, "Stats", text)

    def closeEvent(self, event) -> None:
        self._stop_phase()
        self.tts.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())