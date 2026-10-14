"""The weather conditions a quote can be filed under, and how live weather maps onto them.

``CONDITIONS`` is the one roster: the miner files every quote under one of
these keys, the baker groups by them, and :func:`conditions_for` turns an
Open-Meteo observation into an ordered list of them (the first is the real
weather, the rest are what to show when its pool runs dry).

Stdlib only, so the weather client and the picker can import it without
pulling in Pillow.
"""
from __future__ import annotations

from dataclasses import dataclass

# Every condition, in a stable order for reports and the coverage table.
CONDITIONS: tuple[str, ...] = (
    "thunder",
    "snow",
    "sleet",
    "downpour",
    "rain",
    "drizzle",
    "fog",
    "wind",
    "clouds",
    "sunshine",
    "heat",
    "frost",
    "night_sky",
)

# Short human labels for logs, the coverage report and the debug footer.
LABELS: dict[str, str] = {
    "thunder": "Thunderstorm",
    "snow": "Snow",
    "sleet": "Sleet or hail",
    "downpour": "Heavy rain",
    "rain": "Rain",
    "drizzle": "Drizzle",
    "fog": "Fog or mist",
    "wind": "Wind",
    "clouds": "Cloud",
    "sunshine": "Sunshine",
    "heat": "Heat",
    "frost": "Frost",
    "night_sky": "Clear night",
}

# What to fall back to, in order, when a condition's own pool is empty or
# every quote in it was shown recently. Each list starts with the condition
# itself. Fallbacks stay close to the real weather: a heavy-rain day may show
# ordinary rain, never sunshine.
FALLBACKS: dict[str, tuple[str, ...]] = {
    "thunder": ("thunder", "downpour", "rain"),
    "snow": ("snow", "frost"),
    "sleet": ("sleet", "snow", "rain"),
    "downpour": ("downpour", "rain"),
    "rain": ("rain", "drizzle", "downpour"),
    "drizzle": ("drizzle", "rain", "fog"),
    "fog": ("fog", "drizzle", "clouds"),
    "wind": ("wind", "clouds"),
    "clouds": ("clouds",),
    "sunshine": ("sunshine",),
    "heat": ("heat", "sunshine"),
    "frost": ("frost", "snow"),
    "night_sky": ("night_sky",),
}

# Thresholds, in the units Open-Meteo returns by default (°C, km/h).
WIND_KMH = 45.0
GUST_KMH = 65.0
HEAT_C = 29.0
FROST_C = 0.0

# WMO weather interpretation codes, as Open-Meteo documents them.
_THUNDER_CODES = frozenset({95, 96, 99})
_SLEET_CODES = frozenset({56, 57, 66, 67})
_SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})
_DOWNPOUR_CODES = frozenset({65, 82})
_RAIN_CODES = frozenset({61, 63, 80, 81})
_DRIZZLE_CODES = frozenset({51, 53, 55})
_FOG_CODES = frozenset({45, 48})


@dataclass(frozen=True)
class Observation:
    """The slice of the current weather the picker needs."""

    weather_code: int
    temperature_c: float
    wind_kmh: float
    gust_kmh: float
    is_day: bool


def _dedupe(keys: list[str]) -> list[str]:
    return list(dict.fromkeys(keys))


def primary_condition(obs: Observation) -> str:
    """The one condition that best names ``obs``.

    Precipitation and fog come from the WMO code alone. A dry sky is wind when
    it blows hard enough, frost below freezing, heat on a hot day under any
    sky, then sunshine, a clear night, or cloud.
    """
    code = obs.weather_code
    if code in _THUNDER_CODES:
        return "thunder"
    if code in _SLEET_CODES:
        return "sleet"
    if code in _SNOW_CODES:
        return "snow"
    if code in _DOWNPOUR_CODES:
        return "downpour"
    if code in _RAIN_CODES:
        return "rain"
    if code in _DRIZZLE_CODES:
        return "drizzle"
    if code in _FOG_CODES:
        return "fog"
    if obs.wind_kmh >= WIND_KMH or obs.gust_kmh >= GUST_KMH:
        return "wind"
    if obs.temperature_c <= FROST_C:
        return "frost"
    clear = code in (0, 1)
    if obs.is_day and code <= 3 and obs.temperature_c >= HEAT_C:
        return "heat"
    if clear:
        return "sunshine" if obs.is_day else "night_sky"
    if code == 2 and obs.is_day:
        return "sunshine"
    return "clouds"


def conditions_for(obs: Observation) -> list[str]:
    """Ordered condition keys to draw from for ``obs``: the real weather first.

    After the primary condition's own fallbacks, strong wind is offered
    whenever it is blowing, since a gale is weather whatever else is falling.
    """
    primary = primary_condition(obs)
    keys = list(FALLBACKS[primary])
    # Heat under an overcast sky borrows from cloud, not sunshine.
    if primary == "heat" and obs.weather_code == 3:
        keys = ["heat", "clouds"]
    if primary != "wind" and (obs.wind_kmh >= WIND_KMH or obs.gust_kmh >= GUST_KMH):
        keys.append("wind")
    return _dedupe(keys)
