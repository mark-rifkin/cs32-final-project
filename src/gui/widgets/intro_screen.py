from __future__ import annotations

"""Intro / splash screen shown before the first clue begins.

This version is intentionally simple:
- no QGraphicsOpacityEffect
- no button shadows
- explicit painted blue background
- loading tile swaps directly into a Start button of the same size
- no Tutorial or Settings controls in this version
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QStackedLayout, QVBoxLayout, QWidget

from src.gui.gui_theme import COLORS, Metrics, intro_start_button_qss


class LoadingLogoWidget(QWidget):
    """Three-circle loading mark with a moving red center disc."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.active_index = 1

        self.timer = QTimer(self)
        self.timer.setInterval(240)
        self.timer.timeout.connect(self._advance)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def start_animation(self) -> None:
        if not self.timer.isActive():
            self.timer.start()

    def stop_animation(self) -> None:
        self.timer.stop()

    def _advance(self) -> None:
        self.active_index = (self.active_index + 1) % 3
        self.update()

    def paintEvent(self, event) -> None:  # noqa: D401 - Qt signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(8, 8, -8, -8)
        shadow_rect = rect.translated(0, 8)

        # Keep the logo shadow only. Button shadows are intentionally removed.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["shadow"]))
        painter.drawRoundedRect(shadow_rect, rect.height() * 0.18, rect.height() * 0.18)

        painter.setBrush(QColor(COLORS["panel"]))
        painter.drawRoundedRect(rect, rect.height() * 0.18, rect.height() * 0.18)

        socket_y = rect.center().y()
        ring_outer = rect.height() * 0.34
        ring_inner = ring_outer * 0.72
        x_spacing = rect.width() / 3.0

        centers: list[tuple[float, float]] = []
        for i in range(3):
            cx = rect.left() + x_spacing * (i + 0.5)
            centers.append((cx, socket_y))

            outer_path = QPainterPath()
            inner_path = QPainterPath()
            outer_path.addEllipse(cx - ring_outer, socket_y - ring_outer, ring_outer * 2, ring_outer * 2)
            inner_path.addEllipse(cx - ring_inner, socket_y - ring_inner, ring_inner * 2, ring_inner * 2)
            ring_path = outer_path.subtracted(inner_path)

            painter.setBrush(QColor("#f4f4f4"))
            painter.drawPath(ring_path)

        active_cx, active_cy = centers[self.active_index]
        disc_r = ring_inner * 0.78

        painter.setBrush(QColor("#7d1100"))
        painter.drawEllipse(active_cx - disc_r, active_cy - disc_r + 4, disc_r * 2, disc_r * 2)

        painter.setBrush(QColor(COLORS["red"]))
        painter.drawEllipse(active_cx - disc_r, active_cy - disc_r, disc_r * 2, disc_r * 2)


class IntroScreen(QWidget):
    """Startup screen with wordmark, loading logo, and Start tile."""

    start_requested = Signal()

    WORDMARK_PATH = Path(__file__).resolve().parents[3] / "assets" / "ui" / "podium_wordmark.png"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.metrics: Metrics | None = None
        self.is_ready = False

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)

        self.root = QVBoxLayout(self)
        self.root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.wordmark_label = QLabel()
        self.wordmark_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wordmark_label.setStyleSheet("background: transparent;")

        self.wordmark_fallback = QLabel("PODIUM")
        self.wordmark_fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wordmark_fallback.setStyleSheet("background: transparent;")
        self.wordmark_fallback.hide()

        # Stage is the exact fixed box used by both loading logo and Start.
        self.stage = QWidget()
        self.stage.setStyleSheet("background: transparent;")
        self.stage_stack = QStackedLayout(self.stage)
        self.stage_stack.setContentsMargins(0, 0, 0, 0)

        self.loading_page = QWidget()
        self.loading_page.setStyleSheet("background: transparent;")
        self.loading_layout = QVBoxLayout(self.loading_page)
        self.loading_layout.setContentsMargins(0, 0, 0, 0)
        self.loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.loading_logo = LoadingLogoWidget()
        self.loading_layout.addWidget(self.loading_logo, alignment=Qt.AlignmentFlag.AlignCenter)

        self.start_page = QWidget()
        self.start_page.setStyleSheet("background: transparent;")
        self.start_layout = QVBoxLayout(self.start_page)
        self.start_layout.setContentsMargins(0, 0, 0, 0)
        self.start_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.start_button = QPushButton("Start")
        self.start_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.start_button.clicked.connect(self.start_requested.emit)
        self.start_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stage_stack.addWidget(self.loading_page)
        self.stage_stack.addWidget(self.start_page)
        self.stage_stack.setCurrentWidget(self.loading_page)

        self.root.addStretch(2)
        self.root.addWidget(self.wordmark_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.root.addWidget(self.wordmark_fallback, alignment=Qt.AlignmentFlag.AlignCenter)
        self.root.addSpacing(25)
        self.root.addWidget(self.stage, alignment=Qt.AlignmentFlag.AlignCenter)
        self.root.addStretch(3)

        self.start_button.setToolTip("Start game (Space when ready)")
        self._load_wordmark_pixmap()

    def _load_wordmark_pixmap(self) -> None:
        self.wordmark_pixmap = QPixmap(str(self.WORDMARK_PATH))
        if self.wordmark_pixmap.isNull():
            self.wordmark_label.hide()
            self.wordmark_fallback.show()
        else:
            self.wordmark_label.show()
            self.wordmark_fallback.hide()

    def paintEvent(self, event) -> None:  # noqa: D401 - Qt signature
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS["intro_bg"]))

    def apply_metrics(self, m: Metrics) -> None:
        """Apply responsive sizing to the intro screen."""
        self.metrics = m

        self.root.setContentsMargins(m.outer_margin, m.outer_margin, m.outer_margin, m.outer_margin)
        self.root.setSpacing(m.intro_button_gap)

        if self.wordmark_pixmap.isNull():
            self.wordmark_fallback.setStyleSheet(
                "background: transparent;"
                f"color:{COLORS['wordmark']};"
                f"font-size:{m.banner_font * 2}px;"
                "font-weight:300;"
                "letter-spacing:4px;"
            )
        else:
            scaled = self.wordmark_pixmap.scaled(
                m.intro_wordmark_w,
                m.intro_wordmark_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.wordmark_label.setPixmap(scaled)
            self.wordmark_label.setFixedSize(scaled.size())

        # The stage fixes the loading logo and Start button to exactly the same box.
        self.stage.setFixedSize(m.intro_logo_w, m.intro_logo_h)
        self.loading_logo.setFixedSize(m.intro_logo_w, m.intro_logo_h)
        self.start_button.setFixedSize(m.intro_logo_w, m.intro_logo_h)
        self.start_button.setStyleSheet(intro_start_button_qss(m))

    def start_loading_animation(self) -> None:
        """Show the loading tile and start the red-disc animation."""
        self.is_ready = False
        self.stage_stack.setCurrentWidget(self.loading_page)
        self.loading_logo.show()
        self.loading_logo.start_animation()

    def set_ready(self) -> None:
        """Replace the loading tile with the Start button."""
        if self.is_ready:
            return

        self.is_ready = True
        self.loading_logo.stop_animation()
        self.stage_stack.setCurrentWidget(self.start_page)

    def reset_to_loading(self) -> None:
        """Return the intro screen to its loading state."""
        self.is_ready = False
        self.stage_stack.setCurrentWidget(self.loading_page)
        self.loading_logo.show()
        self.loading_logo.start_animation()
