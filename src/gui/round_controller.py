from __future__ import annotations

"""Round logic and state machine for the game screen. (Not including the
intro screen)
"""

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from src.gui.widgets.action_rail import ActionRail
from src.gui.widgets.clue_panel import CluePanel
from src.gui.workers import LoadRoundWorker, PlayAudioWorker
from src.models import Attempt, Question
from src.services.question_service import QuestionService
from src.services.sfx_service import SFXService
from src.services.stats_store import StatsStore
from src.services.tts_service import TTSService


@dataclass
class ReadyRound:
    """A question and cached audio, ready to play"""
    question: Question
    audio_path: Path


class RoundController(QObject):
    """Controller for the main game flow after the intro screen."""

    startup_ready = Signal()

    EARLY_LOCKOUT_MS = 250 # lockout duration after early buzz
    NO_BUZZ_TIMEOUT_S = 5 # time to buzz after clue finishes
    ANSWER_TIME_S = 5 # time to respond after buzzing
    AUTO_ADVANCE_MS = 450 # delay before next clue after correct/incorrect

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

        # current round state
        self.question: Question | None = None
        self.audio_path: Path | None = None

        # States: IDLE LOADING READING UNLOCKED ANSWERING REVEAL
        self.state = "IDLE"  

        self.menu_open = False # if menu buttons are revealed
        self.reveal_mode = "grade"  # "grade" or "next"

        # Initialize timer parameters
        self.early_buzzed = False
        self.unlock_time: float | None = None
        self.current_buzz_delta_ms: float | None = None
        self.locked_until = 0.0
        self.phase_deadline: float | None = None

        # Startup / round preload queue. New rounds appended to back, gameplay consumes from front
        self.ready_rounds: deque[ReadyRound] = deque()
        self.target_ready_buffer = 3 # preferred queue size
        self.startup_min_ready = 2 # size required before start revealed
        self.startup_complete = False
        self.preload_thread: QThread | None = None # current preload thread
        self.waiting_for_ready_round = False # UI needs next prepared round

        self.play_thread: QThread | None = None # audio playback thread

        # no-buzz/answer timer
        self.phase_timer = QTimer(self) 
        self.phase_timer.setSingleShot(True)
        self.phase_timer.timeout.connect(self._on_phase_timeout)

        # after-buzz timer (actuates lights)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(100)
        self.countdown_timer.timeout.connect(self._update_answer_lights)

        # starts next clue after grading
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self.load_next_round)

        # flashes green on succesful buzz
        self.buzz_flash_timer = QTimer(self)
        self.buzz_flash_timer.setSingleShot(True)
        self.buzz_flash_timer.timeout.connect(self._make_answer_button)

        # locks out on early buzz
        self.lockout_timer = QTimer(self)
        self.lockout_timer.setSingleShot(True)
        self.lockout_timer.timeout.connect(self._clear_buzz_lockout)

        # Wire action rail buttons to methods 
        self.action_rail.menu_requested.connect(self.toggle_menu)
        self.action_rail.skip_requested.connect(self.skip_clue)
        self.action_rail.primary_requested.connect(self.handle_primary_action)
        self.action_rail.next_requested.connect(self.load_next_round)
        self.action_rail.wrong_requested.connect(lambda: self.grade_attempt(False))
        self.action_rail.right_requested.connect(lambda: self.grade_attempt(True))

        self._reset_round_display()

    def start(self) -> None:
        """Begin background preloading for the intro screen.

        The intro screen animation runs independently. When we have warmed the
        preload queue enough, this controller emits ``startup_ready``.
        """
        self._fill_preload_buffer()

    def start_first_round(self) -> None:
        """Begin gameplay after the intro screen's Start button is pressed."""
        if self.state in {"READING", "UNLOCKED", "ANSWERING"}: # should be in loading
            return

        self._stop_phase()
        self._reset_round_display()

        if self.ready_rounds:
            self._consume_ready_round() 
        else:
            # Fallback safety path: if Start is pressed early, show the
            # normal loading state and wait for the next prepared clue.
            self.load_next_round()

    # ------------------------------------------------------------------
    # Action rail mode control
    # ------------------------------------------------------------------

    def _refresh_action_mode(self) -> None:
        """Determines which buttons should be shown on action rail"""
        if self.menu_open: # menu prioritized
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
        """Flips menu state"""
        self.menu_open = not self.menu_open
        self._refresh_action_mode()

    # ------------------------------------------------------------------
    # Keyboard shortcut handlers
    # ------------------------------------------------------------------

    def handle_space_shortcut(self) -> None:
        """No action, buzz/answer, or next, depending on state"""
        if self.menu_open:
            return

        if self.state in {"READING", "UNLOCKED", "ANSWERING"}:
            self.handle_primary_action()
            return

        if self.state == "REVEAL" and self.reveal_mode == "next":
            self.load_next_round()

    def handle_skip_shortcut(self) -> None:
        """Skips while reading/unlocked"""
        if self.menu_open:
            return

        if self.state in {"READING", "UNLOCKED"}:
            self.skip_clue()

    def handle_wrong_shortcut(self) -> None:
        """Grades wrong"""
        if self.menu_open:
            return

        if self.state == "REVEAL" and self.reveal_mode == "grade":
            self.grade_attempt(False)

    def handle_right_shortcut(self) -> None:
        """"Grades correct"""
        if self.menu_open:
            return

        if self.state == "REVEAL" and self.reveal_mode == "grade":
            self.grade_attempt(True)

    # ------------------------------------------------------------------
    # Preload queue
    # ------------------------------------------------------------------

    def _clear_preload_thread(self) -> None:
        """Runs at end of preload thread, requests queue refill"""
        self.preload_thread = None
        self._fill_preload_buffer()

    def _fill_preload_buffer(self) -> None:
        """If preload thread not running and not enough rounds preloaded, start thread"""
        if self.preload_thread is not None:
            return

        if len(self.ready_rounds) >= self.target_ready_buffer:
            return

        self._start_preload_worker()

    def _start_preload_worker(self) -> None:
        """Starts preload worker to load rounds. Set up to quit/delete thread on success or error"""
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
        """
        ready_round = ReadyRound(question=question, audio_path=Path(audio_path))
        self.ready_rounds.append(ready_round)

        # If enough clues ready, emit startup ready signal to end intro screen
        if not self.startup_complete and len(self.ready_rounds) >= self.startup_min_ready:
            self.startup_complete = True
            self.startup_ready.emit()

        # If loading between rounds, consume clue
        if self.state == "LOADING" and self.waiting_for_ready_round:
            self._consume_ready_round()

    def _consume_ready_round(self) -> None:
        """Remove ready round from queue, starts it, and refills buffer """
        # if no round available, wait for buffer to fill
        if not self.ready_rounds:
            self.waiting_for_ready_round = True
            self._fill_preload_buffer()
            return
        # Take the oldest prepared round first
        ready_round = self.ready_rounds.popleft()
        self.waiting_for_ready_round = False

        self._begin_round(ready_round)
        self._fill_preload_buffer()

    # ------------------------------------------------------------------
    # Round reset / startup
    # ------------------------------------------------------------------

    def _reset_round_display(self) -> None:
        """Resets all per-round state before starting new round"""
        self.menu_open = False
        self.reveal_mode = "grade"
        self.early_buzzed = False
        self.unlock_time = None
        self.current_buzz_delta_ms = None
        self.locked_until = 0.0

        self.clue_panel.set_unlock_lights(False)
        self.action_rail.set_answer_phase_active(False)
        self.action_rail.set_answer_light_count(0)

        self.action_rail.set_skip_enabled(False)
        self.action_rail.set_primary_enabled(False)
        self.action_rail.set_next_enabled(False)
        self.action_rail.set_reveal_buttons_enabled(False)

        self.lockout_timer.stop()
        self.buzz_flash_timer.stop()
        self.action_rail._set_primary_normal()
        self._refresh_action_mode()

    def load_next_round(self) -> None:
        """If round not already active, load new clue"""
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
    # Individual round control
    # ------------------------------------------------------------------

    def _begin_round(self, ready_round: ReadyRound) -> None:
        """Starts play of a clue"""
        self.question = ready_round.question
        self.audio_path = ready_round.audio_path

        # Display clue
        self.clue_panel.set_question(self.question)
        
        # Enable controls
        self.state = "READING"
        self.action_rail.set_skip_enabled(True)
        self.action_rail.set_primary_enabled(True)
        self.action_rail._set_primary_normal()
        self._refresh_action_mode()

        # Play audio
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
        """Deletes audio thread reference"""
        self.play_thread = None

    @Slot()
    def _on_audio_finished(self) -> None:
        """Unlocks buzzer and turns on side lightswhen audio finishes"""
        if self.state != "READING":
            return

        self.state = "UNLOCKED"
        self.unlock_time = time.perf_counter()
        self.clue_panel.set_unlock_lights(True)
        self.action_rail.set_skip_enabled(True)

        # Enable buzzer if not locked out
        if time.perf_counter() < self.locked_until:
            self._start_lockout_visual()
        else:
            self.action_rail._set_primary_normal()
            self.action_rail.set_primary_enabled(True)

        # Start no-buzz timeout
        self.phase_deadline = time.perf_counter() + self.NO_BUZZ_TIMEOUT_S
        self.phase_timer.start(self.NO_BUZZ_TIMEOUT_S * 1000)
        self._refresh_action_mode()

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        """Pause round and display error"""
        self.state = "IDLE"
        self._stop_phase()
        self._reset_round_display()
        self.show_error(message)

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _stop_phase(self) -> None:
        """End actions for UNLOCKED or ANSWERING state"""
        self.phase_timer.stop()
        self.countdown_timer.stop()
        self.phase_deadline = None
        self.action_rail.set_answer_phase_active(False)

    def _start_answer_phase(self) -> None:
        """After successful buzz, turn off unlock lights and activate answer lights"""
        self.state = "ANSWERING"
        self.clue_panel.set_unlock_lights(False)
        self.action_rail.set_answer_phase_active(True)
        self.action_rail.set_answer_light_count(7)

        self.phase_deadline = time.perf_counter() + self.ANSWER_TIME_S
        self.phase_timer.start(self.ANSWER_TIME_S * 1000)
        self.countdown_timer.start()
        self._refresh_action_mode()

    def _update_answer_lights(self) -> None:
        """Controls answer light countown animation"""
        if self.state != "ANSWERING" or self.phase_deadline is None:
            return

        remaining = self.phase_deadline - time.perf_counter()
        shown = max(0, int(remaining + 0.999)) # don't show no lights until actually 0

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

        self.action_rail.set_answer_light_count(count)

    def _on_phase_timeout(self) -> None:
        """Handle time expiring"""
        if self.state == "UNLOCKED":
            self.sfx.play_negative_triplet()
            self._finish_without_buzz()
        elif self.state == "ANSWERING":
            self._reveal_for_grading()

    # ------------------------------------------------------------------
    # Buzz / skip / reveal
    # ------------------------------------------------------------------

    def handle_primary_action(self) -> None:
        """Buzz or reveal, depending on state"""
        if self.state == "ANSWERING":
            self._reveal_for_grading()
        else:
            self.handle_buzz()

    def handle_buzz(self) -> None:
        """Check if buzz is early/lockout, or accept buzz"""
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
        """Accept buzz, activate animation, and start buzz timer"""
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
        """Reveal answer and activate grading buttons"""
        self._stop_phase()
        self.state = "REVEAL"
        self.reveal_mode = "grade"

        self.action_rail._set_primary_normal()
        self.action_rail.set_primary_enabled(False)

        assert self.question is not None
        self.clue_panel.show_reveal(self.question.correct_response)
        self.sfx.play_reveal()
        self.action_rail.set_reveal_buttons_enabled(True)
        self._refresh_action_mode()

    def skip_clue(self) -> None:
        """User intiates skip"""
        if self.state not in {"READING", "UNLOCKED"}:
            return

        self.tts.stop_playback()
        self.sfx.play_negative_triplet()
        self._finish_without_buzz()

    def _finish_without_buzz(self) -> None:
        """After skip or no-buzz timeout, store attempt and reveal answer"""
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
        """On grading, store attempt and play SFX"""
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

        if correct:
            self.sfx.play_correct()
        else:
            self.sfx.play_incorrect()

        self.action_rail.set_reveal_buttons_enabled(False)
        self.auto_timer.start(self.AUTO_ADVANCE_MS)

    # ------------------------------------------------------------------
    # Buzzer button visuals
    # ------------------------------------------------------------------

    def _start_lockout_visual(self) -> None:
        """Disables buzz button after early buzz"""
        remaining_ms = max(1, int((self.locked_until - time.perf_counter()) * 1000))
        self.action_rail.set_primary_locked()
        self.action_rail.set_primary_enabled(False)
        self.lockout_timer.start(remaining_ms)

    def _clear_buzz_lockout(self) -> None:
        """Re-enables buzz button"""
        if self.state in {"READING", "UNLOCKED"}:
            self.action_rail._set_primary_normal()
            self.action_rail.set_primary_enabled(True)

    def _make_answer_button(self) -> None:
        """Turns buzz button into answer button after succesful buzz"""
        if self.state == "ANSWERING":
            self.action_rail.set_primary_answer()
            self.action_rail.set_primary_enabled(True)
            self._refresh_action_mode()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Stops timers and playback after window close"""
        self._stop_phase()
        self.auto_timer.stop()
        self.buzz_flash_timer.stop()
        self.lockout_timer.stop()
        self.tts.stop_playback()
