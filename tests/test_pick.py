import random

from idle_weather.pick import REPEAT_DAYS, Shown, append_history, pick, read_history

DB = {
    "rain": [{"key": "r1", "author": "A", "quality_score": 100}, {"key": "r2", "author": "B", "quality_score": 100}],
    "drizzle": [{"key": "d1", "author": "C", "quality_score": 100}],
}


def test_picks_from_primary_and_avoids_last_author():
    hist = [Shown("x", "A", 0.0)]
    for seed in range(20):
        row, cond = pick(DB, ["rain", "drizzle"], hist, now=10.0, rng=random.Random(seed))
        assert cond == "rain" and row["key"] == "r2"


def test_falls_back_when_primary_spent():
    hist = [Shown("r1", "A", 0.0), Shown("r2", "B", 1.0)]
    row, cond = pick(DB, ["rain", "drizzle"], hist, now=10.0)
    assert (row["key"], cond) == ("d1", "drizzle")


def test_repeats_oldest_when_everything_spent():
    hist = [Shown("r2", "B", 0.0), Shown("r1", "A", 1.0), Shown("d1", "C", 2.0)]
    row, cond = pick(DB, ["rain", "drizzle"], hist, now=10.0)
    assert (row["key"], cond) == ("r2", "rain")


def test_old_history_expires():
    hist = [Shown("r1", "A", 0.0), Shown("r2", "B", 0.0)]
    _row, cond = pick(DB, ["rain"], hist, now=REPEAT_DAYS * 86400 + 1)
    assert cond == "rain"


def test_unknown_conditions_return_none():
    assert pick(DB, ["snow"], []) is None


def test_history_round_trip_skips_torn_line(tmp_path):
    path = tmp_path / "h.jsonl"
    append_history(path, {"key": "r1", "author": "A"}, "rain", at=5.0)
    with path.open("a") as fh:
        fh.write('{"key": "torn')
    assert read_history(path) == [Shown("r1", "A", 5.0)]
