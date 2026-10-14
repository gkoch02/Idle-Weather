import io

import pytest
from PIL import Image

from idle_weather.pick import load_database
from idle_weather.render import HEIGHT, WIDTH, quote_row, render_png

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
