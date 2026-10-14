from idle_weather.conditions import Observation
from idle_weather.weather import MAX_AGE_SECONDS, Reading, WeatherError, WeatherSource, load_reading, parse_current, request_url

SAMPLE = {"current": {"time": "2026-10-14T09:00", "temperature_2m": 11.3, "weather_code": 61,
                      "wind_speed_10m": 14.2, "wind_gusts_10m": 30.1, "is_day": 1}}


def test_parse_current():
    assert parse_current(SAMPLE) == Observation(61, 11.3, 14.2, 30.1, True)


def test_parse_rejects_garbage():
    try:
        parse_current({"current": {}})
    except WeatherError:
        return
    raise AssertionError("expected WeatherError")


def test_request_url_has_fields():
    url = request_url(51.5, -0.12)
    assert "latitude=51.5000" in url and "weather_code" in url and "is_day" in url


def test_source_caches_and_falls_back(tmp_path):
    cache = tmp_path / "weather.json"
    calls = []

    def ok(lat, lon):
        calls.append(1)
        return Reading(parse_current(SAMPLE), 1000.0)

    src = WeatherSource(1, 2, cache, interval=600, fetcher=ok)
    assert src.current(now=1000.0).observation.weather_code == 61
    assert src.current(now=1100.0) is not None and len(calls) == 1  # inside the interval
    assert load_reading(cache).observation.weather_code == 61

    def down(lat, lon):
        raise WeatherError("offline")

    restarted = WeatherSource(1, 2, cache, interval=600, fetcher=down)
    assert restarted.current(now=2000.0).observation.weather_code == 61
    assert restarted.last_error == "offline"
    assert restarted.current(now=1000.0 + MAX_AGE_SECONDS + 700) is None
