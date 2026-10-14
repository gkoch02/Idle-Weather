"""Fetch the current weather from Open-Meteo, with an on-disk cache for when the network is down.

Open-Meteo needs no API key. The client asks for the handful of current
fields :class:`~idle_weather.conditions.Observation` holds, in °C and km/h.
Stdlib only.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from idle_hours import atomic_io

from idle_weather.conditions import Observation

API_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = ("temperature_2m", "weather_code", "wind_speed_10m", "wind_gusts_10m", "is_day")
TIMEOUT_SECONDS = 15
USER_AGENT = "Idle-Weather (+https://github.com/gkoch02/IdleWeather)"
# An observation older than this is not "the current weather" any more.
MAX_AGE_SECONDS = 3 * 60 * 60


class WeatherError(RuntimeError):
    """The weather could not be fetched or parsed."""


@dataclass(frozen=True)
class Reading:
    """An observation and when it was fetched (epoch seconds)."""

    observation: Observation
    fetched_at: float

    def age(self, now: float | None = None) -> float:
        return (time.time() if now is None else now) - self.fetched_at


def request_url(latitude: float, longitude: float) -> str:
    query = {
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "current": ",".join(CURRENT_FIELDS),
        "timezone": "auto",
    }
    return f"{API_URL}?{urllib.parse.urlencode(query)}"


def parse_current(payload: dict) -> Observation:
    """The :class:`Observation` in an Open-Meteo ``current`` response."""
    try:
        cur = payload["current"]
        return Observation(
            weather_code=int(cur["weather_code"]),
            temperature_c=float(cur["temperature_2m"]),
            wind_kmh=float(cur.get("wind_speed_10m") or 0.0),
            gust_kmh=float(cur.get("wind_gusts_10m") or 0.0),
            is_day=bool(int(cur["is_day"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError(f"unexpected Open-Meteo response: {exc!r}") from exc


def fetch(latitude: float, longitude: float, timeout: float = TIMEOUT_SECONDS) -> Reading:
    """Fetch the current weather. Raises :class:`WeatherError` on any failure."""
    req = urllib.request.Request(request_url(latitude, longitude), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise WeatherError(f"Open-Meteo request failed: {exc!r}") from exc
    return Reading(parse_current(payload), time.time())


def save_reading(path: Path, reading: Reading) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fetched_at": reading.fetched_at, "observation": asdict(reading.observation)}
    atomic_io.atomic_write_text(path, json.dumps(payload) + "\n")


def load_reading(path: Path) -> Reading | None:
    """The cached reading at ``path``, or None when absent or unreadable."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Reading(Observation(**payload["observation"]), float(payload["fetched_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


class WeatherSource:
    """Fetches at most every ``interval`` seconds and falls back to the last good reading.

    The last good reading is cached at ``cache_path`` so a restart without a
    network still knows the weather, until it is ``MAX_AGE_SECONDS`` old.
    """

    def __init__(self, latitude: float, longitude: float, cache_path: Path | None, interval: float, fetcher=fetch):
        self.latitude = latitude
        self.longitude = longitude
        self.cache_path = cache_path
        self.interval = interval
        self._fetch = fetcher
        self._last_attempt: float | None = None
        self.reading: Reading | None = load_reading(cache_path) if cache_path else None
        self.last_error: str | None = None

    def current(self, now: float | None = None) -> Reading | None:
        now = time.time() if now is None else now
        if self._last_attempt is None or now - self._last_attempt >= self.interval:
            self._last_attempt = now
            try:
                self.reading = self._fetch(self.latitude, self.longitude)
                self.last_error = None
                if self.cache_path:
                    save_reading(self.cache_path, self.reading)
            except WeatherError as exc:
                self.last_error = str(exc)
        if self.reading is None or self.reading.age(now) > MAX_AGE_SECONDS:
            return None
        return self.reading
