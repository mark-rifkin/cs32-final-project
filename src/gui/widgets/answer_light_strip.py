from __future__ import annotations

"""Centered answer countdown lights for the bottom action rail.

The strip paints its own rounded background instead of relying only on a Qt
stylesheet. That makes the background more reliable when the strip is inserted
and removed from the bottom rail during mode changes.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

from src.gui.gui_theme import COLORS, Metrics


class AnswerLightStrip(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.lights: list[QFrame] = []
        self.current_count = 0
        self.phase_active = False
        self.metrics: Metrics | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(18, 6, 18, 6)
        self.layout_.setSpacing(12)
        self.layout_.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for _ in range(7):
            light = QFrame()
            self.lights.append(light)
            self.layout_.addWidget(light, alignment=Qt.AlignmentFlag.AlignCenter)

        self.set_phase_active(False)

    def apply_metrics(self, m: Metrics) -> None:
        """Apply button-like sizing and keep the lights centered."""
        self.metrics = m
        self.setFixedHeight(m.action_h)
        self.setFixedWidth(m.timer_strip_w)
        self.layout_.setContentsMargins(m.answer_light_gap, 6, m.answer_light_gap, 6)
        self.layout_.setSpacing(m.answer_light_gap)
        self.layout_.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for light in self.lights:
            light.setFixedSize(m.answer_light_size, m.answer_light_size)

        self.set_active_count(self.current_count)
        self.update()

    def set_phase_active(self, active: bool) -> None:
        self.phase_active = active
        self.set_active_count(self.current_count)
        self.update()

    def set_active_count(self, count: int) -> None:
        self.current_count = count
        center_map = {
            7: [0, 1, 2, 3, 4, 5, 6],
            5: [1, 2, 3, 4, 5],
            3: [2, 3, 4],
            1: [3],
            0: [],
        }
        active = set(center_map.get(count, []))

        for i, light in enumerate(self.lights):
            if not self.phase_active:
                color = "transparent"
            else:
                color = COLORS["light_on"] if i in active else COLORS["light_dim"]
            light.setStyleSheet(
                f"background:{color}; border:none; border-radius:{light.width() // 2}px;"
            )

    def paintEvent(self, event) -> None:  # noqa: D401 - Qt signature
        if not self.phase_active:
            return

        radius = self.metrics.button_radius if self.metrics is not None else 22
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["timer_bg"]))
        painter.drawRoundedRect(self.rect(), radius, radius)
