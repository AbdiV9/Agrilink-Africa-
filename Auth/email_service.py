# Owner: Person 3 (Integration, Logic & API Lead)
"""Email notifications over SMTP (STRETCH).

* ``send_email(to, subject, body)`` sends a plain-text email and returns
  ``(ok, message)``. It never raises.
* ``send_welcome_email(user)`` is called after registration.
* ``send_alert_email(user, notes)`` emails triggered price alerts (called by
  the notification loop).
* ``send_purchase_receipt(user, purchase)`` is called after "Buy now".

Without ``SMTP_HOST`` and ``EMAIL_FROM`` in .env, emails are only logged,
so the app behaves the same offline. Use port 587 (STARTTLS) or 465 (SSL).
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import config
from Auth.validation import validate_email

log = logging.getLogger(__name__)

SIGNATURE = "\n\n— AgriLink Africa\nYou get these emails because you have an AgriLink account."


def send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Send one plain-text email. Without SMTP settings it is logged instead."""
    address = (to or "").strip()
    ok, problem = validate_email(address)
    if not ok:
        return False, f"Can't email: {problem}"
    if not (subject or "").strip() or not (body or "").strip():
        return False, "Email subject and body can't be empty."

    msg = EmailMessage()
    msg["From"] = f"{config.APP_NAME} <{config.EMAIL_FROM}>" if config.EMAIL_FROM else config.APP_NAME
    msg["To"] = address
    msg["Subject"] = subject.strip()[:200]
    msg.set_content(body.strip() + SIGNATURE)

    if not config.EMAIL_ENABLED:
        log.info("[Email not sent: no SMTP_HOST] to %s: %s", address, subject)
        return True, "Email logged (add SMTP settings in .env to send real email)."
    try:
        context = ssl.create_default_context()
        if config.SMTP_PORT == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=15)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
            server.starttls(context=context)
        with server:
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return True, "Email sent."
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP login failed. Check SMTP_USER / SMTP_PASSWORD")
        return False, "Email login failed (check SMTP_USER and SMTP_PASSWORD)."
    except Exception:
        log.exception("Email send failed")
        return False, "Email service is unavailable right now."


def _first_name(user: dict[str, Any]) -> str:
    return (user.get("full_name") or user.get("username") or "there").split()[0]


def send_welcome_email(user: dict[str, Any]) -> tuple[bool, str]:
    """Welcome a newly registered user."""
    role_tip = {
        "farmer": "Tap Sell to list your first crop. Buyers can message you straight away.",
        "buyer": "Open Market to compare prices and message sellers directly.",
        "both": "Use Market to buy and Sell to list your own produce.",
    }.get(user.get("role") or "", "Open Market to get started.")
    body = (f"Hi {_first_name(user)},\n\nWelcome to AgriLink Africa! Your username is @{user.get('username')}.\n\n"
            f"{role_tip}\n\nTip: set a price alert on any crop page and we'll tell you when the price moves.")
    return send_email(user.get("email") or "", "Welcome to AgriLink Africa 🌾", body)


def send_alert_email(user: dict[str, Any], notes: list[dict[str, Any]]) -> tuple[bool, str]:
    """Email the price alerts in ``notes`` (other kinds are skipped)."""
    price_notes = [n for n in notes if n.get("kind") == "price"]
    if not price_notes:
        return True, "No price alerts to email."
    lines = "\n".join(f"• {n['title']}\n  {n['body']}" for n in price_notes)
    subject = price_notes[0]["title"] if len(price_notes) == 1 else f"{len(price_notes)} price alerts triggered"
    body = f"Hi {_first_name(user)},\n\nYour AgriLink price alerts:\n\n{lines}\n\nOpen the app to act on them."
    return send_email(user.get("email") or "", f"🔔 {subject}", body)


def send_purchase_receipt(user: dict[str, Any], purchase: dict[str, Any]) -> tuple[bool, str]:
    """Receipt after a purchase. ``purchase`` needs crop_name, quantity, unit, total_price, seller_username."""
    unit = purchase.get("unit") or "kg"
    body = (f"Hi {_first_name(user)},\n\nThanks for your order on AgriLink.\n\n"
            f"Crop: {purchase.get('crop_name')}\n"
            f"Quantity: {float(purchase.get('quantity') or 0):g} {unit}\n"
            f"Total: {purchase.get('currency') or config.DEFAULT_CURRENCY} {float(purchase.get('total_price') or 0):,.2f}\n"
            f"Seller: @{purchase.get('seller_username')}\n\n"
            "Message the seller in the app to agree pickup or delivery. Check produce before paying.")
    return send_email(user.get("email") or "", f"Your AgriLink order: {purchase.get('crop_name')}", body)
