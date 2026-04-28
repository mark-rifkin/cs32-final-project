from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui_theme import (
    COLORS,
    Metrics,
    action_button_qss,
    banner_qss,
    card_qss,
    clue_text_qss,
    metrics_for,
    pill_qss,
    symbol_button_qss,
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


class DotColumn(QWidget):
    def __init__(self, count: int = 48, parent: QWidget | None = None):
        super().__init__(parent)
        self.dots: list[QFrame] = []
        self.active = False

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 12, 0, 12)
        self.outer.setSpacing(4)

        for _ in range(count):
            dot = QFrame()
            self.dots.append(dot)

            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addStretch()
            row.addWidget(dot)
            row.addStretch()
            self.outer.addLayout(row)

        self.outer.addStretch()

    def apply_metrics(self, m: Metrics) -> None:
        self.setFixedWidth(m.side_gutter_w)
        self.outer.setContentsMargins(0, m.card_pad // 2, 0, m.card_pad // 2)
        self.outer.setSpacing(m.side_dot_gap)

        for dot in self.dots:
            dot.setFixedSize(m.side_dot_size, m.side_dot_size)

        self.set_active(self.active)

    def set_active(self, active: bool) -> None:
        self.active = active
        color = COLORS["text"] if active else "transparent"
        for dot in self.dots:
            dot.setStyleSheet(f"background:{color}; border-radius:{dot.width() // 2}px;")

class AnswerLightStrip(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.lights: list[QFrame] = []
        self.current_count = 0
        self.phase_active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 18, 26, 18)
        layout.setSpacing(22)

        for _ in range(7):
            light = QFrame()
            light.setFixedSize(18, 18)
            self.lights.append(light)
            layout.addWidget(light, alignment=Qt.AlignmentFlag.AlignCenter)

        self.set_phase_active(False)

    def set_phase_active(self, active: bool) -> None:
        self.phase_active = active
        bg = COLORS["panel"] if active else "transparent"
        self.setStyleSheet(f"background:{bg}; border-radius:28px;")
        self.set_active_count(self.current_count)

    def set_active_count(self, count: int) -> None:
        self.current_count = count

        center_map = {
            7: [0, 1, 2, 3, 4, 5, 6],
            5: [1, 2, 3, 4, 5],
            3: [2, 3, 4],
            1: [3],
            0: [],
        }
        active = set(center_map[count])

        for i, light in enumerate(self.lights):
            if not self.phase_active:
                color = "transparent"
            else:
                color = COLORS["light_on"] if i in active else COLORS["light_dim"]

            light.setStyleSheet(f"background:{color}; border-radius:9px;")
            
    def apply_metrics(self, m: Metrics) -> None:
        self.setFixedHeight(m.answer_strip_h)
        self.setStyleSheet(
            f"background:{COLORS['panel'] if self.phase_active else 'transparent'}; "
            f"border-radius:{m.answer_strip_radius}px;"
        )

        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(m.answer_light_gap, 14, m.answer_light_gap, 14)
            layout.setSpacing(m.answer_light_gap)

        for light in self.lights:
            light.setFixedSize(m.answer_light_size, m.answer_light_size)

        self.set_active_count(self.current_count)

class MainWindow(QMainWindow):
    EARLY_LOCKOUT_MS = 250
    NO_BUZZ_TIMEOUT_S = 5
    ANSWER_TIME_S = 5
    AUTO_ADVANCE_MS = 450

    def __init__(self):
        super().__init__()

        self.questions = QuestionService()
        self.tts = TTSService()
        self.stats = StatsStore()
        self.stats.start_session()

        self.metrics = metrics_for(self.size())

        self.question: Question | None = None
        self.audio_path: Path | None = None

        self.state = "IDLE"  # IDLE LOADING READING UNLOCKED ANSWERING REVEAL
        self.menu_open = False
        self.reveal_mode = "grade"  # or "next"

        self.early_buzzed = False
        self.unlock_time: float | None = None
        self.current_buzz_delta_ms: float | None = None
        self.locked_until = 0.0
        self.phase_deadline: float | None = None

        self.preloaded_round: tuple[Question, Path] | None = None
        self.preload_thread: QThread | None = None
        self.waiting_for_preloaded = False

        self.play_thread: QThread | None = None

        ## TIMERS 
        self.phase_timer = QTimer(self)
        self.phase_timer.setSingleShot(True)
        self.phase_timer.timeout.connect(self._on_phase_timeout)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(100)
        self.countdown_timer.timeout.connect(self._update_answer_lights)

        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self.load_next_round)

        self.buzz_flash_timer = QTimer(self)
        self.buzz_flash_timer.setSingleShot(True)
        self.buzz_flash_timer.timeout.connect(self._make_answer_button)

        self.lockout_timer = QTimer(self)
        self.lockout_timer.setSingleShot(True)
        self.lockout_timer.timeout.connect(self._clear_buzz_lockout)

        self._build_ui()
        self._apply_metrics()
        self._apply_window_style()

    # ---------- UI BUILD ----------

    def _build_ui(self) -> None:
        self.setWindowTitle("Podium")
        self.resize(1100, 760)
        self.setMinimumSize(900, 620)

        central = QWidget()
        self.setCentralWidget(central)

        self.root = QHBoxLayout(central)

        # main column
        self.left_col = QVBoxLayout()

        self.category_banner = QLabel("LOADING...")
        self.category_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.category_banner.setSizePolicy(
            self.category_banner.sizePolicy().horizontalPolicy(),
            self.category_banner.sizePolicy().verticalPolicy(),
        )

        # SIZE CATEGORY LABEL TO QUESTION CARD
        self.header_wrap = QWidget()
        header_layout = QHBoxLayout(self.header_wrap)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.header_left_pad = QWidget()
        self.header_right_pad = QWidget()
        self.header_left_pad.setFixedWidth(28)
        self.header_right_pad.setFixedWidth(28)

        header_layout.addWidget(self.header_left_pad)
        header_layout.addWidget(self.category_banner, 1)
        header_layout.addWidget(self.header_right_pad)

        self.left_col.addWidget(self.header_wrap)

        self.card_wrap = QWidget()
        self.card_wrap_layout = QHBoxLayout(self.card_wrap)
        self.card_wrap_layout.setContentsMargins(0, 0, 0, 0)

        self.left_dots = DotColumn()
        self.right_dots = DotColumn()

        self.card = QFrame()
        self.card_layout = QVBoxLayout(self.card)

        self.card_layout.addStretch()

        self.main_text = QLabel("Preparing next clue...")
        self.main_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_text.setWordWrap(True)

        self.card_layout.addWidget(self.main_text)
        self.card_layout.addStretch()

        self.metadata_row = QHBoxLayout()
        self.metadata_row.addStretch()

        self.round_pill = QLabel("J")
        self.value_pill = QLabel("$???")
        self.date_pill = QLabel("Unknown")

        self.metadata_row.addWidget(self.round_pill)
        self.metadata_row.addWidget(self.value_pill)
        self.metadata_row.addSpacing(12)
        self.metadata_row.addWidget(self.date_pill)

        self.card_layout.addLayout(self.metadata_row)

        self.card_wrap_layout.addWidget(self.left_dots)
        self.card_wrap_layout.addWidget(self.card, 1)
        self.card_wrap_layout.addWidget(self.right_dots)

        self.left_col.addWidget(self.card_wrap, 1)

        self.answer_strip = AnswerLightStrip()
        self.answer_strip.set_phase_active(False)

        self.strip_row = QHBoxLayout()
        self.strip_row.addStretch()
        self.strip_row.addWidget(self.answer_strip)
        self.strip_row.addStretch()
        self.left_col.addLayout(self.strip_row)

        self.root.addLayout(self.left_col, 1)

        # right rail
        self.right_col = QVBoxLayout()

        self.menu_button = QPushButton("Menu")
        self.menu_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_button.clicked.connect(self.toggle_menu)
        self.right_col.addWidget(self.menu_button)

        self.right_col.addStretch()

        self.action_panel = QWidget()
        self.action_layout = QVBoxLayout(self.action_panel)
        self.action_layout.setContentsMargins(0, 0, 0, 0)

        self.skip_button = QPushButton("Skip")
        self.skip_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.skip_button.clicked.connect(self.skip_clue)

        self.buzz_button = QPushButton("Buzz")
        self.buzz_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.buzz_button.clicked.connect(self.handle_primary_button)

        self.next_reveal_button = QPushButton("Next")
        self.next_reveal_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_reveal_button.clicked.connect(self.load_next_round)

        self.wrong_button = QPushButton("✕")
        self.wrong_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.wrong_button.clicked.connect(lambda: self.grade_attempt(False))

        self.right_button = QPushButton("✓")
        self.right_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.right_button.clicked.connect(lambda: self.grade_attempt(True))

        self.stats_button = QPushButton("Stats")
        self.stats_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stats_button.clicked.connect(self.show_stats)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settings_button.clicked.connect(self.show_settings)

        self.quit_button = QPushButton("Quit")
        self.quit_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.quit_button.clicked.connect(self.close)

        self.right_col.addWidget(self.action_panel)
        self.right_col.addStretch()

        self.root.addLayout(self.right_col)

        self.statusBar().hide()

        self._render_action_panel()
        self._reset_round_display()

    def _apply_window_style(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background:{COLORS['bg']};
            }}
            QWidget {{
                background:{COLORS['bg']};
                color:{COLORS['text']};
            }}
            """
        )

    def _apply_metrics(self) -> None:
        m = self.metrics

        self.root.setContentsMargins(m.outer_margin, m.outer_margin, m.outer_margin, m.outer_margin)
        self.root.setSpacing(m.gap)
        self.left_col.setSpacing(m.gap)
        self.right_col.setSpacing(m.gap)

        self.category_banner.setFixedHeight(m.banner_h)
        self.category_banner.setStyleSheet(banner_qss(m))

        self.card.setMinimumHeight(m.card_min_h)
        self.card.setStyleSheet(card_qss(m))
        self.card_layout.setContentsMargins(m.card_pad, m.card_pad, m.card_pad, max(18, m.card_pad - 8))
        self.card_layout.setSpacing(max(12, m.gap - 4))

        self.main_text.setStyleSheet(clue_text_qss(m))

        self.round_pill.setStyleSheet(pill_qss(m, COLORS["text"]))
        self.value_pill.setStyleSheet(pill_qss(m, COLORS["accent"]))
        self.date_pill.setStyleSheet(pill_qss(m, COLORS["text"]))

        self.left_dots.apply_metrics(m)
        self.right_dots.apply_metrics(m)

        self.answer_strip.apply_metrics(m)

        self.menu_button.setFixedSize(m.rail_width, m.banner_h)
        self.menu_button.setStyleSheet(action_button_qss(m))

        for button in (self.skip_button, self.stats_button, self.settings_button, self.quit_button, self.next_reveal_button):
            button.setFixedSize(m.rail_width, m.action_h)
            button.setStyleSheet(action_button_qss(m))

        self.buzz_button.setFixedSize(m.rail_width, m.buzz_h)
        self.buzz_button.setStyleSheet(action_button_qss(m))

        self.wrong_button.setFixedSize(m.rail_width, m.buzz_h)
        self.right_button.setFixedSize(m.rail_width, m.buzz_h)
        self.wrong_button.setStyleSheet(symbol_button_qss(m, COLORS["red"]))
        self.right_button.setStyleSheet(symbol_button_qss(m, COLORS["green"]))

        self.action_layout.setSpacing(m.gap)

    def resizeEvent(self, event) -> None:
        self.metrics = metrics_for(event.size())
        self._apply_metrics()
        super().resizeEvent(event)

    # ---------- ACTION PANEL ----------

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _render_action_panel(self) -> None:
        self._clear_layout(self.action_layout)

        if self.menu_open:
            self.action_layout.addWidget(self.stats_button)
            self.action_layout.addWidget(self.settings_button)
            self.action_layout.addWidget(self.quit_button)
            return

        if self.state == "REVEAL":
            if self.reveal_mode == "next":
                self.action_layout.addWidget(self.next_reveal_button)
            else:
                self.action_layout.addWidget(self.wrong_button)
                self.action_layout.addWidget(self.right_button)
            return

        if self.state == "ANSWERING":
            self.action_layout.addWidget(self.buzz_button)
            return

        if self.state in {"READING", "UNLOCKED"}:
            self.action_layout.addWidget(self.skip_button)
            self.action_layout.addWidget(self.buzz_button)
            return

        # LOADING / IDLE: no buttons besides Menu

    def toggle_menu(self) -> None:
        self.menu_open = not self.menu_open
        self._render_action_panel()

    # ---------- PRELOAD ----------

    def _clear_preload_thread(self) -> None:
        self.preload_thread = None

    def _start_preload(self) -> None:
        if self.preload_thread is not None or self.preloaded_round is not None:
            return

        self.preload_thread = QThread(self)
        self.preload_worker = LoadRoundWorker(self.questions, self.tts)
        self.preload_worker.moveToThread(self.preload_thread)

        self.preload_thread.started.connect(self.preload_worker.run)
        self.preload_worker.finished.connect(self._on_preload_ready)
        self.preload_worker.error.connect(self._on_worker_error)

        self.preload_worker.finished.connect(self.preload_thread.quit)
        self.preload_worker.error.connect(self.preload_thread.quit)
        self.preload_worker.finished.connect(self.preload_worker.deleteLater)
        self.preload_worker.error.connect(self.preload_worker.deleteLater)
        self.preload_thread.finished.connect(self.preload_thread.deleteLater)
        self.preload_thread.finished.connect(self._clear_preload_thread)

        self.preload_thread.start()

    @Slot(object, str)
    def _on_preload_ready(self, question: Question, audio_path: str) -> None:
        self.preloaded_round = (question, Path(audio_path))
        if self.state == "LOADING" and self.waiting_for_preloaded:
            self._consume_preloaded_round()

    def _consume_preloaded_round(self) -> None:
        assert self.preloaded_round is not None
        question, audio_path = self.preloaded_round
        self.preloaded_round = None
        self.waiting_for_preloaded = False
        self._begin_round(question, audio_path)
        self._start_preload()

    # ---------- ROUND/UI STATE ----------

    def _reset_round_display(self) -> None:
        self.menu_open = False
        self.reveal_mode = "grade"
        self.early_buzzed = False
        self.unlock_time = None
        self.current_buzz_delta_ms = None
        self.locked_until = 0.0

        self.left_dots.set_active(False)
        self.right_dots.set_active(False)
        self.answer_strip.set_phase_active(False)
        self.answer_strip.set_active_count(0)

        self.skip_button.setEnabled(False)
        self.buzz_button.setEnabled(False)
        self.next_reveal_button.setEnabled(False)
        self.wrong_button.setEnabled(False)
        self.right_button.setEnabled(False)

        self.lockout_timer.stop()
        self.buzz_flash_timer.stop()
        self._set_buzz_button_normal()
        self.reveal_mode = "grade"
        self.next_reveal_button.setEnabled(False)

        self._render_action_panel()

    def _set_question_display(self) -> None:
        if self.question is None:
            return

        self.category_banner.setText((self.question.category or "").upper())
        self.main_text.setText((self.question.clue_text or "").upper())

        round_label = self.question.round or "J"
        self.round_pill.setText(f"{round_label[:1].upper()}")

        self.value_pill.setText(f"${self.question.value}" if self.question.value else "$???")

        if self.question.air_date is not None:
            date_text = f"{self.question.air_date.month}-{self.question.air_date.day}-{self.question.air_date.year}"
        else:
            date_text = "Unknown"
        self.date_pill.setText(date_text)

    def _show_reveal_screen(self) -> None:
        if self.question is None:
            return

        self.main_text.setText(f"What is {self.question.correct_response}?")
        self.left_dots.set_active(False)
        self.right_dots.set_active(False)
        self.answer_strip.set_phase_active(False)

        self.wrong_button.setEnabled(False)
        self.right_button.setEnabled(False)
        self.next_reveal_button.setEnabled(False)

        if self.reveal_mode == "grade":
            self.wrong_button.setEnabled(True)
            self.right_button.setEnabled(True)
        else:
            self.next_reveal_button.setEnabled(True)

        self._render_action_panel()

    ## BUZZ BUTTON STYLING
    def _set_buzz_button_style(
            self,
            text: str,
            bg: str,
            fg: str = COLORS["text"],
        ) -> None:
            self.buzz_button.setText(text)
            self.buzz_button.setStyleSheet(
                f"""
                QPushButton {{
                    background:{bg};
                    color:{fg};
                    border:none;
                    border-radius:26px;
                    font-size:26px;
                    font-weight:700;
                }}
                QPushButton:hover {{
                    background:{bg};
                }}
                QPushButton:pressed {{
                    background:{bg};
                }}
                QPushButton:disabled {{
                    background:{bg};
                    color:{fg};
                }}
                """
            )

    def _set_buzz_button_normal(self) -> None:
        self._set_buzz_button_style("Buzz", COLORS["panel"])

    def _set_buzz_button_locked(self) -> None:
        self._set_buzz_button_style("Buzz", COLORS["red"])

    def _set_buzz_button_success(self) -> None:
        self._set_buzz_button_style("Buzz", COLORS["green"])

    def _set_buzz_button_answer(self) -> None:
        self._set_buzz_button_style("Answer", COLORS["panel"])

    def _start_lockout_visual(self) -> None:
        remaining_ms = max(1, int((self.locked_until - time.perf_counter()) * 1000))
        self._set_buzz_button_locked()
        self.buzz_button.setEnabled(False)
        self.lockout_timer.start(remaining_ms)

    def _clear_buzz_lockout(self) -> None:
        if self.state in {"READING", "UNLOCKED"}:
            self._set_buzz_button_normal()
            self.buzz_button.setEnabled(True)

    def _make_answer_button(self) -> None:
        if self.state == "ANSWERING":
            self._set_buzz_button_answer()
            self.buzz_button.setEnabled(True)
            self._render_action_panel()

    def handle_primary_button(self) -> None:
        if self.state == "ANSWERING":
            self._reveal_for_grading()
        else:
            self.handle_buzz()

    # ---------- ROUND LOAD / PLAY ----------

    def load_next_round(self) -> None:
        if self.state in {"LOADING", "READING", "UNLOCKED", "ANSWERING"}:
            return

        self.state = "LOADING"
        self._stop_phase()
        self._reset_round_display()
   
        self.category_banner.setText("LOADING...")
        self.main_text.setText("Preparing next clue...")

        if self.preloaded_round is not None:
            self._consume_preloaded_round()
        else:
            self.waiting_for_preloaded = True
            self._start_preload()

    def _begin_round(self, question: Question, audio_path: Path) -> None:
        self.question = question
        self.audio_path = audio_path
        self._set_question_display()

        self.state = "READING"
        self.skip_button.setEnabled(True)
        self.buzz_button.setEnabled(True)
        self._render_action_panel()

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
        self.left_dots.set_active(True)
        self.right_dots.set_active(True)
        self.skip_button.setEnabled(True)

        if time.perf_counter() < self.locked_until:
            self._start_lockout_visual()
        else:
            self._set_buzz_button_normal()
            self.buzz_button.setEnabled(True)

        self.phase_deadline = time.perf_counter() + self.NO_BUZZ_TIMEOUT_S
        self.phase_timer.start(self.NO_BUZZ_TIMEOUT_S * 1000)

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self.state = "IDLE"
        self._stop_phase()
        self._reset_round_display()
        QMessageBox.critical(self, "Error", message)

    # ---------- TIMERS ----------

    def _stop_phase(self) -> None:
        self.phase_timer.stop()
        self.countdown_timer.stop()
        self.phase_deadline = None
        self.answer_strip.set_phase_active(False)

    def _start_answer_phase(self) -> None:
        self.state = "ANSWERING"
        self.left_dots.set_active(False)
        self.right_dots.set_active(False)
        self.answer_strip.set_phase_active(True)
        self.answer_strip.set_active_count(7)

        self.phase_deadline = time.perf_counter() + self.ANSWER_TIME_S
        self.phase_timer.start(self.ANSWER_TIME_S * 1000)
        self.countdown_timer.start()
        self._render_action_panel()

    def _update_answer_lights(self) -> None:
        if self.state != "ANSWERING" or self.phase_deadline is None:
            return

        remaining = self.phase_deadline - time.perf_counter()
        shown = max(0, int(remaining + 0.999))

        if shown >= 5:
            count = 7
        elif shown == 4:
            count = 5
        elif shown == 3:
            count = 3
        elif shown == 2:
            count = 1
        else:
            count = 0

        self.answer_strip.set_active_count(count)

    def _on_phase_timeout(self) -> None:
        if self.state == "UNLOCKED":
            self._finish_without_buzz("No buzz within 5 seconds.")
        elif self.state == "ANSWERING":
            self._reveal_for_grading()

    # ---------- USER ACTIONS ----------

    def handle_buzz(self) -> None:
        now = time.perf_counter()

        if self.state == "READING":
            self.early_buzzed = True
            self.locked_until = now + self.EARLY_LOCKOUT_MS / 1000.0
            self._start_lockout_visual()
            return

        if self.state == "UNLOCKED":
            if now < self.locked_until:
                self._start_lockout_visual()
                return
            self._accept_buzz()

    def _accept_buzz(self) -> None:
        if self.unlock_time is None:
            return

        self.lockout_timer.stop()

        buzz_time = time.perf_counter()
        self.current_buzz_delta_ms = (buzz_time - self.unlock_time) * 1000.0

        self._stop_phase()
        self.skip_button.setEnabled(False)

        self._set_buzz_button_success()
        self.buzz_button.setEnabled(False)

        self._start_answer_phase()
        self.buzz_flash_timer.start(250)

    def _reveal_for_grading(self) -> None:
        self._stop_phase()
        self.state = "REVEAL"
        self.reveal_mode = "grade"
        self._set_buzz_button_normal()
        self.buzz_button.setEnabled(False)
        self._show_reveal_screen()

    def skip_clue(self) -> None:
        if self.state not in {"READING", "UNLOCKED"}:
            return

        self.tts.stop_playback()
        self._finish_without_buzz()

    def _finish_without_buzz(self, reason: str) -> None:
        if self.question is None:
            return

        self._stop_phase()
        self.state = "REVEAL"
        self.reveal_mode = "next"

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

        self.skip_button.setEnabled(False)
        self.buzz_button.setEnabled(False)
        self.next_reveal_button.setEnabled(True)

        self._show_reveal_screen()

    def grade_attempt(self, correct: bool) -> None:
        if self.question is None:
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

        self.wrong_button.setEnabled(False)
        self.right_button.setEnabled(False)
        self.auto_timer.start(self.AUTO_ADVANCE_MS)

    # ---------- MENU ----------

    def show_stats(self) -> None:
        text = self.stats.summary_text("current") + "\n\n" + self.stats.summary_text("overall")
        QMessageBox.information(self, "Stats", text)

    def show_settings(self) -> None:
        QMessageBox.information(self, "Settings", "Settings panel not implemented yet.")

    # ---------- EVENTS ----------

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.handle_buzz()
            event.accept()
            return

        if event.key() == Qt.Key.Key_S:
            if self.state in {"READING", "UNLOCKED"} and not self.menu_open:
                self.skip_clue()
                event.accept()
                return

        if event.key() == Qt.Key.Key_M:
            self.toggle_menu()
            event.accept()
            return

        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self._stop_phase()
        self.tts.stop_playback()
        self.tts.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 11))

    window = MainWindow()
    window.show()

    # Start preload, then consume it immediately after the event loop starts.
    window._start_preload()
    QTimer.singleShot(0, window.load_next_round)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())