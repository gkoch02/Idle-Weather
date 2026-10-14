"""Bake the mined candidates into the runtime quote database.

A candidate ships only once it has been reviewed and accepted in
``assets/curation.json``. The baker ranks every eligible candidate per
condition and, with ``--queue``, writes the best unreviewed ones to a file for
the next review pass.

    idle-weather bake                                  # write assets/weather_quotes.jsonl
    idle-weather bake --queue output/review-queue.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from idle_hours import atomic_io
from idle_hours.jsonl_io import iter_jsonl

from idle_weather.conditions import CONDITIONS

ASSETS = Path(__file__).resolve().parent / "assets"
DATABASE_PATH = ASSETS / "weather_quotes.jsonl"
CURATION_PATH = ASSETS / "curation.json"

# A candidate below this score is never shown.
MIN_SCORE = 95
# At most this many quotes from one book per condition, so one long novel
# about a wet winter does not own the rain.
PER_BOOK_CAP = 6
# How deep into each condition's ranking a review pass reaches.
QUEUE_DEPTH = 260

# Fields the runtime reads, in the order they are written.
SHIPPED_FIELDS = ("key", "condition", "display_quote", "matched_text", "author", "title", "source_id", "quality_score")


def load_curation(path: Path = CURATION_PATH) -> tuple[set[str], dict[str, str]]:
    """``(accepted keys, {rejected key: reason})`` from the curation file."""
    if not path.exists():
        return set(), {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("accepted", [])), dict(data.get("rejected", {}))


def ranked(rows: list[dict], rejected: dict[str, str]) -> dict[str, list[dict]]:
    """Eligible candidates per condition, best first, deduplicated and capped per book."""
    by_condition: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["quality_score"] >= MIN_SCORE and row["key"] not in rejected and row.get("author"):
            by_condition[row["condition"]].append(row)
    out: dict[str, list[dict]] = {}
    for cond, cands in by_condition.items():
        cands.sort(key=lambda r: (-r["quality_score"], r["key"]))
        seen: set[str] = set()
        per_book: Counter[str] = Counter()
        kept = []
        for row in cands:
            text = row["display_quote"]
            if text in seen or per_book[row["source_id"]] >= PER_BOOK_CAP:
                continue
            seen.add(text)
            per_book[row["source_id"]] += 1
            kept.append(row)
        out[cond] = kept
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", default="output/candidates.jsonl")
    parser.add_argument("--output", default=str(DATABASE_PATH))
    parser.add_argument("--curation", default=str(CURATION_PATH))
    parser.add_argument("--queue", default=None, help="Write the unreviewed top candidates here for review.")
    parser.add_argument("--queue-depth", type=int, default=QUEUE_DEPTH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    accepted, rejected = load_curation(Path(args.curation))
    by_condition = ranked(list(iter_jsonl(Path(args.input))), rejected)

    shipped = []
    queue = []
    for cond in CONDITIONS:
        rows = by_condition.get(cond, [])
        shipped.extend(r for r in rows if r["key"] in accepted)
        queue.extend(r for r in rows[: args.queue_depth] if r["key"] not in accepted)

    out = Path(args.output)
    atomic_io.atomic_write_lines(
        out, (json.dumps({f: r.get(f) for f in SHIPPED_FIELDS}, ensure_ascii=False) for r in shipped)
    )
    counts = Counter(r["condition"] for r in shipped)
    print(f"Baked {len(shipped)} quotes into {out}")
    for cond in CONDITIONS:
        print(f"  {cond:10} {counts.get(cond, 0)}")
    if args.queue:
        queue_path = Path(args.queue)
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_io.atomic_write_lines(queue_path, (json.dumps(r, ensure_ascii=False) for r in queue))
        print(f"Wrote {len(queue)} unreviewed candidates to {queue_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
