from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import QSize


COLORS = {
    "bg": "#00145e",
    "panel": "#0a22b8",
    "panel_hover": "#1430d3",
    "panel_pressed": "#081c8f",
    "text": "#f4f4f4",
    "accent": "#f7b14a",
    "red": "#d42a00",
    "green": "#6e9424",
    "light_dim": "#17309f",
    "light_on": "#d42a00",
    "pill_bg": "#1730d7",
}


def clamp(value: float, low: int, high: int) -> int:
    return max(low, min(int(value), high))


@dataclass(frozen=True)
class Metrics:
    outer_margin: int
    gap: int
    rail_width: int

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

    action_w: int
    action_h: int
    buzz_h: int
    button_radius: int
    action_font: int
    symbol_font: int

    answer_strip_h: int
    answer_strip_radius: int
    answer_light_size: int
    answer_light_gap: int


def metrics_for(size: QSize) -> Metrics:
    w = max(size.width(), 900)
    h = max(size.height(), 620)
    short = min(w, h)

    return Metrics(
        outer_margin=clamp(short * 0.03, 16, 32),
        gap=clamp(short * 0.025, 14, 28),
        rail_width=clamp(w * 0.16, 170, 230),

        banner_h=clamp(h * 0.11, 72, 108),
        banner_radius=clamp(short * 0.03, 20, 32),
        banner_font=clamp(short * 0.052, 28, 46),
        banner_pad_h=clamp(short * 0.02, 14, 24),

        card_min_h=clamp(h * 0.52, 360, 560),
        card_radius=clamp(short * 0.04, 24, 42),
        card_pad=clamp(short * 0.04, 24, 42),
        clue_font=clamp(short * 0.036, 22, 34),

        pill_radius=clamp(short * 0.02, 14, 22),
        pill_font=clamp(short * 0.022, 14, 20),
        pill_pad_v=clamp(short * 0.008, 4, 8),
        pill_pad_h=clamp(short * 0.018, 12, 20),

        side_gutter_w=clamp(short * 0.02, 14, 22),
        side_dot_size=clamp(short * 0.0045, 3, 5),
        side_dot_gap=clamp(short * 0.0045, 3, 5),

        action_w=clamp(w * 0.13, 130, 170),
        action_h=clamp(h * 0.12, 88, 118),
        buzz_h=clamp(h * 0.15, 104, 145),
        button_radius=clamp(short * 0.03, 18, 28),
        action_font=clamp(short * 0.03, 20, 28),
        symbol_font=clamp(short * 0.065, 40, 62),

        answer_strip_h=clamp(h * 0.09, 58, 86),
        answer_strip_radius=clamp(short * 0.028, 20, 28),
        answer_light_size=clamp(short * 0.018, 12, 18),
        answer_light_gap=clamp(short * 0.022, 14, 22),
    )


def banner_qss(m: Metrics) -> str:
    return f"""
    background:{COLORS['panel']};
    color:{COLORS['text']};
    border-radius:{m.banner_radius}px;
    font-size:{m.banner_font}px;
    font-weight:800;
    padding:8px {m.banner_pad_h}px;
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
    border-radius:{m.pill_radius}px;
    padding:{m.pill_pad_v}px {m.pill_pad_h}px;
    font-size:{m.pill_font}px;
    font-weight:700;
    """


def action_button_qss(m: Metrics, fg: str | None = None) -> str:
    fg = fg or COLORS["text"]
    return f"""
    QPushButton {{
        background:{COLORS['panel']};
        color:{fg};
        border:none;
        border-radius:{m.button_radius}px;
        font-size:{m.action_font}px;
        font-weight:700;
    }}
    QPushButton:hover {{
        background:{COLORS['panel_hover']};
    }}
    QPushButton:pressed {{
        background:{COLORS['panel_pressed']};
    }}
    QPushButton:disabled {{
        background:{COLORS['panel']};
        color:{fg};
    }}
    """


def symbol_button_qss(m: Metrics, fg: str) -> str:
    return f"""
    QPushButton {{
        background:{COLORS['panel']};
        color:{fg};
        border:none;
        border-radius:{m.button_radius}px;
        font-size:{m.symbol_font}px;
        font-weight:700;
    }}
    QPushButton:hover {{
        background:{COLORS['panel_hover']};
    }}
    QPushButton:pressed {{
        background:{COLORS['panel_pressed']};
    }}
    """