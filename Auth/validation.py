# Owner: Person 3 (Integration, Logic & API Lead)
"""Input validation for registration and profile forms.

Each ``validate_*`` function returns ``(ok, message)``: message is "" when
valid, otherwise a short, friendly error to show inline under the field.
"""

from __future__ import annotations

import re
from typing import Any

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
SYMBOL_RE = re.compile(r"[^A-Za-z0-9]")

# Country calling code -> (country, allowed subscriber-number lengths).
AFRICAN_CALLING_CODES: dict[str, tuple[str, tuple[int, ...]]] = {
    "+254": ("Kenya", (9,)),
    "+234": ("Nigeria", (10,)),
    "+252": ("Somalia", (7, 8, 9)),
    "+256": ("Uganda", (9,)),
    "+233": ("Ghana", (9,)),
    "+255": ("Tanzania", (9,)),
    "+250": ("Rwanda", (9,)),
    "+257": ("Burundi", (8,)),
    "+251": ("Ethiopia", (9,)),
    "+253": ("Djibouti", (8,)),
    "+211": ("South Sudan", (9,)),
    "+249": ("Sudan", (9,)),
    "+27": ("South Africa", (9,)),
    "+20": ("Egypt", (10,)),
    "+212": ("Morocco", (9,)),
    "+213": ("Algeria", (9,)),
    "+216": ("Tunisia", (8,)),
    "+221": ("Senegal", (9,)),
    "+225": ("Côte d'Ivoire", (10,)),
    "+237": ("Cameroon", (9,)),
    "+244": ("Angola", (9,)),
    "+260": ("Zambia", (9,)),
    "+263": ("Zimbabwe", (9,)),
    "+265": ("Malawi", (9,)),
    "+258": ("Mozambique", (9,)),
    "+267": ("Botswana", (8,)),
}

ROLES = ("farmer", "buyer", "both")


def normalize_phone(phone: str) -> str:
    """Strip spaces, dashes, dots and brackets: '+254 712-345 678' -> '+254712345678'."""
    return re.sub(r"[\s\-().]", "", phone or "")


def validate_username(username: str) -> tuple[bool, str]:
    """3-20 characters: letters, numbers and underscores only."""
    value = (username or "").strip()
    if not value:
        return False, "Username is required."
    if not USERNAME_RE.fullmatch(value):
        return False, "Use 3-20 letters, numbers or underscores (no spaces)."
    return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """A normal-looking email address."""
    value = (email or "").strip()
    if not value:
        return False, "Email is required."
    if len(value) > 254 or not EMAIL_RE.fullmatch(value):
        return False, "Enter a valid email, e.g. name@example.com."
    return True, ""


def validate_phone(phone: str) -> tuple[bool, str]:
    """E.164 with a supported African country code, e.g. +254712345678."""
    value = normalize_phone(phone)
    if not value:
        return False, "Phone number is required."
    if not value.startswith("+"):
        return False, "Include your country code, e.g. +254712345678."
    if not value[1:].isdigit():
        return False, "Phone number can only contain digits after the +."
    # Longest prefix first so "+27" can't shadow a longer code.
    for code in sorted(AFRICAN_CALLING_CODES, key=len, reverse=True):
        if value.startswith(code):
            country, lengths = AFRICAN_CALLING_CODES[code]
            subscriber = value[len(code):]
            if subscriber.startswith("0"):
                return False, f"Drop the leading 0 after {code}, e.g. {code}712345678."
            if len(subscriber) not in lengths:
                expected = " or ".join(str(n) for n in lengths)
                return False, f"{country} numbers need {expected} digits after {code}."
            return True, ""
    return False, "Use an African country code such as +254, +234, +252, +256 or +233."


def validate_password(password: str) -> tuple[bool, str]:
    """8+ characters with an upper-case letter, a lower-case letter, a digit and a symbol."""
    value = password or ""
    missing = []
    if len(value) < 8:
        missing.append("at least 8 characters")
    if not re.search(r"[A-Z]", value):
        missing.append("an upper-case letter")
    if not re.search(r"[a-z]", value):
        missing.append("a lower-case letter")
    if not re.search(r"\d", value):
        missing.append("a number")
    if not SYMBOL_RE.search(value):
        missing.append("a symbol (e.g. !@#)")
    if missing:
        return False, "Password needs " + ", ".join(missing) + "."
    return True, ""


def validate_registration(data: dict[str, Any]) -> dict[str, str]:
    """Validate a whole registration form.

    Returns ``{field_name: error}`` for every invalid field, or ``{}`` if the
    form is valid. Field names match the register page's TextFields.
    """
    errors: dict[str, str] = {}
    checks = {
        "username": validate_username,
        "email": validate_email,
        "phone": validate_phone,
        "password": validate_password,
    }
    for field, check in checks.items():
        ok, message = check(data.get(field, ""))
        if not ok:
            errors[field] = message
    if not (data.get("full_name") or "").strip():
        errors["full_name"] = "Please enter your full name."
    if "confirm_password" in data and data.get("confirm_password") != data.get("password"):
        errors["confirm_password"] = "Passwords don't match."
    if (data.get("role") or "") not in ROLES:
        errors["role"] = "Choose farmer, buyer or both."
    if not (data.get("country") or "").strip():
        errors["country"] = "Please choose your country."
    if not (data.get("region") or "").strip():
        errors["region"] = "Please enter your region or town."
    return errors
