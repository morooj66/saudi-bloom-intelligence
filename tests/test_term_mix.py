"""Regional commercial-term mix (geoMap (6).csv): ingestion, interpretation, scale isolation, chart honesty, integrity, dashboard."""
import hashlib
import json
import shutil

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from bloom import config as C
from bloom.ingest import assign_group
from bloom.integrity import IntegrityReport, _check_scale_isolation, verify
from bloom.overview import (AVAILABLE, CENSORED, NO_DATA, MIX_TERM_ORDER, term_mix_cell_counts, term_mix_order, term_mix_regions, term_mix_table,
                            term_mix_text_alternative)
from bloom.regions import ISO_CODES
from bloom.schema import ScaleMixError, assert_same_scale
from conftest import ROOT, run_cli

P = C.PROCESSED_DIR
FILE = "geoMap (6).csv"
ORIGINAL_SHA256 = "c5e37404361998eb97b470ba6222d3d321b1769dbcf008fc82bd14f4ce536820"
EIGHT_ORIGINALS = {  # SHA-256 of the eight raw exports as ingested before this feature (must never change)
    'geoMap (1).csv': "0cf310c41fdc59e28ff0bb69bafd788cb4a187a12c3295907436d9a088bd55b3",
    'geoMap (2).csv': "f7f04f4d5ae86ab43a4ccca75c83e4f3e09d0732a83bc869ec88405cfc83b97e",
    'geoMap (3).csv': "ad1a5c25a5030b91b7640ccdb94e0fd080dd9179b3de645aeb2883da119f1b52",
    'geoMap (4).csv': "1eacc4a4734dc244f80d4273ebe0a5d5b77df63078c10a8526494b448eb535e3",
    'geoMap (5).csv': "d95c998c32eb481f16a7ce949a36a4d80febbcb1ff8be7fec095a0e6892b68fb",
    'geoMap.csv': "e580956d52b847727c7546b1d75de9e2cad546373f7a2a0e25251893900a0e13",
    'multiTimeline (1).csv': "97cd39e1837cfe9dc79be5129c853f756e0fc4da879cc18a75bfc1948b1cecb9",
    'multiTimeline.csv': "3ddcab2e3082d7386145827eec8cc929cd36f7d9df147d41aee5fd4ff29f716c",
}
pytestmark = pytest.mark.skipif(not (P / "region_groupB4_share.parquet").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


@pytest.fixture(scope="module")
def mix():
    return pd.read_parquet(P / "region_groupB4_share.parquet")


@pytest.fixture(scope="module")
def idx():
    return pd.read_parquet(P / "phase_a" / "regional_index_by_term.parquet")


@pytest.fixture(scope="module")
def share_a():
    return pd.read_parquet(P / "region_groupA_share.parquet")


# ------------------------------------------------------------------------------------------------ raw data, manifest, group
def test_original_file_hash_is_pinned_in_every_copy():
    man = {e["file_name"]: e for e in json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))}
    assert man[FILE]["sha256"] == ORIGINAL_SHA256
    for folder in (C.INCOMING_DIR, C.RAW_DIR):
        assert hashlib.sha256((folder / FILE).read_bytes()).hexdigest() == ORIGINAL_SHA256


def test_the_eight_original_raw_files_are_byte_identical_to_before():
    man = {e["file_name"]: e for e in json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))}
    for name, digest in EIGHT_ORIGINALS.items():
        assert man[name]["sha256"] == digest
        assert hashlib.sha256((C.RAW_DIR / name).read_bytes()).hexdigest() == digest
        assert hashlib.sha256((C.INCOMING_DIR / name).read_bytes()).hexdigest() == digest
    assert len(EIGHT_ORIGINALS) == 8


def test_manifest_is_append_only_nine_entries_and_new_one_is_last_group_b4():
    man = json.loads(C.MANIFEST_JSON.read_text(encoding="utf-8"))
    assert len(man) == 9 and len({e["scale_id"] for e in man}) == 9
    e = [x for x in man if x["file_name"] == FILE][0]
    assert e["comparison_group"] == C.GROUP_B4_SHARE and e["scale_id"] == f"{C.GROUP_B4_SHARE}|geomap|{FILE}"
    assert e["kind"] == "geomap" and e["n_data_rows"] == 13 and (e["window_start"], e["window_end"]) == ("2021-11-10", "2026-11-10")
    assert sum(1 for x in man if x["comparison_group"] == C.GROUP_B) == 1  # the weekly four-term timeline keeps group B


def test_assign_group_separates_the_weekly_index_from_the_regional_share():
    assert assign_group("timeline", list(C.COMMERCIAL_TERMS)) == C.GROUP_B
    assert assign_group("geomap", list(C.COMMERCIAL_TERMS)) == C.GROUP_B4_SHARE
    assert assign_group("geomap", list(C.ALL_TERMS)) == C.GROUP_A


