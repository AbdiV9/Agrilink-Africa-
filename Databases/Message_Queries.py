# Owner: Person 1 (Backend & Database Lead)
"""In-app messages between buyers and sellers (SMS/email copies are logged here too)."""

from __future__ import annotations

from typing import Any

from Databases.db import get_connection, rows_to_dicts

VALID_CHANNELS = ("app", "sms", "email")
MAX_BODY_LENGTH = 2000


def send_message(
    sender_id: int,
    receiver_id: int,
    body: str,
    listing_id: int | None = None,
    channel: str = "app",
) -> int:
    """Store a message and return its id."""
    text = (body or "").strip()
    if not text:
        raise ValueError("Message cannot be empty.")
    if len(text) > MAX_BODY_LENGTH:
        raise ValueError(f"Message is too long (max {MAX_BODY_LENGTH} characters).")
    if channel not in VALID_CHANNELS:
        raise ValueError("Channel must be app, sms or email.")
    if sender_id == receiver_id:
        raise ValueError("You can't message yourself.")
    with get_connection() as conn:
        for uid, label in ((sender_id, "Sender"), (receiver_id, "Recipient")):
            if conn.execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone() is None:
                raise ValueError(f"{label} does not exist.")
        if listing_id is not None and conn.execute(
            "SELECT 1 FROM listings WHERE id = ?", (listing_id,)
        ).fetchone() is None:
            raise ValueError("That listing does not exist.")
        cur = conn.execute(
            "INSERT INTO messages (sender_id, receiver_id, listing_id, body, channel) VALUES (?, ?, ?, ?, ?)",
            (sender_id, receiver_id, listing_id, text, channel),
        )
        return int(cur.lastrowid)


def get_conversations(user_id: int) -> list[dict[str, Any]]:
    """One row per person the user has messaged with, most recent first.

    Keys: other_id, other_username, other_full_name, other_verified,
    last_body, last_at, last_sender_id, unread_count.
    """
    sql = """
        WITH mine AS (
            SELECT m.*,
                   CASE WHEN m.sender_id = :uid THEN m.receiver_id ELSE m.sender_id END AS other_id
            FROM messages m
            WHERE m.sender_id = :uid OR m.receiver_id = :uid
        ),
        latest AS (
            SELECT other_id, MAX(id) AS last_id FROM mine GROUP BY other_id
        )
        SELECT l.other_id,
               u.username  AS other_username,
               u.full_name AS other_full_name,
               u.verified  AS other_verified,
               m.body       AS last_body,
               m.created_at AS last_at,
               m.sender_id  AS last_sender_id,
               (SELECT COUNT(*) FROM mine x
                 WHERE x.other_id = l.other_id AND x.receiver_id = :uid AND x.is_read = 0) AS unread_count
        FROM latest l
        JOIN messages m ON m.id = l.last_id
        JOIN users u ON u.id = l.other_id
        ORDER BY m.created_at DESC, m.id DESC
    """
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(sql, {"uid": user_id}).fetchall())


def get_thread(a: int, b: int) -> list[dict[str, Any]]:
    """All messages between users ``a`` and ``b``, oldest first, with sender_username."""
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(
            "SELECT m.*, u.username AS sender_username FROM messages m"
            " JOIN users u ON u.id = m.sender_id"
            " WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)"
            " ORDER BY m.created_at, m.id",
            (a, b, b, a),
        ).fetchall())


def mark_read(user_id: int, other_id: int) -> int:
    """Mark everything ``other_id`` sent to ``user_id`` as read. Returns rows changed."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE messages SET is_read = 1 WHERE receiver_id = ? AND sender_id = ? AND is_read = 0",
            (user_id, other_id),
        )
        return cur.rowcount


def get_unread_count(user_id: int) -> int:
    """Total unread messages for the nav-bar badge."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE receiver_id = ? AND is_read = 0", (user_id,)
        ).fetchone()
        return int(row["n"])
