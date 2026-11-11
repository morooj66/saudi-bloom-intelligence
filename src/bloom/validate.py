"""Automated data-quality checks. Each check returns a dict; none mutate data.

level: 'error' failures must be fixed; 'warning' are documented known issues; 'info' are facts.
"""
from __future__ import annotations

import pandas as pd

from . import config as C
from .ingest import inspect_file
from .regions import ISO_CODES
from .trends_io import sha256_file

EXPECTED_TERMS = {C.GROUP_A: set(C.ALL_TERMS), C.GROUP_B: set(C.COMMERCIAL_TERMS), C.GROUP_B4_SHARE: set(C.COMMERCIAL_TERMS)}


def chk(name: str, ok: bool, detail: str, level: str = "error", scope: str = "") -> dict:
    return {"name": name, "scope": scope, "passed": bool(ok), "level": "info" if ok else level, "detail": detail}


def validate_timeline(df: pd.DataFrame, scope: str) -> list[dict]:
    out = []
    group = df["comparison_group"].iloc[0]
    terms = set(df["term"])
    out.append(chk("schema_terms_match_group", terms == EXPECTED_TERMS[group], f"terms={sorted(terms)}", scope=scope))
    out.append(chk("single_scale_id", df["scale_id"].nunique() == 1, f"scale_id={df['scale_id'].unique().tolist()}", scope=scope))
    out.append(chk("no_group_mixing", df["comparison_group"].nunique() == 1, "one comparison group per frame", scope=scope))
    dup = df.duplicated(["term", "week_start"]).sum()
    out.append(chk("no_duplicate_dates", dup == 0, f"duplicate (term,week) rows={dup}", scope=scope))
    out.append(chk("valid_dates", df["week_start"].notna().all(), "all dates parsed", scope=scope))
    not_sun = (df["week_start"].dt.weekday != C.WEEK_START_WEEKDAY).sum()
    out.append(chk("weeks_start_on_sunday", not_sun == 0, f"non-Sunday rows={not_sun}", scope=scope))
    for t, g in df.groupby("term"):
        d = g.sort_values("week_start")["week_start"].diff().dropna().dt.days
        out.append(chk("frequency_constant_7d", (d == 7).all(), f"{t}: gap set={sorted(d.unique().tolist())}", scope=scope))
    n_by_term = df.groupby("term").size()
    out.append(chk("equal_length_per_term", n_by_term.nunique() == 1, f"n per term={n_by_term.unique().tolist()}", scope=scope))
    ex = df.loc[~df["is_censored"] & ~df["is_missing"], "value"]
    out.append(chk("values_in_0_100", ex.between(0, 100).all(), f"min={ex.min()}, max={ex.max()}", scope=scope))
    out.append(chk("group_peak_is_100", ex.max() == 100, f"max exact value={ex.max()} (Trends rescales peak to 100)", scope=scope))
    out.append(chk("integers_only", (ex % 1 == 0).all(), "Trends publishes integers", scope=scope))
    mi = int(df["is_missing"].sum())
    out.append(chk("missing_values", mi == 0, f"blank cells={mi}", level="warning", scope=scope))
    ce = df.groupby("term")["is_censored"].sum()
    out.append({"name": "censored_values", "scope": scope, "passed": True, "level": "info", "detail": f"censored ('<1') cells by term: {ce[ce > 0].to_dict() or 'none'}"})
    bad = df[df["is_censored"] & (df["value"].notna() | (df["censor_upper_bound"] != C.CENSORED_UPPER_BOUND))]
    out.append(chk("censored_not_treated_as_exact", bad.empty, f"censored rows with a numeric value or unexpected bound={len(bad)}", scope=scope))
    z = df.groupby("term")["is_reported_zero"].mean()
    for t, s in z.items():
        out.append({"name": "reported_zero_share", "scope": f"{scope}:{t}", "passed": s <= 0.10, "level": "warning" if s > 0.10 else "info", "detail": f"{s:.1%} of weeks reported 0"})
    return out


def validate_geomap(df: pd.DataFrame, scope: str) -> list[dict]:
    out = []
    regions = set(df["region_iso"])
    out.append(chk("regional_coverage_13", regions == set(ISO_CODES), f"{len(regions)} regions; missing={sorted(set(ISO_CODES) - regions)}", scope=scope))
    dup = df.duplicated(["region_iso", "term"]).sum()
    out.append(chk("no_duplicate_region_term", dup == 0, f"duplicates={dup}", scope=scope))
    out.append(chk("single_scale_id", df["scale_id"].nunique() == 1, df["scale_id"].iloc[0], scope=scope))
    ex = df.loc[~df["is_censored"] & ~df["is_missing"], "value"]
    out.append(chk("values_in_0_100", ex.between(0, 100).all(), f"min={ex.min()}, max={ex.max()}", scope=scope))
    metric = df["metric"].iloc[0]
    if metric == "share_pct_of_compared_terms":
        # per region the shares of the compared terms should sum to ~100 (rounding / censoring tolerance)
        lo = df.groupby("region_iso")["value"].sum(min_count=1)
        hi = df.assign(v=df["value"].fillna(df["censor_upper_bound"]).fillna(0)).groupby("region_iso")["v"].sum()
        ok = ((lo <= 103) & (hi >= 97)).all()
        out.append(chk("shares_sum_to_about_100", ok, f"sum of exact shares per region in [{lo.min():.0f},{lo.max():.0f}]; with censored upper bounds [{hi.min():.0f},{hi.max():.0f}]", scope=scope))
    else:
        out.append(chk("peak_region_is_100", ex.max() == 100, f"max={ex.max()}", scope=scope))
    if df["comparison_group"].iloc[0] == C.GROUP_B4_SHARE:
        out.append(chk("b4_terms_are_the_four_commercial_terms", set(df["term"]) == set(C.COMMERCIAL_TERMS), f"terms={sorted(set(df['term']))}", scope=scope))
        out.append(chk("b4_metric_is_share", metric == "share_pct_of_compared_terms", f"metric={metric}", scope=scope))
        pub = df.groupby("region_iso")["value"].sum(min_count=1)
        out.append({"name": "b4_unresolved_remainder", "scope": scope, "passed": True, "level": "info",
                    "detail": f"published shares per region sum to {pub.min():.0f}–{pub.max():.0f}; the remainder (if any) is censored/blank and is never assigned to a term"})
    miss = df[df["is_missing"]]
    out.append({"name": "missing_regions_no_data", "scope": scope, "passed": miss.empty, "level": "warning" if len(miss) else "info",
                "detail": f"{len(miss)} blank region cells (Trends had no data): {miss['region_en'].tolist()}"})
    cen = df[df["is_censored"]]
    out.append({"name": "censored_values", "scope": scope, "passed": True, "level": "info", "detail": f"{len(cen)} censored cells: {cen['region_en'].tolist()}"})
    return out


