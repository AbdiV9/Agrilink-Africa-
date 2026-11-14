"""Mock data so the UI can be built and previewed without the backend.

Pages never import Databases/Auth query functions directly. They call::

    from UI import mock_data as md
    crops = md.call("get_all_crops")
    history = md.call("get_price_history", crop_id, days=365)

``call`` uses the real function unless ``USE_MOCK`` is on, or the real module
isn't built yet (e.g. Prediction before Phase 6), in which case it uses the
mock version with the same name and the same return shape. Errors from the
real functions are NOT hidden: pages catch them and show ``error_banner``.

Turn mock mode on with the env var ``AGRILINK_USE_MOCK=1`` or
``python -m UI.preview <page> --mock``.
"""

from __future__ import annotations

import importlib
import logging
import math
import os
from datetime import date, datetime, timedelta
from typing import Any, Callable

log = logging.getLogger(__name__)

USE_MOCK: bool = os.getenv("AGRILINK_USE_MOCK", "0") == "1"

# Function name -> module that provides the real implementation.
REAL_SOURCES: dict[str, str] = {
    # Databases.Market_Queries
    **{name: "Databases.Market_Queries" for name in (
        "get_all_crops", "get_crop", "search_listings", "get_listing", "create_listing",
        "get_price_history", "get_latest_price", "record_purchase", "get_purchase_history", "get_sales_history",
        "add_to_watchlist", "remove_from_watchlist", "get_watchlist", "is_in_watchlist")},
    # Databases.User_Queries
    **{name: "Databases.User_Queries" for name in (
        "get_user_by_id", "update_user", "get_seller_profile", "add_review",
        "submit_verification", "get_verifications")},
    # Databases.Message_Queries
    **{name: "Databases.Message_Queries" for name in (
        "send_message", "get_conversations", "get_thread", "mark_read", "get_unread_count")},
    # Databases.Alert_Queries
    **{name: "Databases.Alert_Queries" for name in (
        "create_price_alert", "get_active_alerts", "deactivate_alert", "add_planting", "get_plantings")},
    # Databases.Prediction (Phase 6)
    "predict_price": "Databases.Prediction",
    "get_season_advice": "Databases.Prediction",
    # Auth services (Phases 5-6)
    "get_forecast_for_region": "Auth.weather",
    "message_seller": "Auth.communication",
    "send_sms": "Auth.communication",
    "ask": "Auth.chatbot",
    # STRETCH
    "get_news": "Auth.news",
}


def set_mock(enabled: bool) -> None:
    """Switch mock mode on/off at runtime (used by preview.py)."""
    global USE_MOCK
    USE_MOCK = enabled


def _resolve(name: str) -> Callable[..., Any]:
    """Real function if available and mock mode is off, else the mock."""
    mock_fn = MOCKS.get(name)
    if not USE_MOCK and name in REAL_SOURCES:
        try:
            module = importlib.import_module(REAL_SOURCES[name])
            fn = getattr(module, name)
            return fn
        except (ImportError, AttributeError):
            log.debug("Real %s not available yet; using mock.", name)
    if mock_fn is None:
        raise KeyError(f"No real or mock implementation for '{name}'.")
    return mock_fn


def call(name: str, *args: Any, **kwargs: Any) -> Any:
    """Call a data function by name (real or mock, see module docstring)."""
    return _resolve(name)(*args, **kwargs)


def is_real(name: str) -> bool:
    """True if ``call(name)`` would hit the real implementation."""
    return _resolve(name) is not MOCKS.get(name)


