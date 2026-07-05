"""Full natal chart orchestration + determinism (FR-3.4)."""
import json
from datetime import date, time

from core.chart import BirthData, compute_natal_chart, chart_to_json

BIRTH = BirthData(
    name="Reference One",
    dob=date(1990, 8, 15),
    tob=time(12, 0, 0),
    lat=28.6139,
    lon=77.2090,
    tz_name="Asia/Kolkata",
    ayanamsha="krishnamurti",
    node_type="mean",
)


def test_top_level_structure():
    chart = compute_natal_chart(BIRTH)
    assert set(chart) >= {
        "meta", "grahas", "lagna", "houses", "significators", "vargas", "dasha"
    }


def test_meta_has_determinism_fields():
    meta = compute_natal_chart(BIRTH)["meta"]
    assert meta["ayanamsha"] == "krishnamurti"
    assert meta["node_type"] == "mean"
    assert meta["house_system"] == "placidus"
    assert "ayanamsha_value" in meta
    assert "julian_day" in meta
    assert meta["engine_version"]
    assert meta["swe_version"]


def test_nine_grahas_each_with_kp_chain_and_house():
    grahas = compute_natal_chart(BIRTH)["grahas"]
    assert len(grahas) == 9
    for g in grahas.values():
        assert set(g["kp"]) == {"sign_lord", "star_lord", "sub_lord", "sub_sub_lord"}
        assert 1 <= g["house"] <= 12


def test_twelve_house_cusps_with_kp_chain():
    houses = compute_natal_chart(BIRTH)["houses"]
    assert len(houses) == 12
    for cusp in houses:
        assert set(cusp["kp"]) == {"sign_lord", "star_lord", "sub_lord", "sub_sub_lord"}


def test_ketu_opposite_rahu_in_output():
    grahas = compute_natal_chart(BIRTH)["grahas"]
    diff = (grahas["Ketu"]["longitude"] - grahas["Rahu"]["longitude"]) % 360.0
    assert abs(diff - 180.0) < 1e-4


def test_dasha_tree_three_levels():
    dasha = compute_natal_chart(BIRTH)["dasha"]
    assert len(dasha) == 9
    md = dasha[0]
    assert md["level"] == 1 and md["children"][0]["level"] == 2
    assert md["children"][0]["children"][0]["level"] == 3


def test_sixteen_vargas_present():
    vargas = compute_natal_chart(BIRTH)["vargas"]
    assert len(vargas) == 16


def test_output_is_deterministic():
    a = chart_to_json(compute_natal_chart(BIRTH))
    b = chart_to_json(compute_natal_chart(BIRTH))
    assert a == b
    # and it is valid, key-sorted JSON
    assert json.loads(a) is not None
