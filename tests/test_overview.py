"""Executive-overview logic: every value is computed from the frames passed in (nothing hard-coded)."""
import pandas as pd
import pytest

from bloom import config as C
from bloom.overview import (AVAILABLE, CENSORED, NO_DATA, eid_weeks, friendly_scale, history_coverage, month_extremes, regional_rank_table, regions_covered,
                            strongest_seasonal, toggle_from_map, top_region, yoy_frame, map_text_alternative, ranking_explainer, region_detail,
                            select_from_map, series_text_alternative, spread_of_available, trend_vs_prior_year)
from bloom.regions import ISO_CODES
from bloom.schema import ScaleMixError

P = C.PROCESSED_DIR
pytestmark = pytest.mark.skipif(not (P / "phase_a" / "forecast_status.json").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


@pytest.fixture(scope="module")
def idx():
    return pd.read_parquet(P / "phase_a" / "regional_index_by_term.parquet")


@pytest.fixture(scope="module")
def share():
    return pd.read_parquet(P / "phase_a" / "regional_share_groupA.parquet")


def test_top_region_equals_plain_recomputation(idx):
    for term, g in idx.groupby("term"):
        ex = g[~g["is_missing"] & ~g["is_censored"]]
        r = top_region(idx, term)
        assert r["value"] == ex["value"].max() and r["region_en"] in set(ex.loc[ex["value"] == ex["value"].max(), "region_en"])
        assert r["n_with_data"] == len(ex)


def test_top_region_is_not_hard_coded(idx):
    d = idx[idx["term"] == "محل ورد"].copy()
    d.loc[d["region_iso"] == "SA-01", "value"] = 100.0          # Riyadh now ties with Jazan
    d.loc[d["region_iso"] == "SA-09", "value"] = 90.0           # Jazan drops
    r = top_region(d, "محل ورد")
    assert r["iso"] == "SA-01" and r["value"] == 100.0 and r["runner_up_en"] == "Northern Borders" and r["runner_up_value"] == 96.0  # next highest in the (mutated) data
    d2 = d.copy(); d2.loc[d2["region_iso"] == "SA-09", "value"] = 100.0
    assert set(top_region(d2, "محل ورد")["ties"]) == {"Riyadh", "Jazan"}  # ties are reported, not hidden


def test_top_region_ignores_missing_and_censored(idx):
    d = idx[idx["term"] == "شراء ورد"]
    r = top_region(idx, "شراء ورد")
    assert r["n_with_data"] == 8 and r["iso"] not in set(d.loc[d["is_missing"], "region_iso"])


def test_regions_covered(idx):
    rc = regions_covered(idx)
    assert rc["n_regions"] == 13 and rc["n_terms"] == 5 and rc["n_regions_all_terms"] == 13 - 5 and rc["missing_cells"] == 5


def test_history_coverage_excludes_edge_weeks():
    long_b = pd.read_parquet(P / "timeline_groupB_long.parquet")
    hc = history_coverage(long_b)
    assert hc["n_weeks"] == long_b["week_start"].nunique() - 2 == 260 and hc["n_edge_excluded"] == 2
    assert hc["first"] > long_b["week_start"].min() and hc["last"] < long_b["week_start"].max()


def test_strongest_seasonal_is_the_max_median_lift():
    es = pd.read_parquet(P / "phase_a" / "event_lift_summary.parquet")
    r = strongest_seasonal(es, "محل ورد")
    sub = es[es["term"] == "محل ورد"]
    assert r["median_lift"] == sub["median_lift"].max() and r["event"] == sub.loc[sub["median_lift"].idxmax(), "event"]
    es2 = es.copy(); es2.loc[(es2["term"] == "محل ورد") & (es2["event"] == "valentines_day"), "median_lift"] = 9.0
    assert strongest_seasonal(es2, "محل ورد")["event"] == "valentines_day"  # follows the data


def test_rank_table_never_ranks_missing_or_censored(idx, share):
    for frame in (idx, share):
        for _, d in frame.groupby("term"):
            t = regional_rank_table(d)
            assert len(t) == 13 and set(t["region_iso"]) == set(ISO_CODES)
            na = t[t["status"] != AVAILABLE]
            assert na["rank"].isna().all() and na["gap_to_peak"].isna().all()
            a = t[t["status"] == AVAILABLE]
            if len(a):  # (group-A «شراء ورد» has no available value at all: nothing to rank, and that must not error)
                assert a["rank"].min() == 1 and (a["gap_to_peak"] >= 0).all()
            else:
                assert t["rank"].isna().all()


def test_rank_table_refuses_mixed_exports(idx):
    with pytest.raises(ScaleMixError):
        regional_rank_table(idx)


def test_toggle_from_map():
    assert toggle_from_map([], ["SA-01"]) == ["SA-01"]
    assert toggle_from_map(["SA-01"], ["SA-01"]) == []                       # click again removes
    assert toggle_from_map(["SA-01"], ["SA-09", "SA-10"]) == ["SA-01", "SA-09", "SA-10"]  # shift-click adds several
    assert toggle_from_map(["SA-01"], []) == ["SA-01"]                       # empty event: unchanged
    assert toggle_from_map([], ["not-a-region"]) == []                       # unknown location ignored
    c = ["SA-02"]; toggle_from_map(c, ["SA-03"]); assert c == ["SA-02"]     # input not mutated


def test_yoy_frame_matches_source_values():
    a = pd.read_parquet(P / "timeline_groupB_analytic_weekly.parquet")
    y = yoy_frame(a, "محل ورد")
    assert len(y) == 260
    src = a[~a["is_edge_partial_week"]].set_index("week_start")["value__محل ورد"]
    assert (y.set_index("week_start")["value"] == src).all() and y["woy"].between(1, 52).all()


def test_eid_weeks_cover_five_years_each_with_verification_flag():
    a = pd.read_parquet(P / "timeline_groupB_analytic_weekly.parquet")
    ev = pd.read_parquet(P / "calendar_events.parquet")
    e = eid_weeks(a, ev)
    assert (e["event"] == "eid_al_fitr").sum() == 5 and (e["event"] == "eid_al_adha").sum() == 5
    assert set(e["verification"]) == {"verified_announced", "computed_unverified"}


def test_month_extremes_follow_data():
    mp = pd.read_parquet(P / "phase_a" / "month_profile.parquet")
    m = month_extremes(mp, "محل ورد")
    sub = mp[mp["term"] == "محل ورد"].sort_values("index_vs_overall_mean", ascending=False)
    assert m["top"][0][0] == int(sub.iloc[0]["month"])


def test_friendly_scale_is_readable():
    assert friendly_scale("S_single:محل ورد|geomap|geoMap (4).csv") == "single-term regional index · محل ورد (geoMap (4).csv)"
    assert friendly_scale("B_commercial_4terms|timeline|multiTimeline (1).csv").startswith("group B · 4 commercial terms · weekly series")
    assert friendly_scale("A_general_5terms|geomap|geoMap.csv").startswith("group A · 5 terms · regional shares")


# ---------------------------------------------------------------------------- homepage refinement helpers
@pytest.fixture(scope="module")
def groupb():
    return pd.read_parquet(P / "timeline_groupB_long.parquet")


def test_trend_vs_prior_year_matches_plain_recomputation(groupb):
    r = trend_vs_prior_year(groupb, "محل ورد")
    d = groupb[(groupb["term"] == "محل ورد") & ~groupb["is_edge_partial_week"]].sort_values("week_start")["value"].to_numpy()
    assert r["recent_mean"] == pytest.approx(d[-52:].mean()) and r["prior_mean"] == pytest.approx(d[-104:-52].mean())
    assert r["pct_change"] == pytest.approx(d[-52:].mean() / d[-104:-52].mean() - 1)
    assert r["prior_end"] < r["recent_start"]                                   # windows never overlap
    assert trend_vs_prior_year(groupb.head(60), "محل ورد") is None             # too little history -> no number, not a guess


def test_ranking_explainer_keeps_the_two_exports_separate(idx, share):
    r = ranking_explainer(idx, share, "محل ورد")
    assert r["top"]["region_en"] == "Jazan"                                      # preserved ranking
    assert r["share_top"]["n"] <= 13 and not r["same_leader"]                   # the share export has a different leader
    assert r["share_top"]["regions"] == ["Northern Borders"]


def test_region_detail_states_status_without_inventing_values(idx):
    d = idx[idx["term"] == "شراء ورد"]
    t = regional_rank_table(d)
    for iso in ISO_CODES:
        r = region_detail(d, iso)
        if r["status"] == AVAILABLE:
            assert r["value"] is not None and 1 <= r["rank"] <= r["n_available"] and r["gap_to_peak"] >= 0
        else:
            assert r["value"] is None and r["rank"] is None and r["gap_to_peak"] is None
    assert (t["status"] == AVAILABLE).sum() == region_detail(d, ISO_CODES[0])["n_available"]


def test_select_from_map_last_valid_click_wins_and_empty_event_keeps_state():
    assert select_from_map("SA-01", ["SA-02", "SA-09"]) == "SA-09"
    assert select_from_map("SA-01", []) == "SA-01"
    assert select_from_map("SA-01", ["not-a-region"]) == "SA-01"
    assert select_from_map(None, []) is None


def test_spread_of_available_ignores_censored_and_missing(idx):
    d = idx[idx["term"] == "محل ورد"]
    lo, hi, n = spread_of_available(d)
    ex = d[~d["is_missing"] & ~d["is_censored"]]["value"]
    assert (lo, hi, n) == (ex.min(), ex.max(), len(ex))
    assert spread_of_available(d.iloc[0:0])[2] == 0


def test_text_alternatives_state_counts_and_never_zero_fill(idx, groupb):
    m = map_text_alternative(idx[idx["term"] == "شراء ورد"], "Map")
    assert "8 of 13 regions have values" in m and "no data" in m
    s = series_text_alternative(groupb[groupb["term"] == "محل ورد"], "Weekly")
    assert "weekly values from" in s and "highest in the week of" in s
    assert series_text_alternative(groupb.iloc[0:0], "Weekly") == "Weekly: no data."
