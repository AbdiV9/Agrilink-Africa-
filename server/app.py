# Owner: Person 3 (Integration, Logic & API Lead)
"""AgriLink server (STRETCH): a small FastAPI app to host on Render.com.

What it does:
* **SMS gateway.** ``POST /api/sms/send`` sends SMS through Africa's Talking,
  so the AT key lives only on the server. The desktop app uses it when
  ``SMS_SERVER_URL`` is set and it has no local ``AT_API_KEY``.
* **Incoming SMS.** ``POST /sms/inbound`` is the Africa's Talking callback.
  A text from a registered phone becomes an in-app message (channel 'sms').
  Start it with ``@username`` to choose who gets it; otherwise it goes to the
  person the sender last talked to.
* **Read-only market API.** Crops, listings, price history, AI forecasts and
  news as JSON, e.g. for a future web or USSD front end. Phone numbers and
  password hashes are never returned.

Run locally:  ``uvicorn server.app:app --reload``  then open http://127.0.0.1:8000/docs
Auth: write endpoints need ``Authorization: Bearer <SERVER_API_TOKEN>``.
The inbound SMS callback takes the token as ``?token=...`` in the callback URL.
"""

from __future__ import annotations

import hmac
import logging
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # so "import config" works when started from anywhere
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request  # noqa: E402
from fastapi.responses import PlainTextResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import config  # noqa: E402
from Auth import communication, news  # noqa: E402
from Databases import Market_Queries, Message_Queries, Prediction, User_Queries  # noqa: E402
from Databases.Database_Setup import setup_database  # noqa: E402

log = logging.getLogger("agrilink.server")

SMS_PER_MINUTE = 20
_PUBLIC_LISTING_FIELDS = (
    "id", "crop_id", "crop_name", "unit", "category", "quantity", "price_per_unit", "currency", "location",
    "description", "status", "created_at", "seller_id", "seller_username", "seller_verified", "seller_region",
    "seller_country",
)
_sms_log: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if setup_database():
        log.info("Created and seeded a new database at start-up.")
    if not config.SERVER_API_TOKEN:
        log.warning("SERVER_API_TOKEN is not set: SMS sending and the inbound callback are disabled.")
    yield


app = FastAPI(title="AgriLink Africa API", version=config.APP_VERSION, lifespan=lifespan)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _token_ok(given: str | None) -> bool:
    return bool(config.SERVER_API_TOKEN) and hmac.compare_digest((given or "").encode(),
                                                                config.SERVER_API_TOKEN.encode())


def require_token(authorization: str | None = Header(default=None)) -> None:
    """Dependency: a valid ``Authorization: Bearer <SERVER_API_TOKEN>`` header."""
    if not config.SERVER_API_TOKEN:
        raise HTTPException(503, "Server has no SERVER_API_TOKEN set, so this endpoint is disabled.")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not _token_ok(token.strip()):
        raise HTTPException(401, "Invalid or missing API token.")


def _rate_limit(key: str, limit: int = SMS_PER_MINUTE) -> None:
    now = time.monotonic()
    hits = _sms_log[key]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(429, f"Too many SMS. The limit is {limit} a minute.")
    hits.append(now)


def public_listing(row: dict[str, Any]) -> dict[str, Any]:
    """Listing without seller phone or anything private."""
    return {k: row.get(k) for k in _PUBLIC_LISTING_FIELDS if k in row}


def _crop_or_404(crop_id: int) -> dict[str, Any]:
    crop = Market_Queries.get_crop(crop_id)
    if not crop:
        raise HTTPException(404, "Crop not found.")
    return crop


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, Any]:
    """For Render's health check."""
    return {"ok": True, "app": config.APP_NAME, "version": config.APP_VERSION,
            "sms": "africastalking" if config.SMS_ENABLED else "log-only",
            "token_set": bool(config.SERVER_API_TOKEN)}


# --------------------------------------------------------------------------
# Market (read-only)
# --------------------------------------------------------------------------
@app.get("/api/crops")
def crops() -> list[dict[str, Any]]:
    """Every crop with today's price and change."""
    out = []
    for crop in Market_Queries.get_all_crops():
        latest = Market_Queries.get_latest_price(crop["id"]) or {}
        out.append({**crop, "price": latest.get("price"), "change_pct": latest.get("change_pct"),
                    "price_date": latest.get("date")})
    return out


