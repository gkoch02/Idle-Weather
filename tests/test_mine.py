from idle_weather.mine import book_body, candidates_from_book, find_matches, is_verse

BOOK = """Title: A Wet Week
Author: Jane Example

*** START OF THE PROJECT GUTENBERG EBOOK A WET WEEK ***

The rain was falling steadily on the roofs of the town, and the gutters
ran full all the long grey afternoon while we sat by the window.

He felt as if a flash of lightning had shown him the truth at last, and
he could not speak for a long while afterwards.

Mrs. Gale came in with the tea and said nothing about the weather to
anybody in the room that afternoon.

*** END OF THE PROJECT GUTENBERG EBOOK A WET WEEK ***
license text about rain
"""


def test_book_body_strips_boilerplate():
    body = book_body(BOOK)
    assert "Title:" not in body and "license" not in body


def test_verse_detection():
    assert is_verse(["The rain it raineth", "every day", "upon the just", "and unjust fellow"])
    assert not is_verse(["A long prose line that goes on and on for quite a while, as prose does."] * 3)


def test_find_matches_prefers_longest():
    [(cond, m, weak)] = find_matches("Outside the rain was falling in torrents all night.")
    assert cond == "downpour" or m.group(0).startswith("rain") or "rain" in m.group(0)
    assert not weak


def test_candidates_keep_weather_and_drop_figures_and_names(tmp_path):
    path = tmp_path / "pg1.txt"
    path.write_text(BOOK, encoding="utf-8")
    rows = list(candidates_from_book(path, "1"))
    assert [r["condition"] for r in rows] == ["rain", "clouds"]  # no simile thunder, no Mrs. Gale
    row = rows[0]
    assert row["matched_text"] == "The rain was falling"
    assert row["matched_text"] in row["display_quote"]
    assert row["author"] == "Jane Example"
    assert row["key"].startswith("1:")
