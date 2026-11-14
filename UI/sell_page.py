# Owner: Person 2 (Frontend Flet UI Lead)
"""Create a listing (/sell) with a live "today's market price" hint."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import ACCENT, PRIMARY, RADIUS, crop_emoji, fs, palette

log = logging.getLogger(__name__)


def build_sell_view(page: ft.Page, **params: Any) -> ft.View:
    """Listing form: crop, quantity, price (with market hint), location, description."""
    pal = palette(page)
    user = session.user or md.MOCK_USER
    uid = int(user["id"])
    try:
        crops = md.call("get_all_crops")
    except Exception:
        log.exception("get_all_crops failed")
        return c.app_view(page, "/sell", tr("sell.title", "Sell"), nav="/sell", controls=[
            c.error_banner(tr("sell.crops_error", "Couldn't load crops."), on_retry=lambda e: page.go("/sell"))])
    crops_by_id = {str(cr["id"]): cr for cr in crops}

    crop_dd = ft.Dropdown(
        label=tr("sell.crop", "What are you selling?"), expand=True, text_size=fs(15), border_radius=12,
        options=[ft.dropdown.Option(str(cr["id"]), f"{crop_emoji(cr['name'])} {cr['name']}") for cr in crops],
    )
    qty = ft.TextField(label=tr("sell.quantity", "Quantity"), keyboard_type=ft.KeyboardType.NUMBER,
                       suffix_text="kg", expand=True, text_size=fs(15), border_radius=12)
    price = ft.TextField(label=tr("sell.price", "Price per unit"), keyboard_type=ft.KeyboardType.NUMBER,
                         prefix_text="KES ", expand=True, text_size=fs(15), border_radius=12)
    location = ft.TextField(label=tr("sell.location", "Pickup location"), value=user.get("region") or "",
                            prefix_icon=ft.Icons.LOCATION_ON_OUTLINED, text_size=fs(15), border_radius=12)
    description = ft.TextField(label=tr("sell.description", "Description"), multiline=True, min_lines=3,
                               max_lines=6, max_length=500, text_size=fs(15), border_radius=12,
                               hint_text=tr("sell.description_hint", "Quality, variety, drying, delivery options…"))
    market_hint = ft.Text("", size=fs(13), color=pal.muted)
    use_market = ft.TextButton(tr("sell.use_market", "Use market price"), visible=False)
    estimate = ft.Text("", size=fs(14), weight=ft.FontWeight.W_600)
    form_error = ft.Text("", color=pal.down, size=fs(13), visible=False)
    market_price: dict[str, float | None] = {"value": None}

    def refresh_estimate() -> None:
        try:
            q, p = float(qty.value or 0), float(price.value or 0)
            estimate.value = tr("sell.estimate", "You'd earn about {amount} if it all sells",
                                amount=c.format_money(q * p)) if q > 0 and p > 0 else ""
        except ValueError:
            estimate.value = ""

    def crop_changed(e: ft.ControlEvent | None = None) -> None:
        crop = crops_by_id.get(crop_dd.value or "")
        crop_dd.error_text = None
        if not crop:
            return
        qty.suffix_text = crop.get("unit", "kg")
        try:
            latest = md.call("get_latest_price", crop["id"]) or {}
        except Exception:
            latest = {}
        market_price["value"] = latest.get("price")
        if latest.get("price"):
            market_hint.value = tr("sell.market_hint", "Today's market price: {price}/{unit} ({chg} this week)",
                                   price=c.format_money(latest["price"]), unit=crop.get("unit", "kg"),
                                   chg=c.format_pct(latest.get("change_pct")))
            use_market.visible = True
        else:
            market_hint.value = tr("sell.no_market", "No market price available for this crop yet.")
            use_market.visible = False
        page.update()

    def apply_market(e: ft.ControlEvent) -> None:
        if market_price["value"]:
            price.value = f"{market_price['value']:.2f}"
            price.error_text = None
            refresh_estimate()
            page.update()

    def number_changed(e: ft.ControlEvent) -> None:
        e.control.error_text = None
        refresh_estimate()
        page.update()

    crop_dd.on_change = crop_changed
    use_market.on_click = apply_market
    qty.on_change = number_changed
    price.on_change = number_changed

    def parse_positive(field: ft.TextField, label: str) -> float | None:
        raw = (field.value or "").strip()
        try:
            value = float(raw)
        except ValueError:
            field.error_text = tr("sell.need_number", "Enter {what} as a number", what=label.lower())
            return None
        if value <= 0:
            field.error_text = tr("sell.positive", "{what} must be more than 0", what=label)
            return None
        return value

    def submit(e: ft.ControlEvent) -> None:
        form_error.visible = False
        crop_dd.error_text = None if crop_dd.value else tr("sell.need_crop", "Choose a crop")
        q = parse_positive(qty, tr("sell.quantity", "Quantity"))
        p = parse_positive(price, tr("sell.price_short", "Price"))
        if not crop_dd.value or q is None or p is None:
            page.update()
            return
        if market_price["value"] and p > market_price["value"] * 3:
            price.error_text = tr("sell.too_high", "That's over 3× the market price. Please check it.")
            page.update()
            return
        try:
            new_id = md.call("create_listing", {
                "seller_id": uid, "crop_id": int(crop_dd.value), "quantity": q, "price_per_unit": p,
                "location": (location.value or "").strip(), "description": (description.value or "").strip(),
            })
        except ValueError as exc:
            form_error.value = str(exc)
            form_error.visible = True
            page.update()
            return
        except Exception:
            log.exception("create_listing failed")
            form_error.value = tr("sell.error", "Couldn't publish your listing. Please try again.")
            form_error.visible = True
            page.update()
            return
        c.show_snack(page, tr("sell.published", "Your listing is live! 🎉"))
        page.go(f"/listing/{new_id}")

    buyer_note: list[ft.Control] = []
    if user.get("role") == "buyer":
        buyer_note = [c.alert_tile(tr("sell.buyer_note", "You're registered as a buyer"),
                                   tr("sell.buyer_note_sub", "You can still sell. Switch to 'Both' in Settings to show up as a farmer."),
                                   "info")]

    form = ft.Container(
        padding=16, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Row([crop_dd]),
            ft.Row([qty]),
            ft.Row([price]),
            ft.Row([ft.Icon(ft.Icons.SHOW_CHART, size=fs(16), color=ACCENT), ft.Container(market_hint, expand=True),
                    use_market], spacing=6, wrap=True),
            location,
            description,
            estimate,
            form_error,
            ft.FilledButton(tr("sell.publish", "Publish listing"), icon=ft.Icons.PUBLISH, height=fs(50), on_click=submit,
                            style=ft.ButtonStyle(bgcolor=PRIMARY, color="white",
                                                 shape=ft.RoundedRectangleBorder(radius=12))),
        ], spacing=12),
    )

    try:
        unread = md.call("get_unread_count", uid)
    except Exception:
        unread = 0
    return c.app_view(page, "/sell", tr("sell.title", "Sell your harvest"), nav="/sell", unread=unread, controls=[
        ft.Text(tr("sell.intro", "Buyers across the region will see your listing straight away."),
                size=fs(14), color=pal.muted),
        *buyer_note,
        form,
        ft.Container(height=8),
    ])
