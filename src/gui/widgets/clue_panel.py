from __future__ import annotations

"""Composite widget for the left side of the game screen.

This owns the category banner, the question/reveal card, the clue-side light
columns, and the answer-time light strip.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.gui_theme import COLORS, Metrics, banner_qss, card_qss, clue_text_qss, pill_qss
from src.gui.widgets.dot_column import DotColumn
from src.models import Question


class CluePanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.metrics: Metrics | None = None
        self.category_text = "LOADING..."

        self.root = QVBoxLayout(self)

        # Header wrapper uses transparent side gutters so the visible width of
        # the category banner lines up with the visible width of the clue card.
        self.header_wrap = QWidget()
        self.header_layout = QHBoxLayout(self.header_wrap)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(10)

        self.header_left_pad = QWidget()
        self.header_right_pad = QWidget()

        self.category_banner = QLabel("LOADING...")
        self.category_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.category_banner.setWordWrap(False)

        self.header_layout.addWidget(self.header_left_pad)
        self.header_layout.addWidget(self.category_banner, 1)
        self.header_layout.addWidget(self.header_right_pad)
        self.root.addWidget(self.header_wrap)

        self.card_wrap = QWidget()
        self.card_wrap_layout = QHBoxLayout(self.card_wrap)
        self.card_wrap_layout.setContentsMargins(0, 0, 0, 0)

        self.left_dots = DotColumn(side="left")
        self.right_dots = DotColumn(side="right")

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

        for pill in (self.round_pill, self.value_pill, self.date_pill):
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Required for reliable rounded QLabel backgrounds on all platforms.
            pill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.metadata_row.addWidget(self.round_pill)
        self.metadata_row.addWidget(self.value_pill)
        self.metadata_row.addSpacing(12)
        self.metadata_row.addWidget(self.date_pill)
        self.card_layout.addLayout(self.metadata_row)

        self.card_wrap_layout.addWidget(self.left_dots)
        self.card_wrap_layout.addWidget(self.card, 1)
        self.card_wrap_layout.addWidget(self.right_dots)
        self.root.addWidget(self.card_wrap, 1)


    def apply_metrics(self, m: Metrics) -> None:
        self.metrics = m
        self.root.setSpacing(m.gap)
        self.header_layout.setSpacing(m.gap)
        self.card_wrap_layout.setSpacing(m.gap)

        self.card.setMinimumHeight(m.card_min_h)
        self.card.setStyleSheet(card_qss(m))
        self.card_layout.setContentsMargins(m.card_pad, m.card_pad, m.card_pad, max(18, m.card_pad - 8))
        self.card_layout.setSpacing(max(12, m.gap - 4))

        self.main_text.setStyleSheet(clue_text_qss(m))
        self.round_pill.setStyleSheet(pill_qss(m, COLORS["text"]))
        self.value_pill.setStyleSheet(pill_qss(m, COLORS["accent"]))
        self.date_pill.setStyleSheet(pill_qss(m, COLORS["text"]))

        pill_h = m.pill_font + 2 * m.pill_pad_v + 8
        for pill in (self.round_pill, self.value_pill, self.date_pill):
            # A fixed height plus a half-height border radius gives a true
            # rounded-pill shape instead of a barely rounded rectangle.
            pill.setFixedHeight(pill_h)

        self.left_dots.apply_metrics(m)
        self.right_dots.apply_metrics(m)
        self.header_left_pad.setFixedWidth(self.left_dots.width()) 
        self.header_right_pad.setFixedWidth(self.right_dots.width())
        self.category_banner.setFixedHeight(m.banner_h)
        self._update_category_banner_style()

    def resizeEvent(self, event) -> None:
        self._update_category_banner_style()
        super().resizeEvent(event)

    def _fit_category_font_size(self) -> int:
        """Shrink category font so long category names do not get cut off."""
        if self.metrics is None:
            return 28

        text = self.category_text or " "
        available_w = max(80, self.category_banner.width() - 2 * self.metrics.banner_pad_h - 16)
        available_h = max(20, self.category_banner.height() - 8)

        # Try the normal banner size first, then step down until it fits.
        for size in range(self.metrics.banner_font, 15, -1):
            font = QFont()
            font.setPixelSize(size)
            font.setWeight(QFont.Weight.Bold)
            fm = QFontMetrics(font)
            if fm.horizontalAdvance(text) <= available_w and fm.height() <= available_h:
                return size

        return 16

    def _update_category_banner_style(self) -> None:
        if self.metrics is None:
            return

        font_size = self._fit_category_font_size()
        self.category_banner.setStyleSheet(banner_qss(self.metrics, font_size=font_size))
        self.category_banner.setText(self.category_text)

    def set_loading(self) -> None:
        self.category_text = "LOADING..."
        self._update_category_banner_style()
        self.main_text.setText("Preparing next clue...")
        self.set_unlock_lights(False)

    def set_question(self, question: Question) -> None:
        self.category_text = (question.category or "").upper()
        self._update_category_banner_style()
        self.main_text.setText((question.clue_text or "").upper())

        round_label = question.round or "J"
        self.round_pill.setText(f"{round_label[:1].upper()}")
        self.value_pill.setText(f"${question.value}" if question.value else "$???")

        if question.air_date is not None:
            date_text = f"{question.air_date.month}-{question.air_date.day}-{question.air_date.year}"
        else:
            date_text = "Unknown"
        self.date_pill.setText(date_text)

    def show_reveal(self, correct_response: str) -> None:
        self.main_text.setText(f"What is {correct_response}?")
        self.set_unlock_lights(False)

    def set_unlock_lights(self, active: bool) -> None:
        self.left_dots.set_active(active)
        self.right_dots.set_active(active)



    def debug_card_widget(self) -> QWidget:
            """Return the visible clue-card widget used for alignment debugging."""
            return self.card