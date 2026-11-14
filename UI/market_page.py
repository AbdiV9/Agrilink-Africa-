"""Market (/market): a "Listings" tab (search, filters, card grid) and a
"Markets" tab (Trading 212-style price list with sparklines)."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import RADIUS, crop_emoji, fs, palette

log = logging.getLogger(__name__)

MARKET_SORTS = [("name", "A-Z"), ("gainers", "Top gainers"), ("losers", "Top losers")]


def _listings_tab(page: ft.Page, uid: int, crops: list[dict[str, Any]]) -> ft.Control:
    """Search bar + filter sheet + responsive grid of crop cards."""
    results = ft.ResponsiveRow(spacing=10, run_spacing=10)
    count = ft.Text("", size=fs(13), color=palette(page).muted)
    status = ft.Container()

    try:
        watched = {w["id"] for w in md.call("get_watchlist", uid)}
    except Exception:
        watched = set()

    def on_heart(listing: dict[str, Any], hearted: bool) -> None:
        try:
            if hearted:
                md.call("add_to_watchlist", uid, listing["crop_id"])
                watched.add(listing["crop_id"])
                c.show_snack(page, tr("market.watch_added", "{crop} added to your watchlist", crop=listing["crop_name"]))
            else:
                md.call("remove_from_watchlist", uid, listing["crop_id"])
                watched.discard(listing["crop_id"])
                c.show_snack(page, tr("market.watch_removed", "{crop} removed from your watchlist", crop=listing["crop_name"]))
        except Exception as exc:
            c.show_snack(page, str(exc), error=True)

    def run_search(filters: dict[str, Any], update: bool = True) -> None:
        session.data["market_filters"] = filters
        status.content = None
        try:
            rows = md.call("search_listings", **filters)
        except ValueError as exc:
            rows = []
            status.content = c.error_banner(str(exc))
        except Exception:
            log.exception("search_listings failed")
            rows = []
            status.content = c.error_banner(tr("market.load_error", "Couldn't load listings."),
                                            on_retry=lambda e: run_search(filters))
        if rows:
            results.controls = [
                c.crop_card(l, on_click=lambda l: page.go(f"/listing/{l['id']}"), on_heart=on_heart,
                            hearted=l["crop_id"] in watched)
                for l in rows
            ]
        else:
            results.controls = [] if status.content else [ft.Container(
                col=12, content=c.empty_state(
                    ft.Icons.SEARCH_OFF, tr("market.none", "No listings match"),
                    tr("market.none_sub", "Try a different crop, price range or location.")))]
        count.value = tr("market.count", "{n} listings", n=len(rows))
        if update:
            try:
                page.update()
            except Exception:
                pass

    initial = session.data.get("market_filters") or {}
    search = c.search_bar_with_filters(page, crops, run_search, initial=initial)
    run_search({**search.filters}, update=False)

    return ft.Column([search, count, status, results], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)


def _markets_tab(page: ft.Page, crops: list[dict[str, Any]]) -> ft.Control:
    """Every crop: latest price, weekly % change and a 30-day sparkline."""
    pal = palette(page)
    rows: list[dict[str, Any]] = []
    for crop in crops:
        try:
            latest = md.call("get_latest_price", crop["id"]) or {}
            history = md.call("get_price_history", crop["id"], days=30)
        except Exception:
            log.exception("Price load failed for %s", crop.get("name"))
            latest, history = {}, []
        rows.append({**crop, "price": latest.get("price"), "change_pct": latest.get("change_pct", 0.0),
                     "spark": [h["price"] for h in history]})

    listing = ft.Column(spacing=8)
    sort_state = {"value": session.data.get("markets_sort", "name")}

    def row_control(r: dict[str, Any]) -> ft.Container:
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            bgcolor=pal.card, border_radius=RADIUS, ink=True,
            on_click=lambda e: page.go(f"/crop/{r['id']}"),
            content=ft.Row([
                ft.Container(ft.Text(crop_emoji(r["name"]), size=fs(22)), width=42, height=42,
                             bgcolor=pal.card_alt, border_radius=21, alignment=ft.alignment.center),
                ft.Column([
                    ft.Text(r["name"], size=fs(15), weight=ft.FontWeight.W_600),
                    ft.Text(f"{r.get('category') or ''} · {r.get('unit', 'kg')}", size=fs(12), color=pal.muted),
                ], spacing=0, expand=True),
                c.sparkline(r["spark"], width=84, height=34),
                ft.Column([
                    ft.Text(c.format_money(r["price"]), size=fs(14), weight=ft.FontWeight.W_600),
                    c.change_chip(r["change_pct"], page, size=11),
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END, width=112),
            ], spacing=10),
        )

    def render(update: bool = True) -> None:
        key = sort_state["value"]
        if key == "gainers":
            ordered = sorted(rows, key=lambda r: r["change_pct"] or 0, reverse=True)
        elif key == "losers":
            ordered = sorted(rows, key=lambda r: r["change_pct"] or 0)
        else:
            ordered = sorted(rows, key=lambda r: r["name"])
        listing.controls = [row_control(r) for r in ordered] or [
            c.empty_state(ft.Icons.SHOW_CHART, tr("market.no_prices", "No price data yet"))]
        if update:
            listing.update()

    def sort_changed(e: ft.ControlEvent) -> None:
        sort_state["value"] = next(iter(e.control.selected))
        session.data["markets_sort"] = sort_state["value"]
        render()

    selector = ft.SegmentedButton(
        segments=[ft.Segment(value=k, label=ft.Text(tr(f"market.sort_{k}", label), size=fs(12)))
                  for k, label in MARKET_SORTS],
        selected={sort_state["value"]}, show_selected_icon=False, on_change=sort_changed,
    )
    render(update=False)
    up = sum(1 for r in rows if (r["change_pct"] or 0) >= 0)
    summary = ft.Text(tr("market.summary", "{up} of {n} crops are up this week", up=up, n=len(rows)),
                      size=fs(13), color=pal.muted)
    return ft.Column([ft.Row([selector], scroll=ft.ScrollMode.AUTO), summary, listing],
                     spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)


def build_market_view(page: ft.Page, **params: Any) -> ft.View:
    """Listings + Markets tabs."""
    uid = int((session.user or md.MOCK_USER)["id"])
    try:
        crops = md.call("get_all_crops")
    except Exception:
        log.exception("get_all_crops failed")
        return c.app_view(page, "/market", tr("market.title", "Market"), nav="/market", controls=[
            c.error_banner(tr("market.crops_error", "Couldn't load crops. Please try again."),
                           on_retry=lambda e: page.go("/market"))])

    def tab_changed(e: ft.ControlEvent) -> None:
        session.data["market_tab"] = e.control.selected_index

    tabs = ft.Tabs(
        selected_index=session.data.get("market_tab", 0),
        animation_duration=200,
        expand=True,
        on_change=tab_changed,
        tabs=[
            ft.Tab(text=tr("market.tab_listings", "Listings"), icon=ft.Icons.GRID_VIEW,
                   content=ft.Container(_listings_tab(page, uid, crops), padding=ft.padding.only(top=12))),
            ft.Tab(text=tr("market.tab_markets", "Markets"), icon=ft.Icons.SHOW_CHART,
                   content=ft.Container(_markets_tab(page, crops), padding=ft.padding.only(top=12))),
        ],
    )
    try:
        unread = md.call("get_unread_count", uid)
    except Exception:
        unread = 0
    return c.app_view(page, "/market", tr("market.title", "Market"), nav="/market", unread=unread,
                      scroll=False, controls=[tabs])
