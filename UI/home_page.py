"""Home dashboard (/home): greeting, alerts, watchlist with sparklines, weather."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import ACCENT, PRIMARY, RADIUS, crop_emoji, fs, palette

log = logging.getLogger(__name__)


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return tr("home.morning", "Good morning")
    if hour < 17:
        return tr("home.afternoon", "Good afternoon")
    return tr("home.evening", "Good evening")


def _safe(label: str, fn, *args: Any, **kwargs: Any) -> tuple[Any, ft.Control | None]:
    """Run a data call; on failure return (None, error_banner) instead of crashing."""
    try:
        return fn(*args, **kwargs), None
    except Exception:
        log.exception("Home: %s failed", label)
        return None, c.error_banner(tr("home.load_error", "Couldn't load {what}.", what=label))


def _watch_row(page: ft.Page, crop: dict[str, Any]) -> ft.Container:
    """Trading 212-style watchlist row: emoji, name, sparkline, price, % chip."""
    pal = palette(page)
    try:
        history = md.call("get_price_history", crop["id"], days=30)
    except Exception:
        history = []
    return ft.Container(
        padding=ft.padding.symmetric(horizontal=12, vertical=10),
        bgcolor=pal.card,
        border_radius=RADIUS,
        ink=True,
        on_click=lambda e: page.go(f"/crop/{crop['id']}"),
        content=ft.Row([
            ft.Container(ft.Text(crop_emoji(crop["name"]), size=fs(22)), width=40, height=40,
                         bgcolor=pal.card_alt, border_radius=20, alignment=ft.alignment.center),
            ft.Column([
                ft.Text(crop["name"], size=fs(15), weight=ft.FontWeight.W_600),
                ft.Text(f"per {crop.get('unit', 'kg')}", size=fs(12), color=pal.muted),
            ], spacing=0, expand=True),
            c.sparkline([h["price"] for h in history], width=80, height=34),
            ft.Column([
                ft.Text(c.format_money(crop.get("price")), size=fs(14), weight=ft.FontWeight.W_600),
                c.change_chip(crop.get("change_pct"), page, size=11),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END),
        ], spacing=12),
    )


def _harvest_alerts(plantings: list[dict[str, Any]]) -> list[ft.Control]:
    tiles: list[ft.Control] = []
    for p in plantings:
        days = p.get("days_to_harvest")
        if days is None or days > 7:
            continue
        if days < 0:
            title = tr("home.harvest_overdue", "{crop} was due for harvest {n} days ago", crop=p["crop_name"], n=-days)
        elif days == 0:
            title = tr("home.harvest_today", "Harvest your {crop} today", crop=p["crop_name"])
        else:
            title = tr("home.harvest_soon", "Harvest {crop} in {n} days", crop=p["crop_name"], n=days)
        acres = f" · {p['area_acres']:g} acres" if p.get("area_acres") else ""
        tiles.append(c.alert_tile(title, f"{tr('home.expected', 'Expected')} {p['expected_harvest']}{acres}", "harvest"))
    return tiles


def _price_alert_tiles(page: ft.Page, alerts: list[dict[str, Any]]) -> list[ft.Control]:
    tiles: list[ft.Control] = []
    for a in alerts:
        try:
            latest = md.call("get_latest_price", a["crop_id"]) or {}
        except Exception:
            latest = {}
        now = latest.get("price")
        arrow = "≥" if a["direction"] == "above" else "≤"
        hit = now is not None and ((a["direction"] == "above" and now >= a["target_price"])
                                   or (a["direction"] == "below" and now <= a["target_price"]))
        title = f"{a['crop_name']} {arrow} {c.format_money(a['target_price'])}"
        subtitle = (tr("home.alert_hit", "Target reached! Now {price}", price=c.format_money(now)) if hit
                    else tr("home.alert_now", "Now {price}", price=c.format_money(now)))
        tiles.append(c.alert_tile(title, subtitle, "price",
                                  on_click=lambda e, cid=a["crop_id"]: page.go(f"/crop/{cid}")))
    return tiles


def build_home_view(page: ft.Page, **params: Any) -> ft.View:
    """Dashboard for the logged-in user."""
    pal = palette(page)
    user = session.user or md.MOCK_USER
    uid = int(user["id"])
    first_name = (user.get("full_name") or user["username"]).split()[0]

    # --- greeting card -----------------------------------------------------
    hero = ft.Container(
        padding=18,
        border_radius=RADIUS + 4,
        gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                                   colors=[PRIMARY, "#43A047"]),
        content=ft.Column([
            ft.Text(f"{_greeting()}, {first_name} 👋", size=fs(22), weight=ft.FontWeight.W_700, color="white"),
            ft.Text(f"{user.get('region') or ''}{', ' if user.get('region') else ''}{user.get('country') or ''}"
                    f" · {datetime.now():%A %d %B}", size=fs(13), color="#E8F5E9"),
            ft.Row([
                ft.FilledButton(tr("home.ask_ai", "Ask AgriLink AI"), icon=ft.Icons.AUTO_AWESOME,
                                style=ft.ButtonStyle(bgcolor=ACCENT, color="#1B1F1C"),
                                on_click=lambda e: page.go("/chatbot")),
                ft.OutlinedButton(tr("home.sell", "Sell crops"), icon=ft.Icons.ADD,
                                  style=ft.ButtonStyle(color="white", side=ft.BorderSide(1, "white")),
                                  on_click=lambda e: page.go("/sell")),
            ], wrap=True, spacing=8),
        ], spacing=8),
    )

    # --- alerts --------------------------------------------------------------
    alert_controls: list[ft.Control] = []
    plantings, err = _safe(tr("home.plantings", "plantings"), md.call, "get_plantings", uid)
    if err:
        alert_controls.append(err)
    alert_controls += _harvest_alerts(plantings or [])
    alerts, err = _safe(tr("home.price_alerts", "price alerts"), md.call, "get_active_alerts", uid)
    if err:
        alert_controls.append(err)
    alert_controls += _price_alert_tiles(page, alerts or [])
    for banner in session.data.get("banners", []):  # filled by Auth.notifications (Phase 5)
        alert_controls.append(c.alert_tile(banner.get("title", ""), banner.get("body", ""), banner.get("kind", "info")))
    if not alert_controls:
        alert_controls.append(c.alert_tile(tr("home.no_alerts", "No alerts right now"),
                                           tr("home.no_alerts_sub", "Set a price alert from any crop page."), "info"))

    # --- watchlist -------------------------------------------------------------
    watch_controls: list[ft.Control] = []
    watchlist, err = _safe(tr("home.watchlist", "watchlist"), md.call, "get_watchlist", uid)
    if err:
        watch_controls.append(err)
    elif not watchlist:
        watch_controls.append(c.empty_state(
            ft.Icons.FAVORITE_BORDER, tr("home.watch_empty", "No crops in your watchlist"),
            tr("home.watch_empty_sub", "Tap the heart on any crop to follow its price."),
            tr("home.browse", "Browse market"), lambda e: page.go("/market")))
    else:
        watch_controls += [_watch_row(page, crop) for crop in watchlist]

    # --- weather (loaded in the background: it may call the internet) ---------
    weather_box = ft.Container(content=c.loading_spinner(tr("home.weather_loading", "Loading weather…")))

    def load_weather() -> None:
        try:
            forecast = md.call("get_forecast_for_region", user.get("region") or "Nairobi")
        except Exception:
            log.exception("Weather failed")
            forecast = None
        weather_box.content = c.weather_card(forecast, page)
        try:
            weather_box.update()
        except Exception:  # not on the page yet; it'll render with the view
            pass

    page.run_thread(load_weather)

    # --- news (STRETCH; also loaded in the background) ------------------------
    news_box = ft.Column([c.loading_spinner(tr("news.loading", "Loading news…"))], spacing=8)

    def load_news() -> None:
        from UI.news_page import news_tile

        try:
            items = (md.call("get_news", 3) or {}).get("items") or []
            news_box.controls = [news_tile(page, item, compact=True) for item in items] or [
                ft.Text(tr("news.none_home", "No news right now."), size=fs(13), color=pal.muted)]
        except Exception:
            log.exception("News failed")
            news_box.controls = [ft.Text(tr("news.error", "Couldn't load news."), size=fs(13), color=pal.muted)]
        try:
            news_box.update()
        except Exception:
            pass

    page.run_thread(load_news)

    try:
        unread = md.call("get_unread_count", uid)
    except Exception:
        unread = 0

    return c.app_view(
        page, "/home", "AgriLink Africa", nav="/home", unread=unread,
        actions=[ft.IconButton(ft.Icons.PERSON, icon_color="white", tooltip=tr("home.profile", "My profile"),
                               on_click=lambda e: page.go(f"/profile/{uid}"))],
        controls=[
            hero,
            c.section_title(tr("home.alerts_title", "Alerts")),
            *alert_controls,
            c.section_title(tr("home.watch_title", "Your watchlist"), tr("home.see_markets", "Markets"),
                            lambda e: page.go("/market")),
            *watch_controls,
            c.section_title(tr("home.weather_title", "Weather")),
            weather_box,
            c.section_title(tr("news.home_title", "Farming news"), tr("news.see_all", "See all"),
                            lambda e: page.go("/news")),
            news_box,
            ft.Container(height=8),
        ],
    )
