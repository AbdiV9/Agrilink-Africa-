"""Colours, light/dark themes and app-wide text scaling.

* ``apply_theme(page, dark, text_scale)`` sets both themes and the mode.
* ``fs(size)`` scales a font size by the user's text-size setting. Use it
  for every explicit ``size=`` so the Settings slider affects everything.
* ``palette(page)`` returns the colours for the current mode.
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

# --- Brand ----------------------------------------------------------------
PRIMARY = "#2E7D32"        # leaf green
PRIMARY_DARK = "#1B5E20"
PRIMARY_LIGHT = "#A5D6A7"
ACCENT = "#F9A825"         # harvest gold
UP = "#2E7D32"             # price up (Trading 212 style)
DOWN = "#C62828"           # price down
UP_DARK_MODE = "#66BB6A"   # brighter greens/reds read better on dark backgrounds
DOWN_DARK_MODE = "#EF5350"
WHITE = "#FFFFFF"

RADIUS = 14
PAD = 16                   # standard side gutter (phone width)
MAX_CONTENT_WIDTH = 1000   # content is centred and capped on desktop


@dataclass(frozen=True)
class Palette:
    """Colours that change between light and dark mode."""

    bg: str
    card: str
    card_alt: str
    border: str
    text: str
    muted: str
    up: str
    down: str
    chip_up_bg: str
    chip_down_bg: str


LIGHT = Palette(
    bg="#F5F7F4", card="#FFFFFF", card_alt="#EEF3EC", border="#DDE5DA",
    text="#1B1F1C", muted="#5F6B62", up=UP, down=DOWN,
    chip_up_bg="#E3F2E4", chip_down_bg="#FCE4E4",
)
DARK = Palette(
    bg="#0F1411", card="#18201B", card_alt="#202A23", border="#2C3830",
    text="#E8EEE9", muted="#9AA89E", up=UP_DARK_MODE, down=DOWN_DARK_MODE,
    chip_up_bg="#1E3A24", chip_down_bg="#3E1F1F",
)

# Module state set by apply_theme(); read by fs() and palette().
_state = {"dark": False, "text_scale": 1.0}


def fs(size: float) -> float:
    """Font size scaled by the current text-size setting."""
    return round(size * _state["text_scale"], 1)


def text_scale() -> float:
    """Current text scale (1.0 = normal)."""
    return float(_state["text_scale"])


def is_dark(page: ft.Page | None = None) -> bool:
    """True when dark mode is on."""
    if page is not None and page.theme_mode is not None:
        return page.theme_mode == ft.ThemeMode.DARK
    return bool(_state["dark"])


def palette(page: ft.Page | None = None) -> Palette:
    """Colours for the current mode."""
    return DARK if is_dark(page) else LIGHT


def trend_color(change_pct: float | None, page: ft.Page | None = None) -> str:
    """Green for up/flat, red for down."""
    pal = palette(page)
    return pal.down if (change_pct or 0) < 0 else pal.up


def _text_theme(scale: float) -> ft.TextTheme:
    """Material text styles scaled by ``scale`` (affects text without explicit sizes)."""
    sizes = {
        "display_large": 57, "display_medium": 45, "display_small": 36,
        "headline_large": 32, "headline_medium": 28, "headline_small": 24,
        "title_large": 22, "title_medium": 16, "title_small": 14,
        "body_large": 16, "body_medium": 14, "body_small": 12,
        "label_large": 14, "label_medium": 12, "label_small": 11,
    }
    return ft.TextTheme(**{name: ft.TextStyle(size=round(px * scale, 1)) for name, px in sizes.items()})


def _build_theme(dark: bool, scale: float) -> ft.Theme:
    """One ThemeData for light or dark mode."""
    pal = DARK if dark else LIGHT
    return ft.Theme(
        color_scheme_seed=PRIMARY,
        color_scheme=ft.ColorScheme(
            primary=UP_DARK_MODE if dark else PRIMARY,
            on_primary=WHITE if not dark else "#0B1F0D",
            secondary=ACCENT,
            on_secondary="#1B1F1C",
            surface=pal.card,
            on_surface=pal.text,
            on_surface_variant=pal.muted,
            outline=pal.border,
            error=pal.down,
        ),
        text_theme=_text_theme(scale),
        scaffold_bgcolor=pal.bg,
        card_color=pal.card,
        divider_color=pal.border,
        use_material3=True,
        visual_density=ft.VisualDensity.COMFORTABLE,
        page_transitions=ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.CUPERTINO,
            ios=ft.PageTransitionTheme.CUPERTINO,
            macos=ft.PageTransitionTheme.CUPERTINO,
            linux=ft.PageTransitionTheme.CUPERTINO,
            windows=ft.PageTransitionTheme.CUPERTINO,
        ),
    )


def light_theme(scale: float = 1.0) -> ft.Theme:
    """Light ThemeData."""
    return _build_theme(False, scale)


def dark_theme(scale: float = 1.0) -> ft.Theme:
    """Dark ThemeData."""
    return _build_theme(True, scale)


def apply_theme(page: ft.Page, dark: bool = False, text_scale: float = 1.0) -> None:
    """Apply light/dark mode and text scaling to the whole app."""
    scale = min(2.5, max(0.5, float(text_scale or 1.0)))
    _state["dark"] = bool(dark)
    _state["text_scale"] = scale
    page.theme = light_theme(scale)
    page.dark_theme = dark_theme(scale)
    page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
    page.bgcolor = palette(page).bg
    try:
        page.update()
    except Exception:  # page not connected yet (e.g. during start-up or tests)
        pass


# Emoji fallbacks for crop images (shown when a photo is missing or offline).
CROP_EMOJI = {
    "maize": "🌽", "beans": "🫘", "cassava": "🍠", "sorghum": "🌾", "millet": "🌾",
    "rice": "🍚", "coffee": "☕", "tea": "🍵", "tomatoes": "🍅", "onions": "🧅",
    "potatoes": "🥔", "avocado": "🥑",
}


def crop_emoji(name: str | None) -> str:
    """Emoji for a crop name (🌱 if unknown)."""
    return CROP_EMOJI.get((name or "").strip().lower(), "🌱")
