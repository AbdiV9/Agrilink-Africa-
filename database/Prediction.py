# Owner: Person 1 (Backend & Database Lead)
"""AI price prediction and season advice.

Model: a ridge regression (scikit-learn) per crop on daily prices with
* seasonal features: sin/cos of day-of-year (1st and 2nd harmonics) and a
  harvest-dip feature centred on the crop's harvest month,
* a linear trend (years since the first data point),
* weekly purchase volume for that crop from the ``purchases`` table.

Forecasts are anchored to the latest real prices (the average residual of
the last 7 days is carried forward), so the dashed line starts where the
chart ends. ``evaluate_model`` holds out the last 30 days and reports MAE.

If scikit-learn isn't installed, a numpy least-squares fit with the same
features is used instead. Run ``python -m Databases.Prediction`` to print
the MAE for every crop.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any

import numpy as np

from Databases.db import get_connection, rows_to_dicts

log = logging.getLogger(__name__)

try:
    from sklearn.linear_model import Ridge

    _HAS_SKLEARN = True
except ImportError:  # pragma: no cover
    _HAS_SKLEARN = False

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
MIN_POINTS = 60
ANCHOR_DAYS = 7
HOLDOUT_DAYS = 30

# crop_id -> (cache key, fitted model)
_model_cache: dict[int, tuple[tuple[Any, ...], "_Model"]] = {}


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def _load_crop(crop_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM crops WHERE id = ?", (crop_id,)).fetchone()
        return dict(row) if row else None


def _load_history(crop_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return rows_to_dicts(conn.execute(
            "SELECT date, price FROM price_history WHERE crop_id = ? ORDER BY date", (crop_id,)).fetchall())


def _weekly_volume(crop_id: int) -> dict[tuple[int, int], float]:
    """ISO (year, week) -> total quantity purchased for this crop."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT p.created_at, p.quantity FROM purchases p JOIN listings l ON l.id = p.listing_id"
            " WHERE l.crop_id = ?", (crop_id,)).fetchall()
    volume: dict[tuple[int, int], float] = {}
    for r in rows:
        try:
            iso = date.fromisoformat(str(r["created_at"])[:10]).isocalendar()
        except ValueError:
            continue
        key = (iso[0], iso[1])
        volume[key] = volume.get(key, 0.0) + float(r["quantity"])
    return volume


# --------------------------------------------------------------------------
# Features and model
# --------------------------------------------------------------------------
def _circular_distance(a: int, b: int, period: int = 365) -> int:
    d = abs(a - b) % period
    return min(d, period - d)


def _features(d: date, start: date, harvest_month: int | None, weekly_volume: float) -> list[float]:
    doy = d.timetuple().tm_yday
    angle = 2 * math.pi * doy / 365.25
    harvest_doy = date(d.year, harvest_month or 8, 15).timetuple().tm_yday
    dip = math.exp(-((_circular_distance(doy, harvest_doy) / 20) ** 2))
    return [
        math.sin(angle), math.cos(angle), math.sin(2 * angle), math.cos(2 * angle),
        dip,
        (d - start).days / 365.0,
        math.log1p(weekly_volume) / 5.0,
    ]


class _Model:
    """Fitted regression plus what's needed to build future features."""

    def __init__(self, crop: dict[str, Any], history: list[dict[str, Any]],
                 volume: dict[tuple[int, int], float]) -> None:
        self.crop = crop
        self.start = date.fromisoformat(history[0]["date"])
        self.last_date = date.fromisoformat(history[-1]["date"])
        self.volume = volume
        dates = [date.fromisoformat(h["date"]) for h in history]
        X = np.array([self._row(d) for d in dates])
        y = np.array([float(h["price"]) for h in history])
        if _HAS_SKLEARN:
            self.reg: Any = Ridge(alpha=0.5).fit(X, y)
            fitted = self.reg.predict(X)
        else:  # numpy fallback: ordinary least squares with an intercept
            Xb = np.hstack([X, np.ones((len(X), 1))])
            self.coef, *_ = np.linalg.lstsq(Xb, y, rcond=None)
            fitted = Xb @ self.coef
        # Carry the recent residual forward so forecasts start at today's level.
        self.anchor = float(np.mean(y[-ANCHOR_DAYS:] - fitted[-ANCHOR_DAYS:]))
        recent_weeks = sorted(volume.items())[-4:]
        self.future_volume = float(np.mean([v for _, v in recent_weeks])) if recent_weeks else 0.0

    def _row(self, d: date, future: bool = False) -> list[float]:
        iso = d.isocalendar()
        vol = self.future_volume if future else self.volume.get((iso[0], iso[1]), 0.0)
        return _features(d, self.start, self.crop.get("season_end_month"), vol)

    def predict(self, dates: list[date], future: bool = True) -> np.ndarray:
        X = np.array([self._row(d, future) for d in dates])
        if _HAS_SKLEARN:
            raw = self.reg.predict(X)
        else:
            raw = np.hstack([X, np.ones((len(X), 1))]) @ self.coef
        return np.maximum(raw + self.anchor, 0.01)


