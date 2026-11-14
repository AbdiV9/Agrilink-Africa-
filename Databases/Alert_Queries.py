# Owner: Person 1 (Backend & Database Lead)
"""Price alerts and planting records (used for harvest reminders)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from Databases.db import get_connection, rows_to_dicts

VALID_DIRECTIONS = ("above", "below")


def create_price_alert(user_id: int, crop_id: int, target_price: float, direction: str) -> int:
    """Create an active price alert and return its id."""
    if direction not in VALID_DIRECTIONS:
        raise ValueError("Direction must be 'above' or 'below'.")
    try:
        target = float(target_price)
    except (TypeError, ValueError):
        raise ValueError("Target price must be a number.") from None
    if target <= 0:
        raise ValueError("Target price must be greater than zero.")
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise ValueError("User does not exist.")
        if conn.execute("SELECT 1 FROM crops WHERE id = ?", (crop_id,)).fetchone() is None:
            raise ValueError("Crop does not exist.")
        cur = conn.execute(
            "INSERT INTO price_alerts (user_id, crop_id, target_price, direction) VALUES (?, ?, ?, ?)",
            (user_id, crop_id, target, direction),
        )
        return int(cur.lastrowid)


def get_active_alerts(user_id: int) -> list[dict[str, Any]]:
    """Active alerts for a user, with crop_name and unit."""
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(
            "SELECT a.*, c.name AS crop_name, c.unit FROM price_alerts a"
            " JOIN crops c ON c.id = a.crop_id"
            " WHERE a.user_id = ? AND a.active = 1 ORDER BY c.name, a.id",
            (user_id,),
        ).fetchall())


def deactivate_alert(alert_id: int) -> bool:
    """Switch an alert off (after it fires, or when the user deletes it)."""
    with get_connection() as conn:
        return conn.execute("UPDATE price_alerts SET active = 0 WHERE id = ?", (alert_id,)).rowcount > 0


def add_planting(
    user_id: int,
    crop_id: int,
    planted_on: str | date,
    area: float | None = None,
    notes: str = "",
) -> int:
    """Record a planting. ``expected_harvest`` = planted_on + the crop's growth_days.

    ``planted_on`` may be a ``date`` or a 'YYYY-MM-DD' string. Returns the id.
    """
    if isinstance(planted_on, date):
        planted = planted_on
    else:
        try:
            planted = date.fromisoformat(str(planted_on).strip())
        except ValueError:
            raise ValueError("Planting date must be in YYYY-MM-DD format.") from None
    if planted > date.today():
        raise ValueError("Planting date can't be in the future.")
    acres: float | None = None
    if area not in (None, ""):
        try:
            acres = float(area)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError("Area must be a number of acres.") from None
        if acres <= 0:
            raise ValueError("Area must be greater than zero.")
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise ValueError("User does not exist.")
        crop = conn.execute("SELECT growth_days FROM crops WHERE id = ?", (crop_id,)).fetchone()
        if crop is None:
            raise ValueError("Crop does not exist.")
        harvest = planted + timedelta(days=int(crop["growth_days"] or 0))
        cur = conn.execute(
            "INSERT INTO plantings (user_id, crop_id, planted_on, expected_harvest, area_acres, notes)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, crop_id, planted.isoformat(), harvest.isoformat(), acres, (notes or "").strip() or None),
        )
        return int(cur.lastrowid)


def get_plantings(user_id: int) -> list[dict[str, Any]]:
    """A user's plantings, soonest harvest first, with crop_name and days_to_harvest."""
    with get_connection() as conn:
        rows = rows_to_dicts(conn.execute(
            "SELECT p.*, c.name AS crop_name, c.unit FROM plantings p"
            " JOIN crops c ON c.id = p.crop_id"
            " WHERE p.user_id = ? ORDER BY p.expected_harvest, p.id",
            (user_id,),
        ).fetchall())
    today = date.today()
    for row in rows:
        row["days_to_harvest"] = (
            (date.fromisoformat(row["expected_harvest"]) - today).days if row["expected_harvest"] else None
        )
    return rows
