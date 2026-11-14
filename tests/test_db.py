
"""Database layer tests. Run with:  pytest tests/test_db.py -v"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from Databases import Alert_Queries as AQ
from Databases import Database_Setup
from Databases import Market_Queries as MQ
from Databases import Message_Queries as MsgQ
from Databases import User_Queries as UQ
from Databases.db import get_connection, verify_password


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _user_id(username: str) -> int:
    user = UQ.get_user_by_username(username)
    assert user is not None, username
    return int(user["id"])


def _crop_id(name: str) -> int:
    return next(c["id"] for c in MQ.get_all_crops() if c["name"] == name)


def _new_user(username: str = "test_farmer", role: str = "farmer") -> int:
    return UQ.create_user({
        "username": username, "email": f"{username}@test.com", "password": "Password123!",
        "full_name": "Test User", "role": role, "country": "Kenya", "region": "Kisumu",
        "phone": "+254700000000",
    })


# --------------------------------------------------------------------------
# Setup and seed
# --------------------------------------------------------------------------
def test_create_tables_makes_every_table_and_index(empty_db):
    with get_connection() as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert set(Database_Setup.ALL_TABLES) <= tables
    assert {"idx_listings_crop_id", "idx_listings_seller_id",
            "idx_price_history_crop_dt", "idx_messages_receiver_id"} <= indexes


def test_is_empty_then_seeded(empty_db):
    assert Database_Setup.is_empty() is True
    Database_Setup.seed_data()
    assert Database_Setup.is_empty() is False
    with pytest.raises(RuntimeError):
        Database_Setup.seed_data()


def test_seed_counts(seeded_db):
    with get_connection() as conn:
        count = lambda t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]  # noqa: E731
        assert count("crops") >= 12
        assert count("users") == 8
        assert count("listings") >= 30
        assert count("price_history") == count("crops") * 365
        for table in ("reviews", "messages", "purchases", "plantings"):
            assert count(table) > 0
        countries = {r["country"] for r in conn.execute("SELECT DISTINCT country FROM users")}
    assert {"Kenya", "Nigeria", "Ghana", "Uganda", "Somalia"} <= countries


def test_seed_passwords_are_hashed(seeded_db):
    user = UQ.get_user_by_username("amina_w")
    assert user["password_hash"] != "Password123!"
    assert verify_password("Password123!", user["password_hash"])
    assert not verify_password("wrong", user["password_hash"])


def test_seed_prices_dip_at_harvest(seeded_db):
    """Maize (harvest in August) should be cheaper at harvest than ~2 months before."""
    history = MQ.get_price_history(_crop_id("Maize"), days=365)
    by_month: dict[int, list[float]] = {}
    for row in history:
        by_month.setdefault(int(row["date"][5:7]), []).append(row["price"])
    avg = {m: sum(v) / len(v) for m, v in by_month.items()}
    assert avg[6] > avg[8]


def test_setup_database_is_idempotent(empty_db):
    assert Database_Setup.setup_database() is True
    assert Database_Setup.setup_database() is False


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
def test_create_and_get_user(seeded_db):
    uid = _new_user()
    user = UQ.get_user_by_id(uid)
    assert isinstance(user, dict)
    assert user["username"] == "test_farmer"
    assert user["language"] == "en" and user["dark_mode"] == 0 and user["text_scale"] == 1.0
    assert UQ.get_user_by_username("TEST_FARMER")["id"] == uid  # case-insensitive


def test_duplicate_username_and_email_rejected(seeded_db):
    assert UQ.username_exists("amina_w") and UQ.email_exists("AMINA_W@example.com")
    with pytest.raises(ValueError, match="username"):
        UQ.create_user({"username": "amina_w", "email": "new@test.com", "password": "x", "role": "farmer"})
    with pytest.raises(ValueError, match="email"):
        UQ.create_user({"username": "brand_new", "email": "amina_w@example.com", "password": "x", "role": "buyer"})


def test_invalid_role_rejected(seeded_db):
    with pytest.raises(ValueError, match="Role"):
        UQ.create_user({"username": "x_user", "email": "x@test.com", "password": "x", "role": "trader"})


def test_update_user(seeded_db):
    uid = _user_id("john_otieno")
    assert UQ.update_user(uid, {"dark_mode": True, "text_scale": 1.3, "language": "sw"}) is True
    user = UQ.get_user_by_id(uid)
    assert (user["dark_mode"], user["text_scale"], user["language"]) == (1, 1.3, "sw")
    with pytest.raises(ValueError):
        UQ.update_user(uid, {"username": "hacker"})  # not updatable
    with pytest.raises(ValueError):
        UQ.update_user(uid, {"text_scale": 9})
    assert UQ.update_user(999_999, {"language": "en"}) is False


def test_seller_profile(seeded_db):
    profile = UQ.get_seller_profile(_user_id("amina_w"))
    assert "password_hash" not in profile
    assert profile["verified"] is True
    assert profile["review_count"] > 0 and 1 <= profile["avg_rating"] <= 5
    assert all(l["status"] == "active" for l in profile["listings"])
    assert UQ.get_seller_profile(999_999) is None


def test_add_review_validation(seeded_db):
    seller, buyer = _user_id("grace_n"), _user_id("john_otieno")
    assert UQ.add_review(buyer, seller, 5, "Great beans") > 0
    for bad in (0, 6, 3.5, "five"):
        with pytest.raises(ValueError):
            UQ.add_review(buyer, seller, bad, "")
    with pytest.raises(ValueError):
        UQ.add_review(seller, seller, 5, "me")
    with pytest.raises(ValueError):
        UQ.add_review(999_999, seller, 4, "ghost")


def test_submit_verification(seeded_db):
    uid = _user_id("john_otieno")
    vid = UQ.submit_verification(uid, "cooperative", "KE-COOP-123")
    assert UQ.get_verifications(uid)[0]["id"] == vid
    assert UQ.get_verifications(uid)[0]["status"] == "pending"
    with pytest.raises(ValueError):
        UQ.submit_verification(uid, "passport", "123456")


# --------------------------------------------------------------------------
# Market
# --------------------------------------------------------------------------
def test_get_crops(seeded_db):
    crops = MQ.get_all_crops()
    assert len(crops) >= 12 and all(isinstance(c, dict) for c in crops)
    assert MQ.get_crop(crops[0]["id"])["name"] == crops[0]["name"]
    assert MQ.get_crop(999_999) is None


def test_search_listings_filters_and_sorting(seeded_db):
    everything = MQ.search_listings()
    assert everything and all(l["status"] == "active" for l in everything)
    assert {"crop_name", "seller_username", "seller_verified", "unit"} <= set(everything[0])

    maize = MQ.search_listings(crop_id=_crop_id("Maize"))
    assert maize and all(l["crop_name"] == "Maize" for l in maize)

    text = MQ.search_listings(query="maize")
    assert text and all("maize" in (l["crop_name"] + (l["description"] or "")).lower()
                        or "maize" in (l["location"] or "").lower() for l in text)

    cheap = MQ.search_listings(min_price=40, max_price=100)
    assert all(40 <= l["price_per_unit"] <= 100 for l in cheap)

    asc = [l["price_per_unit"] for l in MQ.search_listings(sort="price_asc")]
    desc = [l["price_per_unit"] for l in MQ.search_listings(sort="price_desc")]
    assert asc == sorted(asc) and desc == sorted(desc, reverse=True)

    nakuru = MQ.search_listings(location="nakuru")
    assert nakuru and all(l["location"] == "Nakuru" for l in nakuru)

    with pytest.raises(ValueError):
        MQ.search_listings(sort="random")
    with pytest.raises(ValueError):
        MQ.search_listings(min_price=-1)
    with pytest.raises(ValueError):
        MQ.search_listings(min_price=100, max_price=10)


def test_search_is_injection_safe(seeded_db):
    assert MQ.search_listings(query="' OR 1=1; DROP TABLE listings; --") == []
    assert len(MQ.search_listings()) > 0


def test_create_listing_and_validation(seeded_db):
    seller, maize = _user_id("amina_w"), _crop_id("Maize")
    lid = MQ.create_listing({"seller_id": seller, "crop_id": maize, "quantity": 100,
                             "price_per_unit": 47.5, "location": "Nakuru", "description": "Dry maize"})
    listing = MQ.get_listing(lid)
    assert listing["crop_name"] == "Maize" and listing["currency"] == "KES"
    bad_inputs = [
        {"quantity": -5}, {"quantity": 0}, {"price_per_unit": -1}, {"price_per_unit": "abc"},
        {"crop_id": 999_999}, {"seller_id": 999_999}, {"quantity": None},
    ]
    for override in bad_inputs:
        data = {"seller_id": seller, "crop_id": maize, "quantity": 10, "price_per_unit": 40, **override}
        with pytest.raises(ValueError):
            MQ.create_listing(data)


def test_db_check_constraints_block_bad_rows(seeded_db):
    """Even raw SQL can't insert a negative price or a 6-star review."""
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection() as conn:
            conn.execute("INSERT INTO listings (seller_id, crop_id, quantity, price_per_unit) VALUES (1, 1, 5, -3)")
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection() as conn:
            conn.execute("INSERT INTO reviews (reviewer_id, seller_id, rating) VALUES (2, 1, 6)")
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection() as conn:  # foreign keys are ON
            conn.execute("INSERT INTO watchlist (user_id, crop_id) VALUES (999999, 1)")


