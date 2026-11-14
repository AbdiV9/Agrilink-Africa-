# Owner: Person 2 (Frontend Flet UI Lead)
"""Purchase history (/purchases, STRETCH).

Tabs: "Bought" (``get_purchase_history``) and "Sold" (``get_sales_history``,
shown to farmers). Each tab has a summary card (total, orders, top crop) and
a list grouped by month; tapping an order opens its listing.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI import theme
from UI.components import tr
from UI.theme import PRIMARY, RADIUS, fs, palette

log = logging.getLogger(__name__)


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Totals for the summary card: total, orders, quantity per unit, top crop."""
    total = sum(float(r.get("total_price") or 0) for r in rows)
    by_crop = Counter()
    for r in rows:
        by_crop[r.get("crop_name") or "?"] += float(r.get("total_price") or 0)
    top = by_crop.most_common(1)[0][0] if by_crop else None
    return {"total": round(total, 2), "orders": len(rows), "top_crop": top,
            "currency": (rows[0].get("currency") if rows else None) or "KES"}


def _month(iso: str) -> str:
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(iso)[:19]).strftime("%B %Y")
    except ValueError:
        return str(iso)[:7]


def _summary_card(page: ft.Page, summary: dict[str, Any], selling: bool) -> ft.Container:
    def stat(label: str, value: str) -> ft.Column:
        return ft.Column([ft.Text(value, size=fs(18), weight=ft.FontWeight.W_700, color="white"),
                          ft.Text(label, size=fs(12), color="#FFFFFF")], spacing=2, tight=True)

    return ft.Container(
        padding=16, border_radius=RADIUS + 4,
        gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                                   colors=[PRIMARY, "#43A047"]),
        content=ft.Row([
            stat(tr("purchases.earned", "Earned") if selling else tr("purchases.spent", "Spent"),
                 c.format_money(summary["total"], summary["currency"], 0)),
            stat(tr("purchases.orders", "Orders"), str(summary["orders"])),
            stat(tr("purchases.top", "Top crop"), summary["top_crop"] or "—"),
        ], alignment=ft.MainAxisAlignment.SPACE_AROUND, wrap=True, run_spacing=10),
    )


def _order_row(page: ft.Page, r: dict[str, Any], selling: bool) -> ft.Container:
    pal = palette(page)
    who = f"@{r.get('buyer_username')}" if selling else f"@{r.get('seller_username')}"
    unit = r.get("unit") or "kg"
    return ft.Container(
        padding=12, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border), ink=True,
        on_click=lambda e, lid=r["listing_id"]: page.go(f"/listing/{lid}"),
        content=ft.Row([
            ft.Text(theme.crop_emoji(r.get("crop_name")), size=fs(26)),
            ft.Column([
                ft.Text(f"{r.get('crop_name')} · {float(r.get('quantity') or 0):g}{unit}", size=fs(15),
                        weight=ft.FontWeight.W_600),
                ft.Text(f"{tr('purchases.to', 'to') if selling else tr('purchases.from', 'from')} {who} · "
                        f"{c.short_date(str(r.get('created_at')))}", size=fs(12), color=pal.muted),
            ], spacing=2, expand=True, tight=True),
            ft.Text(c.format_money(r.get("total_price"), r.get("currency") or "KES", 0), size=fs(15),
                    weight=ft.FontWeight.W_700, color=pal.up if selling else pal.text),
        ], spacing=10),
    )


def _tab_content(page: ft.Page, rows: list[dict[str, Any]] | None, selling: bool,
                 error: str | None) -> list[ft.Control]:
    if error:
        return [c.error_banner(error, lambda e: page.go("/purchases"))]
    if not rows:
        if selling:
            return [c.empty_state(ft.Icons.STOREFRONT, tr("purchases.no_sales", "No sales yet"),
                                  tr("purchases.no_sales_sub", "List a crop and buyers can order it."),
                                  tr("home.sell", "Sell crops"), lambda e: page.go("/sell"))]
        return [c.empty_state(ft.Icons.SHOPPING_BAG, tr("purchases.none", "No purchases yet"),
                              tr("purchases.none_sub", "Orders you place from the Market appear here."),
                              tr("home.browse", "Browse market"), lambda e: page.go("/market"))]
    out: list[ft.Control] = [_summary_card(page, summarise(rows), selling)]
    month = None
    for r in rows:
        m = _month(r.get("created_at") or "")
        if m != month:
            month = m
            out.append(ft.Text(m, size=fs(14), weight=ft.FontWeight.W_700, color=palette(page).muted))
        out.append(_order_row(page, r, selling))
    return out


def _load(name: str, uid: int) -> tuple[list[dict[str, Any]] | None, str | None]:
    try:
        return md.call(name, uid), None
    except Exception:
        log.exception("%s failed", name)
        return None, tr("purchases.error", "Couldn't load your orders.")


def build_purchases_view(page: ft.Page, **params: Any) -> ft.View:
    """Bought / Sold history for the logged-in user."""
    user = session.user or md.MOCK_USER
    uid = int(user["id"])
    sells = (user.get("role") or "buyer") in ("farmer", "both")

    bought, bought_err = _load("get_purchase_history", uid)
    sections = [("bought", tr("purchases.bought", "Bought"), bought, bought_err, False)]
    if sells:
        sold, sold_err = _load("get_sales_history", uid)
        sections.append(("sold", tr("purchases.sold", "Sold"), sold, sold_err, True))
        # Farmers usually care about sales first, unless they've only bought
        if sold or not bought:
            sections.reverse()

    body = ft.Column(spacing=10)
    current = {"key": session.data.get("purchases_tab") or sections[0][0]}
    if current["key"] not in {s[0] for s in sections}:
        current["key"] = sections[0][0]

    def show(key: str) -> None:
        current["key"] = key
        session.data["purchases_tab"] = key
        _, _, rows, err, selling = next(s for s in sections if s[0] == key)
        body.controls = _tab_content(page, rows, selling, err)

    show(current["key"])
    controls: list[ft.Control] = []
    if len(sections) > 1:
        def on_change(e: ft.ControlEvent) -> None:
            show(sections[int(e.control.selected_index)][0])
            body.update()

        controls.append(ft.Tabs(
            selected_index=[s[0] for s in sections].index(current["key"]), on_change=on_change,
            tabs=[ft.Tab(text=label) for _, label, *_ in sections], height=fs(48),
            indicator_color=PRIMARY, label_color=PRIMARY))
    controls += [body, ft.Container(height=8)]
    return c.app_view(page, "/purchases", tr("purchases.title", "Purchase history"), controls=controls)
