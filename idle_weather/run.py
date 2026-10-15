"""The Idle Weather appliance loop: watch the weather, repaint the panel with a fitting quote.

Every minute it asks :class:`~idle_weather.weather.WeatherSource` for the
current weather (which fetches at most every ``weather_minutes``). It repaints
when the condition changes or ``rotate_minutes`` have passed since the last
paint, and paints the quiet-hours frame once on entering quiet hours.

Settings come from a TOML file (``--config``) and are overridden by flags. A
bad configuration exits 42, which the systemd unit lists under
``RestartPreventExitStatus`` so it halts instead of flapping, as Idle Hours
does.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from idle_hours import atomic_io, sd_notify
from idle_hours.pidfile import PidfileLockedError, acquire_pidfile
from idle_hours.runtime_quiet import in_quiet_hours
from idle_hours.runtime_theme import pick_next_random_theme, recent_window_size
from idle_hours.theme_names import THEME_ORDER

from idle_weather.bake import DATABASE_PATH
from idle_weather.conditions import LABELS, conditions_for
from idle_weather.pick import append_history, load_database, pick, read_history
from idle_weather.render import shows_a_clock, theme_pool
from idle_weather.weather import WeatherSource

CONFIG_ERROR_EXIT = 42
RENDER_TIMEOUT_SECONDS = 45
DISPLAY_TIMEOUT_SECONDS = 60
# After a failed paint, wait this long before trying again.
RETRY_SECONDS = 5 * 60


class ConfigError(ValueError):
    """The configuration cannot run."""


@dataclass
class Config:
    latitude: float | None = None
    longitude: float | None = None
    theme: str = "random"
    rotate_minutes: float = 30
    weather_minutes: float = 10
    quiet_start: str | None = None
    quiet_end: str | None = None
    display: bool = False
    mode: str = "production"
    state_dir: str = "~/.idle-weather"
    output: str = "output/current.png"
    database: str = str(DATABASE_PATH)

    def validate(self) -> None:
        self._check_types()
        if self.latitude is None or self.longitude is None:
            raise ConfigError("latitude and longitude are required")
        if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ConfigError(f"latitude/longitude out of range: {self.latitude}, {self.longitude}")
        if self.theme != "random" and self.theme not in THEME_ORDER:
            raise ConfigError(f"unknown theme {self.theme!r}")
        if self.mode not in ("production", "debug"):
            raise ConfigError(f"mode must be production or debug, not {self.mode!r}")
        if self.rotate_minutes <= 0 or self.weather_minutes <= 0:
            raise ConfigError("rotate_minutes and weather_minutes must be positive")
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ConfigError("set both quiet_start and quiet_end, or neither")
        for value in (self.quiet_start, self.quiet_end):
            if value is not None:
                try:
                    datetime.strptime(value, "%H:%M")
                except ValueError as exc:
                    raise ConfigError(f"quiet hours must be HH:MM, not {value!r}") from exc
        if not self.database_path.exists():
            raise ConfigError(f"quote database not found: {self.database}")

    def _check_types(self) -> None:
        """Reject a value of the wrong type, which TOML allows (``latitude = "51.5"``)."""
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None and f.name in _OPTIONAL_FIELDS:
                continue
            expected = _FIELD_TYPES[f.name]
            # bool is an int subclass: ``rotate_minutes = true`` is not a number.
            if isinstance(value, bool) and expected is not bool:
                raise ConfigError(f"{f.name} must be {expected.__name__}, not {value!r}")
            if expected is float and isinstance(value, int):
                continue
            if not isinstance(value, expected):
                raise ConfigError(f"{f.name} must be {expected.__name__}, not {value!r}")

    @property
    def database_path(self) -> Path:
        return Path(self.database).expanduser()

    @property
    def state_path(self) -> Path:
        return Path(self.state_dir).expanduser()


_FIELD_TYPES: dict[str, type] = {
    "latitude": float, "longitude": float, "theme": str, "rotate_minutes": float, "weather_minutes": float,
    "quiet_start": str, "quiet_end": str, "display": bool, "mode": str, "state_dir": str, "output": str, "database": str,
}
_OPTIONAL_FIELDS = frozenset({"latitude", "longitude", "quiet_start", "quiet_end"})


def load_config(path: Path | None, overrides: dict) -> Config:
    data: dict = {}
    if path is not None:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"cannot read config {path}: {exc}") from exc
    known = {f.name for f in fields(Config)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"unknown config keys: {', '.join(sorted(unknown))}")
    data.update({k: v for k, v in overrides.items() if v is not None})
    try:
        config = Config(**data)
    except TypeError as exc:
        raise ConfigError(str(exc)) from exc
    config.validate()
    return config


@dataclass
class State:
    """What the loop remembers across restarts."""

    last_condition: str | None = None
    # The pool the shown quote came from, which may be a fallback.
    last_drawn_from: str | None = None
    last_paint_at: float | None = None
    last_key: str | None = None
    last_theme: str | None = None
    quiet: bool = False
    theme_bag: list[str] = field(default_factory=list)
    recent_themes: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> State:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_io.atomic_write_text(path, json.dumps(asdict(self), indent=2) + "\n")


def log(message: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}", flush=True)


class Runner:
    def __init__(self, config: Config, weather: WeatherSource | None = None, runner=subprocess.run):
        self.config = config
        self.state_file = config.state_path / "state.json"
        self.history_file = config.state_path / "history.jsonl"
        self.state = State.load(self.state_file)
        self.database = load_database(config.database_path)
        self.weather = weather or WeatherSource(
            config.latitude, config.longitude, config.state_path / "weather.json", config.weather_minutes * 60
        )
        self._run = runner
        self._retry_at: float | None = None
        # A restart always repaints: the panel may show anything.
        self._painted_this_run = False

    def next_theme(self) -> str:
        if self.config.theme != "random":
            return self.config.theme
        pool = theme_pool()
        # A bag saved before a theme left the pool can still hold it.
        bag = [t for t in self.state.theme_bag if t in pool]
        theme, bag = pick_next_random_theme(bag, recent=self.state.recent_themes, pool=pool)
        window = recent_window_size(len(pool))
        self.state.theme_bag = bag
        self.state.recent_themes = (self.state.recent_themes + [theme])[-window:]
        return theme

    def _paint(self, render_args: list[str], theme: str) -> None:
        output = str(Path(self.config.output).expanduser())
        self._run(
            [sys.executable, "-m", "idle_weather.render", *render_args, "--theme", theme,
             "--mode", self.config.mode, "--database", str(self.config.database_path), "--output", output],
            check=True, timeout=RENDER_TIMEOUT_SECONDS,
        )
        if self.config.display:
            self._run(
                [sys.executable, "-m", "idle_hours.display_inky", output, "--theme", theme],
                check=True, timeout=DISPLAY_TIMEOUT_SECONDS,
            )

    def tick(self, now: datetime) -> str:
        """One pass of the loop. Returns a short description of what it did."""
        ts = now.timestamp()
        time_str = now.strftime("%H:%M")
        if self._retry_at is not None and ts < self._retry_at:
            return "waiting to retry"

        if in_quiet_hours(time_str, self.config.quiet_start, self.config.quiet_end):
            if self.state.quiet and self._painted_this_run:
                return "quiet"
            theme = self.next_theme()
            if not self._try_paint(["--sleep", "--time", time_str], theme, ts):
                return "sleep frame failed"
            self.state.quiet = True
            self.state.last_condition = None
            self.state.save(self.state_file)
            return f"quiet hours began; sleep frame in {theme}"

        reading = self.weather.current(ts)
        if reading is None:
            return f"no current weather ({self.weather.last_error or 'nothing fetched yet'})"
        conditions = conditions_for(reading.observation)
        primary = conditions[0]
        due = (
            not self._painted_this_run
            or self.state.quiet
            or self.state.last_condition != primary
            # The weather is the same but the quote's pool no longer fits it
            # (a sunshine fallback for heat, once the sky turns overcast).
            or (self.state.last_drawn_from is not None and self.state.last_drawn_from not in conditions)
            or self.state.last_paint_at is None
            or ts - self.state.last_paint_at >= self.config.rotate_minutes * 60
        )
        if not due:
            return "idle"

        picked = pick(self.database, conditions, read_history(self.history_file), now=ts)
        if picked is None:
            return f"no quotes for {conditions}"
        row, drawn_from = picked
        theme = self.next_theme()
        if not self._try_paint(["--key", row["key"], "--time", time_str], theme, ts):
            return "paint failed"
        append_history(self.history_file, row, drawn_from, at=ts)
        self.state.quiet = False
        self.state.last_condition = primary
        self.state.last_drawn_from = drawn_from
        self.state.last_key = row["key"]
        self.state.last_theme = theme
        self.state.save(self.state_file)
        obs = reading.observation
        note = "" if drawn_from == primary else f" (from {drawn_from})"
        return (
            f"{LABELS[primary]}{note}, {obs.temperature_c:.0f}°C, wind {obs.wind_kmh:.0f} km/h: "
            f"{row['author']}, {row['title']} [{row['key']}] in {theme}"
        )

    def _try_paint(self, render_args: list[str], theme: str, ts: float) -> bool:
        try:
            self._paint(render_args, theme)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            log(f"paint failed: {exc!r}; retrying in {RETRY_SECONDS // 60} min")
            self._retry_at = ts + RETRY_SECONDS
            return False
        self._retry_at = None
        self._painted_this_run = True
        self.state.last_paint_at = ts
        self.state.last_theme = theme
        return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="TOML settings file.")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--theme", help="An Idle Hours theme, or 'random'.")
    parser.add_argument("--rotate-minutes", type=float)
    parser.add_argument("--weather-minutes", type=float)
    parser.add_argument("--quiet-start")
    parser.add_argument("--quiet-end")
    parser.add_argument("--display", action=argparse.BooleanOptionalAction, default=None, help="Push frames to the Inky panel.")
    parser.add_argument("--mode", choices=("production", "debug"))
    parser.add_argument("--state-dir")
    parser.add_argument("--output")
    parser.add_argument("--database")
    parser.add_argument("--pidfile", default="~/.idle-weather/run.pid", help="Single-instance lock ('' to disable).")
    parser.add_argument("--once", action="store_true", help="Run one tick and exit.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    overrides = {
        "latitude": args.latitude, "longitude": args.longitude, "theme": args.theme,
        "rotate_minutes": args.rotate_minutes, "weather_minutes": args.weather_minutes,
        "quiet_start": args.quiet_start, "quiet_end": args.quiet_end, "display": args.display,
        "mode": args.mode, "state_dir": args.state_dir, "output": args.output, "database": args.database,
    }
    try:
        config = load_config(Path(args.config).expanduser() if args.config else None, overrides)
    except ConfigError as exc:
        print(f"idle-weather: configuration error: {exc}", file=sys.stderr)
        return CONFIG_ERROR_EXIT
    try:
        pidfile = acquire_pidfile(str(Path(args.pidfile).expanduser()) if args.pidfile else None)
    except PidfileLockedError as exc:
        print(f"idle-weather: {exc}", file=sys.stderr)
        return 1

    runner = Runner(config)
    try:
        if args.once:
            log(runner.tick(datetime.now()))
            return 0
        sd_notify.notify_ready()
        log(f"started at {config.latitude}, {config.longitude}; theme {config.theme}")
        if shows_a_clock(config.theme):
            log(f"theme {config.theme} shows a clock; 'random' leaves such themes out")
        last = None
        while True:
            message = runner.tick(datetime.now())
            if message != last or message not in ("idle", "quiet"):
                log(message)
            last = message
            sd_notify.notify_watchdog()
            time.sleep(60 - datetime.now().second + 0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        if pidfile is not None:
            pidfile.release()


if __name__ == "__main__":
    raise SystemExit(main())
