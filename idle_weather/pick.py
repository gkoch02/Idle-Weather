"""Pick a quote for the current weather, skipping what was shown recently.

The baked database (``assets/weather_quotes.jsonl``) groups quotes by
condition. :func:`pick` walks the condition list :func:`conditions_for`
returns, real weather first, and draws from the first condition that still
has a quote not shown in the last ``REPEAT_DAYS``, avoiding the author shown
just before. When every pool on the list is spent it repeats the quote from
the real weather's pool that was shown longest ago.

The history is an append-only JSONL ledger; each line is fsynced and a torn
last line is skipped, as in Idle Hours.
"""
from __future__ import annotations

import json
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from idle_hours.jsonl_io import iter_jsonl

from idle_weather.bake import DATABASE_PATH

REPEAT_DAYS = 30
# How much of the ledger to read back: more than a month of rotations.
HISTORY_TAIL_LINES = 20000


@dataclass(frozen=True)
class Shown:
    key: str
    author: str | None
    at: float


def load_database(path: Path = DATABASE_PATH) -> dict[str, list[dict]]:
    by_condition: dict[str, list[dict]] = defaultdict(list)
    for row in iter_jsonl(path):
        by_condition[row["condition"]].append(row)
    return dict(by_condition)


def read_history(path: Path | None) -> list[Shown]:
    """Every readable ledger entry, oldest first."""
    if path is None or not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-HISTORY_TAIL_LINES:]
    out = []
    for line in lines:
        try:
            entry = json.loads(line)
            out.append(Shown(entry["key"], entry.get("author"), float(entry["at"])))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def append_history(path: Path, row: dict, condition: str, at: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"at": time.time() if at is None else at, "key": row["key"], "author": row.get("author"), "condition": condition}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def pick(
    database: dict[str, list[dict]],
    conditions: list[str],
    history: list[Shown],
    *,
    now: float | None = None,
    rng: random.Random | None = None,
) -> tuple[dict, str] | None:
    """``(row, condition it was drawn from)``, or None when no listed condition has any quote."""
    rng = rng or random.Random()
    now = time.time() if now is None else now
    cutoff = now - REPEAT_DAYS * 86400
    recent = {s.key for s in history if s.at >= cutoff}
    last_author = history[-1].author if history else None

    for cond in conditions:
        fresh = [r for r in database.get(cond, []) if r["key"] not in recent]
        if not fresh:
            continue
        other_author = [r for r in fresh if r.get("author") != last_author]
        pool = other_author or fresh
        weights = [max(1.0, float(r.get("quality_score", 100)) - 90.0) for r in pool]
        return rng.choices(pool, weights=weights, k=1)[0], cond

    for cond in conditions:
        rows = database.get(cond, [])
        if rows:
            last_shown = {s.key: s.at for s in history}
            return min(rows, key=lambda r: (last_shown.get(r["key"], 0.0), r["key"])), cond
    return None