def test_removing_the_ninth_raw_file_from_incoming_fails_the_append_only_pipeline(fresh_copy):
    (fresh_copy / "incoming_data" / FILE).unlink()
    r = run_cli("bloom.pipeline", fresh_copy)
    assert r.returncode == 2 and "append-only" in r.stderr


def test_a_second_four_term_regional_export_is_rejected(project):
    shutil.copy2(project / "incoming_data" / FILE, project / "incoming_data" / "geoMap (9).csv")
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 2 and "comparison group" in r.stderr


# ------------------------------------------------------------------------------------------------ the real data
def test_real_file_has_13_regions_and_the_expected_cell_counts(mix):
    c = term_mix_cell_counts(mix)
    assert c == {"cells": 52, "numeric": 39, "censored": 8, "missing": 5, "regions": 13, "terms": 4}
    assert set(mix["region_iso"]) == set(ISO_CODES) and set(mix["term"]) == set(C.COMMERCIAL_TERMS)
    assert (mix["metric"] == "share_pct_of_compared_terms").all()


def test_every_censored_and_blank_cell_is_in_buy_flowers_and_none_is_a_number(mix):
    nonnum = mix[mix["is_censored"] | mix["is_missing"]]
    assert set(nonnum["term"]) == {"شراء ورد"} and len(nonnum) == 13
    assert nonnum["value"].isna().all()                                   # never zero, never filled
    assert (mix.loc[mix["is_censored"], "censor_upper_bound"] == 1.0).all()
    assert mix.loc[~mix["is_censored"] & ~mix["is_missing"], "value"].between(1, 100).all()   # no fabricated zeros
    assert not (mix["value"] == 0).any()


def test_published_shares_total_100_in_every_region_and_the_remainder_is_zero(mix):
    s = term_mix_regions(mix)
    assert np.allclose(s["published_sum"], 100.0) and (s["unspecified_remainder"] == 0).all() and (s["rounding_excess"] == 0).all()
    assert (s["n_numeric"] == 3).all()


def test_known_values_from_the_original_export(mix):
    v = mix.set_index(["region_en", "term"])["value"]
    assert (v["Riyadh", "محل ورد"], v["Riyadh", "توصيل ورد"], v["Riyadh", "بوكيه ورد"]) == (65, 15, 20)
    assert (v["Jazan", "محل ورد"], v["Asir", "بوكيه ورد"]) == (81, 21)
    t = term_mix_table(mix).set_index(["region_en", "term"])["status"]
    assert t["Jazan", "شراء ورد"] == CENSORED and t["Najran", "شراء ورد"] == NO_DATA and t["Riyadh", "محل ورد"] == AVAILABLE


# ------------------------------------------------------------------------------------------------ interpretation helpers
def _synthetic(values):
    """Four-term frame for one scale where `values` maps region_iso -> (shop, bouquet, delivery, buy) as number | 'c' | None."""
    rows = []
    for i, iso in enumerate(ISO_CODES):
        vals = values.get(iso, (50, 30, 20, "c"))
        for term, v in zip(("محل ورد", "بوكيه ورد", "توصيل ورد", "شراء ورد"), vals):
            rows.append({"region_iso": iso, "region_en": f"R{i}", "region_ar": f"م{i}", "term": term, "value": np.nan if v in ("c", None) else float(v),
                         "is_censored": v == "c", "is_missing": v is None, "censor_upper_bound": 1.0 if v == "c" else np.nan,
                         "comparison_group": C.GROUP_B4_SHARE, "scale_id": "S", "metric": "share_pct_of_compared_terms"})
    return pd.DataFrame(rows)


def test_unresolved_remainder_is_unspecified_and_never_assigned_to_a_term():
    d = _synthetic({ISO_CODES[0]: (60, 20, 10, None)})            # published total 90
    s = term_mix_regions(d).set_index("region_iso").loc[ISO_CODES[0]]
    assert s["published_sum"] == 90 and s["unspecified_remainder"] == 10
    t = term_mix_table(d)
    assert t[(t["region_iso"] == ISO_CODES[0]) & (t["term"] == "شراء ورد")]["value"].isna().all()   # still not a number
    assert t[t["region_iso"] == ISO_CODES[0]]["value"].sum() == 90                                   # nothing redistributed
    assert "unspecified remainder 10%" in term_mix_text_alternative(d)


def test_rounding_excess_is_recorded_not_hidden_or_negative():
    s = term_mix_regions(_synthetic({ISO_CODES[0]: (60, 30, 11, "c")})).set_index("region_iso").loc[ISO_CODES[0]]
    assert s["published_sum"] == 101 and s["unspecified_remainder"] == 0 and s["rounding_excess"] == 1


