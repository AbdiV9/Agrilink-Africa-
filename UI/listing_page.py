# Owner: Person 2 (Frontend Flet UI Lead)
"""Listing detail (/listing/<id>): photo, details, seller card, quantity
picker, Buy and Message seller."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import ACCENT, PRIMARY, RADIUS, fs, palette

log = logging.getLogger(__name__)

# Same wording as Auth.communication.message_seller (Phase 5).
MESSAGE_TEMPLATE = "Hi, I'm interested in your {qty}{unit} of {crop} at {price}. Is it still available?"


def seller_message(listing: dict[str, Any], qty: float | None = None) -> str:
    """Pre-filled first message to a seller."""
    quantity = qty if qty else listing.get("quantity", 0)
    return MESSAGE_TEMPLATE.format(
        qty=f"{quantity:g}", unit=listing.get("unit", "kg"), crop=(listing.get("crop_name") or "").lower(),
        price=f"{c.format_money(listing.get('price_per_unit'), listing.get('currency', 'KES'))}/{listing.get('unit', 'kg')}",
    )


def _step_for(quantity: float) -> float:
    """Sensible +/- step for the quantity picker."""
    if quantity >= 1000:
        return 50
    if quantity >= 200:
        return 10
    return 1


def _seller_card(page: ft.Page, listing: dict[str, Any]) -> ft.Container:
    pal = palette(page)
    try:
        profile = md.call("get_seller_profile", listing["seller_id"]) or {}
    except Exception:
        profile = {}
    name = listing.get("seller_full_name") or listing.get("seller_username") or "Seller"
    initials = "".join(part[0] for part in name.split()[:2]).upper()
    title_row: list[ft.Control] = [ft.Text(name, size=fs(15), weight=ft.FontWeight.W_700, color=palette().text)]
    if listing.get("seller_verified"):
        title_row.append(c.verified_badge(16))
    return ft.Container(
        padding=14, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border), ink=True,
        on_click=lambda e: page.go(f"/profile/{listing['seller_id']}"),
        content=ft.Row([
            ft.CircleAvatar(content=ft.Text(initials, size=fs(16), weight=ft.FontWeight.W_700), bgcolor=PRIMARY, color="white",
                            radius=fs(24)),
            ft.Column([
                ft.Row(title_row, spacing=4),
                ft.Text(f"@{listing.get('seller_username', '')} · {listing.get('seller_region') or ''}",
                        size=fs(12), color=pal.muted),
                c.star_rating(profile.get("avg_rating"), profile.get("review_count", 0), size=14),
            ], spacing=2, expand=True),
            ft.Icon(ft.Icons.CHEVRON_RIGHT, color=pal.muted),
        ], spacing=12),
    )


def build_listing_view(page: ft.Page, listing_id: int, **params: Any) -> ft.View:
    """Detail page for one listing."""
    pal = palette(page)
    route = f"/listing/{listing_id}"
    user = session.user or md.MOCK_USER
    uid = int(user["id"])
    listing = md.call("get_listing", listing_id)
    if listing is None:
        return c.app_view(page, route, tr("listing.title", "Listing"), controls=[
            c.empty_state(ft.Icons.SEARCH_OFF, tr("listing.not_found", "This listing doesn't exist"), "",
                          tr("crop.back_market", "Back to market"), lambda e: page.go("/market"))])

    unit = listing.get("unit", "kg")
    currency = listing.get("currency", "KES")
    own = listing["seller_id"] == uid
    available = float(listing.get("quantity") or 0)
    active = listing.get("status") == "active" and available > 0

    # --- market comparison ---------------------------------------------------
    try:
        market = md.call("get_latest_price", listing["crop_id"]) or {}
    except Exception:
        market = {}
    compare: ft.Control = ft.Container()
    if market.get("price"):
        diff = (listing["price_per_unit"] - market["price"]) / market["price"] * 100
        good = diff <= 0
        compare = ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=6), border_radius=10,
            bgcolor=pal.chip_up_bg if good else pal.card_alt,
            content=ft.Text(
                tr("listing.below_market", "{pct}% below today's market price ({price})", pct=f"{abs(diff):.0f}",
                   price=c.format_money(market["price"])) if good else
                tr("listing.above_market", "{pct}% above today's market price ({price})", pct=f"{diff:.0f}",
                   price=c.format_money(market["price"])),
                size=fs(12), color=pal.up if good else pal.muted),
        )

    # --- quantity picker + total ---------------------------------------------
    step = _step_for(available)
    start_qty = min(available, step * 10) if available else 0
    qty_field = ft.TextField(value=f"{start_qty:g}", width=fs(110), text_align=ft.TextAlign.CENTER,
                             keyboard_type=ft.KeyboardType.NUMBER, suffix_text=unit, dense=True,
                             disabled=not active or own)
    total = ft.Text("", size=fs(16), weight=ft.FontWeight.W_700, color=palette().text)

    def current_qty() -> float | None:
        try:
            value = float((qty_field.value or "0").strip())
        except ValueError:
            return None
        return value

    def refresh_total(update: bool = True) -> None:
        q = current_qty()
        qty_field.error_text = None
        if q is None:
            qty_field.error_text = tr("listing.numbers", "Numbers only")
            total.value = "—"
        elif q <= 0:
            qty_field.error_text = tr("listing.more_than_zero", "Must be > 0")
            total.value = "—"
        elif q > available:
            qty_field.error_text = tr("listing.max", "Max {n}", n=f"{available:g}")
            total.value = "—"
        else:
            total.value = tr("listing.total", "Total: {amount}", amount=c.format_money(q * listing["price_per_unit"], currency))
        if update:
            qty_field.update()
            total.update()

    def bump(delta: float) -> None:
        q = current_qty() or 0
        qty_field.value = f"{min(available, max(step, q + delta)):g}"
        refresh_total()

    qty_field.on_change = lambda e: refresh_total()
    refresh_total(update=False)
    picker = ft.Row([
        ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, on_click=lambda e: bump(-step), disabled=not active or own),
        qty_field,
        ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, on_click=lambda e: bump(step), disabled=not active or own),
        ft.Container(total, expand=True, alignment=ft.alignment.center_right),
    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # --- buy -----------------------------------------------------------------
    def do_buy(dlg: ft.AlertDialog, q: float) -> None:
        page.close(dlg)
        try:
            md.call("record_purchase", listing_id, uid, q)
        except ValueError as exc:
            c.show_snack(page, str(exc), error=True)
            return
        except Exception:
            log.exception("record_purchase failed")
            c.show_snack(page, tr("listing.buy_error", "Purchase failed. Please try again."), error=True)
            return
        _email_receipt(q)
        c.show_snack(page, tr("listing.bought", "Purchase confirmed! {q}{unit} of {crop}. The seller will be in touch.",
                              q=f"{q:g}", unit=unit, crop=listing["crop_name"]))
        page.go(route)  # rebuild with the new quantity

    def _email_receipt(q: float) -> None:
        """Email a receipt in the background (logged only without SMTP settings)."""
        if not session.user or not md.is_real("record_purchase"):
            return
        buyer = dict(session.user)
        receipt = {**listing, "quantity": q, "total_price": q * listing["price_per_unit"]}

        def run() -> None:
            try:
                from Auth.email_service import send_purchase_receipt

                send_purchase_receipt(buyer, receipt)
            except Exception:
                log.exception("Receipt email failed")

        page.run_thread(run)

    def confirm_buy(e: ft.ControlEvent) -> None:
        q = current_qty()
        refresh_total()
        if qty_field.error_text or q is None:
            return
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(tr("listing.confirm_title", "Confirm purchase"), color=palette().text),
            content=ft.Text(tr("listing.confirm_body", "Buy {q}{unit} of {crop} from @{seller} for {amount}?",
                               q=f"{q:g}", unit=unit, crop=listing["crop_name"], seller=listing["seller_username"],
                               amount=c.format_money(q * listing["price_per_unit"], currency)), color=palette().text),
        )
        dlg.actions = [ft.TextButton(tr("common.cancel", "Cancel"), on_click=lambda e: page.close(dlg)),
                       ft.FilledButton(tr("listing.buy", "Buy"), on_click=lambda e: do_buy(dlg, q))]
        page.open(dlg)

    def message_seller(e: ft.ControlEvent) -> None:
        session.data["message_draft"] = {
            "user_id": listing["seller_id"], "listing_id": listing_id,
            "text": seller_message(listing, current_qty() if not qty_field.error_text else None),
        }
        page.go(f"/messages/{listing['seller_id']}")

    buy_label = (tr("listing.your_listing", "This is your listing") if own else
                 tr("listing.buy_now", "Buy now") if active else tr("listing.sold", "Sold out"))
    buy_btn = ft.FilledButton(buy_label, icon=ft.Icons.SHOPPING_CART, height=fs(48), expand=True,
                              disabled=own or not active, on_click=confirm_buy,
                              style=ft.ButtonStyle(bgcolor=PRIMARY, color="white"))
    msg_btn = ft.OutlinedButton(tr("listing.message", "Message seller"), icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                                height=fs(48), expand=True, disabled=own, on_click=message_seller)

    status_chip: list[ft.Control] = []
    if not active:
        status_chip = [ft.Container(ft.Text(tr("listing.sold_chip", "SOLD"), color="white", size=fs(12),
                                            weight=ft.FontWeight.W_700),
                                    bgcolor=pal.down, border_radius=8, padding=ft.padding.symmetric(6, 10))]

    return c.app_view(page, route, listing["crop_name"], controls=[
        ft.Stack([
            c.crop_image(listing.get("image_url"), listing.get("crop_name"), height=230),
            *[ft.Container(chip, left=10, top=10) for chip in status_chip],
        ]),
        ft.Row([
            ft.Text(listing["crop_name"], size=fs(24), weight=ft.FontWeight.W_800, expand=True, color=palette().text),
            ft.Text(listing.get("category") or "", size=fs(13), color=pal.muted),
        ]),
        ft.Row([
            ft.Text(c.format_money(listing["price_per_unit"], currency), size=fs(26), weight=ft.FontWeight.W_800,
                    color=PRIMARY if not page.theme_mode == ft.ThemeMode.DARK else pal.up),
            ft.Text(f"/{unit}", size=fs(15), color=pal.muted),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.END),
        compare,
        ft.Row([
            ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=fs(18), color=pal.muted),
            ft.Text(tr("listing.available", "{q} {unit} available", q=f"{available:g}", unit=unit), size=fs(14), color=palette().text),
            ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=fs(18), color=pal.muted),
            ft.Text(listing.get("location") or "—", size=fs(14), color=palette().text),
        ], wrap=True, spacing=6),
        ft.Text(tr("listing.posted", "Posted {d}", d=c.short_date(listing.get("created_at", ""))),
                size=fs(12), color=pal.muted),
        ft.Text(listing.get("description") or "", size=fs(14), color=palette().text),
        c.section_title(tr("listing.seller", "Seller")),
        _seller_card(page, listing),
        ft.Divider(),
        ft.Text(tr("listing.how_much", "How much do you need?"), size=fs(15), weight=ft.FontWeight.W_600, color=palette().text),
        picker,
        ft.Row([buy_btn, msg_btn], spacing=10),
        ft.Row([ft.Icon(ft.Icons.SHIELD_OUTLINED, size=fs(16), color=ACCENT),
                ft.Text(tr("listing.safety", "Meet in a safe public place and check the produce before paying."),
                        size=fs(12), color=pal.muted, expand=True)]),
        ft.Container(height=8),
    ])
