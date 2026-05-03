from __future__ import annotations

"""Round logic and state machine for the GUI.

This controller owns:
- the ready-round preload queue
- playback worker lifecycle
- timers and state transitions
- clue / buzz / reveal behavior

Design choice:
Keep the queue-based preload improvements, but use the simpler pygame-backed
worker playback path because it previously had lower startup latency.
"""

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Slot

from src.gui.widgets.action_rail import ActionRail
from src.gui.widgets.clue_panel import CluePanel
from src.gui.workers import LoadRoundWorker, PlayAudioWorker
from src.models import Attempt, Question
from src.services.question_service import QuestionService
from src.services.stats_store import StatsStore
from src.services.tts_service import TTSService
from src.services.sfx_service import SFXService


@dataclass
class ReadyRound:
    """A clue whose text and audio are fully prepared."""
    question: Question
    audio_path: Path


class RoundController(QObject):
    EARLY_LOCKOUT_MS = 250
    NO_BUZZ_TIMEOUT_S = 5
    ANSWER_TIME_S = 5
    AUTO_ADVANCE_MS = 450

    def __init__(
        self,
        questions: QuestionService,
        tts: TTSService,
        sfx: SFXService,
        stats: StatsStore,
        clue_panel: CluePanel,
        action_rail: ActionRail,
        show_error: Callable[[str], None],
    ):
        super().__init__()
        self.questions = questions
        self.tts = tts
        self.sfx = sfx
        self.stats = stats
        self.clue_panel = clue_panel
        self.action_rail = action_rail
        self.show_error = show_error

        # Current round data
        self.question: Question | None = None
        self.audio_path: Path | None = None

        # UI / round state
        self.state = "IDLE"  # IDLE LOADING READING UNLOCKED ANSWERING REVEAL
        self.menu_open = False
        self.reveal_mode = "grade"  # "grade" or "next"

        # Timing / attempt state
        self.early_buzzed = False
        self.unlock_time: float | None = None
        self.current_buzz_delta_ms: float | None = None
        self.locked_until = 0.0
        self.phase_deadline: float | None = None

        # Preload queue
        self.ready_rounds: deque[ReadyRound] = deque()
        self.target_ready_buffer = 3
        self.preload_thread: QThread | None = None
        self.waiting_for_ready_round = False
        # On app startup, do not begin the first round until at least this many
        # clues are already fully prepared.
        self.startup_min_ready = 2
        self.startup_complete = False

        # Playback thread
        self.play_thread: QThread | None = None

        # Timers
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

        # UI event wiring
        self.action_rail.menu_requested.connect(self.toggle_menu)
        self.action_rail.skip_requested.connect(self.skip_clue)
        self.action_rail.primary_requested.connect(self.handle_primary_action)
        self.action_rail.next_requested.connect(self.load_next_round)
        self.action_rail.wrong_requested.connect(lambda: self.grade_attempt(False))
        self.action_rail.right_requested.connect(lambda: self.grade_attempt(True))

        self._reset_round_display()

    def start(self) -> None:
        """Warm the queue before starting the first clue.
        Avoids start with empty buffer"""
        self.state = "LOADING"
        self.waiting_for_ready_round = True
        self.clue_panel.set_loading()
        self._refresh_action_mode()
        self._fill_preload_buffer()

    # ------------------------------------------------------------------
    # Action rail mode control
    # ------------------------------------------------------------------

    def _refresh_action_mode(self) -> None:
        if self.menu_open:
            self.action_rail.set_mode("menu")
            return

        if self.state == "REVEAL":
            mode = "reveal_next" if self.reveal_mode == "next" else "reveal_grade"
            self.action_rail.set_mode(mode)
            return

        if self.state == "ANSWERING":
            self.action_rail.set_mode("answer")
            return

        if self.state in {"READING", "UNLOCKED"}:
            self.action_rail.set_mode("clue")
            return

        self.action_rail.set_mode("empty")

    def toggle_menu(self) -> None:
        self.menu_open = not self.menu_open
        self._refresh_action_mode()

    # ------------------------------------------------------------------
    # Keyboard shortcut handlers
    # ------------------------------------------------------------------
    def handle_space_shortcut(self) -> None:
        """Spacebar should trigger the main action for the current screen.
        Mapping:
        - READING / UNLOCKED -> Buzz
        - ANSWERING -> Answer
        - REVEAL with reveal_mode == "next" -> Next
        """
        if self.menu_open:
            return

        if self.state in {"READING", "UNLOCKED", "ANSWERING"}:
            self.handle_primary_action()
            return

        if self.state == "REVEAL" and self.reveal_mode == "next":
            self.load_next_round()

    def handle_skip_shortcut(self) -> None:
        """Enter should skip only while a clue is active."""
        if self.menu_open:
            return

        if self.state in {"READING", "UNLOCKED"}:
            self.skip_clue()

    def handle_wrong_shortcut(self) -> None:
        """Left arrow marks the revealed response as wrong."""
        if self.menu_open:
            return

        if self.state == "REVEAL" and self.reveal_mode == "grade":
            self.grade_attempt(False)

    def handle_right_shortcut(self) -> None:
        """Right arrow marks the revealed response as right."""
        if self.menu_open:
            return

        if self.state == "REVEAL" and self.reveal_mode == "grade":
            self.grade_attempt(True)
    

    # ------------------------------------------------------------------
    # Preload queue
    # ------------------------------------------------------------------

    def _clear_preload_thread(self) -> None:
        """Mark the preload thread as finished, then continue filling the queue.
        """
        self.preload_thread = None
        self._fill_preload_buffer()

    def _fill_preload_buffer(self) -> None:
        """Keep the queue of prepared rounds topped up."""
        if self.preload_thread is not None:
            return

        if len(self.ready_rounds) >= self.target_ready_buffer:
            return

        self._start_preload_worker()

    def _start_preload_worker(self) -> None:
        """Start one worker that fetches a question and prepares its audio."""
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
        """Store a fully prepared round in the queue.

        During startup, wait until we have a small buffer before consuming the
        first round. After startup, consume immediately whenever the UI is waiting.
        """
        ready_round = ReadyRound(
            question=question,
            audio_path=Path(audio_path),
        )
        self.ready_rounds.append(ready_round)

        print(
            f"[DEBUG] ready round queued: {ready_round.audio_path.name} | "
            f"queue_size={len(self.ready_rounds)}"
        )

        if not self.startup_complete:
            # Only begin gameplay after the queue has a little slack.
            if len(self.ready_rounds) >= self.startup_min_ready:
                self.startup_complete = True
                if self.state == "LOADING" and self.waiting_for_ready_round:
                    self._consume_ready_round()
        else:
            if self.state == "LOADING" and self.waiting_for_ready_round:
                self._consume_ready_round()

        self._fill_preload_buffer()

    def _consume_ready_round(self) -> None:
        """Take the next prepared round from the queue and begin it."""
        assert self.ready_rounds
        ready_round = self.ready_rounds.popleft()
        self.waiting_for_ready_round = False

        print(
            f"[DEBUG] consuming ready round: {ready_round.audio_path.name} | "
            f"queue_size_after_pop={len(self.ready_rounds)}"
        )

        self._begin_round(ready_round)
        self._fill_preload_buffer()

    # ------------------------------------------------------------------
    # Round reset / startup
    # ------------------------------------------------------------------

    def _reset_round_display(self) -> None:
        self.menu_open = False
        self.reveal_mode = "grade"
        self.early_buzzed = False
        self.unlock_time = None
        self.current_buzz_delta_ms = None
        self.locked_until = 0.0

        self.clue_panel.set_unlock_lights(False)
        self.clue_panel.set_answer_phase_active(False)
        self.clue_panel.set_answer_light_count(0)

        self.action_rail.set_skip_enabled(False)
        self.action_rail.set_primary_enabled(False)
        self.action_rail.set_next_enabled(False)
        self.action_rail.set_reveal_buttons_enabled(False)

        self.lockout_timer.stop()
        self.buzz_flash_timer.stop()
        self.action_rail._set_primary_normal()
        self._refresh_action_mode()

    def load_next_round(self) -> None:
        """Move to the next clue, using the preload queue if possible."""
        if self.state in {"LOADING", "READING", "UNLOCKED", "ANSWERING"}:
            return

        self.state = "LOADING"
        self._stop_phase()
        self._reset_round_display()
        self.clue_panel.set_loading()
        self._refresh_action_mode()

        if self.ready_rounds:
            self._consume_ready_round()
        else:
            self.waiting_for_ready_round = True
            self._fill_preload_buffer()

    # ------------------------------------------------------------------
    # Playback lifecycle
    # ------------------------------------------------------------------

    def _begin_round(self, ready_round: ReadyRound) -> None:
        self.question = ready_round.question
        self.audio_path = ready_round.audio_path

        print(f"[DEBUG] consuming ready round: {self.audio_path.name}")
        print("[DEBUG] starting playback")

        self.clue_panel.set_question(self.question)

        self.state = "READING"
        self.action_rail.set_skip_enabled(True)
        self.action_rail.set_primary_enabled(True)
        self.action_rail._set_primary_normal()
        self._refresh_action_mode()

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
        """Unlock buzzing once clue audio finishes."""
        if self.state != "READING":
            return

        self.state = "UNLOCKED"
        self.unlock_time = time.perf_counter()
        self.clue_panel.set_unlock_lights(True)
        self.action_rail.set_skip_enabled(True)

        if time.perf_counter() < self.locked_until:
            self._start_lockout_visual()
        else:
            self.action_rail._set_primary_normal()
            self.action_rail.set_primary_enabled(True)

        self.phase_deadline = time.perf_counter() + self.NO_BUZZ_TIMEOUT_S
        self.phase_timer.start(self.NO_BUZZ_TIMEOUT_S * 1000)
        self._refresh_action_mode()

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self.state = "IDLE"
        self._stop_phase()
        self._reset_round_display()
        self.show_error(message)

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _stop_phase(self) -> None:
        self.phase_timer.stop()
        self.countdown_timer.stop()
        self.phase_deadline = None
        self.clue_panel.set_answer_phase_active(False)

    def _start_answer_phase(self) -> None:
        self.state = "ANSWERING"
        self.clue_panel.set_unlock_lights(False)
        self.clue_panel.set_answer_phase_active(True)
        self.clue_panel.set_answer_light_count(7)

        self.phase_deadline = time.perf_counter() + self.ANSWER_TIME_S
        self.phase_timer.start(self.ANSWER_TIME_S * 1000)
        self.countdown_timer.start()
        self._refresh_action_mode()

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

        self.clue_panel.set_answer_light_count(count)

    def _on_phase_timeout(self) -> None:
        self.sfx.play_negative_triplet()

        if self.state == "UNLOCKED":
            self._finish_without_buzz()
        elif self.state == "ANSWERING":
            self._reveal_for_grading()

    # ------------------------------------------------------------------
    # Buzz / skip / reveal
    # ------------------------------------------------------------------

    def handle_primary_action(self) -> None:
        if self.state == "ANSWERING":
            self._reveal_for_grading()
        else:
            self.handle_buzz()

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
        self.action_rail.set_skip_enabled(False)
        self.action_rail.set_primary_success()
        self.action_rail.set_primary_enabled(False)
        self.sfx.play_buzz_success()

        self._start_answer_phase()
        self.buzz_flash_timer.start(250)

    def _reveal_for_grading(self) -> None:
        self._stop_phase()
        self.state = "REVEAL"
        self.reveal_mode = "grade"

        self.action_rail._set_primary_normal()
        self.action_rail.set_primary_enabled(False)

        assert self.question is not None
        self.clue_panel.show_reveal(self.question.correct_response)
        self.action_rail.set_reveal_buttons_enabled(True)
        self._refresh_action_mode()

    def skip_clue(self) -> None:
        if self.state not in {"READING", "UNLOCKED"}:
            return

        self.tts.stop_playback()
        self.sfx.play_negative_triplet()

        self._finish_without_buzz()

    def _finish_without_buzz(self) -> None:
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

        self.action_rail.set_skip_enabled(False)
        self.action_rail.set_primary_enabled(False)
        self.action_rail.set_next_enabled(True)

        self.clue_panel.show_reveal(self.question.correct_response)
        self._refresh_action_mode()

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

         # Grading feedback sound.
        if correct:
            self.sfx.play_correct()
        else:
            self.sfx.play_incorrect()

        self.action_rail.set_reveal_buttons_enabled(False)
        self.auto_timer.start(self.AUTO_ADVANCE_MS)

    # ------------------------------------------------------------------
    # Lockout visuals
    # ------------------------------------------------------------------

    def _start_lockout_visual(self) -> None:
        remaining_ms = max(1, int((self.locked_until - time.perf_counter()) * 1000))
        self.action_rail.set_primary_locked()
        self.action_rail.set_primary_enabled(False)
        self.lockout_timer.start(remaining_ms)

    def _clear_buzz_lockout(self) -> None:
        if self.state in {"READING", "UNLOCKED"}:
            self.action_rail._set_primary_normal()
            self.action_rail.set_primary_enabled(True)

    def _make_answer_button(self) -> None:
        if self.state == "ANSWERING":
            self.action_rail.set_primary_answer()
            self.action_rail.set_primary_enabled(True)
            self._refresh_action_mode()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Stop timers and audio cleanly when the window closes."""
        self._stop_phase()
        self.auto_timer.stop()
        self.buzz_flash_timer.stop()
        self.lockout_timer.stop()
        self.tts.stop_playback()