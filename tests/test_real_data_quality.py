"""Data-quality tests on the REAL Google Trends exports (run the pipeline first)."""
import json

import pandas as pd
import pytest

from bloom import config as C
from bloom.regions import ISO_CODES
from bloom.schema import REGIONAL_SNAPSHOT_COLUMNS, NATIONAL_WEEKLY_COLUMNS, ScaleMixError, assert_same_scale, validate_columns

P = C.PROCESSED_DIR
pytestmark = pytest.mark.skipif(not (P / "validation_results.json").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


@pytest.fixture(scope="module")
def results():
    return json.loads((P / "validation_results.json").read_text(encoding="utf-8"))


def test_no_validation_errors(results):
    errs = [c for c in results["checks"] if not c["passed"] and c["level"] == "error"]
    assert errs == []


@pytest.mark.parametrize("stem,terms", [("A", C.ALL_TERMS), ("B", C.COMMERCIAL_TERMS)])
def test_timeline_schema_and_groups(stem, terms):
    df = pd.read_parquet(P / f"timeline_group{stem}_long.parquet")
    assert set(df["term"]) == set(terms)
    assert df["scale_id"].nunique() == 1 and df["comparison_group"].nunique() == 1
    assert validate_columns(df, [c for c in NATIONAL_WEEKLY_COLUMNS]) == []
    assert not df.duplicated(["term", "week_start"]).any()
    assert (df["week_start"].dt.weekday == 6).all()


def test_weekly_frequency_constant():
    for stem in "AB":
        df = pd.read_parquet(P / f"timeline_group{stem}_long.parquet")
        for _, g in df.groupby("term"):
            assert (g.sort_values("week_start")["week_start"].diff().dropna().dt.days == 7).all()


def test_groups_not_mixed_in_outputs():
    a = pd.read_parquet(P / "timeline_groupA_long.parquet")
    b = pd.read_parquet(P / "timeline_groupB_long.parquet")
    with pytest.raises(ScaleMixError):
        assert_same_scale(a, b)
    # the same term has a different scale in A and B (A: محل ورد max 15; B: max 100)
    assert a.query("term=='محل ورد'")["value"].max() != b.query("term=='محل ورد'")["value"].max()


def test_censored_never_numeric():
    for f in ("timeline_groupA_long", "region_groupA_share", "region_single_term_index"):
        df = pd.read_parquet(P / f"{f}.parquet")
        c = df[df["is_censored"]]
        assert c["value"].isna().all() and (c["censor_upper_bound"] == 1.0).all()


def test_regional_coverage_13():
    for f in ("region_groupA_share", "region_single_term_index"):
        df = pd.read_parquet(P / f"{f}.parquet")
        assert validate_columns(df, REGIONAL_SNAPSHOT_COLUMNS) == []
        for _, g in df.groupby("scale_id"):
            assert set(g["region_iso"]) == set(ISO_CODES) and len(g) == g["region_iso"].nunique() * g["term"].nunique()


def test_numeric_ranges():
    for f in ("timeline_groupA_long", "timeline_groupB_long", "region_groupA_share", "region_single_term_index"):
        v = pd.read_parquet(P / f"{f}.parquet")["value"].dropna()
        assert v.between(0, 100).all()


def test_edge_weeks_flagged():
    df = pd.read_parquet(P / "timeline_groupB_analytic_weekly.parquet")
    flagged = df.loc[df["is_edge_partial_week"], "week_start"].dt.strftime("%Y-%m-%d").tolist()
    assert flagged == ["2021-11-07", "2026-11-08"]


def test_every_scale_in_manifest():
    m = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    ids = {e["scale_id"] for e in m}
    for f in ("timeline_groupA_long", "timeline_groupB_long", "region_groupA_share", "region_single_term_index"):
        assert set(pd.read_parquet(P / f"{f}.parquet")["scale_id"]) <= ids
