# Owner: Person 1 (Backend & Database Lead)
"""User accounts, seller profiles, reviews and farmer verification.

All functions return plain dicts (or None) and raise ``ValueError`` with a
clear, user-facing message when input is invalid.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from Databases.db import get_connection, hash_password, row_to_dict, rows_to_dicts

VALID_ROLES = ("farmer", "buyer", "both")
VALID_DOC_TYPES = ("land_tenure", "cooperative", "gov_registration", "subsidy_program", "livestock")
# Columns a user is allowed to change through update_user().
UPDATABLE_FIELDS = {
    "email", "phone", "password_hash", "full_name", "role", "country", "region",
    "language", "dark_mode", "text_scale", "verified",
}
_PUBLIC_USER_COLUMNS = (
    "id, username, email, phone, full_name, role, country, region, language,"
    " dark_mode, text_scale, verified, created_at"
)


def _user_exists(conn: sqlite3.Connection, user_id: Any) -> bool:
    """True if a user with this id exists."""
    return conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is not None


def create_user(data: dict[str, Any]) -> int:
    """Insert a user and return the new id.

    ``data`` needs ``username``, ``email``, ``role`` and either
    ``password_hash`` (preferred, from Auth) or a plain ``password`` which
    is hashed here. Optional: phone, full_name, country, region, language.
    """
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "").strip().lower()
    if not username:
        raise ValueError("Username is required.")
    if not email:
        raise ValueError("Email is required.")
    if role not in VALID_ROLES:
        raise ValueError("Role must be farmer, buyer or both.")
    password_hash = data.get("password_hash")
    if not password_hash:
        if not data.get("password"):
            raise ValueError("A password is required.")
        password_hash = hash_password(data["password"])
    if username_exists(username):
        raise ValueError("That username is already taken.")
    if email_exists(email):
        raise ValueError("An account with that email already exists.")

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, email, phone, password_hash, full_name, role,"
            " country, region, language) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                username, email, (data.get("phone") or "").strip() or None, password_hash,
                (data.get("full_name") or "").strip() or None, role,
                (data.get("country") or "").strip() or None,
                (data.get("region") or "").strip() or None,
                (data.get("language") or "en").strip() or "en",
            ),
        )
        return int(cur.lastrowid)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Full user row, including ``password_hash`` (needed for login)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", ((username or "").strip(),)
        ).fetchone()
        return row_to_dict(row)


def get_user_by_phone(phone: str) -> dict[str, Any] | None:
    """Full user row by phone number (+254..., spaces ignored). Used for incoming SMS (STRETCH)."""
    number = "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")
    if not number:
        return None
    with get_connection() as conn:
        return row_to_dict(conn.execute(
            "SELECT * FROM users WHERE REPLACE(phone, ' ', '') = ? ORDER BY id LIMIT 1", (number,)).fetchone())


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Full user row by id, including ``password_hash``. Don't show it in the UI."""
    with get_connection() as conn:
        return row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def update_user(user_id: int, fields: dict[str, Any]) -> bool:
    """Update the whitelisted columns in ``fields``. Returns True if a row changed."""
    unknown = set(fields) - UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"These fields cannot be updated: {', '.join(sorted(unknown))}.")
    if not fields:
        return False
    clean = dict(fields)
    if "role" in clean and clean["role"] not in VALID_ROLES:
        raise ValueError("Role must be farmer, buyer or both.")
    if "text_scale" in clean:
        scale = float(clean["text_scale"])
        if not 0.5 <= scale <= 2.5:
            raise ValueError("Text size must be between 0.5x and 2.5x.")
        clean["text_scale"] = scale
    for flag in ("dark_mode", "verified"):
        if flag in clean:
            clean[flag] = 1 if clean[flag] else 0
    if "email" in clean:
        clean["email"] = str(clean["email"]).strip().lower()
        with get_connection() as conn:
            clash = conn.execute(
                "SELECT 1 FROM users WHERE email = ? COLLATE NOCASE AND id != ?", (clean["email"], user_id)
            ).fetchone()
        if clash:
            raise ValueError("An account with that email already exists.")

    # Column names come from the UPDATABLE_FIELDS whitelist; values are parameters.
    assignments = ", ".join(f"{col} = ?" for col in clean)
    with get_connection() as conn:
        cur = conn.execute(f"UPDATE users SET {assignments} WHERE id = ?", (*clean.values(), user_id))
        return cur.rowcount > 0


