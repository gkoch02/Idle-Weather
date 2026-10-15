import io

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


def test_random_pool_leaves_out_clock_furniture():
    pool = theme_pool()
    # A few of each kind, written out: hour carriers, a clock OSD, an imprint.
    for theme in ("tarot", "plaque", "vhs", "metro", "pulp", "sampler", "diags"):
        assert theme not in pool
    assert "saloon" in pool and "newsprint" in pool
    assert resolve_theme("random") in pool


@pytest.mark.parametrize("theme", theme_pool())
def test_random_pool_themes_do_not_show_the_time(theme):
    row = DB["rain"][0]
    assert render_png(row, theme, "03:10", "production") == render_png(row, theme, "14:40", "production")