def test_price_history_and_latest_price(seeded_db):
    cid = _crop_id("Coffee")
    history = MQ.get_price_history(cid, days=30)
    assert len(history) == 30
    assert set(history[0]) == {"date", "price"}
    assert [h["date"] for h in history] == sorted(h["date"] for h in history)
    assert len(MQ.get_price_history(cid)) == 90

    latest = MQ.get_latest_price(cid)
    full = MQ.get_price_history(cid, days=8)
    expected = round((full[-1]["price"] - full[0]["price"]) / full[0]["price"] * 100, 2)
    assert latest["price"] == full[-1]["price"]
    assert latest["change_pct"] == expected


def test_record_purchase(seeded_db):
    seller, buyer = _user_id("amina_w"), _user_id("john_otieno")
    lid = MQ.create_listing({"seller_id": seller, "crop_id": _crop_id("Beans"),
                             "quantity": 100, "price_per_unit": 120})
    pid = MQ.record_purchase(lid, buyer, 40)
    assert pid > 0
    assert MQ.get_listing(lid)["quantity"] == 60
    history = MQ.get_purchase_history(buyer)
    assert history[0]["id"] == pid and history[0]["total_price"] == 4800

    with pytest.raises(ValueError, match="available"):
        MQ.record_purchase(lid, buyer, 61)
    with pytest.raises(ValueError):
        MQ.record_purchase(lid, buyer, -1)
    with pytest.raises(ValueError, match="own"):
        MQ.record_purchase(lid, seller, 1)

    MQ.record_purchase(lid, buyer, 60)
    assert MQ.get_listing(lid)["status"] == "sold"
    with pytest.raises(ValueError, match="no longer"):
        MQ.record_purchase(lid, buyer, 1)


