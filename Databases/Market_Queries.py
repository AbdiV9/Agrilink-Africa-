# Owner: Person 1 (Backend & Database Lead)
"""Crops, listings, price history, purchases and watchlists.

All functions return dicts / lists of dicts and raise ``ValueError`` with a
clear message on invalid input (negative numbers, unknown ids, etc.).
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from Databases.db import get_connection, row_to_dict, rows_to_dicts

SORT_OPTIONS = {
    "newest": "l.created_at DESC, l.id DESC",
    "price_asc": "l.price_per_unit ASC, l.id ASC",
    "price_desc": "l.price_per_unit DESC, l.id DESC",
}

_LISTING_SELECT = (
    "SELECT l.*, c.name AS crop_name, c.unit, c.category, c.image_url,"
    " u.username AS seller_username, u.full_name AS seller_full_name,"
    " u.verified AS seller_verified, u.phone AS seller_phone, u.region AS seller_region,"
    " u.country AS seller_country"
    " FROM listings l"
    " JOIN crops c ON c.id = l.crop_id"
    " JOIN users u ON u.id = l.seller_id"
)


def _positive_number(value: Any, label: str, allow_zero: bool = False) -> float:
    """Parse a number and reject negatives (and zero unless allowed)."""
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{label} must be greater than zero." if not allow_zero else f"{label} cannot be negative.")
    return number


def _exists(conn: sqlite3.Connection, table: str, row_id: Any) -> bool:
    """True if ``table`` has a row with this id (table names are internal constants)."""
    return conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (row_id,)).fetchone() is not None


# --------------------------------------------------------------------------
# Crops
# --------------------------------------------------------------------------
def get_all_crops() -> list[dict[str, Any]]:
    """Every crop, alphabetically."""
    with get_connection() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM crops ORDER BY name").fetchall())


def get_crop(crop_id: int) -> dict[str, Any] | None:
    """One crop by id, or None."""
    with get_connection() as conn:
        return row_to_dict(conn.execute("SELECT * FROM crops WHERE id = ?", (crop_id,)).fetchone())


# --------------------------------------------------------------------------
# Listings
# --------------------------------------------------------------------------
def search_listings(
    query: str = "",
    crop_id: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    location: str | None = None,
    sort: str = "newest",
) -> list[dict[str, Any]]:
    """Search active listings. The WHERE clause is built dynamically with parameters.

    ``query`` matches crop name, description, location or seller username.
    Each result includes crop_name, unit, image_url, seller_username and
    seller_verified.
    """
    if sort not in SORT_OPTIONS:
        raise ValueError("Sort must be one of: " + ", ".join(SORT_OPTIONS) + ".")
    clauses = ["l.status = 'active'"]
    params: list[Any] = []
    if query and query.strip():
        like = f"%{query.strip()}%"
        clauses.append("(c.name LIKE ? OR l.description LIKE ? OR l.location LIKE ? OR u.username LIKE ?)")
        params.extend([like, like, like, like])
    if crop_id is not None:
        clauses.append("l.crop_id = ?")
        params.append(crop_id)
    if min_price is not None:
        clauses.append("l.price_per_unit >= ?")
        params.append(_positive_number(min_price, "Minimum price", allow_zero=True))
    if max_price is not None:
        clauses.append("l.price_per_unit <= ?")
        params.append(_positive_number(max_price, "Maximum price", allow_zero=True))
    if min_price is not None and max_price is not None and float(min_price) > float(max_price):
        raise ValueError("Minimum price can't be higher than maximum price.")
    if location and location.strip():
        clauses.append("l.location LIKE ?")
        params.append(f"%{location.strip()}%")

    sql = f"{_LISTING_SELECT} WHERE {' AND '.join(clauses)} ORDER BY {SORT_OPTIONS[sort]}"
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def get_listing(listing_id: int) -> dict[str, Any] | None:
    """One listing (any status) with crop and seller details, or None."""
    with get_connection() as conn:
        return row_to_dict(conn.execute(f"{_LISTING_SELECT} WHERE l.id = ?", (listing_id,)).fetchone())


def create_listing(data: dict[str, Any]) -> int:
    """Create a listing and return its id.

    ``data`` needs seller_id, crop_id, quantity, price_per_unit. Optional:
    currency (default KES), location, description.
    """
    for key in ("seller_id", "crop_id", "quantity", "price_per_unit"):
        if data.get(key) in (None, ""):
            raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
    quantity = _positive_number(data["quantity"], "Quantity")
    price = _positive_number(data["price_per_unit"], "Price")
    with get_connection() as conn:
        seller = conn.execute("SELECT role FROM users WHERE id = ?", (data["seller_id"],)).fetchone()
        if seller is None:
            raise ValueError("Seller does not exist.")
        if not _exists(conn, "crops", data["crop_id"]):
            raise ValueError("Please choose a valid crop.")
        cur = conn.execute(
            "INSERT INTO listings (seller_id, crop_id, quantity, price_per_unit, currency, location, description)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                data["seller_id"], data["crop_id"], quantity, price,
                (data.get("currency") or "KES").upper(),
                (data.get("location") or "").strip() or None,
                (data.get("description") or "").strip() or None,
            ),
        )
        return int(cur.lastrowid)


# --------------------------------------------------------------------------
# Prices
# --------------------------------------------------------------------------
def get_price_history(crop_id: int, days: int = 90) -> list[dict[str, Any]]:
    """``[{date, price}]`` oldest first, for the last ``days`` days of data.

    The window ends at the crop's most recent price, so charts still look
    full if the seed data is a few days old.
    """
    if days <= 0:
        raise ValueError("Days must be greater than zero.")
    with get_connection() as conn:
        latest = conn.execute("SELECT MAX(date) AS d FROM price_history WHERE crop_id = ?", (crop_id,)).fetchone()
        if latest["d"] is None:
            return []
        start = (date.fromisoformat(latest["d"]) - timedelta(days=days - 1)).isoformat()
        return rows_to_dicts(conn.execute(
            "SELECT date, price FROM price_history WHERE crop_id = ? AND date >= ? ORDER BY date",
            (crop_id, start),
        ).fetchall())


def get_latest_price(crop_id: int) -> dict[str, Any] | None:
    """``{price, change_pct, date}``: latest price and % change vs 7 days earlier.

    None if the crop has no price history.
    """
    with get_connection() as conn:
        latest = conn.execute(
            "SELECT date, price FROM price_history WHERE crop_id = ? ORDER BY date DESC LIMIT 1", (crop_id,)
        ).fetchone()
        if latest is None:
            return None
        week_ago = (date.fromisoformat(latest["date"]) - timedelta(days=7)).isoformat()
        previous = conn.execute(
            "SELECT price FROM price_history WHERE crop_id = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (crop_id, week_ago),
        ).fetchone()
    change = 0.0
    if previous is not None and previous["price"]:
        change = round((latest["price"] - previous["price"]) / previous["price"] * 100, 2)
    return {"price": latest["price"], "change_pct": change, "date": latest["date"]}


# --------------------------------------------------------------------------
# Purchases
# --------------------------------------------------------------------------
def record_purchase(listing_id: int, buyer_id: int, qty: float) -> int:
    """Buy ``qty`` units from a listing. Returns the purchase id.

    Reduces the listing quantity and marks it 'sold' when it reaches zero.
    """
    quantity = _positive_number(qty, "Quantity")
    with get_connection() as conn:
        listing = conn.execute(
            "SELECT id, seller_id, quantity, price_per_unit, status FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
        if listing is None:
            raise ValueError("That listing does not exist.")
        if not _exists(conn, "users", buyer_id):
            raise ValueError("Buyer does not exist.")
        if listing["status"] != "active":
            raise ValueError("This listing is no longer available.")
        if listing["seller_id"] == buyer_id:
            raise ValueError("You can't buy your own listing.")
        if quantity > listing["quantity"]:
            raise ValueError(f"Only {listing['quantity']:g} available.")
        total = round(quantity * listing["price_per_unit"], 2)
        cur = conn.execute(
            "INSERT INTO purchases (listing_id, buyer_id, quantity, total_price) VALUES (?, ?, ?, ?)",
            (listing_id, buyer_id, quantity, total),
        )
        remaining = round(listing["quantity"] - quantity, 4)
        conn.execute(
            "UPDATE listings SET quantity = ?, status = ? WHERE id = ?",
            (remaining, "sold" if remaining <= 0 else "active", listing_id),
        )
        return int(cur.lastrowid)


def get_purchase_history(user_id: int) -> list[dict[str, Any]]:
    """A buyer's purchases, newest first, with crop, unit and seller."""
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(
            "SELECT p.*, l.crop_id, c.name AS crop_name, c.unit, l.price_per_unit, l.currency,"
            " l.seller_id, u.username AS seller_username"
            " FROM purchases p"
            " JOIN listings l ON l.id = p.listing_id"
            " JOIN crops c ON c.id = l.crop_id"
            " JOIN users u ON u.id = l.seller_id"
            " WHERE p.buyer_id = ? ORDER BY p.created_at DESC, p.id DESC",
            (user_id,),
        ).fetchall())


