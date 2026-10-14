import pytest

from idle_weather.conditions import CONDITIONS, FALLBACKS, LABELS, Observation, conditions_for, primary_condition


def obs(code=0, temp=15.0, wind=5.0, gust=10.0, day=True):
    return Observation(code, temp, wind, gust, day)


def test_every_condition_has_a_label_and_fallbacks_starting_with_itself():
    assert set(LABELS) == set(CONDITIONS) == set(FALLBACKS)
    for cond, chain in FALLBACKS.items():
        assert chain[0] == cond
        assert set(chain) <= set(CONDITIONS)


@pytest.mark.parametrize(
    "code, expected",
    [(95, "thunder"), (99, "thunder"), (66, "sleet"), (57, "sleet"), (71, "snow"), (86, "snow"),
     (65, "downpour"), (82, "downpour"), (61, "rain"), (80, "rain"), (53, "drizzle"), (45, "fog"), (3, "clouds")],
)
def test_wmo_codes(code, expected):
    assert primary_condition(obs(code)) == expected


def test_dry_sky_rules():
    assert primary_condition(obs(0, day=True)) == "sunshine"
    assert primary_condition(obs(0, day=False)) == "night_sky"
    assert primary_condition(obs(2, day=False)) == "clouds"
    assert primary_condition(obs(1, temp=33)) == "heat"
    assert primary_condition(obs(1, temp=33, day=False)) == "night_sky"
    assert primary_condition(obs(3, temp=33)) == "heat"
    assert primary_condition(obs(3, temp=33, day=False)) == "clouds"
    assert primary_condition(obs(3, temp=28)) == "clouds"
    assert primary_condition(obs(0, temp=-4)) == "frost"
    assert primary_condition(obs(3, wind=60)) == "wind"
    assert primary_condition(obs(3, gust=80)) == "wind"


def test_precipitation_wins_over_wind_but_wind_is_offered():
    assert conditions_for(obs(61, wind=60)) == ["rain", "drizzle", "downpour", "wind"]
    assert conditions_for(obs(61)) == ["rain", "drizzle", "downpour"]


def test_overcast_heat_falls_back_to_cloud_not_sunshine():
    assert conditions_for(obs(3, temp=33)) == ["heat", "clouds"]
    assert conditions_for(obs(1, temp=33)) == ["heat", "sunshine"]
