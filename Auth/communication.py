# Owner: Person 3 (Integration, Logic & API Lead)
"""Messaging services: in-app messages, SMS (Africa's Talking) and the
"message seller" template.

Every function returns ``(ok, message_or_id)`` and never raises, so the UI
can show a friendly result. SMS goes out with the local ``AT_API_KEY`` if
there is one, otherwise through ``SMS_SERVER_URL`` (server/app.py) if set,
otherwise it is only logged.
"""

from __future__ import annotations

import logging
from typing import Any

import config
from Auth.validation import normalize_phone, validate_phone
from Databases import Message_Queries

log = logging.getLogger(__name__)

MESSAGE_TEMPLATE = "Hi, I'm interested in your {qty}{unit} of {crop} at {price}. Is it still available?"
SMS_MAX_LENGTH = 459  # 3 concatenated SMS segments

_sms_service: Any = None  # africastalking.SMS, created on first use


def build_seller_message(listing: dict[str, Any], qty: float | None = None) -> str:
    """Fill MESSAGE_TEMPLATE from a listing row (``get_listing``/``search_listings``)."""
    quantity = qty if qty else float(listing.get("quantity") or 0)
    unit = listing.get("unit", "kg")
    price = f"{listing.get('currency', 'KES')} {float(listing.get('price_per_unit') or 0):,.2f}/{unit}"
    return MESSAGE_TEMPLATE.format(qty=f"{quantity:g}", unit=unit,
                                   crop=(listing.get("crop_name") or "crop").lower(), price=price)


def send_in_app(sender_id: int, receiver_id: int, body: str, listing_id: int | None = None,
                channel: str = "app") -> tuple[bool, int | str]:
    """Store an in-app message. Returns (True, message_id) or (False, error)."""
    try:
        return True, Message_Queries.send_message(sender_id, receiver_id, body, listing_id=listing_id, channel=channel)
    except ValueError as exc:
        return False, str(exc)
    except Exception:
        log.exception("send_in_app failed")
        return False, "Message could not be saved. Please try again."


def _get_sms_service() -> Any:
    """Initialise the Africa's Talking SDK once (None if unavailable)."""
    global _sms_service
    if _sms_service is not None:
        return _sms_service
    if not config.SMS_ENABLED:
        return None
    try:
        import africastalking

        africastalking.initialize(config.AT_USERNAME, config.AT_API_KEY)
        _sms_service = africastalking.SMS
    except Exception:
        log.exception("Africa's Talking could not be initialised")
        _sms_service = None
    return _sms_service


def _send_via_server(number: str, text: str) -> tuple[bool, str]:
    """Hand the SMS to the AgriLink server (server/app.py), which holds the AT key."""
    try:
        import requests

        resp = requests.post(
            f"{config.SMS_SERVER_URL}/api/sms/send",
            json={"phone": number, "body": text},
            headers={"Authorization": f"Bearer {config.SERVER_API_TOKEN}"} if config.SERVER_API_TOKEN else {},
            timeout=config.SERVER_TIMEOUT_SECONDS,
        )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 200 and data.get("ok"):
            return True, data.get("detail") or "SMS sent."
        if resp.status_code == 401:
            return False, "The SMS server rejected SERVER_API_TOKEN. The in-app message was still sent."
        return False, f"SMS server said: {data.get('detail') or resp.status_code}. The in-app message was still sent."
    except Exception:
        log.exception("SMS server unreachable")
        return False, "SMS server is unreachable right now. The in-app message was still sent."


def send_sms(phone: str, body: str) -> tuple[bool, str]:
    """Send an SMS: local Africa's Talking key first, then the AgriLink server, else log only.

    Returns ``(ok, message)`` and never raises.
    """
    if not config.SMS_ENABLED and config.SMS_SERVER_URL:
        ok, problem = validate_phone(normalize_phone(phone))
        if not ok:
            return False, f"Can't send SMS: {problem}"
        if not (body or "").strip():
            return False, "SMS can't be empty."
        return _send_via_server(normalize_phone(phone), body.strip()[:SMS_MAX_LENGTH])
    return send_sms_local(phone, body)


def send_sms_local(phone: str, body: str) -> tuple[bool, str]:
    """Send an SMS via Africa's Talking (sandbox by default) from this machine.

    Without an API key the SMS is only logged, which still returns
    ``(True, ...)`` so demos work offline. server/app.py calls this directly.
    """
    number = normalize_phone(phone)
    ok, problem = validate_phone(number)
    if not ok:
        return False, f"Can't send SMS: {problem}"
    text = (body or "").strip()
    if not text:
        return False, "SMS can't be empty."
    if len(text) > SMS_MAX_LENGTH:
        text = text[: SMS_MAX_LENGTH - 1] + "…"

    service = _get_sms_service()
    if service is None:
        log.info("[SMS not sent: no AT_API_KEY] to %s: %s", number, text)
        return True, "SMS logged (add AT_API_KEY in .env to send real SMS)."
    try:
        kwargs: dict[str, Any] = {}
        if config.AT_SENDER_ID:
            kwargs["sender_id"] = config.AT_SENDER_ID
        response = service.send(text, [number], **kwargs)
        recipients = (response or {}).get("SMSMessageData", {}).get("Recipients", [])
        status = recipients[0].get("status", "Unknown") if recipients else "Unknown"
        if status.lower() == "success":
            return True, "SMS sent."
        log.warning("SMS to %s returned status %s: %s", number, status, response)
        return False, f"SMS not delivered ({status}). The in-app message was still sent."
    except Exception:
        log.exception("SMS send failed")
        return False, "SMS service is unavailable right now. The in-app message was still sent."


def message_seller(buyer: dict[str, Any], listing: dict[str, Any], qty: float | None = None,
                   via_sms: bool = False) -> tuple[bool, str]:
    """Send the templated first message from a buyer to a listing's seller.

    Always saves an in-app message; with ``via_sms`` also texts the seller.
    """
    if not buyer or not listing:
        return False, "Missing buyer or listing."
    if buyer.get("id") == listing.get("seller_id"):
        return False, "This is your own listing."
    body = build_seller_message(listing, qty)
    ok, result = send_in_app(int(buyer["id"]), int(listing["seller_id"]), body,
                             listing_id=listing.get("id"), channel="sms" if via_sms else "app")
    if not ok:
        return False, str(result)
    if via_sms and listing.get("seller_phone"):
        sms_body = f"AgriLink: @{buyer.get('username', 'a buyer')} says: {body}"
        sms_ok, note = send_sms(listing["seller_phone"], sms_body)
        return True, "Message sent. " + note if sms_ok else "Message sent in the app. " + note
    return True, "Message sent."