def validate_cross(timelines: dict[str, pd.DataFrame], geos: dict[str, pd.DataFrame], manifest: list[dict],
                   root=C.ROOT, incoming=C.INCOMING_DIR) -> list[dict]:
    out = []
    # frequency consistency across groups
    idx = {g: set(df["week_start"]) for g, df in timelines.items()}
    out.append(chk("same_week_grid_across_groups", len({frozenset(v) for v in idx.values()}) == 1, "group A and B share the same weekly grid"))
    # raw preservation
    for e in manifest:
        raw = root / e["raw_path"]
        inc = incoming / e["file_name"]
        ok = raw.exists() and sha256_file(raw) == e["sha256"] and (not inc.exists() or sha256_file(inc) == e["sha256"])
        out.append(chk("raw_checksum_unchanged", ok, e["file_name"], scope=e["file_name"]))
    # window sanity: day-first interpretation must contain the weekly range
    for name, g in geos.items():
        ws, we = g["window_start"].iloc[0], g["window_end"].iloc[0]
        for gname, t in timelines.items():
            first, last = t["week_start"].min(), t["week_start"].max()
            ok = (ws - pd.Timedelta(days=6) <= first <= ws) and (we - pd.Timedelta(days=6) <= last <= we)
            out.append(chk("geomap_window_matches_timeline", ok, f"window {ws.date()}..{we.date()} (day-first) vs weeks {first.date()}..{last.date()}", scope=f"{name}~{gname}"))
    edge_first = timelines[C.GROUP_A]["week_start"].min()
    out.append({"name": "edge_partial_weeks", "scope": "timelines", "passed": False, "level": "warning",
                "detail": f"First bucket {edge_first.date()} starts before the query window (2021-11-10) and the last bucket is "
                          f"cut at the retrieval date; both are partial weeks and are flagged is_edge_partial_week, excluded from profiling."})
    groups = {e["comparison_group"] for e in manifest}
    out.append(chk("groups_present", {C.GROUP_A, C.GROUP_B, C.GROUP_B4_SHARE} <= groups, f"groups={sorted(groups)}"))
    return out


def profile_series(df: pd.DataFrame, window_start: pd.Timestamp, window_end: pd.Timestamp) -> pd.DataFrame:
    """Descriptive suitability stats per term (edge partial weeks excluded). No modelling."""
    from .transform import edge_partial_flags

    rows = []
    for t, g in df.groupby("term"):
        g = g.sort_values("week_start")
        g = g[~edge_partial_flags(g["week_start"], window_start, window_end)]
        s = g["value"]
        n = len(g)
        ex = s.dropna()
        acf = lambda k: float(ex.autocorr(k)) if len(ex) > k + 2 else float("nan")
        # year-over-year: correlation of each week with the same week 52 steps earlier
        yoy = float(pd.Series(s.values).corr(pd.Series(s.values).shift(52))) if n > 60 else float("nan")
        rows.append({
            "comparison_group": g["comparison_group"].iloc[0], "term": t, "n_weeks": n,
            "censored_n": int(g["is_censored"].sum()), "reported_zero_n": int(g["is_reported_zero"].sum()),
            "reported_zero_share": float(g["is_reported_zero"].mean()), "mean": float(ex.mean()), "median": float(ex.median()),
            "std": float(ex.std()), "max": float(ex.max()), "p5": float(ex.quantile(.05)), "p95": float(ex.quantile(.95)),
            "acf_lag1": acf(1), "acf_lag52": acf(52), "yoy_corr_52": yoy,
        })
    p = pd.DataFrame(rows)
    p["usable_resolution"] = p["median"] >= 10  # integer rounding is <=5% of the typical level
    p["low_zero_share"] = p["reported_zero_share"] <= 0.10
    p["low_censoring"] = (p["censored_n"] / p["n_weeks"]) <= 0.05
    p["candidate_for_forecasting"] = p["usable_resolution"] & p["low_zero_share"] & p["low_censoring"]
    return p.sort_values(["candidate_for_forecasting", "yoy_corr_52"], ascending=False).reset_index(drop=True)