def get_sales_history(seller_id: int) -> list[dict[str, Any]]:
    """Purchases made from this seller's listings, newest first, with crop, unit and buyer (STRETCH)."""
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(
            "SELECT p.*, l.crop_id, c.name AS crop_name, c.unit, l.price_per_unit, l.currency,"
            " p.buyer_id, u.username AS buyer_username"
            " FROM purchases p"
            " JOIN listings l ON l.id = p.listing_id"
            " JOIN crops c ON c.id = l.crop_id"
            " JOIN users u ON u.id = p.buyer_id"
            " WHERE l.seller_id = ? ORDER BY p.created_at DESC, p.id DESC",
            (seller_id,),
        ).fetchall())


# --------------------------------------------------------------------------
# Watchlist
# --------------------------------------------------------------------------
def add_to_watchlist(user_id: int, crop_id: int) -> bool:
    """Heart a crop. Returns True if newly added, False if it was already there."""
    with get_connection() as conn:
        if not _exists(conn, "users", user_id):
            raise ValueError("User does not exist.")
        if not _exists(conn, "crops", crop_id):
            raise ValueError("Crop does not exist.")
        cur = conn.execute("INSERT OR IGNORE INTO watchlist (user_id, crop_id) VALUES (?, ?)", (user_id, crop_id))
        return cur.rowcount > 0


def remove_from_watchlist(user_id: int, crop_id: int) -> bool:
    """Un-heart a crop. Returns True if something was removed."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE user_id = ? AND crop_id = ?", (user_id, crop_id))
        return cur.rowcount > 0


def get_watchlist(user_id: int) -> list[dict[str, Any]]:
    """Watched crops (alphabetical) with ``price`` and ``change_pct`` added."""
    with get_connection() as conn:
        crops = rows_to_dicts(conn.execute(
            "SELECT c.* FROM watchlist w JOIN crops c ON c.id = w.crop_id WHERE w.user_id = ? ORDER BY c.name",
            (user_id,),
        ).fetchall())
    for crop in crops:
        latest = get_latest_price(crop["id"]) or {}
        crop["price"] = latest.get("price")
        crop["change_pct"] = latest.get("change_pct", 0.0)
    return crops


def is_in_watchlist(user_id: int, crop_id: int) -> bool:
    """True if the user has hearted this crop (for the heart icon state)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND crop_id = ?", (user_id, crop_id)
        ).fetchone() is not None
