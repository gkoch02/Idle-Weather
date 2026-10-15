"""Render one weather quote to an 800×480 PNG with an Idle Hours theme.

The run loop calls this in a subprocess (as Idle Hours does with its own
renderer) so Pillow and the font cache are released after every frame:

    idle-weather render --key 1342:120:44 --theme saloon --output output/current.png
    idle-weather render --condition fog --theme random --output /tmp/fog.png
    idle-weather render --sleep --theme dark --output output/current.png
"""
from __future__ import annotations

import argparse
import io
import random
from datetime import datetime
from pathlib import Path

from idle_hours import atomic_io
from idle_hours.runtime_theme import random_theme_pool
from idle_hours.theme_names import TIME_SURFACE_THEMES

from idle_weather.bake import DATABASE_PATH
from idle_weather.conditions import CONDITIONS, LABELS
from idle_weather.pick import load_database

WIDTH, HEIGHT = 800, 480


def quote_row(row: dict, condition: str | None = None) -> dict:
    """The row Idle Hours' renderer reads, built from a baked weather row."""
    cond = condition or row["condition"]
    return {
        "display_quote": row["display_quote"],
        "matched_text": row["matched_text"],
        "author": row.get("author"),
        "title": row.get("title"),
        "source_id": row.get("source_id"),
        "quality_score": row.get("quality_score"),
        # The debug footer prints the bucket; here that is the weather.
        "bucket": LABELS.get(cond, cond),
    }


def find_row(database: dict[str, list[dict]], key: str) -> dict:
    for rows in database.values():
        for row in rows:
            if row["key"] == key:
                return row
    raise SystemExit(f"No quote with key {key!r} in the database")


# Themes that draw the time they are given (Idle Hours' TIME_SURFACE_THEMES)
# without reading as a clock: the hour is a tarot numeral, a stop or exit number,
# a gauge, a section plate. A glance sees decoration, so an hour that is half an
# hour stale on a weather panel does no harm. Picked by looking at each frame. A
# time surface not listed here, including any new one, stays out of random until
# someone looks at it; the ones left out show a clock time, "PM", or a label
# reading HOUR or VALID (vhs, platform, cardcatalog, bakelite, reactornight,
# synoptic).
DECORATIVE_TIME_THEMES: frozenset[str] = frozenset({
    "abyssal", "atropos", "beksinski", "betweenus", "betweenus_dark", "biomech", "bladerunner", "codex",
    "culture", "dsky", "expanse", "expedition", "gantry", "hades", "hal", "hippochomp", "hitchhiker",
    "izakaya", "lasvegas", "lieder", "lumon", "metro", "oblivion", "observation", "orbital", "plaque",
    "pourjudgment", "pulp", "saros", "semiotic", "tarot", "traumateam", "trisolaris", "vitrail", "witcher",
    "yorha",
})


def shows_a_clock(theme: str) -> bool:
    """Whether a theme draws the time in a way that reads as one."""
    return theme in TIME_SURFACE_THEMES and theme not in DECORATIVE_TIME_THEMES


def theme_pool() -> tuple[str, ...]:
    """The themes ``random`` draws from: Idle Hours' rotation without the ones
    that show a clock, since a weather frame stays up for half an hour."""
    return tuple(t for t in random_theme_pool() if not shows_a_clock(t))


def resolve_theme(theme: str) -> str:
    return random.choice(theme_pool()) if theme == "random" else theme


def render_png(row: dict | None, theme: str, time_str: str, mode: str, sleep: bool = False) -> bytes:
    from idle_hours import render_quote as rq

    if sleep:
        image = rq.render_sleep_frame(time_str, WIDTH, HEIGHT, theme=theme)
    else:
        assert row is not None
        image = rq.render(time_str, quote_row(row), WIDTH, HEIGHT, mode=mode, theme=theme)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    from idle_hours.theme_names import THEME_ORDER

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--key", help="Render this quote.")
    which.add_argument("--condition", choices=CONDITIONS, help="Render a random quote for this condition.")
    which.add_argument("--sleep", action="store_true", help="Render the quiet-hours frame.")
    parser.add_argument("--theme", default="default", choices=("random", *THEME_ORDER))
    parser.add_argument("--time", default=None, help="HH:MM for themes that draw the time (default: now).")
    parser.add_argument("--mode", default="production", choices=("production", "debug"))
    parser.add_argument("--database", default=str(DATABASE_PATH))
    parser.add_argument("--output", default="output/current.png")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    theme = resolve_theme(args.theme)
    time_str = args.time or datetime.now().strftime("%H:%M")
    row = None
    if not args.sleep:
        database = load_database(Path(args.database).expanduser())
        if args.key:
            row = find_row(database, args.key)
        else:
            rows = database.get(args.condition) or []
            if not rows:
                raise SystemExit(f"No quotes for {args.condition!r}")
            row = random.choice(rows)
    png = render_png(row, theme, time_str, args.mode, sleep=args.sleep)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_io.atomic_write_bytes(out, png)
    what = "sleep frame" if row is None else row["key"]
    print(f"Rendered {what} in {theme} to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
