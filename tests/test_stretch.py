# Owner: Person 3 (Integration, Logic & API Lead)
"""Tests for the STRETCH features: server, email, news, purchase history.

Run with:  pytest tests/test_stretch.py -v   (no internet, SMTP or SMS needed)
"""

from __future__ import annotations

import pytest

import config
from Auth import communication, email_service, news
from Databases import Market_Queries, Message_Queries, User_Queries

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
<item><title>Maize prices fall in Nakuru - Daily Nation</title><link>https://example.com/a</link>
<pubDate>Thu, 12 Nov 2026 08:00:00 GMT</pubDate><description>&lt;b&gt;Harvest&lt;/b&gt; arrives</description></item>
<item><title>Cocoa demand strong</title><link>https://example.com/b</link><source>Reuters</source>
<pubDate>Fri, 13 Nov 2026 08:00:00 GMT</pubDate></item>
<item><title>Bad link</title><link>javascript:alert(1)</link></item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "SMS_ENABLED", False)
    monkeypatch.setattr(config, "SMS_SERVER_URL", "")
    monkeypatch.setattr(config, "EMAIL_ENABLED", False)
    monkeypatch.setattr(config, "SERVER_API_TOKEN", "test-token")
    monkeypatch.setattr(news, "_fetch", lambda url: (_ for _ in ()).throw(ConnectionError("offline")))
    news._cache.clear()
    yield
    news._cache.clear()


# --------------------------------------------------------------------------
# News
# --------------------------------------------------------------------------
def test_parse_feed_cleans_and_orders():
    items = news.parse_feed(RSS)
    assert [i["title"] for i in items] == ["Cocoa demand strong", "Maize prices fall in Nakuru"]
    assert items[1]["source"] == "Daily Nation" and items[1]["summary"] == "Harvest arrives"
    assert items[0]["source"] == "Reuters"
    assert all(i["link"].startswith("https://") for i in items)


def test_news_live_then_cache_then_crop_filter(monkeypatch):
    monkeypatch.setattr(news, "_fetch", lambda url: news.parse_feed(RSS))
    assert news.get_news()["source"] == "live"
    second = news.get_news(crop="maize")
    assert second["source"] == "cache" and [i["title"] for i in second["items"]] == ["Maize prices fall in Nakuru"]


def test_news_sample_when_offline():
    data = news.get_news(limit=3)
    assert data["source"] == "sample" and len(data["items"]) == 3


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
def test_email_logged_without_smtp():
    assert email_service.send_email("a@b.co", "Hi", "Body") == (
        True, "Email logged (add SMTP settings in .env to send real email).")
    assert email_service.send_email("not-an-email", "Hi", "Body")[0] is False
    assert email_service.send_email("a@b.co", "", "Body")[0] is False


