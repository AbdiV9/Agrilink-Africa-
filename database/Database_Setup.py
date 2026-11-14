# Owner: Person 1 (Backend & Database Lead)
"""Creates the AgriLink Africa schema and fills it with realistic demo data.

Run directly to (re)build a local database::

    python -m Databases.Database_Setup          # create + seed if empty
    python -m Databases.Database_Setup --reset  # delete agrilink.db first

All prices are stored in KES so that listings, price history and
predictions can be compared directly (see the spec decision log).
"""

from __future__ import annotations

import math
import os
import random
import sys
from datetime import date, datetime, timedelta
from typing import Any

from Databases.db import get_connection, get_db_path, hash_password

SEED_PASSWORD = "Password123!"
PRICE_HISTORY_DAYS = 365
_RNG_SEED = 2026

# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL CHECK (role IN ('farmer', 'buyer', 'both')),
    country       TEXT,
    region        TEXT,
    language      TEXT NOT NULL DEFAULT 'en',
    dark_mode     INTEGER NOT NULL DEFAULT 0,
    text_scale    REAL NOT NULL DEFAULT 1.0,
    verified      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crops (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL UNIQUE,
    category           TEXT,
    unit               TEXT NOT NULL DEFAULT 'kg',
    season_start_month INTEGER CHECK (season_start_month BETWEEN 1 AND 12),
    season_end_month   INTEGER CHECK (season_end_month BETWEEN 1 AND 12),
    growth_days        INTEGER CHECK (growth_days > 0),
    image_url          TEXT
);

CREATE TABLE IF NOT EXISTS listings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    crop_id        INTEGER NOT NULL REFERENCES crops(id),
    quantity       REAL NOT NULL CHECK (quantity >= 0),
    price_per_unit REAL NOT NULL CHECK (price_per_unit > 0),
    currency       TEXT NOT NULL DEFAULT 'KES',
    location       TEXT,
    description    TEXT,
    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'sold', 'paused')),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_history (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    date    TEXT NOT NULL,
    price   REAL NOT NULL CHECK (price > 0),
    market  TEXT,
    source  TEXT
);

CREATE TABLE IF NOT EXISTS purchases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id  INTEGER NOT NULL REFERENCES listings(id),
    buyer_id    INTEGER NOT NULL REFERENCES users(id),
    quantity    REAL NOT NULL CHECK (quantity > 0),
    total_price REAL NOT NULL CHECK (total_price >= 0),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id   INTEGER NOT NULL REFERENCES users(id),
    receiver_id INTEGER NOT NULL REFERENCES users(id),
    listing_id  INTEGER REFERENCES listings(id) ON DELETE SET NULL,
    body        TEXT NOT NULL,
    channel     TEXT NOT NULL DEFAULT 'app' CHECK (channel IN ('app', 'sms', 'email')),
    is_read     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reviewer_id INTEGER NOT NULL REFERENCES users(id),
    seller_id   INTEGER NOT NULL REFERENCES users(id),
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, crop_id)
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    crop_id      INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    target_price REAL NOT NULL CHECK (target_price > 0),
    direction    TEXT NOT NULL CHECK (direction IN ('above', 'below')),
    active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS plantings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    crop_id          INTEGER NOT NULL REFERENCES crops(id),
    planted_on       TEXT NOT NULL,
    expected_harvest TEXT,
    area_acres       REAL CHECK (area_acres IS NULL OR area_acres > 0),
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS verifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doc_type      TEXT NOT NULL CHECK (doc_type IN ('land_tenure', 'cooperative',
                  'gov_registration', 'subsidy_program', 'livestock')),
    doc_reference TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'approved', 'rejected')),
    submitted_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_listings_crop_id      ON listings(crop_id);
CREATE INDEX IF NOT EXISTS idx_listings_seller_id    ON listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_price_history_crop_dt ON price_history(crop_id, date);
CREATE INDEX IF NOT EXISTS idx_messages_receiver_id  ON messages(receiver_id);
"""

ALL_TABLES = [
    "verifications", "plantings", "price_alerts", "watchlist", "reviews",
    "messages", "purchases", "price_history", "listings", "crops", "users",
]


def create_tables() -> None:
    """Create every table and index (safe to call repeatedly)."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)