def test_watchlist(seeded_db):
    uid = _new_user("watcher", "buyer")
    rice = _crop_id("Rice")
    assert MQ.add_to_watchlist(uid, rice) is True
    assert MQ.add_to_watchlist(uid, rice) is False  # already there
    assert MQ.is_in_watchlist(uid, rice)
    watch = MQ.get_watchlist(uid)
    assert watch[0]["name"] == "Rice" and watch[0]["price"] > 0 and "change_pct" in watch[0]
    assert MQ.remove_from_watchlist(uid, rice) is True
    assert MQ.get_watchlist(uid) == []
    with pytest.raises(ValueError):
        MQ.add_to_watchlist(uid, 999_999)


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------
def test_messages_flow(seeded_db):
    a, b = _new_user("alice_buyer", "buyer"), _new_user("bob_farmer", "farmer")
    MsgQ.send_message(a, b, "Hi Bob, is your maize available?")
    MsgQ.send_message(b, a, "Yes, 200kg.", channel="sms")
    MsgQ.send_message(a, b, "Great, I'll take it.")

    thread = MsgQ.get_thread(a, b)
    assert [m["body"] for m in thread] == ["Hi Bob, is your maize available?", "Yes, 200kg.", "Great, I'll take it."]
    assert thread[1]["channel"] == "sms"

    convos = MsgQ.get_conversations(b)
    assert len(convos) == 1
    assert convos[0]["other_id"] == a and convos[0]["unread_count"] == 2
    assert convos[0]["last_body"] == "Great, I'll take it."
    assert MsgQ.get_unread_count(b) == 2

    assert MsgQ.mark_read(b, a) == 2
    assert MsgQ.get_conversations(b)[0]["unread_count"] == 0


def test_message_validation(seeded_db):
    a, b = _user_id("john_otieno"), _user_id("amina_w")
    for kwargs in ({"body": "   "}, {"body": "hi", "channel": "fax"}, {"body": "x" * 2001},
                   {"body": "hi", "listing_id": 999_999}):
        with pytest.raises(ValueError):
            MsgQ.send_message(a, b, **kwargs)
    with pytest.raises(ValueError):
        MsgQ.send_message(a, a, "talking to myself")
    with pytest.raises(ValueError):
        MsgQ.send_message(a, 999_999, "hello?")


