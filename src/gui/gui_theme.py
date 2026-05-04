from __future__ import annotations

"""Shared colors, metrics, and stylesheet helpers for the GUI.

This file keeps the visual system in one place:
- global color palette
- window-size-derived measurements
- reusable button/card/banner styles

Button shadows are intentionally not used. They add repaint complexity and made
hover behavior less reliable.
"""

from dataclasses import dataclass

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget


COLORS = {
    "bg": "#00145e",
    "panel": "#0a22b8",
    "panel_hover": "#0a22b8",
    "timer_bg": "#0a22b8",
    "panel_pressed": "#1730d7",
    "text": "#f4f4f4",
    "accent": "#f7b14a",
    "red": "#d42a00",
    "green": "#6e9424",
    "light_dim": "#00145e",
    "light_on": "#d42a00",
    "pill_bg": "#1730d7",
    "shadow": "#03125d",
    "intro_bg": "#00145e",
    "wordmark": "#a9a9a9",
}


def clamp(value: float, low: int, high: int) -> int:
    """Clamp a computed dimension into a reasonable range."""
    return max(low, min(int(value), high))


@dataclass(frozen=True)
class Metrics:
    """Window-size-derived measurements used across the GUI."""

    outer_margin: int
    gap: int
    rail_width: int
    timer_strip_w: int
    action_margin_w: int

    banner_h: int
    banner_radius: int
    banner_font: int
    banner_pad_h: int

    card_min_h: int
    card_radius: int
    card_pad: int
    clue_font: int

    pill_radius: int
    pill_font: int
    pill_pad_v: int
    pill_pad_h: int

    side_gutter_w: int
    side_dot_size: int
    side_dot_gap: int

    action_h: int
    buzz_h: int
    button_radius: int
    action_font: int
    symbol_font: int

    answer_strip_h: int
    answer_strip_radius: int
    answer_light_size: int
    answer_light_gap: int

    intro_wordmark_w: int
    intro_wordmark_h: int
    intro_logo_w: int
    intro_logo_h: int
    intro_button_w: int
    intro_button_h: int
    intro_button_gap: int
    intro_start_font: int

    shadow_offset_y: int
    shadow_blur: int


def metrics_for(size: QSize) -> Metrics:
    """Compute responsive sizing values from the current window size."""
    w = max(size.width(), 900)
    h = max(size.height(), 620)
    short = min(w, h)

    banner_h = clamp(h * 0.11, 72, 108)
    action_h = clamp(banner_h * 0.52, 42, 58)
    side_gutter_w = clamp(short * 0.02, 14, 22)
    gap = clamp(short * 0.025, 14, 28)

    return Metrics(
        outer_margin=clamp(short * 0.03, 16, 32),
        gap=gap,
        rail_width=clamp(w * 0.16, 170, 230),
        timer_strip_w=clamp(w * 0.30, 260, 420),
        # Kept for compatibility; ActionRail now mirrors the clue-card layout
        # structurally instead of using margin math.
        action_margin_w=0,

        banner_h=banner_h,
        banner_radius=clamp(short * 0.03, 20, 32),
        banner_font=clamp(short * 0.052, 28, 46),
        banner_pad_h=clamp(short * 0.02, 14, 24),

        card_min_h=clamp(h * 0.52, 360, 560),
        card_radius=clamp(short * 0.04, 24, 42),
        card_pad=clamp(short * 0.04, 24, 42),
        clue_font=clamp(short * 0.05, 30, 45),

        pill_radius=clamp((clamp(short * 0.022, 14, 20) + 2 * clamp(short * 0.008, 4, 8) + 8) / 2, 12, 22),
        pill_font=clamp(short * 0.022, 14, 20),
        pill_pad_v=clamp(short * 0.008, 4, 8),
        pill_pad_h=clamp(short * 0.018, 12, 20),

        side_gutter_w=side_gutter_w,
        side_dot_size=clamp(short * 0.0045, 3, 5),
        side_dot_gap=clamp(short * 0.0045, 3, 5),

        action_h=action_h,
        buzz_h=action_h,
        button_radius=action_h // 2,
        action_font=clamp(short * 0.03, 20, 28),
        symbol_font=clamp(short * 0.065, 40, 62),

        answer_strip_h=action_h,
        answer_strip_radius=action_h // 2,
        answer_light_size=clamp(action_h * 0.34, 13, 19),
        answer_light_gap=clamp(short * 0.014, 9, 16),

        intro_wordmark_w=clamp(w * 0.74, 560, 980),
        intro_wordmark_h=clamp(h * 0.24, 150, 260),
        intro_logo_w=clamp(w * 0.58, 460, 820),
        intro_logo_h=clamp(h * 0.22, 160, 300),
        intro_button_w=clamp(w * 0.28, 260, 380),
        intro_button_h=clamp(h * 0.11, 64, 90),
        intro_button_gap=clamp(short * 0.018, 12, 20),
        intro_start_font=clamp(short * 0.095, 54, 88),

        shadow_offset_y=0,
        shadow_blur=0,
    )


