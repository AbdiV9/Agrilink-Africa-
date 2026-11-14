# Owner: Person 3 (Integration, Logic & API Lead)
"""Registration, login (with lockout) and logout.

* ``register_user(data) -> (ok, message)``
* ``login_user(username, password) -> (True, user_dict)`` or ``(False, message)``
* ``logout()``

After 5 failed logins for the same username, that username is locked for
5 minutes. Lockout state is kept in memory (it resets when the app restarts,
which is fine for a single-device hackathon demo).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import config
from Auth.session import public_user, session
from Auth.validation import normalize_phone, validate_registration
from Databases import User_Queries
from Databases.db import hash_password, verify_password

log = logging.getLogger(__name__)

# username (lower case) -> {"failures": int, "locked_until": float}
_attempts: dict[str, dict[str, float]] = {}
# Indirection so tests can fake the clock.
_clock: Callable[[], float] = time.time

GENERIC_LOGIN_ERROR = "Incorrect username or password."


def register_user(data: dict[str, Any]) -> tuple[bool, str]:
    """Validate, check duplicates, hash the password and create the user.

    ``data`` keys: username, full_name, email, phone, password,
    confirm_password (optional), role, country, region, language (optional).
    On failure the message lists every problem, one per line.
    """
    errors = validate_registration(data)
    if errors:
        return False, "\n".join(errors.values())
    username = data["username"].strip()
    email = data["email"].strip().lower()
    if User_Queries.username_exists(username):
        return False, "That username is already taken."
    if User_Queries.email_exists(email):
        return False, "An account with that email already exists."
    try:
        User_Queries.create_user({
            "username": username,
            "email": email,
            "phone": normalize_phone(data["phone"]),
            "password_hash": hash_password(data["password"]),
            "full_name": data["full_name"].strip(),
            "role": data["role"],
            "country": data["country"].strip(),
            "region": data["region"].strip(),
            "language": data.get("language") or "en",
        })
    except ValueError as exc:
        return False, str(exc)
    except Exception:  # unexpected DB problem: never crash the UI
        log.exception("Registration failed for %s", username)
        return False, "Something went wrong creating your account. Please try again."
    log.info("Registered new user %s", username)
    _send_welcome_async(username)
    return True, "Account created! You can now log in."


def _send_welcome_async(username: str) -> None:
    """Email a welcome in the background so registration never waits on SMTP."""
    def run() -> None:
        try:
            from Auth.email_service import send_welcome_email

            user = User_Queries.get_user_by_username(username)
            if user:
                send_welcome_email(user)
        except Exception:
            log.exception("Welcome email failed")

    threading.Thread(target=run, name="welcome-email", daemon=True).start()


def _lockout_remaining(key: str) -> float:
    """Seconds left on a lockout for this username (0 if not locked)."""
    state = _attempts.get(key)
    if not state:
        return 0.0
    remaining = state.get("locked_until", 0.0) - _clock()
    if remaining <= 0 and state.get("locked_until"):
        _attempts.pop(key, None)  # lock expired: start fresh
        return 0.0
    return max(0.0, remaining)


def _record_failure(key: str) -> str:
    """Count a failed attempt and return the message to show."""
    state = _attempts.setdefault(key, {"failures": 0, "locked_until": 0.0})
    state["failures"] += 1
    left = config.MAX_LOGIN_ATTEMPTS - int(state["failures"])
    if left <= 0:
        state["locked_until"] = _clock() + config.LOCKOUT_SECONDS
        minutes = config.LOCKOUT_SECONDS // 60
        return f"Too many failed attempts. Your account is locked for {minutes} minutes."
    plural = "attempt" if left == 1 else "attempts"
    return f"{GENERIC_LOGIN_ERROR} {left} {plural} left."


def _format_wait(seconds: float) -> str:
    """'4 min 05 s' style countdown text."""
    total = int(round(seconds))
    return f"{total // 60} min {total % 60:02d} s"


def login_user(username: str, password: str) -> tuple[bool, dict[str, Any] | str]:
    """Check credentials. On success stores the user in ``session`` and returns it."""
    name = (username or "").strip()
    if not name or not password:
        return False, "Enter your username and password."
    key = name.lower()
    remaining = _lockout_remaining(key)
    if remaining > 0:
        return False, f"Too many failed attempts. Try again in {_format_wait(remaining)}."

    try:
        user = User_Queries.get_user_by_username(name)
    except Exception:
        log.exception("Login lookup failed")
        return False, "Can't reach the database right now. Please try again."

    # Unknown usernames count as failures too, so attackers can't tell which exist.
    if user is None or not verify_password(password, user["password_hash"]):
        return False, _record_failure(key)

    _attempts.pop(key, None)
    session.login(user)
    log.info("User %s logged in", user["username"])
    return True, public_user(user)  # type: ignore[return-value]


def logout() -> None:
    """Clear the session."""
    if session.user:
        log.info("User %s logged out", session.user.get("username"))
    session.clear()


def reset_lockouts() -> None:
    """Forget all failed attempts (used by tests)."""
    _attempts.clear()