def is_empty() -> bool:
    """Return True when the schema is missing or no crops have been seeded."""
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM crops").fetchone()
            return row["n"] == 0
    except Exception:  # table does not exist yet
        return True


def setup_database() -> bool:
    """Create the schema and seed it if empty. Returns True if it seeded.

    This is the single call ``main.py`` makes at start-up.
    """
    create_tables()
    if is_empty():
        seed_data()
        return True
    return False


# --------------------------------------------------------------------------
# Seed data
# --------------------------------------------------------------------------
# name, category, unit, planting month, harvest month, growth_days, base KES/unit
CROPS: list[tuple[str, str, str, int, int, int, float]] = [
    ("Maize",    "Cereal",     "kg", 3, 8,  120, 45.0),
    ("Beans",    "Legume",     "kg", 3, 6,  90,  120.0),
    ("Cassava",  "Root/Tuber", "kg", 4, 2,  300, 30.0),
    ("Sorghum",  "Cereal",     "kg", 3, 7,  110, 50.0),
    ("Millet",   "Cereal",     "kg", 3, 7,  100, 70.0),
    ("Rice",     "Cereal",     "kg", 5, 10, 130, 140.0),
    ("Coffee",   "Cash crop",  "kg", 3, 11, 240, 520.0),
    ("Tea",      "Cash crop",  "kg", 3, 6,  90,  300.0),
    ("Tomatoes", "Vegetable",  "kg", 1, 4,  75,  80.0),
    ("Onions",   "Vegetable",  "kg", 2, 6,  110, 90.0),
    ("Potatoes", "Root/Tuber", "kg", 3, 6,  100, 55.0),
    ("Avocado",  "Fruit",      "kg", 2, 9,  180, 60.0),
]

# username, full name, role, country, region, phone, language, verified
USERS: list[tuple[str, str, str, str, str, str, str, int]] = [
    ("amina_w",    "Amina Wanjiru",  "farmer", "Kenya",   "Nakuru",    "+254712345678",  "sw", 1),
    ("john_otieno", "John Otieno",   "buyer",  "Kenya",   "Nairobi",   "+254722000111",  "en", 0),
    ("chidi_okafor", "Chidi Okafor", "farmer", "Nigeria", "Kano",      "+2348031234567", "ha", 1),
    ("funmi_ade",  "Funmilayo Adeyemi", "buyer", "Nigeria", "Lagos",   "+2348091112233", "yo", 0),
    ("kwame_m",    "Kwame Mensah",   "both",   "Ghana",   "Kumasi",    "+233244123456",  "en", 1),
    ("grace_n",    "Grace Nakato",   "farmer", "Uganda",  "Mbale",     "+256772123456",  "en", 0),
    ("hodan_ali",  "Hodan Ali",      "farmer", "Somalia", "Baidoa",    "+252615123456",  "so", 0),
    ("yusuf_w",    "Yusuf Warsame",  "buyer",  "Somalia", "Mogadishu", "+252617654321",  "so", 0),
]

MARKETS = ["Nairobi (Wakulima)", "Kano (Dawanau)", "Kumasi (Kejetia)", "Kampala (Owino)", "Mogadishu (Bakaara)"]

LISTING_DESCRIPTIONS = [
    "Freshly harvested, sorted and bagged. Can deliver within the county.",
    "Grade A quality, dried and cleaned. Bulk discounts for cooperatives.",
    "Organic, no chemical sprays used this season. Pickup from farm gate.",
    "Stored in a hermetic bag, moisture tested. Ready for collection.",
    "Smallholder cooperative stock, consistent quality, invoices available.",
    "Hand-picked this week. Message me to arrange transport.",
]

REVIEW_COMMENTS = [
    (5, "Excellent quality and delivered on time. Will buy again!"),
    (5, "Very honest seller, the weight was exactly as listed."),
    (4, "Good produce, slightly late pickup but well communicated."),
    (4, "Fair price for the quality. Recommended."),
    (3, "Okay overall, some bags had a bit of moisture."),
    (5, "Best tomatoes in the region, my restaurant customers loved them."),
    (2, "Quantity was less than agreed. Seller refunded the difference."),
]


