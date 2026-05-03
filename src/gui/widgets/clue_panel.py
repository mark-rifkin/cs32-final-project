from __future__ import annotations

"""Composite widget for the left side of the app.

This owns the category banner, the question/reveal card, the clue-side light
columns, and the answer-time light strip.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.theme.gui_theme import (
    COLORS,
    Metrics,
    banner_qss,
    card_qss,
    clue_text_qss,
    pill_qss,
)
from src.gui.widgets.answer_light_strip import AnswerLightStrip
from src.gui.widgets.dot_column import DotColumn
from src.models import Question


class CluePanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.root = QVBoxLayout(self)

        # Header wrapper uses transparent side gutters so the visible width of
        # the category banner lines up with the visible width of the clue card.
        self.header_wrap = QWidget()
        header_layout = QHBoxLayout(self.header_wrap)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.header_left_pad = QWidget()
        self.header_right_pad = QWidget()

        self.category_banner = QLabel("LOADING...")
        self.category_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addWidget(self.header_left_pad)
        header_layout.addWidget(self.category_banner, 1)
        header_layout.addWidget(self.header_right_pad)
        self.root.addWidget(self.header_wrap)

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
        self.root.addWidget(self.card_wrap, 1)

        self.answer_strip = AnswerLightStrip()
        self.answer_strip.set_phase_active(False)

        strip_row = QHBoxLayout()
        strip_row.addStretch()
        strip_row.addWidget(self.answer_strip)
        strip_row.addStretch()
        self.root.addLayout(strip_row)

    def apply_metrics(self, m: Metrics) -> None:
        self.root.setSpacing(m.gap)

        self.header_left_pad.setFixedWidth(m.side_gutter_w)
        self.header_right_pad.setFixedWidth(m.side_gutter_w)

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

    def set_loading(self) -> None:
        self.category_banner.setText("LOADING...")
        self.main_text.setText("Preparing next clue...")
        self.set_unlock_lights(False)
        self.answer_strip.set_phase_active(False)
        self.answer_strip.set_active_count(0)

    def set_question(self, question: Question) -> None:
        self.category_banner.setText((question.category or "").upper())
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
        self.answer_strip.set_phase_active(False)

    def set_unlock_lights(self, active: bool) -> None:
        self.left_dots.set_active(active)
        self.right_dots.set_active(active)

    def set_answer_phase_active(self, active: bool) -> None:
        self.answer_strip.set_phase_active(active)

    def set_answer_light_count(self, count: int) -> None:
        self.answer_strip.set_active_count(count)
