from datetime import datetime

import pytest

from idle_weather.bake import DATABASE_PATH
from idle_weather.conditions import Observation
from idle_weather.run import CONFIG_ERROR_EXIT, ConfigError, Runner, load_config, main
from idle_weather.weather import Reading


class FakeWeather:
    def __init__(self, obs):
        self.obs = obs
        self.last_error = None

    def current(self, now=None):
        return Reading(self.obs, now) if self.obs else None


def make(tmp_path, obs, **cfg):
    calls = []
    config = load_config(None, {"latitude": 51.5, "longitude": 0.0, "state_dir": str(tmp_path),
                                "output": str(tmp_path / "out.png"), "theme": "saloon", **cfg})
    runner = Runner(config, weather=FakeWeather(obs), runner=lambda cmd, **kw: calls.append(cmd))
    return runner, calls


RAIN = Observation(61, 10.0, 5.0, 10.0, True)
SUN = Observation(0, 20.0, 5.0, 10.0, True)


def test_paints_on_start_then_idles_then_rotates(tmp_path):
    runner, calls = make(tmp_path, RAIN, rotate_minutes=30)
    t0 = datetime(2026, 10, 14, 9, 0)
    assert "Rain" in runner.tick(t0)
    assert len(calls) == 1 and "--key" in calls[0]
    assert runner.tick(datetime(2026, 10, 14, 9, 10)) == "idle"
    assert "Rain" in runner.tick(datetime(2026, 10, 14, 9, 31))
    assert len(calls) == 2


def test_condition_change_repaints(tmp_path):
    runner, _calls = make(tmp_path, RAIN)
    runner.tick(datetime(2026, 10, 14, 9, 0))
    runner.weather.obs = SUN
    assert "Sunshine" in runner.tick(datetime(2026, 10, 14, 9, 5))


def test_display_pushes_to_inky(tmp_path):
    runner, calls = make(tmp_path, RAIN, display=True)
    runner.tick(datetime(2026, 10, 14, 9, 0))
    assert calls[1][2] == "idle_hours.display_inky"


def test_quiet_hours_paint_sleep_frame_once(tmp_path):
    runner, calls = make(tmp_path, RAIN, quiet_start="22:00", quiet_end="07:00")
    assert "quiet hours" in runner.tick(datetime(2026, 10, 14, 23, 0))
    assert "--sleep" in calls[0]
    assert runner.tick(datetime(2026, 10, 14, 23, 1)) == "quiet"
    assert "Rain" in runner.tick(datetime(2026, 10, 15, 7, 0))


def test_no_weather_waits(tmp_path):
    runner, calls = make(tmp_path, None)
    assert runner.tick(datetime(2026, 10, 14, 9, 0)).startswith("no current weather")
    assert calls == []


def test_quote_not_repeated_across_rotations(tmp_path):
    runner, _calls = make(tmp_path, RAIN, rotate_minutes=1)
    keys = []
    for minute in range(20):
        runner.tick(datetime(2026, 10, 14, 9, minute))
        keys.append(runner.state.last_key)
    assert len(set(keys)) == 20


def test_config_errors(tmp_path):
    with pytest.raises(ConfigError):
        load_config(None, {"latitude": 1.0})
    with pytest.raises(ConfigError):
        load_config(None, {"latitude": 1.0, "longitude": 1.0, "theme": "nope"})
    bad = tmp_path / "c.toml"
    bad.write_text('latitude = 1\nlongitude = 2\ncolour = "red"\n')
    with pytest.raises(ConfigError):
        load_config(bad, {})
    assert main(["--config", str(bad), "--pidfile", ""]) == CONFIG_ERROR_EXIT


@pytest.mark.parametrize(
    "toml",
    ['latitude = "51.5"\nlongitude = 0.0\n', 'latitude = 51.5\nlongitude = 0.0\nrotate_minutes = "30"\n',
     'latitude = 51.5\nlongitude = 0.0\nrotate_minutes = true\n', 'latitude = 51.5\nlongitude = 0.0\ndisplay = "yes"\n'],
)
def test_wrong_toml_types_are_config_errors(tmp_path, toml):
    path = tmp_path / "c.toml"
    path.write_text(toml)
    with pytest.raises(ConfigError):
        load_config(path, {})
    assert main(["--config", str(path), "--pidfile", ""]) == CONFIG_ERROR_EXIT


def test_integer_coordinates_are_fine(tmp_path):
    path = tmp_path / "c.toml"
    path.write_text("latitude = 51\nlongitude = 0\nrotate_minutes = 30\n")
    assert load_config(path, {}).latitude == 51


def test_renderer_gets_an_expanded_database_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    db = tmp_path / "weather.jsonl"
    db.write_text(DATABASE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    runner, calls = make(tmp_path, RAIN, database="~/weather.jsonl")
    runner.tick(datetime(2026, 10, 14, 9, 0))
    cmd = calls[0]
    assert cmd[cmd.index("--database") + 1] == str(db)


def test_repaints_when_the_shown_fallback_no_longer_fits(tmp_path):
    hot_clear = Observation(1, 33.0, 5.0, 10.0, True)
    hot_overcast = Observation(3, 33.0, 5.0, 10.0, True)
    runner, calls = make(tmp_path, hot_clear)
    # Every heat quote shown recently, so the clear-sky pick falls back to sunshine.
    runner.database = {"heat": [], "sunshine": runner.database["sunshine"], "clouds": runner.database["clouds"]}
    assert "(from sunshine)" in runner.tick(datetime(2026, 10, 14, 13, 0))
    assert runner.tick(datetime(2026, 10, 14, 13, 5)) == "idle"
    runner.weather.obs = hot_overcast
    assert "(from clouds)" in runner.tick(datetime(2026, 10, 14, 13, 10))
    assert len(calls) == 2


def test_random_rotation_skips_clocks(tmp_path):
    from idle_weather.render import shows_a_clock

    runner, _calls = make(tmp_path, RAIN, theme="random")
    runner.state.theme_bag = ["vhs", "saloon"]  # saved before vhs left the pool
    picks = [runner.next_theme() for _ in range(200)]
    assert picks[0] == "saloon"
    assert not any(shows_a_clock(t) for t in picks)
