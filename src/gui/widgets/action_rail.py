from __future__ import annotations

"""Right-side control rail for the GUI.

This widget owns all buttons and exposes simple signals so the controller can
manage behavior without caring about layout details.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from src.gui.theme.gui_theme import COLORS, Metrics, action_button_qss, symbol_button_qss


class ActionRail(QWidget):
    menu_requested = Signal()
    skip_requested = Signal()
    primary_requested = Signal()
    next_requested = Signal()
    wrong_requested = Signal()
    right_requested = Signal()
    stats_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.mode = "empty"
        self.metrics: Metrics | None = None

        self.root = QVBoxLayout(self)

        self.menu_button = QPushButton("Menu")
        self.menu_button.setFocusPolicy(self.menu_button.focusPolicy().NoFocus)
        self.menu_button.clicked.connect(self.menu_requested.emit)
        self.root.addWidget(self.menu_button)
        self.root.addStretch()

        self.action_panel = QWidget()
        self.action_layout = QVBoxLayout(self.action_panel)
        self.action_layout.setContentsMargins(0, 0, 0, 0)

        self.skip_button = QPushButton("Skip")
        self.skip_button.setFocusPolicy(self.skip_button.focusPolicy().NoFocus)
        self.skip_button.clicked.connect(self.skip_requested.emit)

        self.primary_button = QPushButton("Buzz")
        self.primary_button.setFocusPolicy(self.primary_button.focusPolicy().NoFocus)
        self.primary_button.clicked.connect(self.primary_requested.emit)

        self.next_button = QPushButton("Next")
        self.next_button.setFocusPolicy(self.next_button.focusPolicy().NoFocus)
        self.next_button.clicked.connect(self.next_requested.emit)

        self.wrong_button = QPushButton("✕")
        self.wrong_button.setFocusPolicy(self.wrong_button.focusPolicy().NoFocus)
        self.wrong_button.clicked.connect(self.wrong_requested.emit)

        self.right_button = QPushButton("✓")
        self.right_button.setFocusPolicy(self.right_button.focusPolicy().NoFocus)
        self.right_button.clicked.connect(self.right_requested.emit)

        self.stats_button = QPushButton("Stats")
        self.stats_button.setFocusPolicy(self.stats_button.focusPolicy().NoFocus)
        self.stats_button.clicked.connect(self.stats_requested.emit)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setFocusPolicy(self.settings_button.focusPolicy().NoFocus)
        self.settings_button.clicked.connect(self.settings_requested.emit)

        self.quit_button = QPushButton("Quit")
        self.quit_button.setFocusPolicy(self.quit_button.focusPolicy().NoFocus)
        self.quit_button.clicked.connect(self.quit_requested.emit)

        self.root.addWidget(self.action_panel)
        self.root.addStretch()

        self._set_primary_normal()
        self.set_mode("empty")
        self._refresh_tooltips

    def apply_metrics(self, m: Metrics) -> None:
        self.metrics = m
        self.root.setSpacing(m.gap)
        self.action_layout.setSpacing(m.gap)

        self.menu_button.setFixedSize(m.rail_width, m.banner_h)
        self.menu_button.setStyleSheet(action_button_qss(m))

        for button in (self.skip_button, self.stats_button, self.settings_button, self.quit_button, self.next_button):
            button.setFixedSize(m.rail_width, m.action_h)
            button.setStyleSheet(action_button_qss(m))

        self.primary_button.setFixedSize(m.rail_width, m.buzz_h)
        self.primary_button.setStyleSheet(action_button_qss(m))

        self.wrong_button.setFixedSize(m.rail_width, m.buzz_h)
        self.right_button.setFixedSize(m.rail_width, m.buzz_h)
        self.wrong_button.setStyleSheet(symbol_button_qss(m, COLORS["red"]))
        self.right_button.setStyleSheet(symbol_button_qss(m, COLORS["green"]))
        self._refresh_tooltips()

    def _clear_layout(self) -> None:
        while self.action_layout.count():
            item = self.action_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def set_mode(self, mode: str) -> None:
        """Switch which buttons are shown beneath Menu."""
        self.mode = mode
        self._clear_layout()

        if mode == "menu":
            self.action_layout.addWidget(self.stats_button)
            self.action_layout.addWidget(self.settings_button)
            self.action_layout.addWidget(self.quit_button)
        elif mode == "clue":
            self.action_layout.addWidget(self.skip_button)
            self.action_layout.addWidget(self.primary_button)
        elif mode == "answer":
            self.action_layout.addWidget(self.primary_button)
        elif mode == "reveal_grade":
            self.action_layout.addWidget(self.wrong_button)
            self.action_layout.addWidget(self.right_button)
        elif mode == "reveal_next":
            self.action_layout.addWidget(self.next_button)
        # empty / loading intentionally show no buttons here

    def _set_primary_style(self, text: str, bg: str, fg: str = COLORS["text"]) -> None:
        self.primary_button.setText(text)
        if self.metrics is None:
            return
        self.primary_button.setStyleSheet(action_button_qss(self.metrics, fg=fg, bg=bg))
        self._refresh_tooltips

    def _set_primary_normal(self) -> None:
        self._set_primary_style("Buzz", COLORS["panel"])

    def set_primary_locked(self) -> None:
        self._set_primary_style("Buzz", COLORS["red"])

    def set_primary_success(self) -> None:
        self._set_primary_style("Buzz", COLORS["green"])

    def set_primary_answer(self) -> None:
        self._set_primary_style("Answer", COLORS["panel"])

    def set_primary_enabled(self, enabled: bool) -> None:
        self.primary_button.setEnabled(enabled)

    def set_skip_enabled(self, enabled: bool) -> None:
        self.skip_button.setEnabled(enabled)

    def set_reveal_buttons_enabled(self, enabled: bool) -> None:
        self.wrong_button.setEnabled(enabled)
        self.right_button.setEnabled(enabled)

    def set_next_enabled(self, enabled: bool) -> None:
        self.next_button.setEnabled(enabled)

    def _refresh_tooltips(self) -> None:
        """Update hover hints to show the active keyboard shortcuts."""
        self.menu_button.setToolTip("Menu (M)")
        self.skip_button.setToolTip("Skip clue (Enter)")
        self.next_button.setToolTip("Next clue (Space)")
        self.wrong_button.setToolTip("Mark wrong (Left Arrow)")
        self.right_button.setToolTip("Mark right (Right Arrow)")

        self.stats_button.setToolTip("Show stats")
        self.settings_button.setToolTip("Open settings")
        self.quit_button.setToolTip("Quit application")

        # Primary button meaning changes with state.
        text = self.primary_button.text().strip().lower()
        if text == "answer":
            self.primary_button.setToolTip("Reveal answer for grading (Space)")
        else:
            # Covers Buzz, locked Buzz, green success Buzz, etc.
            self.primary_button.setToolTip("Buzz (Space)")