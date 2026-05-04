from __future__ import annotations

"""Top-level main window.

The window owns screen composition:
- intro screen before the first clue
- game screen after Start

The round controller owns gameplay state after the intro screen is dismissed.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from src.gui.round_controller import RoundController
from src.gui.gui_theme import COLORS, metrics_for
from src.gui.widgets.action_rail import ActionRail
from src.gui.widgets.clue_panel import CluePanel
from src.gui.widgets.intro_screen import IntroScreen
from src.services.question_service import QuestionService
from src.services.sfx_service import SFXService
from src.services.stats_store import StatsStore
from src.services.tts_service import TTSService


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Podium")

        logo_path = Path(__file__).resolve().parents[2] / "assets" / "ui" / "logo.png"
        self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(1100, 760)
        self.setMinimumSize(900, 620)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.questions = QuestionService()
        self.tts = TTSService()
        self.sfx = SFXService()
        self.stats = StatsStore()

        central = QWidget()
        self.setCentralWidget(central)
        self.stack = QStackedWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

        self.intro_screen = IntroScreen()

        self.game_page = QWidget()
        self.game_page.setStyleSheet(f"background:{COLORS['bg']};")

        self.root = QVBoxLayout(self.game_page)
        self.clue_panel = CluePanel()
        self.action_rail = ActionRail()

        self.root.addWidget(self.clue_panel, 1)
        self.root.addWidget(self.action_rail)

        self.stack.addWidget(self.intro_screen)
        self.stack.addWidget(self.game_page)
        self.stack.setCurrentWidget(self.intro_screen)
        self.statusBar().hide()

        self.controller = RoundController(
            questions=self.questions,
            tts=self.tts,
            sfx=self.sfx,
            stats=self.stats,
            clue_panel=self.clue_panel,
            action_rail=self.action_rail,
            show_error=self.show_error,
        )

        self.intro_screen.start_requested.connect(self._enter_game)
        self.controller.startup_ready.connect(self.intro_screen.set_ready)

        self.action_rail.stats_requested.connect(self.show_stats)
        self.action_rail.quit_requested.connect(self.close)

        self._apply_window_style()
        self._apply_metrics()

    def start(self) -> None:
        """Kick off intro audio + startup preload after the event loop is live."""
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self.intro_screen.start_loading_animation()
        self.sfx.play_intro_theme()
        self.controller.start()

    def _enter_game(self) -> None:
        """Switch from the intro screen into the main gameplay view."""
        if self.stats.current_session_id is None:
            self.stats.start_session()

        self.stack.setCurrentWidget(self.game_page)
        self.setFocus()
        self.controller.start_first_round()

    def _apply_window_style(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background:{COLORS['intro_bg']};
            }}
            """
        )

    def _apply_metrics(self) -> None:
        metrics = metrics_for(self.size())

        self.root.setContentsMargins(
            metrics.outer_margin,
            metrics.outer_margin,
            metrics.outer_margin,
            metrics.outer_margin,
        )
        self.root.setSpacing(metrics.gap)

        self.intro_screen.apply_metrics(metrics)
        self.clue_panel.apply_metrics(metrics)
        self.action_rail.apply_metrics(metrics)

    def resizeEvent(self, event) -> None:
        self._apply_metrics()
        super().resizeEvent(event)

    def show_stats(self) -> None:
        text = self.stats.summary_text("current") + "\n\n" + self.stats.summary_text("overall")
        QMessageBox.information(self, "Stats", text)

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)

    def keyPressEvent(self, event) -> None:
        """Window-level keyboard shortcuts."""
        if event.isAutoRepeat():
            event.ignore()
            return

        key = event.key()
        current = self.stack.currentWidget()

        if current is self.intro_screen:
            if key == Qt.Key.Key_Space and self.intro_screen.is_ready:
                self._enter_game()
                event.accept()
                return
            super().keyPressEvent(event)
            return

        if key == Qt.Key.Key_Space:
            self.controller.handle_space_shortcut()
            event.accept()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.controller.handle_skip_shortcut()
            event.accept()
            return

        if key == Qt.Key.Key_Left:
            self.controller.handle_wrong_shortcut()
            event.accept()
            return

        if key == Qt.Key.Key_Right:
            self.controller.handle_right_shortcut()
            event.accept()
            return

        if key == Qt.Key.Key_M:
            self.controller.toggle_menu()
            event.accept()
            return

        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.controller.shutdown()
        self.tts.close()
        self.sfx.close()
        super().closeEvent(event)