def test_email_uses_smtp(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host

        def starttls(self, context=None):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent.append(msg)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(config, "EMAIL_ENABLED", True)
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    monkeypatch.setattr(config, "EMAIL_FROM", "noreply@agrilink.africa")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    user = {"username": "john_otieno", "full_name": "John Otieno", "email": "john@example.com", "role": "buyer"}
    assert email_service.send_welcome_email(user) == (True, "Email sent.")
    assert sent[0]["To"] == "john@example.com" and "Welcome" in sent[0]["Subject"]
    notes = [{"kind": "price", "title": "Maize rose above KES 40.00", "body": "Now KES 41.00/kg."},
             {"kind": "season", "title": "x", "body": "y"}]
    assert email_service.send_alert_email(user, notes)[0]
    assert sent[1]["Subject"] == "🔔 Maize rose above KES 40.00" and "season" not in sent[1].get_content()


# --------------------------------------------------------------------------
# Purchase history
# --------------------------------------------------------------------------
def test_sales_history_matches_purchases(seeded_db):
    amina = User_Queries.get_user_by_username("amina_w")["id"]
    sales = Market_Queries.get_sales_history(amina)
    assert sales and all(Market_Queries.get_listing(s["listing_id"])["seller_id"] == amina for s in sales)
    assert {"crop_name", "buyer_username", "total_price", "unit"} <= set(sales[0])
    assert [s["created_at"] for s in sales] == sorted((s["created_at"] for s in sales), reverse=True)


def test_purchases_summary():
    from UI.purchases_page import summarise

    rows = [{"total_price": 100, "crop_name": "Maize", "currency": "KES"},
            {"total_price": 250, "crop_name": "Coffee"}, {"total_price": 50, "crop_name": "Maize"}]
    assert summarise(rows) == {"total": 400, "orders": 3, "top_crop": "Coffee", "currency": "KES"}
    assert summarise([])["top_crop"] is None


# --------------------------------------------------------------------------
# SMS through the server
# --------------------------------------------------------------------------
def test_app_routes_sms_via_server(monkeypatch):
    calls = []

    class Resp:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return {"ok": True, "detail": "SMS sent."}

    import requests

    monkeypatch.setattr(config, "SMS_SERVER_URL", "https://agrilink.example.com")
    monkeypatch.setattr(requests, "post", lambda url, **kw: calls.append((url, kw)) or Resp())
    assert communication.send_sms("+254712345678", "Hello") == (True, "SMS sent.")
    url, kw = calls[0]
    assert url == "https://agrilink.example.com/api/sms/send"
    assert kw["headers"]["Authorization"] == "Bearer test-token" and kw["json"]["phone"] == "+254712345678"
    assert communication.send_sms("0712", "Hello")[0] is False and len(calls) == 1


# --------------------------------------------------------------------------
# FastAPI server
# --------------------------------------------------------------------------
@pytest.fixture
def client(seeded_db):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from server import app as server_app

    server_app._sms_log.clear()
    with TestClient(server_app.app) as c:
        yield c


def test_server_read_api(client):
    assert client.get("/health").json()["ok"] is True
    crops = client.get("/api/crops").json()
    assert len(crops) == 12 and crops[0]["price"] is not None
    maize = next(c for c in crops if c["name"] == "Maize")
    assert len(client.get(f"/api/crops/{maize['id']}/prices?days=30").json()["history"]) == 30
    assert len(client.get(f"/api/crops/{maize['id']}/forecast?days=7").json()["forecast"]) == 7
    assert client.get("/api/crops/9999/prices").status_code == 404
    rows = client.get("/api/listings", params={"crop_id": maize["id"], "sort": "price_asc"}).json()
    assert rows and all("seller_phone" not in r for r in rows)
    assert [r["price_per_unit"] for r in rows] == sorted(r["price_per_unit"] for r in rows)
    assert client.get("/api/listings", params={"sort": "drop table"}).status_code == 422
    assert "seller_phone" not in client.get(f"/api/listings/{rows[0]['id']}").json()
    assert client.get("/api/news?limit=2").json()["source"] == "sample"


def test_server_sms_requires_token(client):
    body = {"phone": "+254712345678", "body": "Hi"}
    assert client.post("/api/sms/send", json=body).status_code == 401
    assert client.post("/api/sms/send", json=body, headers={"Authorization": "Bearer nope"}).status_code == 401
    ok = client.post("/api/sms/send", json=body, headers={"Authorization": "Bearer test-token"})
    assert ok.status_code == 200 and ok.json()["ok"] is True
    bad = client.post("/api/sms/send", json={"phone": "0712", "body": "Hi"},
                      headers={"Authorization": "Bearer test-token"})
    assert bad.status_code == 400


def test_server_sms_rate_limit(client):
    headers = {"Authorization": "Bearer test-token"}
    codes = [client.post("/api/sms/send", json={"phone": "+254712345678", "body": "Hi"}, headers=headers).status_code
             for _ in range(22)]
    assert codes.count(200) == 20 and codes[-1] == 429


def test_server_disabled_without_token(client, monkeypatch):
    monkeypatch.setattr(config, "SERVER_API_TOKEN", "")
    assert client.post("/api/sms/send", json={"phone": "+254712345678", "body": "Hi"},
                       headers={"Authorization": "Bearer "}).status_code == 503
    assert client.post("/sms/inbound", content=b"from=%2B254712345678&text=hi").status_code == 401


def test_inbound_sms_becomes_message(client):
    amina = User_Queries.get_user_by_username("amina_w")
    john = User_Queries.get_user_by_username("john_otieno")
    form = {"from": amina["phone"], "to": "12345", "text": "@john_otieno Yes, still 400kg left"}
    assert client.post("/sms/inbound?token=wrong", data=form).status_code == 401
    assert client.post("/sms/inbound?token=test-token", data=form).text == "OK"
    last = Message_Queries.get_thread(amina["id"], john["id"])[-1]
    assert last["body"] == "Yes, still 400kg left" and last["channel"] == "sms" and last["sender_id"] == amina["id"]
    # Without @username it replies to the latest conversation partner
    client.post("/sms/inbound?token=test-token", data={"from": amina["phone"], "text": "Pickup Friday?"})
    partner = Message_Queries.get_conversations(amina["id"])[0]
    assert partner["last_body"] == "Pickup Friday?"
    # Unknown phones are ignored but still get 200 so AT doesn't retry
    assert client.post("/sms/inbound?token=test-token", data={"from": "+254799999999", "text": "hi"}).text == "OK"