def _circular_day_distance(a: int, b: int, period: int = 365) -> int:
    """Shortest distance in days between two day-of-year values."""
    d = abs(a - b) % period
    return min(d, period - d)


def _seasonal_price(base: float, harvest_month: int, d: date, days_from_start: int,
                    rng: random.Random) -> float:
    """Build one day's price from a seasonal wave + trend + noise.

    * Prices peak about 2 months before harvest (stocks run low) and
      bottom out at harvest (supply glut), modelled with a cosine wave
      plus a sharper dip centred on the harvest date.
    * A gentle upward trend (~6% a year) models inflation.
    * Gaussian noise (~2.5%) keeps the chart looking like a real market.
    """
    doy = d.timetuple().tm_yday
    harvest_doy = date(d.year, harvest_month, 15).timetuple().tm_yday
    peak_doy = (harvest_doy - 60) % 365
    wave = 0.18 * math.cos(2 * math.pi * _circular_day_distance(doy, peak_doy) / 365)
    harvest_dip = -0.12 * math.exp(-((_circular_day_distance(doy, harvest_doy) / 20) ** 2))
    trend = 0.06 * days_from_start / 365
    noise = rng.gauss(0, 0.025)
    return round(max(base * 0.3, base * (1 + wave + harvest_dip + trend + noise)), 2)


