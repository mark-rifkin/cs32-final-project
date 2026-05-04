from __future__ import annotations

"""Vertical clue-side light columns used during buzzer unlock.

The dot columns sit outside the clue card.

Important layout idea:
- The clue card geometry should not change.
- The dot gutter should be narrower.
- Dots should align toward the card-facing edge of that gutter.
- Dot rows should distribute from top to bottom, not cluster in the middle.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from src.gui.gui_theme import COLORS, Metrics


class DotColumn(QWidget):
    def __init__(
        self,
        count: int = 64,
        side: str = "left",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        if side not in {"left", "right"}:
            raise ValueError("side must be 'left' or 'right'")

        self.side = side
        self.dots: list[QFrame] = []
        self.active = False

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)

        for _ in range(count):
            dot = QFrame()
            self.dots.append(dot)

            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(0)

            # Move each dot toward the clue-card-facing edge.
            if self.side == "left":
                row.addStretch()
                row.addWidget(dot)
            else:
                row.addWidget(dot)
                row.addStretch()

            # A stretch before every row distributes rows vertically.
            self.outer.addStretch(1)
            self.outer.addLayout(row)

        # Final stretch completes the full-height distribution.
        self.outer.addStretch(1)

    def apply_metrics(self, m: Metrics) -> None:
        # Use a narrower visual gutter than the layout's historical side gutter.
        # This moves the dots closer to the clue card without changing the card.
        gutter_w = max(m.side_dot_size + 2, m.side_gutter_w // 2)
        self.setFixedWidth(gutter_w)

        # Very small vertical inset so dots nearly span the full card height.
        vertical_inset = max(2, m.side_dot_size)
        self.outer.setContentsMargins(0, vertical_inset, 0, vertical_inset)

        for dot in self.dots:
            dot.setFixedSize(m.side_dot_size, m.side_dot_size)

        self.set_active(self.active)

    def set_active(self, active: bool) -> None:
        """Keep the gutter width fixed; only change whether dots are visible."""
        self.active = active
        color = COLORS["text"] if active else "transparent"

        for dot in self.dots:
            dot.setStyleSheet(
                f"background:{color}; border-radius:{dot.width() // 2}px;"
            )