# --------------------------------------------------------------------------
# Mock dataset (same shapes as the real query functions)
# --------------------------------------------------------------------------
_CROP_ROWS = [
    # id, name, category, start, end, growth, base price
    (1, "Maize", "Cereal", 3, 8, 120, 45.0), (2, "Beans", "Legume", 3, 6, 90, 120.0),
    (3, "Cassava", "Root/Tuber", 4, 2, 300, 30.0), (4, "Sorghum", "Cereal", 3, 7, 110, 50.0),
    (5, "Millet", "Cereal", 3, 7, 100, 70.0), (6, "Rice", "Cereal", 5, 10, 130, 140.0),
    (7, "Coffee", "Cash crop", 3, 11, 240, 520.0), (8, "Tea", "Cash crop", 3, 6, 90, 300.0),
    (9, "Tomatoes", "Vegetable", 1, 4, 75, 80.0), (10, "Onions", "Vegetable", 2, 6, 110, 90.0),
    (11, "Potatoes", "Root/Tuber", 3, 6, 100, 55.0), (12, "Avocado", "Fruit", 2, 9, 180, 60.0),
]
MOCK_CROPS: list[dict[str, Any]] = [
    {"id": cid, "name": n, "category": cat, "unit": "kg", "season_start_month": s, "season_end_month": e,
     "growth_days": g, "image_url": f"crops/{n.lower()}.jpg"}
    for cid, n, cat, s, e, g, _ in _CROP_ROWS
]
_BASE = {cid: base for cid, *_rest, base in _CROP_ROWS}
_HARVEST = {cid: e for cid, _n, _c, _s, e, _g, _b in _CROP_ROWS}

MOCK_USERS: dict[int, dict[str, Any]] = {
    1: {"id": 1, "username": "amina_w", "email": "amina_w@example.com", "phone": "+254712345678",
        "full_name": "Amina Wanjiru", "role": "farmer", "country": "Kenya", "region": "Nakuru",
        "language": "en", "dark_mode": 0, "text_scale": 1.0, "verified": 1, "created_at": "2026-05-01 09:00:00"},
    2: {"id": 2, "username": "john_otieno", "email": "john_otieno@example.com", "phone": "+254722000111",
        "full_name": "John Otieno", "role": "buyer", "country": "Kenya", "region": "Nairobi",
        "language": "en", "dark_mode": 0, "text_scale": 1.0, "verified": 0, "created_at": "2026-05-16 09:00:00"},
    3: {"id": 3, "username": "chidi_okafor", "email": "chidi_okafor@example.com", "phone": "+2348031234567",
        "full_name": "Chidi Okafor", "role": "farmer", "country": "Nigeria", "region": "Kano",
        "language": "ha", "dark_mode": 0, "text_scale": 1.0, "verified": 1, "created_at": "2026-06-01 09:00:00"},
}
MOCK_USER = MOCK_USERS[1]  # the "logged in" user in mock previews


def _price_on(crop_id: int, d: date, offset: int) -> float:
    """Deterministic seasonal price (same idea as the real seed data, no randomness)."""
    base = _BASE[crop_id]
    doy = d.timetuple().tm_yday
    harvest = date(d.year, _HARVEST[crop_id], 15).timetuple().tm_yday
    peak = (harvest - 60) % 365
    dist = lambda a, b: min(abs(a - b) % 365, 365 - abs(a - b) % 365)  # noqa: E731
    wave = 0.18 * math.cos(2 * math.pi * dist(doy, peak) / 365)
    dip = -0.12 * math.exp(-((dist(doy, harvest) / 20) ** 2))
    wiggle = 0.02 * math.sin(offset * 1.7 + crop_id) + 0.01 * math.sin(offset * 0.45)
    return round(base * (1 + wave + dip + 0.06 * offset / 365 + wiggle), 2)


def _history(crop_id: int, days: int = 90) -> list[dict[str, Any]]:
    today = date.today()
    start = today - timedelta(days=364)
    rows = [{"date": (start + timedelta(days=i)).isoformat(), "price": _price_on(crop_id, start + timedelta(days=i), i)}
            for i in range(365)]
    return rows[-days:]


def _crop(crop_id: int) -> dict[str, Any] | None:
    return next((dict(c) for c in MOCK_CROPS if c["id"] == crop_id), None)