def username_exists(username: str) -> bool:
    """Case-insensitive username check."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", ((username or "").strip(),)
        ).fetchone() is not None


def email_exists(email: str) -> bool:
    """Case-insensitive email check."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM users WHERE email = ? COLLATE NOCASE", ((email or "").strip(),)
        ).fetchone() is not None


def get_seller_profile(user_id: int) -> dict[str, Any] | None:
    """Public profile for the Depop-style profile page.

    Returns the user (without password_hash) plus ``avg_rating`` (float,
    1 dp, 0.0 if none), ``review_count``, ``verified`` (bool), ``listings``
    (their active listings with crop name) and ``reviews`` (newest first,
    with reviewer username). None if the user doesn't exist.
    """
    with get_connection() as conn:
        user = conn.execute(f"SELECT {_PUBLIC_USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return None
        stats = conn.execute(
            "SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count FROM reviews WHERE seller_id = ?",
            (user_id,),
        ).fetchone()
        listings = conn.execute(
            "SELECT l.*, c.name AS crop_name, c.unit, c.image_url FROM listings l"
            " JOIN crops c ON c.id = l.crop_id"
            " WHERE l.seller_id = ? AND l.status = 'active' ORDER BY l.created_at DESC",
            (user_id,),
        ).fetchall()
        reviews = conn.execute(
            "SELECT r.*, u.username AS reviewer_username, u.full_name AS reviewer_full_name"
            " FROM reviews r JOIN users u ON u.id = r.reviewer_id"
            " WHERE r.seller_id = ? ORDER BY r.created_at DESC",
            (user_id,),
        ).fetchall()

    profile = dict(user)
    profile["avg_rating"] = round(stats["avg_rating"], 1) if stats["avg_rating"] is not None else 0.0
    profile["review_count"] = int(stats["review_count"])
    profile["verified"] = bool(profile["verified"])
    profile["listings"] = rows_to_dicts(listings)
    profile["reviews"] = rows_to_dicts(reviews)
    return profile


def add_review(reviewer_id: int, seller_id: int, rating: int, comment: str = "") -> int:
    """Add a 1-5 star review and return its id."""
    try:
        rating_int = int(rating)
    except (TypeError, ValueError):
        raise ValueError("Rating must be a whole number from 1 to 5.") from None
    if rating_int != rating or not 1 <= rating_int <= 5:
        raise ValueError("Rating must be a whole number from 1 to 5.")
    if reviewer_id == seller_id:
        raise ValueError("You can't review yourself.")
    with get_connection() as conn:
        if not _user_exists(conn, reviewer_id):
            raise ValueError("Reviewer does not exist.")
        if not _user_exists(conn, seller_id):
            raise ValueError("Seller does not exist.")
        cur = conn.execute(
            "INSERT INTO reviews (reviewer_id, seller_id, rating, comment) VALUES (?, ?, ?, ?)",
            (reviewer_id, seller_id, rating_int, (comment or "").strip()),
        )
        return int(cur.lastrowid)


def submit_verification(user_id: int, doc_type: str, doc_reference: str) -> int:
    """Submit a verification document (status starts as 'pending'). Returns its id."""
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError("Document type must be one of: " + ", ".join(VALID_DOC_TYPES) + ".")
    reference = (doc_reference or "").strip()
    if len(reference) < 3:
        raise ValueError("Please enter the document reference number.")
    with get_connection() as conn:
        if not _user_exists(conn, user_id):
            raise ValueError("User does not exist.")
        cur = conn.execute(
            "INSERT INTO verifications (user_id, doc_type, doc_reference) VALUES (?, ?, ?)",
            (user_id, doc_type, reference),
        )
        return int(cur.lastrowid)


def get_verifications(user_id: int) -> list[dict[str, Any]]:
    """All verification submissions for a user, newest first."""
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(
            "SELECT * FROM verifications WHERE user_id = ? ORDER BY submitted_at DESC, id DESC", (user_id,)
        ).fetchall())