def test_text_alternative_distinguishes_censored_from_missing_and_states_the_limits(mix):
    a = term_mix_text_alternative(mix)
    assert "Riyadh: flower shop 65%, flower bouquet 20%, flower delivery 15%, buy flowers censored (below 1%)" in a
    assert "Najran: flower shop 77%, flower bouquet 19%, flower delivery 4%, buy flowers no data reported" in a
    assert a.count("censored (below 1%)") == 8 and a.count("no data reported") == 5
    assert "not volume or sales" in a


def test_order_is_neutral_by_default_and_never_places_missing_first(mix):
    assert term_mix_order(mix) == term_mix_table(mix).drop_duplicates("region_iso").sort_values("region_en")["region_iso"].tolist()
    by_shop = term_mix_order(mix, "محل ورد")
    vals = mix[mix["term"] == "محل ورد"].set_index("region_iso")["value"].reindex(by_shop)
    assert vals.is_monotonic_decreasing and len(by_shop) == 13


# ------------------------------------------------------------------------------------------------ scale isolation
def test_mixing_with_the_index_or_the_five_term_shares_raises_scale_mix_error(mix, idx, share_a):
    for other in (idx, share_a):
        with pytest.raises(ScaleMixError):
            assert_same_scale(mix, other)
        with pytest.raises(ScaleMixError):
            term_mix_table(pd.concat([mix, other], ignore_index=True))
    with pytest.raises(ScaleMixError):                           # a single-scale frame of the WRONG measure is refused too
        term_mix_table(share_a)


def test_new_dataset_has_its_own_scale_id_shared_with_no_other_processed_frame(mix, idx, share_a):
    ids = {mix["scale_id"].iloc[0]}
    assert ids.isdisjoint(set(idx["scale_id"])) and ids.isdisjoint(set(share_a["scale_id"]))
    assert not (set(idx["source_file"]) | set(share_a["source_file"])) & {FILE}
    assert set(mix["source_file"]) == {FILE}


def test_region_index_dataset_still_has_exactly_five_single_term_exports_and_jazan_is_first(idx):
    assert idx["term"].nunique() == 5 and len(idx) == 65
    top = idx[(idx["term"] == "محل ورد") & ~idx["is_missing"]].sort_values("value", ascending=False).iloc[0]
    assert top["region_en"] == "Jazan" and top["value"] == 100


# ------------------------------------------------------------------------------------------------ integrity
def test_integrity_verifies_and_includes_the_new_checks(built_project):
    rep = verify(built_project)
    assert rep.ok, rep.failures
    assert any(c["name"] == "four-term regional shares keep their own scale" and c["ok"] for c in rep.checks)
    assert any("9 raw files verified" in c["detail"] for c in rep.checks)


def test_tampered_new_raw_file_is_detected(fresh_copy):
    f = fresh_copy / "data/raw" / FILE
    f.write_bytes(f.read_bytes() + b" ")
    assert "raw file hashes match manifest" in {c["name"] for c in verify(fresh_copy).failures}


def test_tampered_new_processed_dataset_is_detected(fresh_copy):
    f = fresh_copy / "data/processed/region_groupB4_share.parquet"
    f.write_bytes(f.read_bytes() + b"\0")
    assert "processed: output hashes match provenance" in {c["name"] for c in verify(fresh_copy).failures}


def test_missing_new_dataset_is_detected(fresh_copy):
    (fresh_copy / "data/processed/region_groupB4_share.parquet").unlink()
    assert not verify(fresh_copy).ok


def test_scale_isolation_check_fails_if_the_new_scale_is_shared(fresh_copy):
    proc = fresh_copy / "data/processed"
    b4 = pd.read_parquet(proc / "region_groupB4_share.parquet")
    a = pd.read_parquet(proc / "region_groupA_share.parquet")
    a["scale_id"] = b4["scale_id"].iloc[0]
    a.to_parquet(proc / "region_groupA_share.parquet", index=False)
    rep = IntegrityReport()
    from types import SimpleNamespace
    _check_scale_isolation(rep, SimpleNamespace(processed=proc), json.loads((fresh_copy / "data/manifest.json").read_text(encoding="utf-8")))
    assert not rep.ok and "shared with another dataset" in rep.checks[0]["detail"]


def test_forecast_gate_and_withholding_are_unchanged(built_project):
    st = json.loads((built_project / "data/processed/phase_a/forecast_status.json").read_text(encoding="utf-8"))["forecast"]
    assert st["forecast_published"] is False and st["gate"]["passed"] is False
    assert not (built_project / "data/processed/phase_a/forecast_national.parquet").exists()
    assert round(st["gate"]["relative_mae_improvement"], 4) == 0.0533
    assert [round(x, 2) for x in st["gate"]["mean_abs_error_diff_ci95"]] == [-0.89, 1.9]


