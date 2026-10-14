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


def resolve_theme(theme: str) -> str:
    from idle_hours.runtime_theme import pick_random_theme

    return pick_random_theme() if theme == "random" else theme


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
