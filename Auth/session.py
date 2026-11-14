# Owner: Person 3 (Integration, Logic & API Lead)
"""The logged-in user's session (a module-level singleton).

Usage::

    from Auth.session import session

    if session.is_logged_in():
        print(session.user["username"])

``session.user`` never contains ``password_hash``.
"""

from __future__ import annotations

from typing import Any

from Databases import User_Queries

_PRIVATE_FIELDS = ("password_hash",)


def public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    """Copy of a user dict with private fields (password hash) removed."""
    if user is None:
        return None
    return {k: v for k, v in user.items() if k not in _PRIVATE_FIELDS}


class Session:
    """Holds the current user plus a small scratch dict for UI state."""

    _instance: "Session | None" = None

    def __new__(cls) -> "Session":
        # Singleton: Session() always returns the same object.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.user = None
            cls._instance.data = {}
        return cls._instance

    user: dict[str, Any] | None
    data: dict[str, Any]

    @property
    def user_id(self) -> int | None:
        """The logged-in user's id, or None."""
        return int(self.user["id"]) if self.user else None

    def is_logged_in(self) -> bool:
        """True when a user is logged in."""
        return self.user is not None

    def login(self, user: dict[str, Any]) -> None:
        """Store a user (password hash stripped). Called by Auth.auth.login_user."""
        self.user = public_user(user)
        self.data = {}

    def refresh(self) -> dict[str, Any] | None:
        """Reload the user from the database (e.g. after Settings changes).

        Logs out if the account no longer exists. Returns the fresh user.
        """
        if self.user is None:
            return None
        fresh = User_Queries.get_user_by_id(self.user["id"])
        if fresh is None:
            self.clear()
            return None
        self.user = public_user(fresh)
        return self.user

    def clear(self) -> None:
        """Forget the user and any UI state."""
        self.user = None
        self.data = {}


session = Session()
