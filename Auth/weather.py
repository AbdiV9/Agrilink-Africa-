# Owner: Person 3 (Integration, Logic & API Lead)
"""7-day weather from the free Open-Meteo API (no key needed), cached for 1 hour.

Return shape (used by ``UI.components.weather_card``)::

    {"region", "lat", "lon", "source": "live" | "cache" | "sample",
     "days": [{"date", "t_max", "t_min", "rain_mm", "rain_chance", "code", "condition"}]}

If the API can't be reached, the last cached forecast is returned
(``source='cache'``), otherwise a plausible sample (``source='sample'``).
"""

from __future__ import annotations

import logging
import math
import time
from datetime import date, timedelta
from typing import Any

import config

log = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

# Major agricultural regions and cities -> (lat, lon).
REGION_COORDS: dict[str, tuple[float, float]] = {
    # Kenya
    "nairobi": (-1.29, 36.82), "nakuru": (-0.30, 36.07), "eldoret": (0.51, 35.27), "kisumu": (-0.09, 34.77),
    "mombasa": (-4.04, 39.67), "meru": (0.05, 37.65), "kitale": (1.02, 35.00), "machakos": (-1.52, 37.26),
    "nyeri": (-0.42, 36.95), "kericho": (-0.37, 35.28),
    # Nigeria
    "lagos": (6.52, 3.38), "kano": (12.00, 8.52), "abuja": (9.08, 7.40), "kaduna": (10.52, 7.44),
    "ibadan": (7.38, 3.94), "jos": (9.90, 8.86), "port harcourt": (4.82, 7.03), "enugu": (6.45, 7.51),
    "benue": (7.73, 8.54), "sokoto": (13.06, 5.24),
    # Ghana
    "accra": (5.60, -0.19), "kumasi": (6.69, -1.62), "tamale": (9.40, -0.85), "takoradi": (4.90, -1.76),
    "ashanti": (6.75, -1.52), "bolgatanga": (10.79, -0.85),
    # Uganda
    "kampala": (0.35, 32.58), "mbale": (1.08, 34.18), "gulu": (2.78, 32.30), "mbarara": (-0.61, 30.65),
    "jinja": (0.42, 33.20), "masaka": (-0.33, 31.73),
    # Somalia
    "mogadishu": (2.05, 45.32), "baidoa": (3.12, 43.65), "hargeisa": (9.56, 44.06), "kismayo": (-0.36, 42.55),
    "beledweyne": (4.74, 45.20), "bay": (3.12, 43.65), "jowhar": (2.78, 45.50),
    # Neighbours
    "dar es salaam": (-6.79, 39.21), "arusha": (-3.37, 36.68), "dodoma": (-6.16, 35.75), "mwanza": (-2.52, 32.90),
    "kigali": (-1.95, 30.06), "addis ababa": (9.03, 38.74), "juba": (4.85, 31.58), "lusaka": (-15.39, 28.32),
}
DEFAULT_REGION = "nairobi"

WMO_CONDITIONS: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Violent showers", 85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}

# (lat, lon rounded) -> (timestamp, forecast)
_cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
_clock = time.time  # tests can replace this


def condition_for(code: int | None) -> str:
    """Plain-English description of a WMO weather code."""
    return WMO_CONDITIONS.get(int(code) if code is not None else -1, "Mixed conditions")


def lookup_region(region: str | None) -> tuple[str, float, float]:
    """Find coordinates for a region name (case-insensitive, partial match ok)."""
    key = (region or "").strip().lower()
    if key in REGION_COORDS:
        return key.title(), *REGION_COORDS[key]
    for name, coords in REGION_COORDS.items():
        if key and (key in name or name in key):
            return name.title(), *coords
    lat, lon = REGION_COORDS[DEFAULT_REGION]
    return (region or DEFAULT_REGION).strip().title() or "Nairobi", lat, lon


