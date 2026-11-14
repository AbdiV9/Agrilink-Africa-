# Owner: Person 3 (Integration, Logic & API Lead)
"""Central configuration. Secrets are read ONLY here, from .env / environment.

Other modules do ``import config`` and read e.g. ``config.ANTHROPIC_API_KEY``.
Missing keys are empty strings, and each feature checks the ``*_ENABLED``
flags so the app degrades gracefully instead of crashing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

try:  # python-dotenv is optional at runtime; plain env vars still work.
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _env(name: str, default: str = "") -> str:
    """Read an env var, stripped, falling back to ``default`` when empty."""
    value = os.getenv(name, "").strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    """Read an integer env var, falling back to ``default`` if missing/invalid."""
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


# --- App ------------------------------------------------------------------
APP_NAME = "AgriLink Africa"
APP_VERSION = "0.1.0"
DEBUG = _env("AGRILINK_DEBUG", "0") == "1"
ASSETS_DIR = str(PROJECT_ROOT / "UI" / "assets")
DEFAULT_CURRENCY = "KES"

# --- AI chatbot -----------------------------------------------------------
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-opus-5-5")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")
AI_PROVIDER = "anthropic" if ANTHROPIC_API_KEY else ("openai" if OPENAI_API_KEY else "")
AI_ENABLED = bool(AI_PROVIDER)

# --- SMS (Africa's Talking) -----------------------------------------------
AT_USERNAME = _env("AT_USERNAME", "sandbox")
AT_API_KEY = _env("AT_API_KEY")
AT_SENDER_ID = _env("AT_SENDER_ID")
SMS_ENABLED = bool(AT_API_KEY)

# --- Translation ----------------------------------------------------------
DEEPL_KEY = _env("DEEPL_KEY")
TRANSLATION_ENABLED = bool(DEEPL_KEY)

# --- Weather (Open-Meteo is free and needs no key) ------------------------
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CACHE_SECONDS = 3600

# --- AgriLink server (STRETCH: server/app.py, e.g. hosted on Render) ------
# When SMS_SERVER_URL is set and there is no local AT_API_KEY, the app sends
# SMS through the server, so the Africa's Talking key only lives on the server.
SMS_SERVER_URL = _env("SMS_SERVER_URL").rstrip("/")
SERVER_API_TOKEN = _env("SERVER_API_TOKEN")
SERVER_TIMEOUT_SECONDS = 10

# --- Email (STRETCH: any SMTP server, e.g. Gmail with an app password) ------
SMTP_HOST = _env("SMTP_HOST")
SMTP_PORT = _env_int("SMTP_PORT", 587)
SMTP_USER = _env("SMTP_USER")
SMTP_PASSWORD = _env("SMTP_PASSWORD")
EMAIL_FROM = _env("EMAIL_FROM", SMTP_USER)
EMAIL_ENABLED = bool(SMTP_HOST and EMAIL_FROM)

# --- News feed (STRETCH: any RSS feed, no key needed) ------------------------
NEWS_FEED_URL = _env(
    "NEWS_FEED_URL",
    "https://news.google.com/rss/search?q=agriculture+Africa+farmers+crop+prices&hl=en-KE&gl=KE&ceid=KE:en",
)
NEWS_CACHE_SECONDS = 3600

# --- Background jobs ------------------------------------------------------
NOTIFICATION_INTERVAL_SECONDS = _env_int("NOTIFICATION_INTERVAL_SECONDS", 600)

# --- Auth -----------------------------------------------------------------
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 5 * 60

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def feature_summary() -> dict[str, bool]:
    """Which optional integrations are switched on (shown in logs and Settings)."""
    return {
        "ai_chatbot": AI_ENABLED,
        "sms": SMS_ENABLED,
        "translation": TRANSLATION_ENABLED,
        "weather": True,
        "email": EMAIL_ENABLED,
        "sms_server": bool(SMS_SERVER_URL),
        "news": True,
    }
