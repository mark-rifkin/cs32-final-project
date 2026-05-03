from __future__ import annotations

"""Top-level main window.

This class builds the top-level layout for the main window.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from src.gui.round_controller import RoundController
from src.gui.theme.gui_theme import COLORS, metrics_for
from src.gui.widgets.action_rail import ActionRail
from src.gui.widgets.clue_panel import CluePanel
from src.services.question_service import QuestionService
from src.services.stats_store import StatsStore
from src.services.tts_service import TTSService
from src.services.sfx_service import SFXService


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Podium")
        self.resize(1100, 760)
        self.setMinimumSize(900, 620)
        # Make sure the main window, not a child button, owns keyboard focus.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.questions = QuestionService()
        self.tts = TTSService()
        self.sfx = SFXService()
        self.stats = StatsStore()
        self.stats.start_session()

        central = QWidget()
        self.setCentralWidget(central)

        self.root = QHBoxLayout(central)
        self.left_col = QVBoxLayout()
        self.right_col = QVBoxLayout()

        self.clue_panel = CluePanel()
        self.action_rail = ActionRail()

        self.left_col.addWidget(self.clue_panel, 1)
        self.right_col.addWidget(self.action_rail)

        self.root.addLayout(self.left_col, 1)
        self.root.addLayout(self.right_col)
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

        # MainWindow still owns dialogs and application-level actions.
        self.action_rail.stats_requested.connect(self.show_stats)
        self.action_rail.settings_requested.connect(self.show_settings)
        self.action_rail.quit_requested.connect(self.close)

        self._apply_window_style()
        self._apply_metrics()

    def start(self) -> None:
        """Start the GUI round flow after the event loop is live.

        We also force focus back to the window so Space/S/M shortcuts work
        consistently on macOS as well as Windows.
        """
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self.controller.start()

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
        metrics = metrics_for(self.size())
        self.root.setContentsMargins(metrics.outer_margin, metrics.outer_margin, metrics.outer_margin, metrics.outer_margin)
        self.root.setSpacing(metrics.gap)
        self.left_col.setSpacing(metrics.gap)
        self.right_col.setSpacing(metrics.gap)

        self.clue_panel.apply_metrics(metrics)
        self.action_rail.apply_metrics(metrics)

    def resizeEvent(self, event) -> None:
        self._apply_metrics()
        super().resizeEvent(event)

    def show_stats(self) -> None:
        text = self.stats.summary_text("current") + "\n\n" + self.stats.summary_text("overall")
        QMessageBox.information(self, "Stats", text)

    def show_settings(self) -> None:
        QMessageBox.information(self, "Settings", "Settings panel not implemented yet.")

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)

    def keyPressEvent(self, event) -> None:
        """Window-level keyboard shortcuts.

        We ignore auto-repeat so holding a key down does not trigger repeated
        buzzes, skips, or accidental multiple next actions.
        """
        if event.isAutoRepeat():
            event.ignore()
            return

        key = event.key()

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