def _sample_forecast(lat: float, lon: float) -> list[dict[str, Any]]:
    """Deterministic, plausible tropical forecast used when offline."""
    today = date.today()
    seed = int(abs(lat * 100 + lon * 10))
    codes = [1, 2, 61, 3, 80, 0, 95]
    days = []
    for i in range(7):
        code = codes[(seed + i) % len(codes)]
        rainy = code >= 51
        base = 27 - abs(lat) * 0.3 - (3 if abs(lat) < 2 and 34 < lon < 38 else 0)  # cooler highlands
        days.append({
            "date": (today + timedelta(days=i)).isoformat(),
            "t_max": round(base + 2 * math.sin(i + seed), 1),
            "t_min": round(base - 10 + math.cos(i + seed), 1),
            "rain_mm": round((4 + (seed + i) % 9) if rainy else (seed + i) % 2 * 0.4, 1),
            "rain_chance": 70 + (seed + i) % 25 if rainy else 5 + (seed + i) % 20,
            "code": code,
            "condition": condition_for(code),
        })
    return days


def _fetch(lat: float, lon: float) -> list[dict[str, Any]]:
    """Call Open-Meteo and convert the daily arrays into our day dicts."""
    if requests is None:
        raise RuntimeError("requests is not installed")
    response = requests.get(config.WEATHER_API_URL, timeout=8, params={
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max",
    })
    response.raise_for_status()
    daily = response.json()["daily"]
    days = []
    for i, day in enumerate(daily["time"]):
        code = daily["weather_code"][i]
        days.append({
            "date": day,
            "t_max": daily["temperature_2m_max"][i],
            "t_min": daily["temperature_2m_min"][i],
            "rain_mm": daily["precipitation_sum"][i] or 0.0,
            "rain_chance": (daily.get("precipitation_probability_max") or [0] * 7)[i] or 0,
            "code": code,
            "condition": condition_for(code),
        })
    return days


def get_forecast(lat: float, lon: float) -> dict[str, Any]:
    """7-day forecast for coordinates. Never raises."""
    key = (round(float(lat), 2), round(float(lon), 2))
    cached = _cache.get(key)
    if cached and _clock() - cached[0] < config.WEATHER_CACHE_SECONDS:
        stored = cached[1]
        return {**stored, "source": "cache" if stored["source"] == "live" else stored["source"]}
    try:
        days = _fetch(*key)
        forecast = {"lat": key[0], "lon": key[1], "source": "live", "days": days}
        _cache[key] = (_clock(), forecast)
        return forecast
    except Exception as exc:
        log.warning("Weather API unavailable (%s); using %s data", exc, "cached" if cached else "sample")
        if cached and cached[1]["source"] == "live":
            return {**cached[1], "source": "cache"}
        sample = {"lat": key[0], "lon": key[1], "source": "sample", "days": _sample_forecast(*key)}
        # Remember the sample for 10 minutes so offline pages don't wait on the network every time.
        _cache[key] = (_clock() - config.WEATHER_CACHE_SECONDS + 600, sample)
        return sample


def get_forecast_for_region(region: str | None) -> dict[str, Any]:
    """7-day forecast for a region name such as 'Nakuru' or 'Kano'."""
    name, lat, lon = lookup_region(region)
    return {**get_forecast(lat, lon), "region": name}


def weather_summary(forecast: dict[str, Any]) -> str:
    """One-line text summary for the chatbot and notifications."""
    days = forecast.get("days") or []
    if not days:
        return "No forecast available."
    rain_days = sum(1 for d in days if (d.get("rain_mm") or 0) >= 2)
    total_rain = sum(d.get("rain_mm") or 0 for d in days)
    hi = max(d.get("t_max") or 0 for d in days)
    lo = min(d.get("t_min") or 0 for d in days)
    return (f"{forecast.get('region', 'Your area')} next 7 days: {lo:.0f}-{hi:.0f}°C, "
            f"{rain_days} rainy day(s), about {total_rain:.0f} mm rain. Today: {days[0].get('condition')}.")
