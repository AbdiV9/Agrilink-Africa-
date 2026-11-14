# Owner: Person 3 (Integration, Logic & API Lead)
"""Auth, session and service tests. Run with:  pytest tests/test_auth.py -v

No test touches the internet or a paid API: weather falls back to sample
data, SMS is log-only without AT_API_KEY, and the chatbot is forced offline.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import config
from Auth import auth, chatbot, communication, notifications, translation, weather
from Auth.session import Session, session
from Auth.validation import (normalize_phone, validate_email, validate_password, validate_phone,
                             validate_registration, validate_username)
from Databases import Alert_Queries, Market_Queries, Message_Queries, User_Queries

GOOD_FORM = {
    "username": "new_farmer", "full_name": "New Farmer", "email": "new@farm.co.ke", "phone": "+254700111222",
    "password": "Secret12!", "confirm_password": "Secret12!", "role": "farmer", "country": "Kenya",
    "region": "Kisumu",
}


@pytest.fixture(autouse=True)
def clean_state(monkeypatch: pytest.MonkeyPatch):
    """Fresh session, no lockouts, no AI/SMS/DeepL keys, no network for every test."""
    session.clear()
    auth.reset_lockouts()
    monkeypatch.setattr(config, "AI_ENABLED", False)
    monkeypatch.setattr(config, "AI_PROVIDER", "")
    monkeypatch.setattr(config, "SMS_ENABLED", False)
    monkeypatch.setattr(config, "TRANSLATION_ENABLED", False)
    monkeypatch.setattr(weather, "_fetch", lambda lat, lon: (_ for _ in ()).throw(ConnectionError("offline")))
    weather._cache.clear()
    yield
    session.clear()
    auth.reset_lockouts()


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value,ok", [
    ("amina_w", True), ("abc", True), ("a" * 20, True),
    ("ab", False), ("a" * 21, False), ("has space", False), ("bad-dash", False), ("", False),
])
def test_validate_username(value, ok):
    assert validate_username(value)[0] is ok


@pytest.mark.parametrize("value,ok", [
    ("amina@example.com", True), ("a.b+c@farm.co.ke", True),
    ("no-at-sign", False), ("a@b", False), ("@example.com", False), ("", False),
])
def test_validate_email(value, ok):
    assert validate_email(value)[0] is ok


@pytest.mark.parametrize("value,ok", [
    ("+254712345678", True), ("+254 712 345 678", True), ("+2348031234567", True), ("+252615123456", True),
    ("+256772123456", True), ("+233244123456", True), ("+27821234567", True),
    ("0712345678", False), ("+2540712345678", False), ("+25471234", False), ("+447911123456", False),
    ("+254abc", False), ("", False),
])
def test_validate_phone(value, ok):
    assert validate_phone(value)[0] is ok, validate_phone(value)


def test_normalize_phone():
    assert normalize_phone("+254 (712) 345-678") == "+254712345678"


@pytest.mark.parametrize("value,ok", [
    ("Password123!", True), ("Secret12!", True),
    ("short1!", False), ("alllowercase1!", False), ("ALLUPPER1!", False), ("NoDigits!!", False),
    ("NoSymbol123", False), ("", False),
])
def test_validate_password(value, ok):
    assert validate_password(value)[0] is ok


def test_password_message_lists_what_is_missing():
    ok, msg = validate_password("abc")
    assert not ok and "8 characters" in msg and "upper-case" in msg and "symbol" in msg


def test_validate_registration_collects_field_errors():
    assert validate_registration(GOOD_FORM) == {}
    errors = validate_registration({**GOOD_FORM, "username": "x", "confirm_password": "nope", "role": "trader",
                                    "region": ""})
    assert set(errors) == {"username", "confirm_password", "role", "region"}


# --------------------------------------------------------------------------
# Registration, login, lockout, logout
# --------------------------------------------------------------------------
def test_register_then_login(seeded_db):
    ok, msg = auth.register_user(GOOD_FORM)
    assert ok, msg
    stored = User_Queries.get_user_by_username("new_farmer")
    assert stored["password_hash"] != "Secret12!"
    assert stored["phone"] == "+254700111222"
    ok, user = auth.login_user("new_farmer", "Secret12!")
    assert ok and user["username"] == "new_farmer"
    assert "password_hash" not in user


def test_register_rejects_duplicates_and_bad_input(seeded_db):
    ok, msg = auth.register_user({**GOOD_FORM, "username": "amina_w"})
    assert not ok and "username" in msg.lower()
    ok, msg = auth.register_user({**GOOD_FORM, "email": "amina_w@example.com"})
    assert not ok and "email" in msg.lower()
    ok, msg = auth.register_user({**GOOD_FORM, "password": "weak", "confirm_password": "weak"})
    assert not ok and "Password needs" in msg


def test_login_success_sets_session(seeded_db):
    ok, user = auth.login_user("amina_w", "Password123!")
    assert ok
    assert session.is_logged_in() and session.user_id == user["id"]
    assert "password_hash" not in session.user


def test_login_wrong_password_counts_down(seeded_db):
    ok, msg = auth.login_user("amina_w", "wrong")
    assert not ok and "4 attempts left" in msg
    assert not session.is_logged_in()


def test_unknown_user_gets_generic_message(seeded_db):
    ok, msg = auth.login_user("nobody_here", "Password123!")
    assert not ok and msg.startswith(auth.GENERIC_LOGIN_ERROR)


def test_lockout_after_five_failures_and_expiry(seeded_db, monkeypatch):
    now = [1_000_000.0]
    monkeypatch.setattr(auth, "_clock", lambda: now[0])
    for _ in range(4):
        assert not auth.login_user("amina_w", "wrong")[0]
    ok, msg = auth.login_user("amina_w", "wrong")
    assert not ok and "locked" in msg
    # Even the right password is refused while locked
    ok, msg = auth.login_user("amina_w", "Password123!")
    assert not ok and "Try again in 5 min" in msg
    now[0] += 4 * 60
    assert not auth.login_user("amina_w", "Password123!")[0]
    now[0] += 61
    ok, _ = auth.login_user("amina_w", "Password123!")
    assert ok


def test_lockout_is_per_username(seeded_db):
    for _ in range(5):
        auth.login_user("amina_w", "wrong")
    assert auth.login_user("john_otieno", "Password123!")[0]


def test_login_requires_both_fields(seeded_db):
    assert auth.login_user("", "x") == (False, "Enter your username and password.")


def test_logout_clears_session(seeded_db):
    auth.login_user("amina_w", "Password123!")
    session.data["chat_history"] = [{"role": "user", "text": "hi"}]
    auth.logout()
    assert not session.is_logged_in() and session.data == {}


def test_session_is_singleton_and_refreshes(seeded_db):
    assert Session() is session
    auth.login_user("amina_w", "Password123!")
    User_Queries.update_user(session.user_id, {"dark_mode": True, "text_scale": 1.3})
    assert session.user["dark_mode"] == 0
    session.refresh()
    assert session.user["dark_mode"] == 1 and session.user["text_scale"] == 1.3


# --------------------------------------------------------------------------
# Communication
# --------------------------------------------------------------------------
def test_message_seller_template_and_sms_log(seeded_db):
    buyer = User_Queries.get_user_by_username("john_otieno")
    listing = Market_Queries.get_listing(1)
    ok, note = communication.message_seller(buyer, listing, qty=25, via_sms=True)
    assert ok and "logged" in note
    last = Message_Queries.get_thread(buyer["id"], listing["seller_id"])[-1]
    assert last["body"].startswith("Hi, I'm interested in your 25kg of ")
    assert last["channel"] == "sms" and last["listing_id"] == 1


def test_message_seller_blocks_own_listing(seeded_db):
    listing = Market_Queries.get_listing(1)
    seller = User_Queries.get_user_by_id(listing["seller_id"])
    assert communication.message_seller(seller, listing) == (False, "This is your own listing.")


def test_send_sms_validation():
    assert communication.send_sms("0712345678", "hi")[0] is False
    assert communication.send_sms("+254712345678", "  ")[0] is False
    assert communication.send_sms("+254712345678", "Hello")[0] is True  # log-only mode


# --------------------------------------------------------------------------
# Weather (offline fallbacks)
# --------------------------------------------------------------------------
def test_weather_sample_when_offline():
    forecast = weather.get_forecast_for_region("Nakuru")
    assert forecast["region"] == "Nakuru" and forecast["source"] == "sample"
    assert len(forecast["days"]) == 7
    assert {"date", "t_max", "t_min", "rain_mm", "rain_chance", "code", "condition"} <= set(forecast["days"][0])


def test_weather_cache_used_when_api_fails(monkeypatch):
    live = [{"date": date.today().isoformat(), "t_max": 25, "t_min": 14, "rain_mm": 2, "rain_chance": 40,
             "code": 61, "condition": "Light rain"}]
    monkeypatch.setattr(weather, "_fetch", lambda lat, lon: live)
    assert weather.get_forecast(-1.29, 36.82)["source"] == "live"
    assert weather.get_forecast(-1.29, 36.82)["source"] == "cache"          # within the hour
    monkeypatch.setattr(weather, "_fetch", lambda lat, lon: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(weather, "_clock", lambda: 10**12)                   # cache expired
    stale = weather.get_forecast(-1.29, 36.82)
    assert stale["source"] == "cache" and stale["days"] == live


def test_region_lookup():
    assert weather.lookup_region("KANO")[0] == "Kano"
    assert weather.lookup_region("Nakuru County")[0] == "Nakuru"
    name, lat, lon = weather.lookup_region("Somewhere Unknown")
    assert name == "Somewhere Unknown" and (lat, lon) == weather.REGION_COORDS["nairobi"]


# --------------------------------------------------------------------------
# Translation
# --------------------------------------------------------------------------
def test_translation_built_in_and_fallback():
    assert translation.t("nav.home", lang="sw") == "Nyumbani"
    assert translation.t("nav.home", lang="so") == "Hoyga"
    assert translation.t("nav.home", lang="en") == "nav.home"          # English: caller's default is used
    assert translation.t("nav.home", "Home", lang="ha") == "nav.home"  # no DeepL key
    assert translation.translate("Hello", "fr") == "Hello"


def test_translations_keep_placeholders():
    import re

    for lang, strings in translation.STRINGS.items():
        for key, text in strings.items():
            for name in re.findall(r"\{(\w+)\}", text):
                assert name in {"crop", "n", "price", "up", "q", "unit", "amount", "chg"}, (lang, key, name)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
def test_price_alert_fires_once(seeded_db):
    auth.login_user("john_otieno", "Password123!")
    uid = session.user_id
    price = Market_Queries.get_latest_price(1)["price"]
    Alert_Queries.create_price_alert(uid, 1, price - 1, "above")
    fired = [n for n in notifications.check_price_alerts(uid) if n["crop_id"] == 1]
    assert fired and fired[0]["kind"] == "price"
    assert not [n for n in notifications.check_price_alerts(uid) if n["crop_id"] == 1]


def test_harvest_and_season_alerts(seeded_db):
    amina = User_Queries.get_user_by_username("amina_w")["id"]
    harvest = notifications.check_harvest_alerts(amina)
    assert any("Maize" in n["title"] for n in harvest)
    maize = next(c for c in Market_Queries.get_all_crops() if c["name"] == "Maize")
    season = notifications.check_season_alerts(date(2026, maize["season_start_month"], 1))
    assert any(n["crop_id"] == maize["id"] and "Planting season" in n["title"] for n in season)


def test_run_checks_dedupes(seeded_db):
    auth.login_user("amina_w", "Password123!")
    first = notifications.run_checks(session.user_id)
    assert first
    assert notifications.run_checks(session.user_id) == []


# --------------------------------------------------------------------------
# Chatbot (offline mode)
# --------------------------------------------------------------------------
def test_find_crops_understands_local_words(seeded_db):
    crops = Market_Queries.get_all_crops()
    names = {c["name"] for c in chatbot.find_crops("Bei ya mahindi na nyanya?", crops)}
    assert names == {"Maize", "Tomatoes"}
    assert {c["name"] for c in chatbot.find_crops("best potato price", crops)} == {"Potatoes"}


def test_context_includes_user_weather_and_forecast(seeded_db):
    user = User_Queries.get_user_by_username("amina_w")
    ctx = chatbot.build_context(user, "Best time to sell my maize?")
    assert ctx["user"]["region"] == "Nakuru" and ctx["language"] == "Kiswahili"
    assert ctx["plantings"] and len(ctx["market"]) >= 12
    assert ctx["mentioned"][0]["name"] == "Maize" and ctx["mentioned"][0]["forecast_30d"]
    text = chatbot.format_context(ctx)
    assert "Reply in: Kiswahili" in text and "Maize" in text


@pytest.mark.parametrize("question,expected", [
    ("What should I plant this month?", "plant"),
    ("Best time to sell my maize?", "Maize"),
    ("Find cheapest tomatoes near me", "Cheapest Tomatoes"),
    ("Summarise today's market", "Market summary"),
])
def test_offline_answers(seeded_db, question, expected):
    user = User_Queries.get_user_by_username("amina_w")
    answer = chatbot.ask(user, question)
    assert expected.lower() in answer.lower() and "Offline mode" in answer


def test_ask_handles_empty_and_api_failure(seeded_db, monkeypatch):
    assert "Ask me anything" in chatbot.ask(None, "   ")
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "AI_PROVIDER", "anthropic")

    def boom(messages):
        raise RuntimeError("Can't reach the AI service (no internet?).")

    monkeypatch.setattr(chatbot, "_ask_claude", boom)
    answer = chatbot.ask(User_Queries.get_user_by_username("amina_w"), "Summarise today's market")
    assert answer.startswith("⚠️ Can't reach the AI service") and "Market summary" in answer


def test_history_messages_alternate():
    msgs = chatbot._history_messages({"history": [
        {"role": "assistant", "text": "welcome"}, {"role": "user", "text": "a"},
        {"role": "user", "text": "b"}, {"role": "assistant", "text": "c"}]})
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "a\n\nb"
