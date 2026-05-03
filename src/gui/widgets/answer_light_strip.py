from __future__ import annotations

"""Bottom red countdown lights shown during answer time."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

from src.gui.theme.gui_theme import COLORS, Metrics


class AnswerLightStrip(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.lights: list[QFrame] = []
        self.current_count = 0
        self.phase_active = False

        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(26, 18, 26, 18)
        self.layout_.setSpacing(22)

        for _ in range(7):
            light = QFrame()
            light.setFixedSize(18, 18)
            self.lights.append(light)
            self.layout_.addWidget(light, alignment=Qt.AlignmentFlag.AlignCenter)

        self.set_phase_active(False)

    def apply_metrics(self, m: Metrics) -> None:
        self.setFixedHeight(m.answer_strip_h)
        self.layout_.setContentsMargins(m.answer_light_gap, 14, m.answer_light_gap, 14)
        self.layout_.setSpacing(m.answer_light_gap)

        for light in self.lights:
            light.setFixedSize(m.answer_light_size, m.answer_light_size)

        self.set_phase_active(self.phase_active)
        self.set_active_count(self.current_count)

    def set_phase_active(self, active: bool) -> None:
        self.phase_active = active
        bg = COLORS["panel"] if active else "transparent"
        # The strip always occupies layout space; only the visuals change.
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
            light.setStyleSheet(f"background:{color}; border-radius:{light.width() // 2}px;")