# ------------------------------------------------------------------------------------------------ chart honesty
def _fig(mix):
    import sys
    sys.path[:0] = [str(ROOT / "app")]
    import components as K
    return K.term_mix_bar(mix, term_mix_order(mix))


def test_chart_draws_only_published_numbers_and_marks_the_rest_without_zeros(mix):
    fig = _fig(mix)
    bars = [t for t in fig.data if t.type == "bar"]
    assert sum(len(b.x) for b in bars) == 39                                             # one segment per numeric cell, nothing else
    assert all(v > 0 for b in bars for v in b.x)                                         # no zero-width segments
    assert not any("شراء ورد" in (b.name or "") for b in bars)                            # buy flowers is never drawn as a bar
    assert not any("Unspecified" in (b.name or "") for b in bars)                         # remainder is 0 here -> no phantom segment
    markers = {t.name: t for t in fig.data if t.type == "scatter"}
    cens = [n for n in markers if "censored" in n][0]; miss = [n for n in markers if "no data" in n][0]
    assert len(markers[cens].x) == 8 and len(markers[miss].x) == 5                       # censored and missing are distinguishable, counts match the file
    assert markers[cens].marker.symbol != markers[miss].marker.symbol
    assert set(markers[cens].text) == {"<1%"} and set(markers[miss].text) == {"no data"}
    assert fig.layout.barmode == "stack" and list(fig.layout.xaxis.range)[0] == 0 and fig.layout.xaxis.fixedrange


def test_chart_shows_a_hatched_unspecified_segment_when_shares_total_less_than_100():
    import sys
    sys.path[:0] = [str(ROOT / "app")]
    import components as K
    d = _synthetic({ISO_CODES[0]: (60, 20, 10, None)})
    fig = K.term_mix_bar(d, term_mix_order(d))
    rem = [t for t in fig.data if t.type == "bar" and "Unspecified" in (t.name or "")]
    assert len(rem) == 1 and list(rem[0].x) == [10.0] and rem[0].marker.pattern.shape == "/"
    assert "not assigned to any term" in rem[0].name


def test_hover_text_states_it_is_not_volume_or_sales(mix):
    fig = _fig(mix)
    assert all("not search volume or sales" in t.hovertemplate for t in fig.data if t.type == "bar")


# ------------------------------------------------------------------------------------------------ dashboard
def _regions_view(root, monkeypatch):
    monkeypatch.setenv("BLOOM_ROOT", str(root))
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=90).run()
    at.radio(key="section").set_value("regions").run()
    return at


def _mix_view(root, monkeypatch):
    monkeypatch.setenv("BLOOM_ROOT", str(root))
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=90).run()
    at.radio(key="section").set_value("mix").run()
    return at


def _text(at):
    return " ".join([m.value for m in at.markdown] + [m.value for m in at.info])


def test_term_mix_view_renders_with_caveats_text_alternative_and_no_exceptions(built_project, monkeypatch):
    at = _mix_view(built_project, monkeypatch)
    t = _text(at)
    assert not at.exception and len(at.get("plotly_chart")) == 1
    for needle in ("Commercial-term mix across the 13 regions", "relative composition", "not</b> search volume, sales, revenue, market size or consumer demand",
                   "never combined with the regional interest index", "Text alternative", "39 are numeric", "8 are censored", "5 are blank",
                   "never drawn as zero", "cannot be drawn as a bar", "not established"):
        assert needle in t, needle
    assert "Riyadh: flower shop 65%" in t


def test_other_regional_views_and_homepage_are_unchanged(built_project, monkeypatch):
    at = _regions_view(built_project, monkeypatch)
    assert not at.exception and len(at.get("plotly_chart")) >= 2                     # map + ranked bar of the default index view
    assert "Jazan" in _text(at)
    at.radio(key="section").set_value("overview").run()
    t = _text(at)
    assert not at.exception and "Highest relative search interest for" in t and "Jazan" in t and "13 of 13" in t
    at.radio(key="section").set_value("forecast").run()
    assert not at.exception and len(at.get("plotly_chart")) == 0


def test_data_engineering_lists_the_ninth_file_and_its_own_group(built_project, monkeypatch):
    at = _regions_view(built_project, monkeypatch)
    at.radio(key="section").set_value("data").run()
    assert not at.exception
    blob = " ".join(d.value.to_csv() for d in at.dataframe)
    assert "geoMap (6).csv" in blob and "B4 · 4-term regional shares" in blob and "Regional shares · four commercial terms" in blob
