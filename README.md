<!-- Owner: Person 3 (Integration, Logic & API Lead) -->
# AgriLink Africa 

AgriLink Africa is a crop marketplace for African farmers and buyers, built in Python with Flet. It combines:

* a peer-to-peer market where you list, search and filter crops and message the seller,
* trading-style price pages with live-looking charts and AI forecasts,
* a 7-day weather forecast for your region,
* an AI assistant that knows today's prices, forecasts, weather and your plantings,
* price, harvest and season alerts,
* Swahili and Somali built in (more languages through DeepL), dark mode and adjustable text size.

It runs as a desktop window (phone-shaped by default) or in a browser. Every external service is optional. Without its key, each feature falls back to offline or sample behaviour, so the app always runs.

---

## 1. Setup

You need **Python 3.11 or newer**.

```bash
cd agrilink
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Flet is pinned to `>=0.24,<0.29` on purpose, because Flet 0.80 and later changed the API this app uses. Don't upgrade it on its own.

### Optional keys in `.env`

| Key | Feature it turns on | Without it |
|---|---|---|
| `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) | Real AI chatbot answers | Rule-based "offline mode" answers from the same data |
| `AT_USERNAME` / `AT_API_KEY` | Real SMS to sellers through Africa's Talking (`sandbox` while testing) | The SMS is logged and saved as a message |
| `DEEPL_KEY` | Translation into languages other than Swahili and Somali | English for those languages |
| *(none needed)* | Weather from Open-Meteo, which is free and needs no key | A sample forecast when you're offline |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | Real emails: welcome, price alerts, purchase receipts (Gmail needs an app password) | Emails are logged |
| `SMS_SERVER_URL` + `SERVER_API_TOKEN` | Send SMS through your Render server, so the AT key stays off laptops | Local key, or logged |
| `NEWS_FEED_URL` | A different RSS feed for the News page (Google News is the default, no key) | Sample headlines when offline |

Keys are only ever read from `.env`, through `config.py`. **Never commit `.env`.**

## 2. Run

```bash
python main.py                 # desktop window
flet run --web main.py         # in a browser
```

On the first run, `agrilink.db` is created and seeded with 12 crops, 8 users, 36 listings, a year of price history, purchases, reviews, messages and plantings.

**Demo logins** (all use the password `Password123!`):

| Username | Role | Where | Good for showing |
|---|---|---|---|
| `amina_w` | farmer ✔ | Nakuru, KE (Swahili) | Harvest alert, maize listings, Swahili UI |
| `john_otieno` | buyer | Nairobi, KE | Buying, messaging sellers, watchlist |
| `chidi_okafor` | farmer ✔ | Kano, NG | Sorghum harvest due, reviews |
| `kwame_m` | both ✔ | Kumasi, GH | Cocoa and coffee |
| `hodan_ali` | farmer | Baidoa, SO | Somali UI |

To reset the data, delete `agrilink.db`, or run `python -c "from Databases.Database_Setup import reset_database; reset_database()"`.

### Working on the UI without the backend

```bash
python -m UI.preview components                 # gallery of every shared component
python -m UI.preview /market --mock --dark      # a single page with mock data
python -m UI.preview /crop/1 --scale 1.4 --web
```

### The server (STRETCH, `server/app.py`)

A small FastAPI app that acts as the SMS gateway (outgoing and incoming) and a read-only market API.

```bash
uvicorn server.app:app --reload        # then open http://127.0.0.1:8000/docs
```

| Endpoint | What it does |
|---|---|
| `GET /health` | Status, used by Render's health check |
| `GET /api/crops`, `/api/crops/{id}/prices?days=90`, `/api/crops/{id}/forecast?days=30` | Prices, history and the AI forecast |
| `GET /api/listings?query=&crop_id=&min_price=&max_price=&location=&sort=` and `/api/listings/{id}` | Active listings (never includes phone numbers) |
| `GET /api/news?crop=maize` | The news feed |
| `POST /api/sms/send` | Sends an SMS. Needs `Authorization: Bearer <SERVER_API_TOKEN>`, max 20 a minute |
| `POST /sms/inbound?token=<SERVER_API_TOKEN>` | Africa's Talking incoming-SMS callback. A text from a registered phone becomes an in-app message; start it with `@username` to pick who gets it |

**Deploy on Render:**
1. Push the project to GitHub.
2. In Render, choose **New > Blueprint** and pick the repo. `render.yaml` sets up the service and generates `SERVER_API_TOKEN`.
3. Add `AT_API_KEY` in the Render dashboard.
4. Copy the service URL and the generated token into each laptop's `.env` as `SMS_SERVER_URL` and `SERVER_API_TOKEN`.
5. In Africa's Talking, set the incoming-SMS callback to `https://<your-service>.onrender.com/sms/inbound?token=<SERVER_API_TOKEN>`.

### Checking the price model

```bash
python -m Databases.Prediction     # MAE on the last 30 days for every crop
```

## 3. Test

```bash
pytest -v          # 111 tests, about 30 s, no internet needed
pytest tests/test_db.py      # database and prediction (Person 1)
pytest tests/test_auth.py    # validation, login lockout, services, chatbot (Person 3)
pytest tests/test_stretch.py # server, email, news, purchase history (Person 3)
```

The tests use a temporary database (via `AGRILINK_DB_PATH`), so your real `agrilink.db` is never touched. All AI, SMS, DeepL and weather calls are switched off or faked.


### How the pieces connect

