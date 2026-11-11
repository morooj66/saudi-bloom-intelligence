import copy
import json

import pytest

from bloom import config as C
from bloom.geo import ATTRIBUTION_TEXT, load_geojson, region_label_points, validate_geojson, verify_geo
from bloom.regions import ISO_CODES

SRC = json.loads((C.paths().geo / "SOURCE.json").read_text(encoding="utf-8"))


def test_real_boundary_file_is_valid_and_verified():
    assert validate_geojson(load_geojson()) == []
    ok, detail = verify_geo()
    assert ok, detail


def test_boundary_file_has_exactly_the_13_regions():
    ids = sorted(f["properties"]["shapeISO"] for f in load_geojson()["features"])
    assert ids == sorted(ISO_CODES) and len(ids) == 13


def test_license_and_attribution_recorded():
    assert "Open Database License" in SRC["license"] and "OpenStreetMap" in SRC["upstream_source"]
    assert (C.paths().geo / "ATTRIBUTION.md").read_text(encoding="utf-8").count("OpenStreetMap contributors") >= 1
    assert "OpenStreetMap" in ATTRIBUTION_TEXT and "ODbL" in ATTRIBUTION_TEXT


def test_validation_catches_missing_region():
    d = load_geojson(); d["features"] = d["features"][:-1]
    assert validate_geojson(d)


def test_validation_catches_wrong_iso_code():
    d = load_geojson(); d["features"][0]["properties"]["shapeISO"] = "SA-99"
    assert any("ISO" in p for p in validate_geojson(d))


def test_validation_catches_swapped_geometries():
    d = copy.deepcopy(load_geojson())
    a, b = d["features"][0], d["features"][1]
    a["geometry"], b["geometry"] = b["geometry"], a["geometry"]
    assert any("expected only in" in p for p in validate_geojson(d))


def test_validation_catches_unclosed_ring_and_bad_coordinates():
    d = copy.deepcopy(load_geojson())
    g = d["features"][0]["geometry"]
    ring = g["coordinates"][0][0] if g["type"] == "MultiPolygon" else g["coordinates"][0]
    ring[-1] = [ring[-1][0] + 0.5, ring[-1][1]]
    assert any("not closed" in p for p in validate_geojson(d))
    d2 = copy.deepcopy(load_geojson())
    g2 = d2["features"][0]["geometry"]
    r2 = g2["coordinates"][0][0] if g2["type"] == "MultiPolygon" else g2["coordinates"][0]
    r2[0] = r2[-1] = [200.0, 0.0]
    assert any("outside Saudi bounding box" in p for p in validate_geojson(d2))


def test_verify_geo_fails_closed_on_tampering(tmp_path):
    import shutil
    dst = tmp_path / "p" / "data" / "geo"
    shutil.copytree(C.paths().geo, dst)
    f = dst / "saudi_adm1_geoboundaries_simplified.geojson"
    f.write_bytes(f.read_bytes() + b" ")
    ok, detail = verify_geo(tmp_path / "p")
    assert not ok and "hash" in detail
    assert not verify_geo(tmp_path / "nowhere")[0]


def test_label_points_fall_inside_saudi_bbox():
    pts = region_label_points(load_geojson())
    assert set(pts) == set(ISO_CODES) and all(33 < x < 57 and 15 < y < 33 for x, y in pts.values())


def test_rewind_changes_order_only_and_leaves_stored_file_untouched():
    from bloom.geo import _signed_area, rewind_for_plotly
    src = load_geojson()
    before = json.dumps(src, sort_keys=True)
    out = rewind_for_plotly(src)
    assert json.dumps(src, sort_keys=True) == before  # input not mutated
    for fa, fb in zip(src["features"], out["features"]):
        ga, gb = fa["geometry"], fb["geometry"]
        pa = ga["coordinates"] if ga["type"] == "MultiPolygon" else [ga["coordinates"]]
        pb = gb["coordinates"] if gb["type"] == "MultiPolygon" else [gb["coordinates"]]
        for ra, rb in zip(pa, pb):
            assert sorted(map(tuple, ra[0])) == sorted(map(tuple, rb[0]))  # same vertices
            assert _signed_area(rb[0]) > 0 and abs(abs(_signed_area(ra[0])) - abs(_signed_area(rb[0]))) < 1e-9  # clockwise, same area
    assert validate_geojson(out) == []