def _ts(days_ago: float, rng: random.Random) -> str:
    """Timestamp ``days_ago`` days in the past at a random working hour."""
    moment = datetime.now() - timedelta(days=days_ago)
    moment = moment.replace(hour=rng.randint(7, 19), minute=rng.randint(0, 59), second=0, microsecond=0)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def seed_data() -> None:
    """Fill an empty database with realistic, deterministic demo data.

    Everyone's password is ``Password123!``. Raises ``RuntimeError`` if the
    database already contains crops (call ``reset_database`` first).
    """
    if not is_empty():
        raise RuntimeError("Database already seeded; use reset_database() to start over.")
    rng = random.Random(_RNG_SEED)
    today = date.today()
    # Hash once and reuse for all demo accounts: bcrypt is slow on purpose.
    seed_hash = hash_password(SEED_PASSWORD)

    with get_connection() as conn:
        cur = conn.cursor()

        # ---- crops -------------------------------------------------------
        crop_ids: dict[str, int] = {}
        base_prices: dict[int, float] = {}
        harvest_months: dict[int, int] = {}
        for name, category, unit, start, end, growth, base in CROPS:
            cur.execute(
                "INSERT INTO crops (name, category, unit, season_start_month, season_end_month,"
                " growth_days, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, category, unit, start, end, growth, f"crops/{name.lower()}.jpg"),
            )
            cid = int(cur.lastrowid)
            crop_ids[name] = cid
            base_prices[cid] = base
            harvest_months[cid] = end

        # ---- users -------------------------------------------------------
        user_ids: dict[str, int] = {}
        for i, (username, full_name, role, country, region, phone, lang, verified) in enumerate(USERS):
            cur.execute(
                "INSERT INTO users (username, email, phone, password_hash, full_name, role,"
                " country, region, language, verified, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (username, f"{username}@example.com", phone, seed_hash, full_name, role,
                 country, region, lang, verified, _ts(200 - i * 15, rng)),
            )
            user_ids[username] = int(cur.lastrowid)
        sellers = [user_ids[u[0]] for u in USERS if u[2] in ("farmer", "both")]
        buyers = [user_ids[u[0]] for u in USERS if u[2] in ("buyer", "both")]
        region_of = {user_ids[u[0]]: u[4] for u in USERS}

        # ---- price history (365 days per crop) ---------------------------
        start_day = today - timedelta(days=PRICE_HISTORY_DAYS - 1)
        latest_price: dict[int, float] = {}
        history_rows: list[tuple[Any, ...]] = []
        for cid, base in base_prices.items():
            market = MARKETS[cid % len(MARKETS)]
            for offset in range(PRICE_HISTORY_DAYS):
                d = start_day + timedelta(days=offset)
                price = _seasonal_price(base, harvest_months[cid], d, offset, rng)
                history_rows.append((cid, d.isoformat(), price, market, "seed"))
                latest_price[cid] = price
        cur.executemany(
            "INSERT INTO price_history (crop_id, date, price, market, source) VALUES (?, ?, ?, ?, ?)",
            history_rows,
        )

        # ---- listings (36) -----------------------------------------------
        listing_rows: list[dict[str, Any]] = []
        crop_list = list(crop_ids.values())
        for i in range(36):
            seller = sellers[i % len(sellers)]
            cid = crop_list[(i * 5) % len(crop_list)]
            price = round(latest_price[cid] * rng.uniform(0.88, 1.15), 2)
            qty = float(rng.choice([50, 90, 100, 200, 250, 500, 750, 1000, 2000]))
            status = "sold" if i % 12 == 11 else "active"
            cur.execute(
                "INSERT INTO listings (seller_id, crop_id, quantity, price_per_unit, currency,"
                " location, description, status, created_at) VALUES (?, ?, ?, ?, 'KES', ?, ?, ?, ?)",
                (seller, cid, qty, price, region_of[seller], rng.choice(LISTING_DESCRIPTIONS),
                 status, _ts(rng.uniform(0, 30), rng)),
            )
            listing_rows.append({"id": int(cur.lastrowid), "seller_id": seller, "crop_id": cid,
                                 "price": price, "qty": qty})

        # ---- purchases (spread over the last 12 weeks) -------------------
        for i in range(48):
            listing = listing_rows[rng.randrange(len(listing_rows))]
            buyer = rng.choice([b for b in buyers if b != listing["seller_id"]])
            qty = float(rng.choice([10, 20, 25, 50, 100]))
            cur.execute(
                "INSERT INTO purchases (listing_id, buyer_id, quantity, total_price, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (listing["id"], buyer, qty, round(qty * listing["price"], 2), _ts(rng.uniform(0, 84), rng)),
            )

        # ---- reviews -----------------------------------------------------
        for i in range(18):
            seller = sellers[i % len(sellers)]
            reviewer = rng.choice([b for b in buyers if b != seller])
            rating, comment = rng.choice(REVIEW_COMMENTS)
            cur.execute(
                "INSERT INTO reviews (reviewer_id, seller_id, rating, comment, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (reviewer, seller, rating, comment, _ts(rng.uniform(1, 90), rng)),
            )

        # ---- messages (a few realistic conversations) --------------------
        def first_listing(seller_id: int) -> dict[str, Any]:
            return next(l for l in listing_rows if l["seller_id"] == seller_id)

        conversations = [
            ("john_otieno", "amina_w", [
                "Hi, I'm interested in your maize. Is it still available?",
                "Yes, 500kg ready for pickup in Nakuru.",
                "Great, can you do KES 44 per kg for all of it?",
                "I can do 46. It's very good quality, moisture tested.",
            ]),
            ("funmi_ade", "chidi_okafor", [
                "Good morning, do you deliver to Lagos?",
                "Yes, every Friday by truck. Delivery fee depends on the quantity.",
            ]),
            ("yusuf_w", "hodan_ali", [
                "Asc, how much sorghum do you have?",
                "Around 1,000 kg from this harvest.",
                "I'll take 300 kg. Can I collect on Saturday?",
            ]),
            ("kwame_m", "grace_n", [
                "Hello Grace, are your beans the red or white variety?",
            ]),
        ]
        for k, (buyer_name, seller_name, lines) in enumerate(conversations):
            buyer_id, seller_id = user_ids[buyer_name], user_ids[seller_name]
            listing_id = first_listing(seller_id)["id"]
            # Each conversation starts on a different day; replies follow in order.
            start = (datetime.now() - timedelta(days=4 - k)).replace(hour=9, minute=0, second=0, microsecond=0)
            for j, body in enumerate(lines):
                sender, receiver = (buyer_id, seller_id) if j % 2 == 0 else (seller_id, buyer_id)
                is_read = 0 if j == len(lines) - 1 else 1
                sent_at = (start + timedelta(minutes=23 * j)).strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "INSERT INTO messages (sender_id, receiver_id, listing_id, body, channel,"
                    " is_read, created_at) VALUES (?, ?, ?, ?, 'app', ?, ?)",
                    (sender, receiver, listing_id, body, is_read, sent_at),
                )

        # ---- plantings (some harvest within 7 days for the demo) ---------
        growth_of = {c[0]: c[5] for c in CROPS}
        planting_specs = [
            ("amina_w", "Maize", 115, 2.5, "Long rains plot, hybrid H614"),
            ("amina_w", "Beans", 40, 1.0, "Intercropped with maize"),
            ("chidi_okafor", "Sorghum", 105, 4.0, "Near the river field"),
            ("chidi_okafor", "Tomatoes", 30, 0.5, "Drip irrigated greenhouse"),
            ("kwame_m", "Cassava", 200, 3.0, "Behind the homestead"),
            ("grace_n", "Coffee", 100, 1.5, "Arabica on the slopes of Mt Elgon"),
            ("hodan_ali", "Sorghum", 60, 5.0, "Rain-fed, Gu season"),
        ]
        for username, crop, days_ago, acres, notes in planting_specs:
            planted = today - timedelta(days=days_ago)
            harvest = planted + timedelta(days=growth_of[crop])
            cur.execute(
                "INSERT INTO plantings (user_id, crop_id, planted_on, expected_harvest, area_acres, notes)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_ids[username], crop_ids[crop], planted.isoformat(), harvest.isoformat(), acres, notes),
            )

        # ---- watchlists and price alerts ---------------------------------
        watch = {
            "john_otieno": ["Maize", "Beans", "Tomatoes", "Potatoes"],
            "amina_w": ["Maize", "Beans", "Avocado"],
            "funmi_ade": ["Rice", "Tomatoes", "Onions"],
            "kwame_m": ["Cassava", "Coffee", "Maize"],
            "yusuf_w": ["Sorghum", "Rice"],
        }
        for username, crops in watch.items():
            for crop in crops:
                cur.execute("INSERT INTO watchlist (user_id, crop_id) VALUES (?, ?)",
                            (user_ids[username], crop_ids[crop]))
        alert_specs = [
            ("john_otieno", "Maize", 0.95, "below"),
            ("amina_w", "Maize", 1.10, "above"),
            ("funmi_ade", "Tomatoes", 0.90, "below"),
            ("kwame_m", "Coffee", 1.05, "above"),
        ]
        for username, crop, factor, direction in alert_specs:
            cid = crop_ids[crop]
            cur.execute(
                "INSERT INTO price_alerts (user_id, crop_id, target_price, direction) VALUES (?, ?, ?, ?)",
                (user_ids[username], cid, round(latest_price[cid] * factor, 2), direction),
            )

        # ---- verifications (approved ones match users.verified = 1) ------
        verification_specs = [
            ("amina_w", "cooperative", "KE-COOP-NKR-0412", "approved"),
            ("chidi_okafor", "gov_registration", "NG-FMARD-KN-88213", "approved"),
            ("kwame_m", "land_tenure", "GH-LC-ASH-2291", "approved"),
            ("grace_n", "subsidy_program", "UG-OWC-MBL-5520", "pending"),
            ("hodan_ali", "livestock", "SO-MOLFR-BAY-0093", "pending"),
        ]
        for username, doc_type, ref, status in verification_specs:
            cur.execute(
                "INSERT INTO verifications (user_id, doc_type, doc_reference, status, submitted_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_ids[username], doc_type, ref, status, _ts(rng.uniform(20, 60), rng)),
            )


def reset_database() -> None:
    """Drop every table, then recreate and reseed. Demo/dev use only."""
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in ALL_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")  # names are constants, not user input
    create_tables()
    seed_data()


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(get_db_path()):
        os.remove(get_db_path())
    seeded = setup_database()
    print(f"Database ready at {get_db_path()} ({'seeded' if seeded else 'already had data'}).")
