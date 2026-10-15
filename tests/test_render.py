import io
from datetime import datetime

import pytest
from PIL import Image

from idle_weather.pick import load_database
from idle_weather.render import HEIGHT, WIDTH, quote_row, render_png, resolve_theme, theme_pool

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


def test_random_pool_leaves_out_time_surfaces():
    pool = theme_pool()
    # Written out: hour carriers, a clock OSD, the swatch panel.
    for theme in ("tarot", "plaque", "vhs", "metro", "pulp", "diags"):
        assert theme not in pool
    # The Idle Hours name alone does not keep a theme out.
    for theme in ("saloon", "newsprint", "astrarium", "circuit", "sampler"):
        assert theme in pool
    assert resolve_theme("random") in pool


@pytest.mark.parametrize("theme", theme_pool())
def test_random_pool_themes_do_not_show_the_time(theme, monkeypatch):
    # astrarium prints the date and the sun's elevation from the wall clock;
    # pin Idle Hours' one clock seam so a minute ticking between the two
    # renders cannot move it. Only time_str differs.
    monkeypatch.setattr("idle_hours.render_quote.clock.now", lambda: datetime(2026, 10, 15, 12, 0))
    row = DB["rain"][0]
    assert render_png(row, theme, "03:10", "production") == render_png(row, theme, "14:40", "production")