```
main.py ── routes (/login /register /home /market /crop/<id> /listing/<id> /news /purchases
   │                /sell /messages[/<user_id>] /chatbot /profile/<id> /settings)
   │
   ├─ UI/*_page.py ── build_<name>_view(page, **params) -> ft.View
   │      └─ UI.mock_data.call("search_listings", ...)  real function, or mock if USE_MOCK
   │
   ├─ Auth/ ── session, login, SMS, weather, translation (t / tr), notifications, chatbot.ask()
   │
   └─ Databases/ ── SQLite (agrilink.db), parameterised queries, Prediction (Ridge regression)
```

* Pages never write SQL. They call `Databases.*` functions, through `UI.mock_data.call` so P2 can work before P1's functions exist.
* Cross-page state lives in `Auth.session.session.data`, for example `message_draft`, `chatbot_prefill`, `market_filters` and `banners`.
* Errors: the database layer raises `ValueError` with a human message, and the UI shows it inline next to the field.

---

## 5. Final integration checklist

Run through this on each person's machine before the demo.

**Setup**
- [ ] `pip install -r requirements.txt` succeeds on Python 3.11+ (Windows and macOS)
- [ ] `pytest` shows 111 passed
- [ ] Deleting `agrilink.db` and running `python main.py` re-creates and seeds it

**Auth**
- [ ] Register with bad data and see inline errors on each field (phone must be `+254…`-style)
- [ ] Register a new user, then log in with them
- [ ] 5 wrong passwords lock the account for 5 minutes, with a message saying so
- [ ] Log out returns to `/login`, and the back button can't reach `/home`

**Market and selling**
- [ ] Search plus filters (crop, location, price range, sort) narrow the list
- [ ] Crop page: the chart range switches 1W/1M/3M/1Y, the "Show AI prediction" switch adds the dashed forecast line, the watchlist star works
- [ ] Listing page: "Message seller" opens the thread with the template text filled in; "via SMS" shows the logged or sent note
- [ ] Sell: create a listing and it appears in the Market; invalid quantity or price shows an inline error
- [ ] Profile shows the rating, reviews and verified badge; leaving a review updates the average

**Messages, alerts, AI**
- [ ] The unread badge on the Messages tab clears after opening the thread
- [ ] Log in as `amina_w` and see a harvest banner on Home plus a 🔔 SnackBar
- [ ] Set a price alert just under today's price, and it fires within the check interval, once only
- [ ] Chatbot preset buttons answer (offline mode with no key; real AI with a key)
- [ ] With an invalid AI key, the chatbot shows "⚠️ …" plus an offline answer, with no crash
- [ ] Turn off Wi-Fi: weather shows sample data and the app keeps working

**Settings and accessibility**
- [ ] Switch the language to Kiswahili or Soomaali and see the nav bar and main labels change
- [ ] Dark mode and the text-size slider apply at once and persist after logging out and in again
- [ ] At phone width (≈390 px) nothing overflows; desktop width also looks right

## 6. Known limitations

* **Prices are simulated.** The seed data is a realistic seasonal pattern in KES, not a live commodities feed. A real feed (Commodities API) was priority 2 and isn't connected.
* **One currency.** Everything is shown in KES. There is no conversion to NGN, GHS, UGX or SOS yet.
* **AI forecasts are short-term guidance.** The Ridge model has an average error of about 2–3% on a 30-day holdout (`python -m Databases.Prediction`), beating "repeat last price" on 10 of 12 crops. Tea and onions are slightly worse. It's trained on the simulated history, so treat it as a demo of the method.
* **Translation coverage.** Swahili and Somali cover the nav bar and main labels (about 100 strings each), not every sentence. DeepL doesn't support most African languages (Hausa, Yoruba, Amharic and others), so those stay in English. Chatbot replies follow the user's language when a real AI key is set.
* **SMS.** Without `AT_API_KEY` (locally or on the server), messages are logged, not sent. The Africa's Talking sandbox only delivers to its simulator.
* **Incoming SMS land in the server's database, not the laptop's.** The desktop app still uses its own local SQLite file, so replies sent by SMS show up in the server's messages (and its API), not in someone's desktop inbox. Making the app read and write through the server is the next step for a real multi-user marketplace.
* **The server's data resets on Render's free plan.** Its disk is wiped on each deploy or restart, and the database is re-seeded. Add a Render disk or a hosted Postgres to keep data.
* **Notifications** show while the app is open (SnackBar plus Home banners), and price alerts are also emailed. There are no phone push notifications.
* **News** comes from Google News RSS by default. The headlines are in English, and links open in the browser.
* **No payments, delivery or real verification.** "Buy" records a purchase; it doesn't move money. Verification documents are stored as submitted text and approved by hand in the database.
* **Crop images** fall back to emoji unless you add pictures to `UI/assets/crops/` (see the README there).
* **Login lockout** is held in memory, so restarting the app clears it.
* **Flet version.** It's pinned below 0.29. Moving to Flet 1.x would need changes in `main.py` and the pages (`page.open`, `ft.app`).

## 7. Stretch goals (built)

* **Server**: `server/app.py` plus `render.yaml`, covering the SMS gateway, incoming SMS and the read-only market API.
* **Email**: `Auth/email_service.py` sends a welcome email after registration, price alerts, and a receipt after "Buy now".
* **News feed**: `Auth/news.py` plus `/news`, with a "Farming news" section on Home and crop filter chips.
* **Purchase history**: `/purchases`, opened from Settings. It has Bought and Sold tabs with totals, order count, top crop and orders grouped by month.

Integration checklist additions:
- [ ] Home shows 3 news headlines; **See all** opens `/news`; tapping a story opens the browser
- [ ] Settings > Purchase history: buy something, then see it under **Bought** (and under **Sold** for the seller)
- [ ] With SMTP set, registering sends a welcome email and "Buy now" sends a receipt
- [ ] `uvicorn server.app:app` then open `/docs`; `POST /api/sms/send` without the token returns 401
