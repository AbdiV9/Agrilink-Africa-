"""Farming news (/news, STRETCH): headlines from ``Auth.news.get_news``,
filterable by crop. Tapping a story opens it in the browser."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import PRIMARY, RADIUS, fs, palette

log = logging.getLogger(__name__)

FILTER_CROPS = ["Maize", "Beans", "Coffee", "Cocoa", "Tea", "Rice", "Tomatoes", "Cassava"]


def time_ago(iso: str) -> str:
    """'3h ago', '2d ago' or a date, from an ISO timestamp."""
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - when).total_seconds()
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 7 * 86400:
        return f"{int(seconds // 86400)}d ago"
    return f"{when:%d %b %Y}"


def news_tile(page: ft.Page, item: dict[str, Any], compact: bool = False) -> ft.Container:
    """One headline card. Shared with the home page."""
    pal = palette(page)
    meta = " · ".join(x for x in (item.get("source"), time_ago(item.get("published", ""))) if x)
    body: list[ft.Control] = [
        ft.Text(item["title"], size=fs(15), weight=ft.FontWeight.W_600, max_lines=3,
                overflow=ft.TextOverflow.ELLIPSIS),
    ]
    if item.get("summary") and not compact and item["summary"] != item["title"]:
        body.append(ft.Text(item["summary"], size=fs(13), color=pal.muted, max_lines=3,
                            overflow=ft.TextOverflow.ELLIPSIS))
    body.append(ft.Text(meta, size=fs(12), color=pal.muted))
    return ft.Container(
        padding=12, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border),
        ink=True, on_click=lambda e: page.launch_url(item["link"]),
        content=ft.Row([
            ft.Icon(ft.Icons.NEWSPAPER, color=PRIMARY, size=fs(22)),
            ft.Column(body, spacing=4, expand=True, tight=True),
            ft.Icon(ft.Icons.OPEN_IN_NEW, size=fs(16), color=pal.muted),
        ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=10),
    )


def build_news_view(page: ft.Page, **params: Any) -> ft.View:
    """News list with crop filter chips; loads in the background."""
    pal = palette(page)
    selected: dict[str, str | None] = {"crop": session.data.get("news_crop")}
    results = ft.Column(spacing=10)
    note = ft.Text("", size=fs(12), color=pal.muted)
    chips = ft.Row(wrap=True, spacing=6, run_spacing=6)

    def render_chips() -> None:
        chips.controls = [
            ft.Chip(label=ft.Text(tr("news.all", "All") if crop is None else crop, size=fs(13)),
                    selected=selected["crop"] == crop, selected_color=pal.chip_up_bg,
                    on_select=lambda e, crop=crop: choose(crop))
            for crop in [None, *FILTER_CROPS]
        ]

    def safe_update(*controls: ft.Control) -> None:
        for ctl in controls:
            try:
                ctl.update()
            except Exception:  # not mounted yet; renders with the view
                pass

    def load() -> None:
        try:
            data = md.call("get_news", 30, selected["crop"])
        except Exception:
            log.exception("News failed")
            results.controls = [c.error_banner(tr("news.error", "Couldn't load news."), lambda e: start())]
            safe_update(results)
            return
        items = data.get("items") or []
        if data.get("source") == "sample":
            note.value = tr("news.offline", "You're offline, so these are sample stories.")
        elif data.get("source") == "cache":
            note.value = tr("news.cached", "Showing saved stories from the last hour.")
        else:
            note.value = ""
        if items:
            results.controls = [news_tile(page, item) for item in items]
        else:
            results.controls = [c.empty_state(ft.Icons.NEWSPAPER, tr("news.none", "No stories about {crop} right now",
                                                                       crop=selected["crop"] or ""),
                                              tr("news.none_sub", "Try another crop or All."))]
        safe_update(results, note)

    def start() -> None:
        results.controls = [c.loading_spinner(tr("news.loading", "Loading news…"))]
        safe_update(results)
        page.run_thread(load)

    def choose(crop: str | None) -> None:
        selected["crop"] = crop
        session.data["news_crop"] = crop
        render_chips()
        safe_update(chips)
        start()

    render_chips()
    start()
    return c.app_view(page, "/news", tr("news.title", "Farming news"), controls=[
        chips, note, results, ft.Container(height=8),
    ], actions=[ft.IconButton(ft.Icons.REFRESH, icon_color="white", tooltip=tr("news.refresh", "Refresh"),
                              on_click=lambda e: start())])
