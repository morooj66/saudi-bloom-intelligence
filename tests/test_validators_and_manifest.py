"""Negative tests for validators (mutations of REAL parsed frames, in memory) and manifest consistency."""
import json

import pandas as pd
import pytest

from bloom import config as C
from bloom.ingest import fingerprint
from bloom.trends_io import sha256_file
from bloom.validate import validate_geomap, validate_timeline

P = C.PROCESSED_DIR
pytestmark = pytest.mark.skipif(not (P / "validation_results.json").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


def failed(checks, level="error"):
    return {c["name"] for c in checks if not c["passed"] and c["level"] == level}


@pytest.fixture
def tl():
    return pd.read_parquet(P / "timeline_groupB_long.parquet")


@pytest.fixture
def geo_share():
    return pd.read_parquet(P / "region_groupA_share.parquet")


@pytest.fixture
def geo_idx():
    return pd.read_parquet(P / "region_single_term_index.parquet").query("term == 'محل ورد'")


def test_real_timelines_have_no_errors():
    for s in "AB":
        assert failed(validate_timeline(pd.read_parquet(P / f"timeline_group{s}_long.parquet"), s)) == set()


def test_timeline_out_of_range(tl):
    tl.loc[tl.index[3], "value"] = 250.0
    assert "values_in_0_100" in failed(validate_timeline(tl, "x"))


def test_timeline_negative(tl):
    tl.loc[tl.index[3], "value"] = -1.0
    assert "values_in_0_100" in failed(validate_timeline(tl, "x"))


def test_timeline_non_integer(tl):
    tl.loc[tl.index[3], "value"] = 12.5
    assert "integers_only" in failed(validate_timeline(tl, "x"))


def test_timeline_duplicate_rows(tl):
    assert "no_duplicate_dates" in failed(validate_timeline(pd.concat([tl, tl.iloc[[5]]]), "x"))


def test_timeline_gap(tl):
    drop = tl[(tl["term"] == "محل ورد")].index[10]
    assert "frequency_constant_7d" in failed(validate_timeline(tl.drop(index=drop), "x"))


def test_timeline_non_sunday(tl):
    tl["week_start"] = tl["week_start"] + pd.Timedelta(days=1)
    assert "weeks_start_on_sunday" in failed(validate_timeline(tl, "x"))


def test_timeline_wrong_term_set(tl):
    assert "schema_terms_match_group" in failed(validate_timeline(tl[tl["term"] != "شراء ورد"], "x"))


def test_timeline_scale_mixing(tl):
    tl.loc[tl.index[:5], "scale_id"] = "other"
    assert "single_scale_id" in failed(validate_timeline(tl, "x"))


def test_timeline_peak_not_100(tl):
    tl["value"] = tl["value"].clip(upper=90)
    assert "group_peak_is_100" in failed(validate_timeline(tl, "x"))


def test_censored_value_treated_as_number_is_caught():
    df = pd.read_parquet(P / "timeline_groupA_long.parquet")
    i = df.index[df["is_censored"]][0]
    df.loc[i, "value"] = 0.5
    assert "censored_not_treated_as_exact" in failed(validate_timeline(df, "A"))


def test_missing_values_are_a_warning_not_an_error(tl):
    tl.loc[tl.index[7], ["value", "is_missing"]] = [float("nan"), True]
    checks = validate_timeline(tl, "x")
    assert "missing_values" in failed(checks, "warning") and "missing_values" not in failed(checks)


def test_geo_missing_region(geo_idx):
    assert "regional_coverage_13" in failed(validate_geomap(geo_idx[geo_idx["region_iso"] != "SA-01"], "x"))


def test_geo_duplicate_region(geo_idx):
    assert "no_duplicate_region_term" in failed(validate_geomap(pd.concat([geo_idx, geo_idx.iloc[[0]]]), "x"))


def test_geo_out_of_range(geo_idx):
    geo_idx.loc[geo_idx.index[0], "value"] = 140.0
    assert "values_in_0_100" in failed(validate_geomap(geo_idx, "x"))


def test_geo_shares_not_summing_to_100(geo_share):
    geo_share["value"] = geo_share["value"] * 0.5
    assert "shares_sum_to_about_100" in failed(validate_geomap(geo_share, "x"))


def test_geo_missing_is_a_warning_and_never_zero(geo_idx):
    checks = validate_geomap(geo_idx, "x")
    assert "regional_coverage_13" not in failed(checks)
    miss = pd.read_parquet(P / "region_single_term_index.parquet").query("is_missing")
    assert miss["value"].isna().all()  # blank is NaN, never 0


# ---------------- manifest consistency ----------------
def test_manifest_matches_incoming_raw_and_hashes():
    man = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    names = {e["file_name"] for e in man}
    assert names == {p.name for p in C.INCOMING_DIR.glob("*.csv")} == {p.name for p in C.RAW_DIR.glob("*.csv")}
    for e in man:
        assert sha256_file(C.ROOT / e["raw_path"]) == e["sha256"] == sha256_file(C.INCOMING_DIR / e["file_name"])


def test_manifest_scale_ids_unique_and_complete():
    man = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    ids = [e["scale_id"] for e in man]
    assert len(ids) == len(set(ids)) == 9
    assert all(e["normalization"] and e["retrieved_date"] and e["terms"] for e in man)
    groups = {e["comparison_group"] for e in man}
    assert {C.GROUP_A, C.GROUP_B} <= groups


def test_fingerprint_is_order_independent_and_sensitive():
    a = [{"file_name": "a", "sha256": "1"}, {"file_name": "b", "sha256": "2"}]
    assert fingerprint(a) == fingerprint(a[::-1])
    assert fingerprint(a) != fingerprint([{"file_name": "a", "sha256": "1"}, {"file_name": "b", "sha256": "3"}])


def test_provenance_input_fingerprint_matches_manifest():
    man = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    for f in (P / "_provenance.json", P / "phase_a" / "_provenance.json"):
        assert json.loads(f.read_text(encoding="utf-8"))["input_fingerprint"] == fingerprint(man)
