"""Print the current weather at a location, the conditions it maps to, and a quote for it.

    idle-weather now --latitude 51.48 --longitude -0.0
"""
from __future__ import annotations

import argparse
import random

from idle_weather.conditions import LABELS, conditions_for
from idle_weather.pick import load_database, pick
from idle_weather.weather import WeatherError, fetch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        reading = fetch(args.latitude, args.longitude)
    except WeatherError as exc:
        print(exc)
        return 1
    obs = reading.observation
    conditions = conditions_for(obs)
    print(
        f"WMO {obs.weather_code}, {obs.temperature_c:.1f}°C, wind {obs.wind_kmh:.0f} km/h "
        f"(gusts {obs.gust_kmh:.0f}), {'day' if obs.is_day else 'night'}"
    )
    print("conditions: " + " → ".join(f"{c} ({LABELS[c]})" for c in conditions))
    picked = pick(load_database(), conditions, [], rng=random.Random())
    if picked:
        row, cond = picked
        print(f"\n[{cond}] {row['display_quote']}\n  — {row['author']}, {row['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
