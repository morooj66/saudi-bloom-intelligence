"""INDEPENDENT verification of the regional ranking: standard library only, reads the ORIGINAL exports in incoming_data/
(no bloom code, own region-name mapping) and compares with the processed data and the dashboard KPI logic."""
import csv
import io
import re

import pandas as pd
import pytest

from bloom import config as C
from bloom.overview import top_region

MAP = {"جازان": "Jazan", "منطقة الباحة": "Al Bahah", "منطقة عسير": "Asir", "منطقة نجران": "Najran", "منطقة المدينة": "Madinah", "منطقة تبوك": "Tabuk",
       "منطقة حائل": "Hail", "منطقة الحدود الشمالية": "Northern Borders", "منطقة الجوف": "Al Jawf", "القصيم": "Qassim", "مكة المكرمة": "Makkah",
       "المنطقة الشرقية": "Eastern Province", "منطقة الرياض": "Riyadh"}
BIDI = dict.fromkeys([0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF])
P = C.PROCESSED_DIR
pytestmark = pytest.mark.skipif(not (P / "phase_a" / "regional_index_by_term.parquet").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


def read(fname):
    text = (C.INCOMING_DIR / fname).read_text(encoding="utf-8")
    rows = [[c.translate(BIDI).strip() for c in r] for r in csv.reader(io.StringIO(text))]
    h = next(i for i, r in enumerate(rows) if sum(1 for c in r if c) >= 2)
    return rows[h], [r for r in rows[h + 1:] if any(r)]


def cell(c):
    c = c.replace("%", "").strip()
    return None if c == "" or c.startswith("أقل") or c.startswith("<") else float(c)


def independent_ranking(fname, term):
    hdr, body = read(fname)
    terms = [h.split(":")[0].strip() for h in hdr[1:]]
    j = terms.index(term) + 1
    assert len(body) == 13 and {r[0] for r in body} == set(MAP)  # all 13 regions, no extras
    return {MAP[r[0]]: cell(r[j]) for r in body}


def test_flower_shop_index_file_is_what_we_think_it_is():
    hdr, _ = read("geoMap (4).csv")
    assert [h.split(":")[0] for h in hdr[1:]] == ["محل ورد"]                       # single term
    assert re.search(r"10/11/2021 - 10/11/2026", hdr[1])                           # query window stated by Google
    vals = independent_ranking("geoMap (4).csv", "محل ورد")
    assert all(v is not None for v in vals.values())                              # no blank/censored: compatible, complete


def test_jazan_is_highest_for_flower_shop_independently_and_in_the_app_logic():
    vals = independent_ranking("geoMap (4).csv", "محل ورد")
    order = sorted(vals.items(), key=lambda kv: -kv[1])
    assert order[0] == ("Jazan", 100.0) and order[1] == ("Northern Borders", 96.0) and order[2] == ("Najran", 92.0)
    idx = pd.read_parquet(P / "phase_a" / "regional_index_by_term.parquet")
    r = top_region(idx, "محل ورد")
    assert (r["region_en"], r["value"], r["runner_up_en"], r["runner_up_value"]) == ("Jazan", 100.0, "Northern Borders", 96.0)


@pytest.mark.parametrize("fname,term", [("geoMap (1).csv", "ورد"), ("geoMap (2).csv", "توصيل ورد"), ("geoMap (3).csv", "بوكيه ورد"),
                                         ("geoMap (4).csv", "محل ورد"), ("geoMap (5).csv", "شراء ورد")])
def test_processed_index_equals_independent_values_for_every_term(fname, term):
    want = independent_ranking(fname, term)
    idx = pd.read_parquet(P / "phase_a" / "regional_index_by_term.parquet")
    got = idx[idx["term"] == term].set_index("region_en")
    for region, v in want.items():
        if v is None:
            assert bool(got.loc[region, "is_missing"]) and pd.isna(got.loc[region, "value"])  # blank stays missing, never 0
        else:
            assert got.loc[region, "value"] == v


def test_peak_region_is_100_by_definition_in_every_index_export():
    for fname, term in [("geoMap (1).csv", "ورد"), ("geoMap (2).csv", "توصيل ورد"), ("geoMap (4).csv", "محل ورد"), ("geoMap (5).csv", "شراء ورد")]:
        assert max(v for v in independent_ranking(fname, term).values() if v is not None) == 100.0


def test_group_a_share_ranks_the_same_term_differently_and_that_is_documented():
    """Different measure (share among five terms), different top region. Both are correct and must never be merged."""
    shares = independent_ranking("geoMap.csv", "محل ورد")
    top = max(shares.items(), key=lambda kv: kv[1])
    assert top == ("Northern Borders", 13.0)
    assert independent_ranking("geoMap (4).csv", "محل ورد")["Jazan"] == 100.0 and shares["Jazan"] == 11.0
