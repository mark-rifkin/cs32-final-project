from __future__ import annotations

"""Vertical clue-side light columns used during buzzer unlock."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from src.gui.gui_theme import COLORS, Metrics


class DotColumn(QWidget):
    def __init__(self, count: int = 48, parent: QWidget | None = None):
        super().__init__(parent)
        self.dots: list[QFrame] = []
        self.active = False

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 12, 0, 12)
        self.outer.setSpacing(4)

        for _ in range(count):
            dot = QFrame()
            self.dots.append(dot)

            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addStretch()
            row.addWidget(dot)
            row.addStretch()
            self.outer.addLayout(row)

        self.outer.addStretch()

    def apply_metrics(self, m: Metrics) -> None:
        self.setFixedWidth(m.side_gutter_w)
        self.outer.setContentsMargins(0, m.card_pad // 2, 0, m.card_pad // 2)
        self.outer.setSpacing(m.side_dot_gap)

        for dot in self.dots:
            dot.setFixedSize(m.side_dot_size, m.side_dot_size)

        self.set_active(self.active)

    def set_active(self, active: bool) -> None:
        """Keep the gutter width fixed; only change whether dots are visible."""
        self.active = active
        color = COLORS["text"] if active else "transparent"
        for dot in self.dots:
            dot.setStyleSheet(f"background:{color}; border-radius:{dot.width() // 2}px;")
