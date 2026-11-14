# Owner: Person 2 (Frontend Flet UI Lead)
"""Reusable widgets for every AgriLink page.

Main pieces (from the spec): nav_bar, crop_card, price_chart, price_header,
search_bar_with_filters, weather_card, alert_tile, loading_spinner,
error_banner, empty_state. Plus small helpers: app_view (standard page
scaffold), sparkline, change_chip, verified_badge, star_rating,
section_title, format_money and show_snack.

All sizes go through ``theme.fs()`` so the text-size setting applies.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Sequence

import flet as ft

from UI import theme
from UI.theme import ACCENT, PAD, PRIMARY, RADIUS, crop_emoji, fs, palette

Handler = Callable[..., Any] | None

NAV_TABS: list[tuple[str, str, str, str]] = [
    # route, icon, selected icon, label
    ("/home", ft.Icons.HOME_OUTLINED, ft.Icons.HOME, "Home"),
    ("/market", ft.Icons.STOREFRONT_OUTLINED, ft.Icons.STOREFRONT, "Market"),
    ("/sell", ft.Icons.ADD_BOX_OUTLINED, ft.Icons.ADD_BOX, "Sell"),
    ("/messages", ft.Icons.CHAT_BUBBLE_OUTLINE, ft.Icons.CHAT_BUBBLE, "Messages"),
    ("/settings", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings"),
]

CHART_RANGES: dict[str, int] = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
SORT_LABELS: dict[str, str] = {"newest": "Newest first", "price_asc": "Price: low to high",
                               "price_desc": "Price: high to low"}


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def format_money(amount: float | None, currency: str = "KES", decimals: int = 2) -> str:
    """'KES 1,234.50' (or '—' when unknown)."""
    if amount is None:
        return "—"
    return f"{currency} {amount:,.{decimals}f}"


def format_pct(pct: float | None) -> str:
    """'+2.35%' / '-1.10%'."""
    value = pct or 0.0
    return f"{'+' if value >= 0 else ''}{value:.2f}%"


def short_date(iso: str) -> str:
    """'2026-11-13' -> '13 Nov'."""
    try:
        return date.fromisoformat(iso[:10]).strftime("%d %b").lstrip("0")
    except (ValueError, TypeError):
        return iso or ""


def tr(key: str, default: str, **fmt: Any) -> str:
    """Translated UI string via ``Auth.translation.t(key)``, else ``default``.

    Phase 5 provides the dictionary; until then (or for unknown keys) the
    English ``default`` is used. ``fmt`` values fill ``{placeholders}``.
    """
    text = default
    try:
        from Auth.translation import t

        value = t(key, default)
        if value and value != key:
            text = value
    except Exception:  # translation module missing or failing: English
        pass
    try:
        return text.format(**fmt) if fmt else text
    except (KeyError, IndexError, ValueError):
        return default.format(**fmt) if fmt else default


def show_snack(page: ft.Page, message: str, error: bool = False) -> None:
    """Show a short SnackBar message at the bottom of the screen."""
    pal = palette(page)
    page.open(ft.SnackBar(
        content=ft.Text(message, color=theme.WHITE, size=fs(14)),
        bgcolor=pal.down if error else PRIMARY,
        behavior=ft.SnackBarBehavior.FLOATING,
        show_close_icon=True,
    ))


# --------------------------------------------------------------------------
# Page scaffold and navigation
# --------------------------------------------------------------------------
def nav_bar(page: ft.Page, selected: str = "/home", unread: int = 0) -> ft.NavigationBar:
    """Bottom navigation: Home, Market, Sell, Messages, Settings.

    ``selected`` is a route ('/market', '/crop/3' selects nothing special and
    falls back to the closest tab). ``unread`` shows a badge on Messages.
    """
    index = next((i for i, tab in enumerate(NAV_TABS) if selected.startswith(tab[0])), 0)
    destinations = []
    for route, icon, selected_icon, label in NAV_TABS:
        if route == "/messages" and unread:
            badge = ft.Badge(text=str(unread) if unread < 100 else "99+", bgcolor=ACCENT, text_color="#1B1F1C")
            destinations.append(ft.NavigationBarDestination(
                label=tr(f"nav.{label.lower()}", label), icon=ft.Icon(icon, badge=badge),
                selected_icon=ft.Icon(selected_icon, badge=badge)))
        else:
            destinations.append(ft.NavigationBarDestination(label=tr(f"nav.{label.lower()}", label), icon=icon,
                                                            selected_icon=selected_icon))
    return ft.NavigationBar(
        selected_index=index,
        destinations=destinations,
        indicator_color=ft.Colors.with_opacity(0.18, PRIMARY),
        on_change=lambda e: page.go(NAV_TABS[e.control.selected_index][0]),
        height=fs(68),
    )


def confirm_logout(page: ft.Page) -> None:
    """Ask "Log out?" and, if confirmed, clear the session and go to /login."""
    pal = palette(page)

    def do_logout(e: ft.ControlEvent) -> None:
        page.close(dlg)
        from Auth.auth import logout  # imported here so UI previews work without Auth

        logout()
        theme.apply_theme(page, dark=False, text_scale=1.0)
        page.go("/login")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(tr("settings.logout_q", "Log out?")),
        content=ft.Text(tr("settings.logout_body", "You'll need your password to log back in.")),
        actions=[ft.TextButton(tr("common.cancel", "Cancel"), on_click=lambda e: page.close(dlg)),
                 ft.FilledButton(tr("settings.logout", "Log out"), on_click=do_logout,
                                 style=ft.ButtonStyle(bgcolor=pal.down, color="white"))],
    )
    page.open(dlg)


def logout_button(page: ft.Page) -> ft.IconButton:
    """App-bar logout icon (shown on every main tab)."""
    return ft.IconButton(ft.Icons.LOGOUT, icon_color=theme.WHITE, icon_size=fs(24),
                         tooltip=tr("settings.logout", "Log out"), on_click=lambda e: confirm_logout(page))


_INPUT_TYPES = (ft.TextField, ft.Dropdown)
_CHILD_ATTRS = ("controls", "content", "tabs", "actions", "leading", "title", "subtitle", "trailing")


def style_inputs(root: Any, page: ft.Page | None = None) -> None:
    """Give every TextField/Dropdown under ``root`` clear, high-contrast colours.

    Flet 0.28 has no input theme, so main.py calls this on each built view.
    Only attributes a page didn't set itself are changed.
    """
    pal = palette(page)
    accent = PRIMARY if not theme.is_dark(page) else pal.up
    wanted = {
        "color": pal.text, "border_color": pal.border, "focused_border_color": accent, "cursor_color": accent,
        "filled": True, "fill_color": pal.card, "bgcolor": pal.card,
        "label_style": ft.TextStyle(color=pal.muted, size=fs(14), weight=ft.FontWeight.W_500),
        "helper_style": ft.TextStyle(color=pal.muted, size=fs(12)),
        "hint_style": ft.TextStyle(color=pal.muted, size=fs(14)),
        "focused_border_width": 2, "border_width": 1.5,
    }
    seen: set[int] = set()

    def walk(ctl: Any) -> None:
        if ctl is None or id(ctl) in seen:
            return
        seen.add(id(ctl))
        if isinstance(ctl, _INPUT_TYPES):
            for name, value in wanted.items():
                try:
                    if getattr(ctl, name, None) is None:
                        setattr(ctl, name, value)
                except Exception:  # attribute not supported by this control/version
                    pass
            if isinstance(ctl, ft.TextField) and ctl.text_size is None:
                ctl.text_size = fs(15)
        for attr in _CHILD_ATTRS:
            try:
                child = getattr(ctl, attr, None)
            except Exception:
                continue
            for item in child if isinstance(child, list) else [child]:
                if isinstance(item, (ft.Control, ft.Tab)):
                    walk(item)

    walk(root)


def app_view(
    page: ft.Page,
    route: str,
    title: str,
    controls: Sequence[ft.Control],
    nav: str | None = None,
    actions: list[ft.Control] | None = None,
    unread: int = 0,
    fab: ft.FloatingActionButton | None = None,
    scroll: bool = True,
    show_appbar: bool = True,
    padding: int = PAD,
) -> ft.View:
    """Standard page: app bar, centred content capped at MAX_CONTENT_WIDTH, optional nav bar.

    Pass ``nav='/market'`` etc. on top-level tabs; leave it None on detail
    pages (they get a back arrow automatically when a view is underneath).
    """
    pal = palette(page)
    if nav:  # main tabs always offer a way to log out
        actions = (actions or []) + [logout_button(page)]
    body = ft.Container(
        content=ft.Column(list(controls), spacing=14, tight=False,
                          scroll=ft.ScrollMode.AUTO if scroll else None, expand=True),
        padding=ft.padding.symmetric(horizontal=padding, vertical=12),
        width=theme.MAX_CONTENT_WIDTH,
        expand=True,
    )
    return ft.View(
        route=route,
        bgcolor=pal.bg,
        padding=0,
        appbar=ft.AppBar(
            title=ft.Text(title, size=fs(20), weight=ft.FontWeight.W_700, color=theme.WHITE),
            bgcolor=PRIMARY,
            color=theme.WHITE,
            actions=(actions or []) + [ft.Container(width=4)],
            center_title=False,
        ) if show_appbar else None,
        navigation_bar=nav_bar(page, nav, unread) if nav else None,
        floating_action_button=fab,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[ft.Row([body], alignment=ft.MainAxisAlignment.CENTER, expand=True,
                         vertical_alignment=ft.CrossAxisAlignment.START)],
    )


def section_title(text: str, action_text: str | None = None, on_action: Handler = None) -> ft.Row:
    """Bold section heading with an optional 'See all' style link on the right."""
    controls: list[ft.Control] = [ft.Text(text, size=fs(18), weight=ft.FontWeight.W_700, expand=True)]
    if action_text:
        controls.append(ft.TextButton(action_text, on_click=on_action))
    return ft.Row(controls, vertical_alignment=ft.CrossAxisAlignment.CENTER)


# --------------------------------------------------------------------------
# Small badges
# --------------------------------------------------------------------------
def change_chip(change_pct: float | None, page: ft.Page | None = None, size: float = 13) -> ft.Container:
    """Green/red pill with an arrow and the % change."""
    pal = palette(page)
    up = (change_pct or 0) >= 0
    color = pal.up if up else pal.down
    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.ARROW_DROP_UP if up else ft.Icons.ARROW_DROP_DOWN, color=color, size=fs(size + 5)),
            ft.Text(format_pct(change_pct), color=color, size=fs(size), weight=ft.FontWeight.W_600),
        ], spacing=0, tight=True),
        bgcolor=pal.chip_up_bg if up else pal.chip_down_bg,
        border_radius=20,
        padding=ft.padding.only(left=4, right=10, top=2, bottom=2),
    )


def verified_badge(size: float = 16, label: bool = False) -> ft.Control:
    """Blue tick (✔) for verified farmers, optionally with 'Verified' text."""
    icon = ft.Icon(ft.Icons.VERIFIED, color=palette().info, size=fs(size), tooltip="Verified farmer")
    if not label:
        return icon
    return ft.Row([icon, ft.Text("Verified", size=fs(size - 3), color=palette().info, weight=ft.FontWeight.W_600)],
                  spacing=3, tight=True)


def star_rating(rating: float | None, count: int | None = None, size: float = 16) -> ft.Row:
    """★★★★½ (12)"""
    value = rating or 0.0
    stars: list[ft.Control] = []
    for i in range(1, 6):
        if value >= i:
            icon = ft.Icons.STAR
        elif value >= i - 0.5:
            icon = ft.Icons.STAR_HALF
        else:
            icon = ft.Icons.STAR_BORDER
        stars.append(ft.Icon(icon, color=ACCENT, size=fs(size)))
    if count is not None:
        stars.append(ft.Text(f" {value:.1f} ({count})", size=fs(size - 3), color=palette().muted))
    return ft.Row(stars, spacing=0, tight=True)


# --------------------------------------------------------------------------
# Images and cards
# --------------------------------------------------------------------------
def crop_image(image_url: str | None, crop_name: str | None, height: float = 120,
               radius: float = RADIUS) -> ft.Control:
    """Crop photo from UI/assets, falling back to a big emoji on a tinted tile."""
    fallback = ft.Container(
        content=ft.Text(crop_emoji(crop_name), size=height * 0.42),
        alignment=ft.alignment.center,
        bgcolor=palette().card_alt,
        height=height,
        border_radius=radius,
    )
    if not image_url:
        return fallback
    src = image_url if image_url.startswith(("http://", "https://", "/")) else f"/{image_url}"
    return ft.Container(
        content=ft.Image(src=src, fit=ft.ImageFit.COVER, height=height, error_content=fallback,
                         border_radius=radius),
        height=height,
        border_radius=radius,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        bgcolor=palette().card_alt,
    )


def crop_card(
    listing: dict[str, Any],
    on_click: Handler = None,
    on_heart: Handler = None,
    hearted: bool = False,
    col: dict[str, int] | None = None,
) -> ft.Container:
    """Depop-style listing card: photo, heart, crop, price/unit, location, seller ✔.

    ``listing`` is a row from ``search_listings``. ``on_click(listing)`` opens
    the listing; ``on_heart(listing, hearted_now)`` toggles the watchlist.
    """
    pal = palette()
    heart = ft.IconButton(
        icon=ft.Icons.FAVORITE if hearted else ft.Icons.FAVORITE_BORDER,
        icon_color=pal.down if hearted else theme.WHITE,
        icon_size=fs(20),
        bgcolor=ft.Colors.with_opacity(0.35, "#000000"),
        tooltip="Watch this crop",
        data=hearted,
    )

    def toggle_heart(e: ft.ControlEvent) -> None:
        heart.data = not heart.data
        heart.icon = ft.Icons.FAVORITE if heart.data else ft.Icons.FAVORITE_BORDER
        heart.icon_color = pal.down if heart.data else theme.WHITE
        heart.update()
        if on_heart:
            on_heart(listing, heart.data)

    heart.on_click = toggle_heart
    seller_row: list[ft.Control] = [
        ft.Icon(ft.Icons.PERSON_OUTLINE, size=fs(14), color=pal.muted),
        ft.Text(listing.get("seller_username", ""), size=fs(12), color=pal.muted,
                overflow=ft.TextOverflow.ELLIPSIS, expand=True),
    ]
    if listing.get("seller_verified"):
        seller_row.insert(2, verified_badge(14))
    unit = listing.get("unit", "kg")
    return ft.Container(
        col=col or {"xs": 6, "sm": 4, "md": 3},
        bgcolor=pal.card,
        border_radius=RADIUS,
        border=ft.border.all(1, pal.border),
        padding=8,
        ink=True,
        on_click=(lambda e: on_click(listing)) if on_click else None,
        content=ft.Column([
            ft.Stack([
                crop_image(listing.get("image_url"), listing.get("crop_name"), height=fs(118)),
                ft.Container(heart, right=4, top=4),
            ]),
            ft.Text(listing.get("crop_name", ""), size=fs(15), weight=ft.FontWeight.W_700, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(f"{format_money(listing.get('price_per_unit'), listing.get('currency', 'KES'))}/{unit}",
                    size=fs(14), weight=ft.FontWeight.W_600, color=PRIMARY if not theme.is_dark() else pal.up),
            ft.Text(f"{listing.get('quantity', 0):g} {unit} available", size=fs(12), color=pal.muted),
            ft.Row([ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=fs(14), color=pal.muted),
                    ft.Text(listing.get("location") or "—", size=fs(12), color=pal.muted,
                            overflow=ft.TextOverflow.ELLIPSIS, expand=True)], spacing=2),
            ft.Row(seller_row, spacing=3),
        ], spacing=3),
    )


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def sparkline(prices: Sequence[float], width: float = 90, height: float = 36,
              color: str | None = None) -> ft.Control:
    """Tiny trend line with no axes (for watchlist and Markets rows)."""
    values = [float(p) for p in prices if p is not None]
    if len(values) < 2:
        return ft.Container(width=width, height=height)
    line_color = color or theme.trend_color(values[-1] - values[0])
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.1 or 1
    return ft.Container(
        width=width,
        height=height,
        content=ft.LineChart(
            data_series=[ft.LineChartData(
                data_points=[ft.LineChartDataPoint(i, v) for i, v in enumerate(values)],
                color=line_color, stroke_width=2, curved=True, point=False,
            )],
            min_y=lo - pad, max_y=hi + pad, min_x=0, max_x=len(values) - 1,
            interactive=False,
            left_axis=ft.ChartAxis(show_labels=False, labels_size=0),
            bottom_axis=ft.ChartAxis(show_labels=False, labels_size=0),
        ),
    )


def price_header(
    crop_name: str,
    price: float | None,
    change_pct: float | None,
    unit: str = "kg",
    currency: str = "KES",
    subtitle: str | None = None,
    page: ft.Page | None = None,
) -> ft.Column:
    """Trading 212-style header: crop name, BIG price, % chip and '1 week' note."""
    pal = palette(page)
    return ft.Column([
        ft.Row([ft.Text(crop_emoji(crop_name), size=fs(26)),
                ft.Text(crop_name, size=fs(20), weight=ft.FontWeight.W_700)], spacing=8),
        ft.Row([
            ft.Text(format_money(price, currency), size=fs(34), weight=ft.FontWeight.W_800),
            ft.Text(f"/{unit}", size=fs(16), color=pal.muted),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.END, wrap=True),
        ft.Row([change_chip(change_pct, page), ft.Text("past week", size=fs(13), color=pal.muted)], spacing=8),
        *([ft.Text(subtitle, size=fs(12), color=pal.muted)] if subtitle else []),
    ], spacing=4)


class PriceChart(ft.Column):
    """Interactive price chart with a 1W/1M/3M/1Y selector.

    * Line is green when the visible range went up, red when it went down,
      with a matching gradient fill underneath.
    * Hover/tap shows a tooltip with the date and price.
    * ``set_prediction(points)`` / ``show_prediction`` add a dashed gold
      forecast line that continues from the last real price.
    """

    def __init__(
        self,
        history: list[dict[str, Any]],
        prediction: list[dict[str, Any]] | None = None,
        initial_range: str = "3M",
        height: float = 240,
        currency: str = "KES",
        show_prediction: bool = False,
        on_range_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(spacing=8)
        self.history = sorted(history or [], key=lambda r: r["date"])
        self.prediction = prediction or []
        self.range = initial_range if initial_range in CHART_RANGES else "3M"
        self.currency = currency
        self.show_prediction = show_prediction
        self.on_range_change = on_range_change
        self.chart_height = height
        self.selector = ft.SegmentedButton(
            segments=[ft.Segment(value=k, label=ft.Text(k, size=fs(13))) for k in CHART_RANGES],
            selected={self.range},
            show_selected_icon=False,
            on_change=self._range_changed,
        )
        self.chart_box = ft.Container(height=height)
        self.controls = [self.chart_box, ft.Row([self.selector], alignment=ft.MainAxisAlignment.CENTER)]
        self._render()

    # -- public ------------------------------------------------------------
    def set_prediction(self, prediction: list[dict[str, Any]] | None, show: bool = True) -> None:
        """Replace the forecast series and redraw."""
        self.prediction = prediction or []
        self.show_prediction = show
        self._render(update=True)

    def toggle_prediction(self, show: bool) -> None:
        """Show or hide the dashed forecast line."""
        self.show_prediction = show
        self._render(update=True)

    def visible_change_pct(self) -> float:
        """% change across the currently selected range."""
        rows = self._visible_rows()
        if len(rows) < 2 or not rows[0]["price"]:
            return 0.0
        return round((rows[-1]["price"] - rows[0]["price"]) / rows[0]["price"] * 100, 2)

    # -- internals -----------------------------------------------------------
    def _visible_rows(self) -> list[dict[str, Any]]:
        return self.history[-CHART_RANGES[self.range]:]

    def _range_changed(self, e: ft.ControlEvent) -> None:
        self.range = next(iter(e.control.selected))
        self._render(update=True)
        if self.on_range_change:
            self.on_range_change(self.range)

    def _render(self, update: bool = False) -> None:
        rows = self._visible_rows()
        pal = palette()
        if len(rows) < 2:
            self.chart_box.content = ft.Container(
                ft.Text("No price data yet", color=pal.muted, size=fs(14)), alignment=ft.alignment.center)
            if update:
                self.update()
            return

        color = theme.trend_color(rows[-1]["price"] - rows[0]["price"])
        points = [
            ft.LineChartDataPoint(i, r["price"], tooltip=f"{short_date(r['date'])}\n{format_money(r['price'], self.currency)}")
            for i, r in enumerate(rows)
        ]
        series = [ft.LineChartData(
            data_points=points, color=color, stroke_width=2.5, curved=True, point=False,
            prevent_curve_over_shooting=True,
            below_line_gradient=ft.LinearGradient(
                begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                colors=[ft.Colors.with_opacity(0.35, color), ft.Colors.with_opacity(0.0, color)],
            ),
        )]
        all_prices = [r["price"] for r in rows]
        labels_source = list(rows)

        if self.show_prediction and self.prediction:
            start = len(rows) - 1
            pred_points = [ft.LineChartDataPoint(start, rows[-1]["price"], show_tooltip=False)]
            for j, p in enumerate(self.prediction, start=1):
                pred_points.append(ft.LineChartDataPoint(
                    start + j, p["predicted_price"],
                    tooltip=f"{short_date(p['date'])} (forecast)\n{format_money(p['predicted_price'], self.currency)}",
                ))
                all_prices.append(p["predicted_price"])
                labels_source.append({"date": p["date"]})
            series.append(ft.LineChartData(
                data_points=pred_points, color=ACCENT, stroke_width=2.5, dash_pattern=[6, 4],
                curved=True, point=False,
            ))

        lo, hi = min(all_prices), max(all_prices)
        pad = (hi - lo) * 0.08 or max(1.0, hi * 0.05)
        n = len(labels_source)
        step = max(1, (n - 1) // 4)
        bottom_labels = [
            ft.ChartAxisLabel(value=i, label=ft.Text(short_date(labels_source[i]["date"]), size=fs(10), color=pal.muted))
            for i in range(0, n, step)
        ]
        self.chart_box.content = ft.LineChart(
            data_series=series,
            min_x=0, max_x=n - 1,
            min_y=max(0, lo - pad), max_y=hi + pad,
            interactive=True,
            tooltip_bgcolor=ft.Colors.with_opacity(0.92, pal.card_alt),
            horizontal_grid_lines=ft.ChartGridLines(color=ft.Colors.with_opacity(0.4, pal.border), width=1),
            left_axis=ft.ChartAxis(labels_size=fs(46), show_labels=True),
            bottom_axis=ft.ChartAxis(labels=bottom_labels, labels_size=fs(24)),
            border=ft.Border(bottom=ft.BorderSide(1, pal.border)),
            expand=True,
        )
        if update:
            self.update()


def price_chart(
    history: list[dict[str, Any]],
    prediction: list[dict[str, Any]] | None = None,
    initial_range: str = "3M",
    height: float = 240,
    currency: str = "KES",
    show_prediction: bool = False,
    on_range_change: Callable[[str], None] | None = None,
) -> PriceChart:
    """Build a :class:`PriceChart` (history = ``get_price_history`` rows)."""
    return PriceChart(history, prediction, initial_range, height, currency, show_prediction, on_range_change)


# --------------------------------------------------------------------------
# Search and filters
# --------------------------------------------------------------------------
class SearchBarWithFilters(ft.Row):
    """Search box plus a filter button that opens a bottom sheet.

    Calls ``on_search(filters)`` where ``filters`` has exactly the keyword
    arguments of ``Market_Queries.search_listings``: query, crop_id,
    min_price, max_price, location, sort.
    """

    def __init__(self, page: ft.Page, crops: list[dict[str, Any]],
                 on_search: Callable[[dict[str, Any]], None],
                 initial: dict[str, Any] | None = None) -> None:
        super().__init__(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self._page = page
        self.on_search = on_search
        self.filters: dict[str, Any] = {"query": "", "crop_id": None, "min_price": None,
                                        "max_price": None, "location": None, "sort": "newest"}
        self.filters.update(initial or {})
        pal = palette(page)

        self.query_field = ft.TextField(
            hint_text="Search crops, places, sellers…",
            value=self.filters["query"],
            prefix_icon=ft.Icons.SEARCH,
            border_radius=28,
            filled=True,
            dense=True,
            text_size=fs(14),
            expand=True,
            on_submit=lambda e: self._run(),
        )
        self.filter_button = ft.IconButton(ft.Icons.TUNE, tooltip="Filters", on_click=self._open_sheet,
                                           icon_color=PRIMARY if not theme.is_dark() else pal.up)
        self.controls = [self.query_field, self.filter_button]

        # Bottom sheet fields
        self.crop_dd = ft.Dropdown(
            label="Crop", value=str(self.filters["crop_id"] or "all"), dense=True,
            options=[ft.dropdown.Option("all", "All crops")]
            + [ft.dropdown.Option(str(c["id"]), f"{crop_emoji(c['name'])} {c['name']}") for c in crops],
        )
        self.min_field = ft.TextField(label="Min price", keyboard_type=ft.KeyboardType.NUMBER, dense=True,
                                      expand=True, value=self._fmt(self.filters["min_price"]))
        self.max_field = ft.TextField(label="Max price", keyboard_type=ft.KeyboardType.NUMBER, dense=True,
                                      expand=True, value=self._fmt(self.filters["max_price"]))
        self.location_field = ft.TextField(label="Location", prefix_icon=ft.Icons.LOCATION_ON_OUTLINED,
                                           dense=True, value=self.filters["location"] or "")
        self.sort_dd = ft.Dropdown(
            label="Sort by", value=self.filters["sort"], dense=True,
            options=[ft.dropdown.Option(k, v) for k, v in SORT_LABELS.items()],
        )
        self.sheet = ft.BottomSheet(
            show_drag_handle=True,
            is_scroll_controlled=True,
            content=ft.Container(
                padding=ft.padding.only(left=PAD, right=PAD, bottom=PAD),
                content=ft.Column([
                    ft.Text("Filters", size=fs(18), weight=ft.FontWeight.W_700),
                    self.crop_dd,
                    ft.Row([self.min_field, self.max_field], spacing=10),
                    self.location_field,
                    self.sort_dd,
                    ft.Row([
                        ft.OutlinedButton("Reset", on_click=self._reset, expand=True),
                        ft.FilledButton("Apply", on_click=self._apply, expand=True),
                    ], spacing=10),
                ], tight=True, spacing=12, scroll=ft.ScrollMode.AUTO),
            ),
        )
        self._refresh_button()

    @staticmethod
    def _fmt(value: Any) -> str:
        return "" if value in (None, "") else f"{float(value):g}"

    def active_filter_count(self) -> int:
        """How many filters (besides the text query and sort) are set."""
        return sum(1 for k in ("crop_id", "min_price", "max_price", "location") if self.filters.get(k))

    def _refresh_button(self) -> None:
        count = self.active_filter_count()
        self.filter_button.badge = ft.Badge(text=str(count), bgcolor=ACCENT) if count else None

    def _open_sheet(self, e: ft.ControlEvent) -> None:
        self._page.open(self.sheet)

    def _parse_price(self, field: ft.TextField) -> tuple[bool, float | None]:
        raw = (field.value or "").strip()
        field.error_text = None
        if not raw:
            return True, None
        try:
            value = float(raw)
        except ValueError:
            field.error_text = "Numbers only"
            return False, None
        if value < 0:
            field.error_text = "Can't be negative"
            return False, None
        return True, value

    def _apply(self, e: ft.ControlEvent) -> None:
        ok_min, min_price = self._parse_price(self.min_field)
        ok_max, max_price = self._parse_price(self.max_field)
        if ok_min and ok_max and min_price is not None and max_price is not None and min_price > max_price:
            self.max_field.error_text = "Must be ≥ min"
            ok_max = False
        if not (ok_min and ok_max):
            self.sheet.update()
            return
        self.filters.update({
            "crop_id": None if self.crop_dd.value in (None, "all") else int(self.crop_dd.value),
            "min_price": min_price,
            "max_price": max_price,
            "location": (self.location_field.value or "").strip() or None,
            "sort": self.sort_dd.value or "newest",
        })
        self._page.close(self.sheet)
        self._run()

    def _reset(self, e: ft.ControlEvent) -> None:
        self.crop_dd.value = "all"
        self.min_field.value = self.max_field.value = self.location_field.value = ""
        self.min_field.error_text = self.max_field.error_text = None
        self.sort_dd.value = "newest"
        self.sheet.update()

    def _run(self) -> None:
        self.filters["query"] = (self.query_field.value or "").strip()
        self._refresh_button()
        self.update()
        self.on_search(dict(self.filters))


def search_bar_with_filters(page: ft.Page, crops: list[dict[str, Any]],
                            on_search: Callable[[dict[str, Any]], None],
                            initial: dict[str, Any] | None = None) -> SearchBarWithFilters:
    """Build a :class:`SearchBarWithFilters`."""
    return SearchBarWithFilters(page, crops, on_search, initial)


# --------------------------------------------------------------------------
# Weather
# --------------------------------------------------------------------------
def weather_icon(code: int | None) -> tuple[str, str]:
    """(icon, colour) for a WMO weather code as returned by Open-Meteo."""
    c = code if code is not None else 0
    if c == 0:
        return ft.Icons.WB_SUNNY, ACCENT
    if c in (1, 2):
        return ft.Icons.WB_CLOUDY, ACCENT
    if c == 3:
        return ft.Icons.CLOUD, palette().muted
    if c in (45, 48):
        return ft.Icons.FOGGY, palette().muted
    if 51 <= c <= 67 or 80 <= c <= 82:
        return ft.Icons.WATER_DROP, palette().info
    if 71 <= c <= 77 or c in (85, 86):
        return ft.Icons.AC_UNIT, palette().info
    if c >= 95:
        return ft.Icons.THUNDERSTORM, "#3949AB" if not theme.is_dark() else "#9FA8DA"
    return ft.Icons.CLOUD, palette().muted


def weather_card(forecast: dict[str, Any] | None, page: ft.Page | None = None) -> ft.Container:
    """Today's weather plus a 7-day strip.

    ``forecast`` format (from Auth.weather):
    ``{"region", "source": "live"|"cache"|"sample", "days": [{"date", "t_max",
    "t_min", "rain_mm", "rain_chance", "condition", "code"}]}``
    """
    pal = palette(page)
    if not forecast or not forecast.get("days"):
        return ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.CLOUD_OFF, color=pal.muted),
                            ft.Text("Weather is unavailable right now.", color=pal.muted, size=fs(14))]),
            padding=PAD, bgcolor=pal.card, border_radius=RADIUS, border=ft.border.all(1, pal.border),
        )
    days = forecast["days"]
    today = days[0]
    icon, icon_color = weather_icon(today.get("code"))
    note = {"cache": "Saved forecast", "sample": "Sample forecast (offline)"}.get(forecast.get("source", ""), "")

    def day_chip(d: dict[str, Any]) -> ft.Container:
        ic, col = weather_icon(d.get("code"))
        try:
            label = date.fromisoformat(d["date"]).strftime("%a")
        except (ValueError, KeyError):
            label = "—"
        return ft.Container(
            width=fs(62),
            padding=ft.padding.symmetric(vertical=8),
            border_radius=12,
            bgcolor=pal.card_alt,
            content=ft.Column([
                ft.Text(label, size=fs(12), color=pal.muted),
                ft.Icon(ic, color=col, size=fs(22)),
                ft.Text(f"{d.get('t_max', 0):.0f}°", size=fs(13), weight=ft.FontWeight.W_600),
                ft.Text(f"{d.get('rain_mm', 0):.0f}mm", size=fs(11), color=palette().info),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
        )

    return ft.Container(
        padding=PAD,
        bgcolor=pal.card,
        border_radius=RADIUS,
        border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Row([
                ft.Icon(icon, color=icon_color, size=fs(44)),
                ft.Column([
                    ft.Text(f"{today.get('t_max', 0):.0f}° / {today.get('t_min', 0):.0f}°",
                            size=fs(24), weight=ft.FontWeight.W_700),
                    ft.Text(f"{today.get('condition', '')} · {forecast.get('region', '')}", size=fs(13), color=pal.muted),
                ], spacing=0, expand=True),
                ft.Column([
                    ft.Row([ft.Icon(ft.Icons.WATER_DROP, size=fs(14), color=palette().info),
                            ft.Text(f"{today.get('rain_chance', 0):.0f}%", size=fs(13))], spacing=2, tight=True),
                    ft.Text(f"{today.get('rain_mm', 0):.1f} mm", size=fs(12), color=pal.muted),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
            ], spacing=12),
            ft.Row([day_chip(d) for d in days[:7]], spacing=6, scroll=ft.ScrollMode.AUTO),
            *([ft.Text(note, size=fs(11), color=pal.muted, italic=True)] if note else []),
        ], spacing=12),
    )


# --------------------------------------------------------------------------
# Alerts and states
# --------------------------------------------------------------------------
ALERT_STYLES: dict[str, tuple[str, str]] = {
    "price": (ft.Icons.NOTIFICATIONS_ACTIVE, ACCENT),
    "harvest": (ft.Icons.AGRICULTURE, PRIMARY),
    "season": (ft.Icons.CALENDAR_MONTH, "#4E342E"),
    "weather": (ft.Icons.THUNDERSTORM, "#0D47A1"),
    "info": (ft.Icons.INFO_OUTLINE, "#37474F"),
}
# Lighter versions of the same colours so icons stay clear on dark cards.
ALERT_COLORS_DARK = {"price": ACCENT, "harvest": "#81C784", "season": "#BCAAA4", "weather": "#90CAF9",
                     "info": "#B0BEC5"}


def alert_tile(title: str, subtitle: str = "", kind: str = "info",
               on_click: Handler = None, on_dismiss: Handler = None) -> ft.Container:
    """A coloured alert row (price, harvest, season, weather or info)."""
    pal = palette()
    icon, color = ALERT_STYLES.get(kind, ALERT_STYLES["info"])
    if theme.is_dark():
        color = ALERT_COLORS_DARK.get(kind, ALERT_COLORS_DARK["info"])
    trailing = ft.IconButton(ft.Icons.CLOSE, icon_size=fs(18), on_click=on_dismiss, tooltip="Dismiss") \
        if on_dismiss else None
    return ft.Container(
        bgcolor=pal.card,
        border_radius=RADIUS,
        border=ft.border.only(left=ft.BorderSide(4, color)),
        ink=on_click is not None,
        on_click=on_click,
        padding=ft.padding.only(left=12, right=4, top=10, bottom=10),
        content=ft.Row([
            ft.Icon(icon, color=color, size=fs(24)),
            ft.Column([
                ft.Text(title, size=fs(14), weight=ft.FontWeight.W_600, color=pal.text),
                *([ft.Text(subtitle, size=fs(12), color=pal.muted)] if subtitle else []),
            ], spacing=2, expand=True),
            *([trailing] if trailing else []),
        ], spacing=12),
    )


def loading_spinner(message: str = "Loading…") -> ft.Container:
    """Centred progress ring with a caption."""
    return ft.Container(
        alignment=ft.alignment.center,
        padding=30,
        content=ft.Column([
            ft.ProgressRing(color=PRIMARY, width=fs(36), height=fs(36)),
            ft.Text(message, size=fs(13), color=palette().muted),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=12),
    )


def error_banner(message: str, on_retry: Handler = None) -> ft.Container:
    """Red-tinted banner with an optional Retry button."""
    pal = palette()
    return ft.Container(
        bgcolor=pal.chip_down_bg,
        border_radius=RADIUS,
        padding=12,
        content=ft.Row([
            ft.Icon(ft.Icons.ERROR_OUTLINE, color=pal.down),
            ft.Text(message, color=pal.text, size=fs(13), expand=True),
            *([ft.TextButton("Retry", on_click=on_retry)] if on_retry else []),
        ], spacing=10),
    )


def empty_state(icon: str = ft.Icons.INBOX, title: str = "Nothing here yet", message: str = "",
                action_text: str | None = None, on_action: Handler = None) -> ft.Container:
    """Friendly placeholder when a list is empty."""
    pal = palette()
    return ft.Container(
        alignment=ft.alignment.center,
        padding=ft.padding.symmetric(vertical=36, horizontal=PAD),
        content=ft.Column([
            ft.Icon(icon, size=fs(56), color=pal.muted),
            ft.Text(title, size=fs(17), weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
            *([ft.Text(message, size=fs(13), color=pal.muted, text_align=ft.TextAlign.CENTER)] if message else []),
            *([ft.FilledButton(action_text, on_click=on_action)] if action_text else []),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True),
    )