def test_seeded_conversations_exist(seeded_db):
    convos = MsgQ.get_conversations(_user_id("amina_w"))
    assert any(c["other_username"] == "john_otieno" for c in convos)


# --------------------------------------------------------------------------
# Alerts and plantings
# --------------------------------------------------------------------------
def test_price_alerts(seeded_db):
    uid, maize = _new_user("alerter", "buyer"), _crop_id("Maize")
    aid = AQ.create_price_alert(uid, maize, 50, "above")
    alerts = AQ.get_active_alerts(uid)
    assert alerts[0]["id"] == aid and alerts[0]["crop_name"] == "Maize"
    assert AQ.deactivate_alert(aid) is True
    assert AQ.get_active_alerts(uid) == []
    for args in ((uid, maize, 50, "sideways"), (uid, maize, -5, "below"), (uid, 999_999, 50, "below")):
        with pytest.raises(ValueError):
            AQ.create_price_alert(*args)


def test_add_planting_computes_harvest(seeded_db):
    uid, maize = _new_user("planter"), _crop_id("Maize")
    growth = MQ.get_crop(maize)["growth_days"]
    planted = date.today() - timedelta(days=10)
    AQ.add_planting(uid, maize, planted.isoformat(), 2.5)
    plantings = AQ.get_plantings(uid)
    assert plantings[0]["expected_harvest"] == (planted + timedelta(days=growth)).isoformat()
    assert plantings[0]["days_to_harvest"] == growth - 10
    assert plantings[0]["crop_name"] == "Maize"

    with pytest.raises(ValueError):
        AQ.add_planting(uid, maize, "13/11/2026", 1)
    with pytest.raises(ValueError):
        AQ.add_planting(uid, maize, (date.today() + timedelta(days=5)).isoformat(), 1)
    with pytest.raises(ValueError):
        AQ.add_planting(uid, maize, planted, -2)


def test_seed_has_harvest_within_a_week(seeded_db):
    """The demo needs at least one 'harvest soon' alert on the home page."""
    soon = [p for p in AQ.get_plantings(_user_id("amina_w")) if 0 <= p["days_to_harvest"] <= 7]
    assert soon


# --------------------------------------------------------------------------
# Prediction (Phase 6)
# --------------------------------------------------------------------------
def test_predict_price_shape(seeded_db):
    from Databases import Prediction

    maize = _crop_id("Maize")
    points = Prediction.predict_price(maize, days_ahead=30)
    assert len(points) == 30 and set(points[0]) == {"date", "predicted_price"}
    last_real = MQ.get_price_history(maize, days=1)[-1]
    assert points[0]["date"] == (date.fromisoformat(last_real["date"]) + timedelta(days=1)).isoformat()
    # Anchored: the first forecast is close to today's price
    assert abs(points[0]["predicted_price"] - last_real["price"]) / last_real["price"] < 0.08
    with pytest.raises(ValueError):
        Prediction.predict_price(maize, days_ahead=0)
    with pytest.raises(ValueError):
        Prediction.predict_price(999_999)


def test_prediction_mae_on_held_out_30_days(seeded_db):
    """The model must stay within 6% average error on the last 30 days for every crop."""
    from Databases import Prediction

    for crop in MQ.get_all_crops():
        result = Prediction.evaluate_model(crop["id"])
        assert result["days"] == 30
        assert result["mape_pct"] < 6, result


def test_season_advice_is_plain_english(seeded_db):
    from Databases import Prediction

    advice = Prediction.get_season_advice(_crop_id("Maize"), 3)
    assert advice.startswith("Maize prices usually peak in")
    assert "March is planting time for Maize" in advice
    with pytest.raises(ValueError):
        Prediction.get_season_advice(_crop_id("Maize"), 13)


def test_prediction_with_little_history(empty_db):
    from Databases import Prediction

    with get_connection() as conn:
        conn.execute("INSERT INTO crops (name, growth_days) VALUES ('Sesame', 100)")
        cid = conn.execute("SELECT id FROM crops WHERE name='Sesame'").fetchone()["id"]
        conn.execute("INSERT INTO price_history (crop_id, date, price) VALUES (?, ?, 100)",
                     (cid, date.today().isoformat()))
    assert Prediction.predict_price(cid) == []
    assert "Not enough price history" in Prediction.get_season_advice(cid, 1)
