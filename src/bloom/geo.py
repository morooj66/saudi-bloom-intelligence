"""Saudi administrative boundaries (geoBoundaries gbOpen SAU ADM1, ODbL 1.0): load, validate, verify provenance.

No geometry is created or edited here. Pure-python checks (no GIS dependency).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import config as C
from .regions import ISO_CODES, REGIONS

GEOJSON_NAME = "saudi_adm1_geoboundaries_simplified.geojson"
ATTRIBUTION_TEXT = "Boundaries: geoBoundaries (SAU ADM1), © OpenStreetMap contributors, ODbL 1.0 · simplified release, unmodified"
# Independent check: well-known city coordinates (lat, lon) and the region that must contain each.
CITIES = {
    "Riyadh": (24.71, 46.68, "SA-01"), "Jeddah": (21.54, 39.17, "SA-02"), "Madinah": (24.47, 39.61, "SA-03"),
    "Buraydah": (26.33, 43.97, "SA-05"), "Dammam": (26.43, 50.10, "SA-04"), "Abha": (18.22, 42.51, "SA-14"),
    "Tabuk": (28.38, 36.57, "SA-07"), "Hail": (27.52, 41.70, "SA-06"), "Arar": (30.97, 41.02, "SA-08"),
    "Jazan": (16.89, 42.55, "SA-09"), "Najran": (17.49, 44.13, "SA-10"), "Al Bahah": (20.01, 41.47, "SA-11"),
    "Sakaka": (29.97, 40.21, "SA-12"),
}
BBOX = (33.0, 15.0, 57.0, 33.0)  # lon_min, lat_min, lon_max, lat_max (generous box around the Kingdom)


def _polys(geom: dict) -> list:
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def point_in_geometry(lon: float, lat: float, geom: dict) -> bool:
    return any(_in_ring(lon, lat, p[0]) and not any(_in_ring(lon, lat, h) for h in p[1:]) for p in _polys(geom))


def validate_geojson(d: dict) -> list[str]:
    """Return a list of problems (empty = valid)."""
    problems: list[str] = []
    feats = d.get("features", [])
    if d.get("type") != "FeatureCollection":
        problems.append("not a FeatureCollection")
    if len(feats) != C.EXPECTED_REGION_COUNT:
        problems.append(f"expected 13 features, found {len(feats)}")
    iso = [f.get("properties", {}).get("shapeISO") for f in feats]
    if sorted(map(str, iso)) != sorted(ISO_CODES):
        problems.append(f"shapeISO codes differ from the 13 ISO 3166-2:SA codes: {sorted(map(str, iso))}")
    for f in feats:
        g, code = f.get("geometry", {}), f.get("properties", {}).get("shapeISO")
        if g.get("type") not in ("Polygon", "MultiPolygon"):
            problems.append(f"{code}: geometry type {g.get('type')}")
            continue
        for poly in _polys(g):
            for ring in poly:
                if len(ring) < 4 or ring[0][:2] != ring[-1][:2]:
                    problems.append(f"{code}: ring not closed or too short")
                for lon, lat, *_ in ring:
                    if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
                        problems.append(f"{code}: coordinate outside Saudi bounding box ({lon}, {lat})")
                        break
    for city, (lat, lon, expected) in CITIES.items():
        got = [f["properties"]["shapeISO"] for f in feats if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon") and point_in_geometry(lon, lat, f["geometry"])]
        if got != [expected]:
            problems.append(f"{city} expected only in {expected}, found in {got}")
    return problems


def load_geojson(root: Path = C.ROOT) -> dict:
    return json.loads((C.paths(root).geo / GEOJSON_NAME).read_text(encoding="utf-8"))


def verify_geo(root: Path = C.ROOT) -> tuple[bool, str]:
    """(ok, detail). The map is shown only when the file's hash matches SOURCE.json and validation passes."""
    g = C.paths(root).geo
    try:
        src = json.loads((g / "SOURCE.json").read_text(encoding="utf-8"))
        f = g / GEOJSON_NAME
        if hashlib.sha256(f.read_bytes()).hexdigest() != src["files"]["simplified"]["sha256"]:
            return False, "boundary file hash differs from SOURCE.json"
        if "Open Database License" not in src.get("license", ""):
            return False, "licence in SOURCE.json is not the expected ODbL"
        problems = validate_geojson(json.loads(f.read_text(encoding="utf-8")))
        return (not problems), ("; ".join(problems[:3]) if problems else "boundary file verified")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def region_label_points(d: dict) -> dict[str, tuple[float, float]]:
    """(lon, lat) label anchor per region: centroid of the largest exterior ring (vertex-weighted shoelace)."""
    out = {}
    for f in d["features"]:
        ring = max((p[0] for p in _polys(f["geometry"])), key=len)
        a = cx = cy = 0.0
        for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:]):
            c = x1 * y2 - x2 * y1
            a += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c
        out[f["properties"]["shapeISO"]] = (cx / (3 * a), cy / (3 * a)) if a else tuple(ring[0][:2])
    return out


def _signed_area(ring: list) -> float:
    """>0 = clockwise in lon/lat (x right, y up)."""
    return sum((x2 - x1) * (y2 + y1) for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:])) / 2


def rewind_for_plotly(d: dict) -> dict:
    """Return a COPY with exterior rings clockwise and holes counter-clockwise (d3/plotly convention; RFC 7946 is the opposite).

    Only the vertex ORDER of a ring is reversed; no vertex is added, moved or removed. The stored file is not modified.
    """
    import copy

    out = copy.deepcopy(d)
    for f in out["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for k, ring in enumerate(poly):
                cw = _signed_area(ring) > 0
                if (k == 0 and not cw) or (k > 0 and cw):
                    ring.reverse()
    return out