def apply_button_shadow(widget: QWidget, m: Metrics) -> None:
    """No-op helper kept for compatibility with older call sites."""
    widget.setGraphicsEffect(None)


def banner_qss(m: Metrics, font_size: int | None = None) -> str:
    font_size = font_size or m.banner_font
    return f"""
    background:{COLORS['panel']};
    color:{COLORS['text']};
    border:none;
    outline:none;
    border-radius:{m.banner_radius}px;
    font-size:{font_size}px;
    font-weight:800;
    padding:4px {m.banner_pad_h}px;
    """


def card_qss(m: Metrics) -> str:
    return f"background:{COLORS['panel']}; border-radius:{m.card_radius}px;"


def clue_text_qss(m: Metrics) -> str:
    return (
        f"color:{COLORS['text']}; "
        f"font-size:{m.clue_font}px; "
        "font-family:'Georgia'; "
        "font-weight:600;"
    )


def pill_qss(m: Metrics, fg: str) -> str:
    return f"""
    background:{COLORS['pill_bg']};
    color:{fg};
    border:none;
    outline:none;
    border-radius:{m.pill_radius}px;
    padding:{m.pill_pad_v}px {m.pill_pad_h}px;
    font-size:{m.pill_font}px;
    font-weight:700;
    """


def action_button_qss(m: Metrics, fg: str | None = None, bg: str | None = None, font_size: int | None = None) -> str:
    fg = fg or COLORS["text"]
    bg = bg or COLORS["panel"]
    font_size = font_size or m.action_font

    return f"""
    QPushButton {{
        background:{bg};
        color:{fg};
        border:none;
        outline:none;
        border-radius:{m.button_radius}px;
        font-size:{font_size}px;
        font-weight:700;
        padding:0px 12px;
    }}
    QPushButton:hover {{
        background:{bg};
    }}
    QPushButton:pressed {{
        background:{COLORS['panel_pressed']};
    }}
    QPushButton:focus {{
        border:none;
        outline:none;
    }}
    """


def intro_start_button_qss(m: Metrics) -> str:
    """Large intro Start tile style."""
    return f"""
    QPushButton {{
        background:{COLORS['panel']};
        color:{COLORS['text']};
        border:none;
        outline:none;
        border-radius:{m.button_radius}px;
        font-size:{m.intro_start_font}px;
        font-weight:800;
        padding:0px;
    }}
    QPushButton:hover {{
        background:{COLORS['panel']};
        border:none;
        outline:none;
    }}
    QPushButton:pressed {{
        background:{COLORS['panel_pressed']};
        border:none;
        outline:none;
    }}
    QPushButton:focus {{
        border:none;
        outline:none;
    }}
    """


def symbol_button_qss(m: Metrics, fg: str, font_size: int | None = None) -> str:
    font_size = font_size or m.symbol_font
    return f"""
    QPushButton {{
        background:{COLORS['panel']};
        color:{fg};
        border:none;
        outline:none;
        border-radius:{m.button_radius}px;
        font-size:{font_size}px;
        font-weight:700;
        padding:0px;
    }}
    QPushButton:hover {{
        background:{COLORS['panel']};
        border:none;
        outline:none;
    }}
    QPushButton:pressed {{
        background:{COLORS['panel_pressed']};
        border:none;
        outline:none;
    }}
    QPushButton:disabled {{
        background:{COLORS['panel']};
        color:{fg};
        border:none;
        outline:none;
    }}
    """
