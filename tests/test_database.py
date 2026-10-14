"""Invariants of the shipped quote database."""
import json

from idle_hours.match_span import has_display_match

from idle_weather.bake import CURATION_PATH, DATABASE_PATH, MIN_SCORE, SHIPPED_FIELDS
from idle_weather.conditions import CONDITIONS

ROWS = [json.loads(line) for line in DATABASE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
CURATION = json.loads(CURATION_PATH.read_text(encoding="utf-8"))


def test_every_condition_has_quotes():
    counts = {c: sum(r["condition"] == c for r in ROWS) for c in CONDITIONS}
    assert all(n >= 40 for n in counts.values()), counts


def test_rows_are_reviewed_and_well_formed():
    accepted = set(CURATION["accepted"])
    keys = [r["key"] for r in ROWS]
    assert len(keys) == len(set(keys))
    for row in ROWS:
        assert tuple(row) == SHIPPED_FIELDS
        assert row["key"] in accepted and row["key"] not in CURATION["rejected"]
        assert row["condition"] in CONDITIONS
        assert row["quality_score"] >= MIN_SCORE
        assert row["author"] and row["title"]


def test_renderer_can_highlight_every_phrase():
    assert [r["key"] for r in ROWS if not has_display_match(r)] == []
