# Owner: Person 1 (Backend & Database Lead)
"""Low-level SQLite helpers shared by every query module.

Usage::

    from Databases.db import get_connection, rows_to_dicts

    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM crops WHERE id = ?", (1,)).fetchall()
    crops = rows_to_dicts(rows)

The connection commits automatically when the ``with`` block succeeds, rolls
back if it raises, and is always closed afterwards.

Also holds the password hashing helpers, because both the seed data
(Databases) and registration/login (Auth) need exactly the same format.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

try:  # bcrypt is preferred; pbkdf2 is the spec'd fallback.
    import bcrypt  # type: ignore

    _HAS_BCRYPT = True
except ImportError:  # pragma: no cover - depends on environment
    _HAS_BCRYPT = False

DB_FILENAME = "agrilink.db"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PBKDF2_ITERATIONS = 200_000


def get_db_path() -> str:
    """Return the path of the SQLite file.

    Uses the ``AGRILINK_DB_PATH`` environment variable when set (tests use
    this to point at a temporary file), otherwise ``agrilink.db`` in the
    project root. Read on every call so tests can change it at runtime.
    """
    return os.environ.get("AGRILINK_DB_PATH") or str(_PROJECT_ROOT / DB_FILENAME)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a connection with ``row_factory=sqlite3.Row`` and foreign keys ON.

    Commits on success, rolls back on error and always closes the connection.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a single ``sqlite3.Row`` to a dict (``None`` stays ``None``)."""
    return dict(row) if row is not None else None


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert an iterable of ``sqlite3.Row`` objects to a list of dicts."""
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Password hashing (bcrypt, fallback PBKDF2-HMAC-SHA256)
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password.

    Returns a bcrypt hash (``$2b$...``) when bcrypt is installed, otherwise
    ``pbkdf2$<iterations>$<salt_b64>$<hash_b64>``.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    if _HAS_BCRYPT:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "pbkdf2${}${}${}".format(
        _PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a hash made by :func:`hash_password`."""
    if not password or not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2$"):
        try:
            _, iterations, salt_b64, hash_b64 = stored_hash.split("$")
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(hash_b64)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(digest, expected)
    if _HAS_BCRYPT:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except ValueError:
            return False
    return False