def _latest(crop_id: int) -> dict[str, Any] | None:
    h = _history(crop_id, 8)
    if not h:
        return None
    change = round((h[-1]["price"] - h[0]["price"]) / h[0]["price"] * 100, 2)
    return {"price": h[-1]["price"], "change_pct": change, "date": h[-1]["date"]}


_LOCATIONS = ["Nakuru", "Kano", "Kumasi", "Mbale", "Baidoa", "Eldoret"]
_SELLERS = [(1, "amina_w", 1), (3, "chidi_okafor", 1), (4, "kwame_m", 1), (5, "grace_n", 0)]
MOCK_LISTINGS: list[dict[str, Any]] = []
for _i in range(16):
    _cid = MOCK_CROPS[(_i * 5) % 12]["id"]
    _sid, _uname, _ver = _SELLERS[_i % len(_SELLERS)]
    _c = _crop(_cid) or {}
    MOCK_LISTINGS.append({
        "id": _i + 1, "seller_id": _sid, "crop_id": _cid, "quantity": float([100, 250, 500, 1000][_i % 4]),
        "price_per_unit": round((_latest(_cid) or {"price": 50})["price"] * (0.92 + 0.03 * (_i % 6)), 2),
        "currency": "KES", "location": _LOCATIONS[_i % len(_LOCATIONS)],
        "description": "Freshly harvested, sorted and bagged. Can deliver within the county.",
        "status": "active", "created_at": (datetime.now() - timedelta(hours=7 * _i)).strftime("%Y-%m-%d %H:%M:%S"),
        "crop_name": _c.get("name"), "unit": "kg", "category": _c.get("category"), "image_url": _c.get("image_url"),
        "seller_username": _uname, "seller_full_name": _uname.replace("_", " ").title(),
        "seller_verified": _ver, "seller_phone": "+254712345678", "seller_region": _LOCATIONS[_i % 6],
        "seller_country": "Kenya",
    })

_watch: set[int] = {1, 2, 12}
_messages: list[dict[str, Any]] = [
    {"id": 1, "sender_id": 2, "receiver_id": 1, "listing_id": 1, "body": "Hi, I'm interested in your maize. Is it still available?",
     "channel": "app", "is_read": 1, "created_at": "2026-11-10 09:00:00", "sender_username": "john_otieno"},
    {"id": 2, "sender_id": 1, "receiver_id": 2, "listing_id": 1, "body": "Yes, 500kg ready for pickup in Nakuru.",
     "channel": "app", "is_read": 1, "created_at": "2026-11-10 09:23:00", "sender_username": "amina_w"},
    {"id": 3, "sender_id": 2, "receiver_id": 1, "listing_id": 1, "body": "Great, can you do KES 44 per kg?",
     "channel": "app", "is_read": 0, "created_at": "2026-11-10 09:46:00", "sender_username": "john_otieno"},
    {"id": 4, "sender_id": 3, "receiver_id": 1, "listing_id": None, "body": "Do you have bean seed to spare?",
     "channel": "sms", "is_read": 0, "created_at": "2026-11-12 14:10:00", "sender_username": "chidi_okafor"},
]
_alerts: list[dict[str, Any]] = [
    {"id": 1, "user_id": 1, "crop_id": 1, "target_price": 50.0, "direction": "above", "active": 1,
     "crop_name": "Maize", "unit": "kg"},
    {"id": 2, "user_id": 1, "crop_id": 9, "target_price": 70.0, "direction": "below", "active": 1,
     "crop_name": "Tomatoes", "unit": "kg"},
]


def _plantings(user_id: int = 1) -> list[dict[str, Any]]:
    today = date.today()
    specs = [(1, "Maize", 115, 120, 2.5, "Long rains plot"), (2, "Beans", 40, 90, 1.0, "Intercropped")]
    out = []
    for pid, crop, ago, growth, acres, notes in specs:
        planted = today - timedelta(days=ago)
        harvest = planted + timedelta(days=growth)
        out.append({"id": pid, "user_id": user_id, "crop_id": 1 if crop == "Maize" else 2, "crop_name": crop,
                    "unit": "kg", "planted_on": planted.isoformat(), "expected_harvest": harvest.isoformat(),
                    "area_acres": acres, "notes": notes, "days_to_harvest": (harvest - today).days})
    return out


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((r["id"] for r in rows), default=0) + 1


