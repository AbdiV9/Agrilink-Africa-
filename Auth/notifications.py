# Owner: Person 3 (Integration, Logic & API Lead)
"""Price, harvest and season alerts.

* ``check_price_alerts(user_id)``: alerts whose target was hit (each one is
  then switched off so it fires once).
* ``check_harvest_alerts(user_id)``: plantings due within 7 days.
* ``check_season_alerts()``: crops whose planting or harvest month is now.
* ``start_notification_loop(page)``: runs all checks on login and then every
  ``NOTIFICATION_INTERVAL_SECONDS`` (10 min) with ``page.run_task``. It shows
  a SnackBar and adds banners to ``session.data["banners"]`` for the home page.
  Price alerts are also emailed (``Auth.email_service``).

Each notification is ``{"key", "title", "body", "kind", "crop_id"}``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import config
from Auth.session import session
from Databases import Alert_Queries, Market_Queries

log = logging.getLogger(__name__)

HARVEST_WINDOW_DAYS = 7
MAX_BANNERS = 8
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def _money(value: float | None) -> str:
    return "—" if value is None else f"KES {value:,.2f}"


def check_price_alerts(user_id: int) -> list[dict[str, Any]]:
    """Return triggered price alerts and deactivate them."""
    out: list[dict[str, Any]] = []
    for alert in Alert_Queries.get_active_alerts(user_id):
        latest = Market_Queries.get_latest_price(alert["crop_id"])
        if not latest:
            continue
        price = latest["price"]
        hit = (alert["direction"] == "above" and price >= alert["target_price"]) or \
              (alert["direction"] == "below" and price <= alert["target_price"])
        if not hit:
            continue
        word = "rose above" if alert["direction"] == "above" else "dropped below"
        out.append({
            "key": f"price:{alert['id']}",
            "title": f"{alert['crop_name']} {word} {_money(alert['target_price'])}",
            "body": f"Now {_money(price)}/{alert.get('unit', 'kg')}. Tap Market to act on it.",
            "kind": "price",
            "crop_id": alert["crop_id"],
        })
        Alert_Queries.deactivate_alert(alert["id"])
    return out


def check_harvest_alerts(user_id: int) -> list[dict[str, Any]]:
    """Plantings whose expected harvest is today or within the next 7 days."""
    out: list[dict[str, Any]] = []
    for p in Alert_Queries.get_plantings(user_id):
        days = p.get("days_to_harvest")
        if days is None or not 0 <= days <= HARVEST_WINDOW_DAYS:
            continue
        when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        out.append({
            "key": f"harvest:{p['id']}",
            "title": f"Harvest your {p['crop_name']} {when}",
            "body": f"Planted {p['planted_on']}. Line up buyers now: list it on the Sell tab.",
            "kind": "harvest",
            "crop_id": p["crop_id"],
        })
    return out


def check_season_alerts(today: date | None = None) -> list[dict[str, Any]]:
    """Crops whose planting season starts, or harvest arrives, this month."""
    month = (today or date.today()).month
    out: list[dict[str, Any]] = []
    for crop in Market_Queries.get_all_crops():
        if crop.get("season_start_month") == month:
            out.append({
                "key": f"season:plant:{crop['id']}:{month}",
                "title": f"Planting season for {crop['name']} starts in {MONTHS[month - 1]}",
                "body": f"{crop['name']} takes about {crop.get('growth_days')} days to grow.",
                "kind": "season", "crop_id": crop["id"],
            })
        if crop.get("season_end_month") == month:
            out.append({
                "key": f"season:harvest:{crop['id']}:{month}",
                "title": f"{crop['name']} harvest month: prices usually dip",
                "body": "If you can store safely, holding stock a few weeks often pays more.",
                "kind": "season", "crop_id": crop["id"],
            })
    return out


def run_checks(user_id: int, include_season: bool = True) -> list[dict[str, Any]]:
    """Run every check and return only notifications not shown before this login."""
    seen: set[str] = session.data.setdefault("notified_keys", set())
    found: list[dict[str, Any]] = []
    for label, fn in (("price", lambda: check_price_alerts(user_id)),
                      ("harvest", lambda: check_harvest_alerts(user_id)),
                      ("season", check_season_alerts if include_season else (lambda: []))):
        try:
            found.extend(fn())
        except Exception:
            log.exception("%s alert check failed", label)
    fresh = [n for n in found if n["key"] not in seen]
    seen.update(n["key"] for n in fresh)
    return fresh


def _deliver(page: Any, notes: list[dict[str, Any]]) -> None:
    """Add banners for the home page and show one SnackBar summary."""
    if not notes:
        return
    banners: list[dict[str, Any]] = session.data.setdefault("banners", [])
    # Harvest alerts already appear on the home page from plantings, so don't duplicate them.
    for n in notes:
        if n["kind"] != "harvest":
            banners.insert(0, {"title": n["title"], "body": n["body"], "kind": n["kind"]})
    del banners[MAX_BANNERS:]
    try:
        import flet as ft

        priority = {"price": 0, "harvest": 1, "season": 2}
        top = sorted(notes, key=lambda n: priority.get(n["kind"], 3))[0]
        extra = f"  (+{len(notes) - 1} more on Home)" if len(notes) > 1 else ""
        page.open(ft.SnackBar(content=ft.Text(f"🔔 {top['title']}{extra}"), duration=6000,
                              behavior=ft.SnackBarBehavior.FLOATING, show_close_icon=True))
        page.update()
    except Exception:
        log.debug("Could not show notification SnackBar", exc_info=True)


def _email_alerts(user: dict[str, Any], notes: list[dict[str, Any]]) -> None:
    """Also email price alerts (logged only without SMTP settings)."""
    try:
        from Auth.email_service import send_alert_email

        send_alert_email(user, notes)
    except Exception:
        log.exception("Alert email failed")


def start_notification_loop(page: Any) -> None:
    """Start background checks for the logged-in user (called by main.py on login)."""
    if not session.is_logged_in():
        return
    user_id = session.user_id
    interval = max(30, int(config.NOTIFICATION_INTERVAL_SECONDS))

    async def loop() -> None:
        first = True
        while session.is_logged_in() and session.user_id == user_id:
            try:
                notes = await asyncio.to_thread(run_checks, user_id, first)
                _deliver(page, notes)
                if session.user and any(n["kind"] == "price" for n in notes):
                    await asyncio.to_thread(_email_alerts, dict(session.user), notes)
            except Exception:
                log.exception("Notification loop error")
            first = False
            await asyncio.sleep(interval)
        log.info("Notification loop stopped for user %s", user_id)

    try:
        page.run_task(loop)
    except Exception:
        log.exception("Could not start the notification loop")
