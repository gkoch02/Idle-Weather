import io
from datetime import datetime

import pytest
from idle_hours.theme_names import TIME_SURFACE_THEMES
from PIL import Image

from idle_weather.pick import load_database
from idle_weather.render import (
    DECORATIVE_TIME_THEMES,
    HEIGHT,
    WIDTH,
    quote_row,
    render_png,
    resolve_theme,
    theme_pool,
)

DB = load_database()


@pytest.mark.parametrize("theme", ["default", "dark", "saloon", "astrarium", "synoptic"])
def test_renders_a_quote(theme):
    row = DB["rain"][0]
    image = Image.open(io.BytesIO(render_png(row, theme, "09:15", "production")))
    assert image.size == (WIDTH, HEIGHT)


def test_sleep_frame():
    image = Image.open(io.BytesIO(render_png(None, "dark", "23:00", "production", sleep=True)))
    assert image.size == (WIDTH, HEIGHT)


def test_quote_row_labels_the_condition():
    assert quote_row(DB["fog"][0])["bucket"] == "Fog or mist"


def test_random_pool_leaves_out_clocks():
    pool = theme_pool()
    # Written out: the themes that read as a clock, and the swatch panel.
    for theme in ("vhs", "platform", "cardcatalog", "bakelite", "reactornight", "synoptic", "diags"):
        assert theme not in pool
    # The time worked in as decoration does not keep a theme out...
    for theme in ("tarot", "semiotic", "metro", "gantry", "pourjudgment", "dsky"):
        assert theme in pool
    # ...nor does the Idle Hours name.
    for theme in ("saloon", "newsprint", "astrarium", "circuit", "sampler"):
        assert theme in pool
    assert resolve_theme("random") in pool


def test_decorative_list_names_only_time_surfaces():
    # An entry Idle Hours no longer counts as drawing the time is in the pool
    # anyway; drop it here so the list stays the set of judgement calls.
    assert DECORATIVE_TIME_THEMES <= TIME_SURFACE_THEMES


@pytest.mark.parametrize("theme", [t for t in theme_pool() if t not in TIME_SURFACE_THEMES])
def test_pool_themes_outside_the_time_list_do_not_show_the_time(theme, monkeypatch):
    # astrarium prints the date and the sun's elevation from the wall clock;
    # pin Idle Hours' one clock seam so a minute ticking between the two
    # renders cannot move it. Only time_str differs.
    monkeypatch.setattr("idle_hours.render_quote.clock.now", lambda: datetime(2026, 10, 15, 12, 0))
    row = DB["rain"][0]
    assert render_png(row, theme, "03:10", "production") == render_png(row, theme, "14:40", "production")