# --------------------------------------------------------------------------
# Mock functions (names and return shapes match the real ones)
# --------------------------------------------------------------------------
def m_search_listings(query: str = "", crop_id: int | None = None, min_price: float | None = None,
                      max_price: float | None = None, location: str | None = None,
                      sort: str = "newest") -> list[dict[str, Any]]:
    rows = [l for l in MOCK_LISTINGS if l["status"] == "active"]
    if query:
        q = query.lower()
        rows = [l for l in rows if q in f"{l['crop_name']} {l['description']} {l['location']} {l['seller_username']}".lower()]
    if crop_id is not None:
        rows = [l for l in rows if l["crop_id"] == crop_id]
    if min_price is not None:
        rows = [l for l in rows if l["price_per_unit"] >= float(min_price)]
    if max_price is not None:
        rows = [l for l in rows if l["price_per_unit"] <= float(max_price)]
    if location:
        rows = [l for l in rows if location.lower() in (l["location"] or "").lower()]
    key = {"newest": (lambda l: l["created_at"], True), "price_asc": (lambda l: l["price_per_unit"], False),
           "price_desc": (lambda l: l["price_per_unit"], True)}[sort]
    return sorted(rows, key=key[0], reverse=key[1])


def m_create_listing(data: dict[str, Any]) -> int:
    crop = _crop(int(data["crop_id"])) or {}
    new_id = _next_id(MOCK_LISTINGS)
    MOCK_LISTINGS.append({**MOCK_LISTINGS[0], "id": new_id, "seller_id": data["seller_id"], "crop_id": crop.get("id"),
                          "crop_name": crop.get("name"), "image_url": crop.get("image_url"),
                          "quantity": float(data["quantity"]), "price_per_unit": float(data["price_per_unit"]),
                          "location": data.get("location"), "description": data.get("description"),
                          "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    return new_id


def m_record_purchase(listing_id: int, buyer_id: int, qty: float) -> int:
    listing = next((l for l in MOCK_LISTINGS if l["id"] == listing_id), None)
    if listing is None:
        raise ValueError("That listing does not exist.")
    if float(qty) <= 0 or float(qty) > listing["quantity"]:
        raise ValueError(f"Only {listing['quantity']:g} available.")
    listing["quantity"] -= float(qty)
    return 1


def m_get_watchlist(user_id: int) -> list[dict[str, Any]]:
    out = []
    for cid in sorted(_watch):
        crop = _crop(cid) or {}
        latest = _latest(cid) or {}
        out.append({**crop, "price": latest.get("price"), "change_pct": latest.get("change_pct", 0.0)})
    return sorted(out, key=lambda c: c["name"])


def m_get_seller_profile(user_id: int) -> dict[str, Any] | None:
    user = MOCK_USERS.get(user_id) or {**MOCK_USER, "id": user_id}
    return {**user, "verified": bool(user["verified"]), "avg_rating": 4.6, "review_count": 3,
            "listings": [l for l in MOCK_LISTINGS if l["seller_id"] == user_id],
            "reviews": [
                {"id": 1, "reviewer_id": 2, "seller_id": user_id, "rating": 5, "reviewer_username": "john_otieno",
                 "reviewer_full_name": "John Otieno", "comment": "Excellent quality and delivered on time!",
                 "created_at": "2026-10-30 10:00:00"},
                {"id": 2, "reviewer_id": 3, "seller_id": user_id, "rating": 4, "reviewer_username": "chidi_okafor",
                 "reviewer_full_name": "Chidi Okafor", "comment": "Fair price for the quality.",
                 "created_at": "2026-10-12 10:00:00"},
            ]}


def m_get_conversations(user_id: int) -> list[dict[str, Any]]:
    convos: dict[int, dict[str, Any]] = {}
    for m in sorted(_messages, key=lambda x: x["created_at"]):
        if user_id not in (m["sender_id"], m["receiver_id"]):
            continue
        other = m["receiver_id"] if m["sender_id"] == user_id else m["sender_id"]
        u = MOCK_USERS.get(other, {"username": f"user{other}", "full_name": "", "verified": 0})
        c = convos.setdefault(other, {"other_id": other, "other_username": u["username"],
                                      "other_full_name": u["full_name"], "other_verified": u["verified"],
                                      "unread_count": 0})
        c.update({"last_body": m["body"], "last_at": m["created_at"], "last_sender_id": m["sender_id"]})
        if m["receiver_id"] == user_id and not m["is_read"]:
            c["unread_count"] += 1
    return sorted(convos.values(), key=lambda c: c["last_at"], reverse=True)


def m_get_thread(a: int, b: int) -> list[dict[str, Any]]:
    return [dict(m) for m in _messages if {m["sender_id"], m["receiver_id"]} == {a, b}]


def m_send_message(sender_id: int, receiver_id: int, body: str, listing_id: int | None = None,
                   channel: str = "app") -> int:
    if not (body or "").strip():
        raise ValueError("Message cannot be empty.")
    new_id = _next_id(_messages)
    _messages.append({"id": new_id, "sender_id": sender_id, "receiver_id": receiver_id, "listing_id": listing_id,
                      "body": body.strip(), "channel": channel, "is_read": 0,
                      "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      "sender_username": MOCK_USERS.get(sender_id, {}).get("username", "you")})
    return new_id


def m_mark_read(user_id: int, other_id: int) -> int:
    n = 0
    for m in _messages:
        if m["receiver_id"] == user_id and m["sender_id"] == other_id and not m["is_read"]:
            m["is_read"] = 1
            n += 1
    return n


def m_create_price_alert(user_id: int, crop_id: int, target_price: float, direction: str) -> int:
    crop = _crop(crop_id) or {}
    new_id = _next_id(_alerts)
    _alerts.append({"id": new_id, "user_id": user_id, "crop_id": crop_id, "target_price": float(target_price),
                    "direction": direction, "active": 1, "crop_name": crop.get("name"), "unit": "kg"})
    return new_id


def m_predict_price(crop_id: int, days_ahead: int = 30) -> list[dict[str, Any]]:
    today = date.today()
    return [{"date": (today + timedelta(days=i)).isoformat(),
             "predicted_price": round(_price_on(crop_id, today + timedelta(days=i), 364 + i) * 0.99, 2)}
            for i in range(1, days_ahead + 1)]


def m_get_season_advice(crop_id: int, month: int) -> str:
    crop = _crop(crop_id) or {"name": "This crop", "season_end_month": 8}
    peak = date(2000, (crop["season_end_month"] - 2 - 1) % 12 + 1, 1).strftime("%B")
    return f"{crop['name']} prices usually peak in {peak}; consider holding stock for 3 weeks if you can store it safely."


def m_get_forecast_for_region(region: str) -> dict[str, Any]:
    today = date.today()
    codes = [1, 61, 3, 0, 80, 95, 2]
    conditions = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 61: "Light rain",
                  80: "Rain showers", 95: "Thunderstorm"}
    return {"region": region or "Nakuru", "lat": -0.30, "lon": 36.07, "source": "sample", "days": [
        {"date": (today + timedelta(days=i)).isoformat(), "t_max": 24 + (i % 3), "t_min": 12 + (i % 2),
         "rain_mm": [0.4, 6.2, 1.0, 0.0, 8.5, 14.0, 0.2][i], "rain_chance": [10, 70, 30, 5, 80, 90, 10][i],
         "code": codes[i], "condition": conditions[codes[i]]} for i in range(7)]}


def m_ask(user: dict[str, Any] | None, question: str, context: dict[str, Any] | None = None) -> str:
    return ("🌱 (Offline demo answer) Based on this season's pattern, maize prices in your region usually rise "
            "until about two months before harvest. If you can store your grain safely, holding for 2-3 weeks "
            "could earn about 5-8% more. Want me to compare nearby markets?")


def _mock_trades(user_id: int, selling: bool) -> list[dict[str, Any]]:
    """A few purchases (buyer view) or sales (seller view) for previews."""
    rows = []
    for i, listing in enumerate(MOCK_LISTINGS[:6]):
        qty = float([50, 120, 25, 300, 80, 40][i])
        rows.append({
            "id": i + 1, "listing_id": listing["id"], "quantity": qty,
            "total_price": round(qty * listing["price_per_unit"], 2),
            "created_at": (datetime.now() - timedelta(days=9 * i + 1)).strftime("%Y-%m-%d %H:%M:%S"),
            "crop_id": listing["crop_id"], "crop_name": listing["crop_name"], "unit": "kg",
            "price_per_unit": listing["price_per_unit"], "currency": "KES",
            "seller_id": listing["seller_id"], "seller_username": listing["seller_username"],
            "buyer_id": 2 if selling else user_id, "buyer_username": "john_otieno",
        })
    return rows[:4] if selling else rows


def m_get_news(limit: int = 20, crop: str | None = None) -> dict[str, Any]:
    from Auth.news import sample_news

    items = sample_news()
    if crop:
        items = [i for i in items if crop.lower().rstrip("s") in (i["title"] + i["summary"]).lower()]
    return {"items": items[:limit], "source": "sample"}


MOCKS: dict[str, Callable[..., Any]] = {
    "get_all_crops": lambda: [dict(c) for c in MOCK_CROPS],
    "get_crop": _crop,
    "search_listings": m_search_listings,
    "get_listing": lambda listing_id: next((dict(l) for l in MOCK_LISTINGS if l["id"] == listing_id), None),
    "create_listing": m_create_listing,
    "get_price_history": lambda crop_id, days=90: _history(crop_id, days),
    "get_latest_price": _latest,
    "record_purchase": m_record_purchase,
    "get_purchase_history": lambda user_id: _mock_trades(user_id, selling=False),
    "get_sales_history": lambda seller_id: _mock_trades(seller_id, selling=True),
    "add_to_watchlist": lambda user_id, crop_id: (crop_id not in _watch, _watch.add(crop_id))[0],
    "remove_from_watchlist": lambda user_id, crop_id: (crop_id in _watch, _watch.discard(crop_id))[0],
    "get_watchlist": m_get_watchlist,
    "is_in_watchlist": lambda user_id, crop_id: crop_id in _watch,
    "get_user_by_id": lambda user_id: dict(MOCK_USERS.get(user_id, MOCK_USER)),
    "update_user": lambda user_id, fields: (MOCK_USERS.get(user_id, MOCK_USER).update(fields), True)[1],
    "get_seller_profile": m_get_seller_profile,
    "add_review": lambda reviewer_id, seller_id, rating, comment="": 99,
    "submit_verification": lambda user_id, doc_type, doc_reference: 99,
    "get_verifications": lambda user_id: [],
    "send_message": m_send_message,
    "get_conversations": m_get_conversations,
    "get_thread": m_get_thread,
    "mark_read": m_mark_read,
    "get_unread_count": lambda user_id: sum(1 for m in _messages if m["receiver_id"] == user_id and not m["is_read"]),
    "create_price_alert": m_create_price_alert,
    "get_active_alerts": lambda user_id: [a for a in _alerts if a["active"]],
    "deactivate_alert": lambda alert_id: True,
    "add_planting": lambda user_id, crop_id, planted_on, area=None, notes="": 99,
    "get_plantings": _plantings,
    "predict_price": m_predict_price,
    "get_season_advice": m_get_season_advice,
    "get_forecast_for_region": m_get_forecast_for_region,
    "message_seller": lambda buyer, listing, qty=None: (True, "Message sent (demo)."),
    "send_sms": lambda phone, body: (True, "SMS logged (demo)."),
    "ask": m_ask,
    "get_news": m_get_news,
}