def _get_model(crop_id: int) -> _Model | None:
    """Fitted model for a crop (cached until new prices or purchases arrive)."""
    crop = _load_crop(crop_id)
    if crop is None:
        raise ValueError("Crop does not exist.")
    history = _load_history(crop_id)
    if len(history) < MIN_POINTS:
        return None
    volume = _weekly_volume(crop_id)
    key = (history[-1]["date"], len(history), round(sum(volume.values()), 2))
    cached = _model_cache.get(crop_id)
    if cached and cached[0] == key:
        return cached[1]
    model = _Model(crop, history, volume)
    _model_cache[crop_id] = (key, model)
    return model


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def predict_price(crop_id: int, days_ahead: int = 30) -> list[dict[str, Any]]:
    """Daily forecasts ``[{date, predicted_price}]`` for the next ``days_ahead`` days.

    Starts the day after the latest recorded price. Returns [] if there is
    too little history (fewer than 60 days).
    """
    if not 1 <= int(days_ahead) <= 365:
        raise ValueError("days_ahead must be between 1 and 365.")
    model = _get_model(crop_id)
    if model is None:
        return []
    dates = [model.last_date + timedelta(days=i) for i in range(1, int(days_ahead) + 1)]
    prices = model.predict(dates)
    return [{"date": d.isoformat(), "predicted_price": round(float(p), 2)} for d, p in zip(dates, prices)]


def _monthly_averages(history: list[dict[str, Any]]) -> dict[int, float]:
    buckets: dict[int, list[float]] = {}
    for h in history:
        buckets.setdefault(int(h["date"][5:7]), []).append(float(h["price"]))
    return {m: sum(v) / len(v) for m, v in buckets.items()}


def get_season_advice(crop_id: int, month: int) -> str:
    """Plain-English selling/planting advice for a crop in a given month (1-12)."""
    if not 1 <= int(month) <= 12:
        raise ValueError("Month must be 1-12.")
    crop = _load_crop(crop_id)
    if crop is None:
        raise ValueError("Crop does not exist.")
    name = crop["name"]
    history = _load_history(crop_id)
    if len(history) < MIN_POINTS:
        return f"Not enough price history for {name} yet. Check back after a few weeks of market data."

    monthly = _monthly_averages(history)
    peak = max(monthly, key=monthly.get)
    low = min(monthly, key=monthly.get)
    swing = (monthly[peak] - monthly[low]) / monthly[low] * 100
    parts = [f"{name} prices usually peak in {MONTHS[peak - 1]} and are lowest around {MONTHS[low - 1]} "
             f"(about {swing:.0f}% difference)."]

    forecast = predict_price(crop_id, 30)
    latest = float(history[-1]["price"])
    if forecast:
        best = max(forecast, key=lambda f: f["predicted_price"])
        gain = (best["predicted_price"] - latest) / latest * 100
        days = (date.fromisoformat(best["date"]) - date.fromisoformat(history[-1]["date"])).days
        if gain >= 3 and days >= 7:
            weeks = max(1, round(days / 7))
            parts.append(f"Our model expects about +{gain:.0f}% within {days} days; "
                         f"consider holding stock {weeks} week{'s' if weeks > 1 else ''} if you can store it safely.")
        elif forecast[-1]["predicted_price"] < latest * 0.97:
            drop = (latest - forecast[-1]["predicted_price"]) / latest * 100
            parts.append(f"Prices are expected to fall about {drop:.0f}% over the next month, so selling soon makes sense.")
        else:
            parts.append("Prices look steady for the next month; sell when it suits your cash needs.")

    if crop.get("season_start_month") == int(month):
        parts.append(f"{MONTHS[int(month) - 1]} is planting time for {name} (about {crop.get('growth_days')} days to harvest).")
    elif crop.get("season_end_month") == int(month):
        parts.append(f"{MONTHS[int(month) - 1]} is harvest month, when extra supply usually pushes prices down.")
    return " ".join(parts)


def evaluate_model(crop_id: int, holdout_days: int = HOLDOUT_DAYS) -> dict[str, Any]:
    """Train on all but the last ``holdout_days`` days, then score on them.

    Returns ``{crop, mae, mape_pct, naive_mae, days}``. ``naive_mae`` is the
    error of simply repeating the last known price, for comparison.
    """
    crop = _load_crop(crop_id)
    if crop is None:
        raise ValueError("Crop does not exist.")
    history = _load_history(crop_id)
    if len(history) < MIN_POINTS + holdout_days:
        raise ValueError("Not enough history to evaluate.")
    train, test = history[:-holdout_days], history[-holdout_days:]
    model = _Model(crop, train, _weekly_volume(crop_id))
    dates = [date.fromisoformat(h["date"]) for h in test]
    predicted = model.predict(dates)
    actual = np.array([float(h["price"]) for h in test])
    naive = np.full_like(actual, float(train[-1]["price"]))
    return {
        "crop": crop["name"],
        "mae": round(float(np.mean(np.abs(predicted - actual))), 2),
        "mape_pct": round(float(np.mean(np.abs(predicted - actual) / actual) * 100), 2),
        "naive_mae": round(float(np.mean(np.abs(naive - actual))), 2),
        "days": holdout_days,
    }


if __name__ == "__main__":
    from Databases.Database_Setup import setup_database

    setup_database()
    with get_connection() as _conn:
        _ids = [r["id"] for r in _conn.execute("SELECT id FROM crops ORDER BY name")]
    print(f"{'Crop':<10} {'MAE':>8} {'MAPE%':>7} {'Naive MAE':>10}")
    for _cid in _ids:
        r = evaluate_model(_cid)
        print(f"{r['crop']:<10} {r['mae']:>8.2f} {r['mape_pct']:>7.2f} {r['naive_mae']:>10.2f}")
