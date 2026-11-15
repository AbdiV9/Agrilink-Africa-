# Owner: Person 2 (Frontend Flet UI Lead)
"""Crop price page (/crop/<id>): Trading 212-style header and chart, AI
prediction toggle, season advice, price alert, watchlist and sellers."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import ACCENT, PRIMARY, RADIUS, fs, palette

log = logging.getLogger(__name__)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _alert_dialog(page: ft.Page, uid: int, crop: dict[str, Any], current: float | None) -> ft.AlertDialog:
    """Dialog to create a price alert (target + above/below)."""
    target = ft.TextField(
        label=tr("crop.target", "Target price (KES per {unit})", unit=crop.get("unit", "kg")),
        value=f"{current:.2f}" if current else "", keyboard_type=ft.KeyboardType.NUMBER, autofocus=True,
    )
    direction = ft.SegmentedButton(
        segments=[ft.Segment(value="above", label=ft.Text(tr("crop.above", "Goes above"), color=palette().text)),
                  ft.Segment(value="below", label=ft.Text(tr("crop.below", "Drops below"), color=palette().text))],
        selected={"above"}, show_selected_icon=False,
    )
    dlg = ft.AlertDialog(modal=True)

    def save(e: ft.ControlEvent) -> None:
        try:
            value = float((target.value or "").strip())
        except ValueError:
            target.error_text = tr("crop.number_only", "Enter a number, e.g. 50")
            target.update()
            return
        try:
            md.call("create_price_alert", uid, crop["id"], value, next(iter(direction.selected)))
        except ValueError as exc:
            target.error_text = str(exc)
            target.update()
            return
        page.close(dlg)
        c.show_snack(page, tr("crop.alert_set", "Alert set: we'll tell you when {crop} {dir} {price}",
                              crop=crop["name"], dir=next(iter(direction.selected)), price=c.format_money(value)))

    dlg.title = ft.Text(tr("crop.alert_title", "Price alert for {crop}", crop=crop["name"]), color=palette().text)
    dlg.content = ft.Column([
        ft.Text(tr("crop.now", "Now: {price}", price=c.format_money(current)), color=palette(page).muted),
        direction, target,
    ], tight=True, spacing=12, width=340)
    dlg.actions = [ft.TextButton(tr("common.cancel", "Cancel"), on_click=lambda e: page.close(dlg)),
                   ft.FilledButton(tr("crop.save_alert", "Save alert"), on_click=save)]
    return dlg


def build_crop_detail_view(page: ft.Page, crop_id: int, **params: Any) -> ft.View:
    """Price page for one crop."""
    pal = palette(page)
    route = f"/crop/{crop_id}"
    uid = int((session.user or md.MOCK_USER)["id"])
    crop = md.call("get_crop", crop_id)
    if crop is None:
        return c.app_view(page, route, tr("crop.title", "Crop"), controls=[
            c.empty_state(ft.Icons.SEARCH_OFF, tr("crop.not_found", "Crop not found"), "",
                          tr("crop.back_market", "Back to market"), lambda e: page.go("/market"))])

    latest = md.call("get_latest_price", crop_id) or {}
    history = md.call("get_price_history", crop_id, days=365)

    # --- chart + range change caption ---------------------------------------
    range_caption = ft.Text("", size=fs(13), color=pal.muted)

    def update_caption(rng: str | None = None, update: bool = True) -> None:
        pct = chart.visible_change_pct()
        range_caption.value = tr("crop.range_change", "{pct} over {range}", pct=c.format_pct(pct), range=chart.range)
        range_caption.color = pal.up if pct >= 0 else pal.down
        if update:
            range_caption.update()

    chart = c.price_chart(history, initial_range="3M", height=250, on_range_change=update_caption)
    update_caption(update=False)

    # --- AI prediction toggle (loaded on first use) ---------------------------
    prediction_note = ft.Text("", size=fs(12), color=pal.muted, visible=False)
    prediction_cache: dict[str, Any] = {}

    def toggle_prediction(e: ft.ControlEvent) -> None:
        show = bool(e.control.value)
        if show and "points" not in prediction_cache:
            try:
                prediction_cache["points"] = md.call("predict_price", crop_id, days_ahead=30)
            except Exception:
                log.exception("predict_price failed")
                prediction_cache["points"] = []
            points = prediction_cache["points"]
            if points:
                end = points[-1]["predicted_price"]
                now = latest.get("price") or end
                pct = (end - now) / now * 100 if now else 0
                prediction_note.value = tr(
                    "crop.prediction_note", "AI forecast: {price} in 30 days ({pct}). Estimates only, not advice.",
                    price=c.format_money(end), pct=c.format_pct(pct))
            else:
                prediction_note.value = tr("crop.prediction_unavailable", "Prediction is unavailable right now.")
        prediction_note.visible = show
        chart.set_prediction(prediction_cache.get("points"), show=show)
        prediction_note.update()

    prediction_switch = ft.Switch(label=tr("crop.show_prediction", "Show AI prediction"),
                                  active_color=ACCENT, on_change=toggle_prediction)

    # --- watchlist + alert buttons ---------------------------------------------
    try:
        watching = {"on": bool(md.call("is_in_watchlist", uid, crop_id))}
    except Exception:
        watching = {"on": False}
    watch_btn = ft.OutlinedButton()

    def paint_watch() -> None:
        watch_btn.text = tr("crop.watching", "Watching") if watching["on"] else tr("crop.watch", "Add to watchlist")
        watch_btn.icon = ft.Icons.FAVORITE if watching["on"] else ft.Icons.FAVORITE_BORDER
        watch_btn.icon_color = pal.down if watching["on"] else None

    def toggle_watch(e: ft.ControlEvent) -> None:
        try:
            if watching["on"]:
                md.call("remove_from_watchlist", uid, crop_id)
            else:
                md.call("add_to_watchlist", uid, crop_id)
            watching["on"] = not watching["on"]
            paint_watch()
            watch_btn.update()
        except Exception as exc:
            c.show_snack(page, str(exc), error=True)

    watch_btn.on_click = toggle_watch
    paint_watch()
    alert_btn = ft.FilledButton(tr("crop.set_alert", "Set price alert"), icon=ft.Icons.NOTIFICATIONS_ACTIVE,
                                style=ft.ButtonStyle(bgcolor=PRIMARY, color="white"),
                                on_click=lambda e: page.open(_alert_dialog(page, uid, crop, latest.get("price"))))

    # --- season advice + facts -----------------------------------------------
    try:
        advice = md.call("get_season_advice", crop_id, date.today().month)
    except Exception:
        log.exception("get_season_advice failed")
        advice = tr("crop.advice_unavailable", "Season advice is unavailable right now.")
    start, end = crop.get("season_start_month"), crop.get("season_end_month")
    facts = ft.Row([
        _fact(page, ft.Icons.GRASS, tr("crop.plant", "Plant"), MONTHS[start - 1] if start else "—"),
        _fact(page, ft.Icons.AGRICULTURE, tr("crop.harvest", "Harvest"), MONTHS[end - 1] if end else "—"),
        _fact(page, ft.Icons.TIMER_OUTLINED, tr("crop.growth", "Growth"), f"{crop.get('growth_days') or '—'} d"),
    ], spacing=8)
    advice_card = ft.Container(
        padding=14, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=ACCENT),
                    ft.Text(tr("crop.season_advice", "Season advice"), size=fs(16), weight=ft.FontWeight.W_700, color=palette().text)]),
            ft.Text(advice, size=fs(14), color=palette().text),
            facts,
        ], spacing=10),
    )

    # --- sellers for this crop ------------------------------------------------
    try:
        sellers = md.call("search_listings", crop_id=crop_id, sort="price_asc")
    except Exception:
        log.exception("Sellers failed")
        sellers = None
    if sellers is None:
        seller_section: list[ft.Control] = [c.error_banner(tr("crop.sellers_error", "Couldn't load sellers."))]
    elif not sellers:
        seller_section = [c.empty_state(ft.Icons.STOREFRONT, tr("crop.no_sellers", "Nobody is selling {crop} yet",
                                                                 crop=crop["name"]), "",
                                        tr("crop.sell_yours", "Sell yours"), lambda e: page.go("/sell"))]
    else:
        seller_section = [ft.ResponsiveRow([
            c.crop_card(l, on_click=lambda l: page.go(f"/listing/{l['id']}"), hearted=watching["on"])
            for l in sellers], spacing=10, run_spacing=10)]

    return c.app_view(
        page, route, crop["name"],
        actions=[ft.IconButton(ft.Icons.AUTO_AWESOME, icon_color="white", tooltip=tr("crop.ask_ai", "Ask AI"),
                               on_click=lambda e: _ask_about(page, crop))],
        controls=[
            c.price_header(crop["name"], latest.get("price"), latest.get("change_pct"), crop.get("unit", "kg"),
                           subtitle=tr("crop.as_of", "Latest market price · {d}", d=latest.get("date", "—")), page=page),
            range_caption,
            chart,
            prediction_switch,
            prediction_note,
            ft.Row([alert_btn, watch_btn], wrap=True, spacing=10),
            advice_card,
            c.section_title(tr("crop.sellers", "Sellers ({n})", n=len(sellers or []))),
            *seller_section,
            ft.Container(height=8),
        ],
    )


def _fact(page: ft.Page, icon: str, label: str, value: str) -> ft.Container:
    pal = palette(page)
    return ft.Container(
        expand=True, padding=10, border_radius=12, bgcolor=pal.card_alt,
        content=ft.Column([ft.Icon(icon, size=fs(18), color=PRIMARY),
                           ft.Text(label, size=fs(11), color=pal.muted),
                           ft.Text(value, size=fs(14), weight=ft.FontWeight.W_600, color=palette().text)],
                          spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )


def _ask_about(page: ft.Page, crop: dict[str, Any]) -> None:
    """Open the chatbot with a question about this crop pre-filled."""
    session.data["chatbot_prefill"] = tr("crop.ask_prefill", "Explain the price trend for {crop}", crop=crop["name"])
    page.go("/chatbot")
