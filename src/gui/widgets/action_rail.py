from __future__ import annotations

"""Bottom action rail for the game screen.

The rail uses the same shape as the clue panel

    side gutter | main rail area | side gutter
 The visible buttons live inside the main rail area, so their outer edges should line up with the visible clue card edges.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.gui.gui_theme import COLORS, Metrics, action_button_qss, symbol_button_qss
from src.gui.widgets.answer_light_strip import AnswerLightStrip


class ActionRail(QWidget):
    menu_requested = Signal()
    skip_requested = Signal()
    primary_requested = Signal()
    next_requested = Signal()
    wrong_requested = Signal()
    right_requested = Signal()
    stats_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.mode = "empty"
        self.metrics: Metrics | None = None

        # Outer layout mirrors CluePanel.card_wrap_layout. The left/right pads
        # reserve the same space as the clue-side light gutters.
        self.root = QHBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.left_pad = QWidget()
        self.right_pad = QWidget()

        self.center = QWidget()
        self.center_layout = QHBoxLayout(self.center)
        self.center_layout.setContentsMargins(0, 0, 0, 0)
        self.center_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.root.addWidget(self.left_pad)
        self.root.addWidget(self.center, 1)
        self.root.addWidget(self.right_pad)

        self.menu_button = QPushButton("Menu")
        self.menu_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_button.clicked.connect(self.menu_requested.emit)

        self.skip_button = QPushButton("Skip")
        self.skip_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.skip_button.clicked.connect(self.skip_requested.emit)

        self.primary_button = QPushButton("Buzz")
        self.primary_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.primary_button.clicked.connect(self.primary_requested.emit)

        self.next_button = QPushButton("Next")
        self.next_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_button.clicked.connect(self.next_requested.emit)

        self.wrong_button = QPushButton("✕")
        self.wrong_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.wrong_button.clicked.connect(self.wrong_requested.emit)

        self.right_button = QPushButton("✓")
        self.right_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.right_button.clicked.connect(self.right_requested.emit)

        self.stats_button = QPushButton("Stats")
        self.stats_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stats_button.clicked.connect(self.stats_requested.emit)

        self.quit_button = QPushButton("Quit")
        self.quit_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.quit_button.clicked.connect(self.quit_requested.emit)

        self.answer_strip = AnswerLightStrip()

        self._set_primary_normal()
        self.set_mode("empty")
        self._refresh_tooltips()

    def apply_metrics(self, m: Metrics) -> None:
        """Apply sizing and preserve card-edge alignment.

        The important alignment rule is:
        - root spacing == the clue panel's card-wrap spacing
        - left/right pad width == the clue panel's dot-column width

        That makes the center layout begin exactly where the clue card begins.
        """
        self.metrics = m
        self.root.setSpacing(m.gap)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.center_layout.setSpacing(m.gap)

        # In debugging the center area was 9px too wide on each side, so this makes the rail edges match the clue-card edges.
        rail_edge_correction = 9
        dot_gutter_w = max(m.side_dot_size + 2, m.side_gutter_w // 2)

        self.left_pad.setFixedWidth(dot_gutter_w + rail_edge_correction)
        self.right_pad.setFixedWidth(dot_gutter_w + rail_edge_correction)

        normal_w = m.rail_width
        for button in (
            self.menu_button,
            self.skip_button,
            self.stats_button,
            self.quit_button,
            self.next_button,
        ):
            button.setFixedSize(normal_w, m.action_h)
            button.setStyleSheet(action_button_qss(m))
            button.setGraphicsEffect(None)

        self.primary_button.setFixedSize(normal_w, m.action_h)
        if self.primary_button.text().strip().lower() == "answer":
            self.set_primary_answer()
        elif self.primary_button.text().strip().lower() == "buzz" and self.primary_button.isEnabled():
            self._set_primary_normal()
        self.primary_button.setGraphicsEffect(None)

        self.wrong_button.setFixedSize(normal_w, m.action_h)
        self.right_button.setFixedSize(normal_w, m.action_h)
        symbol_size = max(m.action_font + 8, int(m.action_h * 0.72))
        self.wrong_button.setStyleSheet(symbol_button_qss(m, COLORS["red"], font_size=symbol_size))
        self.right_button.setStyleSheet(symbol_button_qss(m, COLORS["green"], font_size=symbol_size))
        self.wrong_button.setGraphicsEffect(None)
        self.right_button.setGraphicsEffect(None)

        self.answer_strip.apply_metrics(m)
        self._refresh_tooltips()
        self.set_mode(self.mode)

    def _clear_center_layout(self) -> None:
        # Remove existing widgets from layout (for changing mode)
        while self.center_layout.count():
            item = self.center_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def set_mode(self, mode: str) -> None:
        """Switch which widgets are shown in the bottom rail as dictated by the controller."""
        self.mode = mode
        self._clear_center_layout()

        self.answer_strip.set_phase_active(mode == "answer")
        self.center_layout.addWidget(self.menu_button)

        if mode == "menu":
            self.center_layout.addWidget(self.stats_button)
            self.center_layout.addStretch(1)
            self.center_layout.addWidget(self.quit_button)
        elif mode == "clue":
            self.center_layout.addWidget(self.skip_button)
            self.center_layout.addStretch(1)
            self.center_layout.addWidget(self.primary_button)
        elif mode == "answer":
            # Keeps timer centered between menu and answer (equal stretches)
            self.center_layout.addStretch(1)
            self.center_layout.addWidget(self.answer_strip, alignment=Qt.AlignmentFlag.AlignCenter)
            self.center_layout.addStretch(1)
            self.center_layout.addWidget(self.primary_button)
        elif mode == "reveal_grade":
            # grading buttons on right side of rail
            self.center_layout.addStretch(1)
            self.center_layout.addWidget(self.wrong_button)
            self.center_layout.addWidget(self.right_button)
        elif mode == "reveal_next":
            self.center_layout.addStretch(1)
            self.center_layout.addWidget(self.next_button)
        else:
            self.center_layout.addStretch(1)

    def _refresh_tooltips(self) -> None:
        self.menu_button.setToolTip("Menu (M)")
        self.skip_button.setToolTip("Skip clue (Enter)")
        self.next_button.setToolTip("Next clue (Space)")
        self.wrong_button.setToolTip("Mark wrong (Left Arrow)")
        self.right_button.setToolTip("Mark right (Right Arrow)")
        self.stats_button.setToolTip("Show stats")
        self.quit_button.setToolTip("Quit")

        text = self.primary_button.text().strip().lower()
        if text == "answer":
            self.primary_button.setToolTip("Reveal answer for grading (Space)")
        else:
            self.primary_button.setToolTip("Buzz (Space)")

    def _set_primary_style(self, text: str, bg: str, fg: str = COLORS["text"]) -> None:
        self.primary_button.setText(text)
        if self.metrics is not None:
            self.primary_button.setStyleSheet(action_button_qss(self.metrics, fg=fg, bg=bg))
            self.primary_button.setGraphicsEffect(None)
        self._refresh_tooltips()

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

    def set_answer_phase_active(self, active: bool) -> None:
        self.answer_strip.set_phase_active(active)

    def set_answer_light_count(self, count: int) -> None:
            self.answer_strip.set_active_count(count)

    def debug_main_area_widget(self) -> QWidget:
        """Return the visible action area used for alignment debugging."""
        return self.center