@app.get("/api/crops/{crop_id}/prices")
def prices(crop_id: int, days: int = Query(90, ge=1, le=365)) -> dict[str, Any]:
    crop = _crop_or_404(crop_id)
    return {"crop": crop["name"], "unit": crop.get("unit"), "history": Market_Queries.get_price_history(crop_id, days)}


@app.get("/api/crops/{crop_id}/forecast")
def forecast(crop_id: int, days: int = Query(30, ge=1, le=90)) -> dict[str, Any]:
    from datetime import date

    crop = _crop_or_404(crop_id)
    return {"crop": crop["name"], "forecast": Prediction.predict_price(crop_id, days),
            "advice": Prediction.get_season_advice(crop_id, date.today().month),
            "note": "Estimates only, not financial advice."}


@app.get("/api/listings")
def listings(query: str = "", crop_id: int | None = None, min_price: float | None = None,
             max_price: float | None = None, location: str | None = None,
             sort: str = Query("newest", pattern="^(newest|price_asc|price_desc)$"),
             limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    try:
        rows = Market_Queries.search_listings(query=query, crop_id=crop_id, min_price=min_price,
                                              max_price=max_price, location=location, sort=sort)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return [public_listing(r) for r in rows[:limit]]


@app.get("/api/listings/{listing_id}")
def listing(listing_id: int) -> dict[str, Any]:
    row = Market_Queries.get_listing(listing_id)
    if not row:
        raise HTTPException(404, "Listing not found.")
    return public_listing(row)


@app.get("/api/news")
def news_feed(limit: int = Query(20, ge=1, le=50), crop: str | None = None) -> dict[str, Any]:
    return news.get_news(limit, crop)


# --------------------------------------------------------------------------
# SMS
# --------------------------------------------------------------------------
class SmsRequest(BaseModel):
    phone: str = Field(..., max_length=20, examples=["+254712345678"])
    body: str = Field(..., min_length=1, max_length=communication.SMS_MAX_LENGTH)


@app.post("/api/sms/send", dependencies=[Depends(require_token)])
def sms_send(req: SmsRequest, request: Request) -> dict[str, Any]:
    """Send one SMS through Africa's Talking (or log it if the server has no AT key)."""
    _rate_limit(request.client.host if request.client else "unknown")
    # Call the local sender directly; never loop back to ourselves via SMS_SERVER_URL.
    ok, detail = communication.send_sms_local(req.phone, req.body)
    if not ok:
        raise HTTPException(400 if "Can't send" in detail or "empty" in detail else 502, detail)
    return {"ok": True, "detail": detail}


def route_inbound_sms(phone: str, text: str) -> tuple[bool, str]:
    """Turn an incoming SMS into an in-app message. Returns (stored, reason)."""
    sender = User_Queries.get_user_by_phone(phone)
    if not sender:
        return False, "unknown phone"
    body = (text or "").strip()
    receiver = None
    if body.startswith("@"):
        handle, _, rest = body.partition(" ")
        receiver = User_Queries.get_user_by_username(handle[1:])
        if receiver:
            body = rest.strip()
    if receiver is None:
        recent = Message_Queries.get_conversations(sender["id"])
        receiver = User_Queries.get_user_by_id(recent[0]["other_id"]) if recent else None
    if receiver is None:
        return False, "no recipient (start the SMS with @username)"
    if not body:
        return False, "empty message"
    try:
        Message_Queries.send_message(sender["id"], receiver["id"], body[:2000], channel="sms")
    except ValueError as exc:
        return False, str(exc)
    return True, f"delivered to @{receiver['username']}"


@app.post("/sms/inbound", response_class=PlainTextResponse)
async def sms_inbound(request: Request, token: str | None = None) -> str:
    """Africa's Talking incoming-SMS callback (form fields: from, to, text, date, id)."""
    if not _token_ok(token):
        raise HTTPException(401, "Invalid or missing token in the callback URL.")
    raw = (await request.body())[:10_000].decode("utf-8", errors="replace")
    form = {k: v[0] for k, v in parse_qs(raw).items()}
    stored, reason = route_inbound_sms(form.get("from", ""), form.get("text", ""))
    log.info("Inbound SMS from %s: %s", form.get("from", "?")[-4:], reason)
    return "OK"  # always 200 so Africa's Talking doesn't retry
