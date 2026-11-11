"""Phase A descriptive analysis: national seasonality, event lift, regional relative comparison.

All outputs describe Google Trends relative search interest. Nothing here estimates volume or sales.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from .calendar_features import EVENT_NAMES
from .schema import assert_same_scale


def national_series(analytic: pd.DataFrame, term: str, drop_edges: bool = True) -> pd.Series:
    d = analytic.copy()
    if drop_edges:
        d = d[~d["is_edge_partial_week"]]
    s = d.set_index("week_start")[f"value__{term}"].astype(float)
    s.name = term
    return s


def seasonal_profile(s: pd.Series) -> pd.DataFrame:
    """Mean/median index by calendar month and by Sunday-based week-of-year (descriptive)."""
    df = s.rename("value").to_frame()
    mid = df.index + pd.Timedelta(days=3)
    df["month"] = mid.month
    df["woy"] = np.minimum((mid.dayofyear - 1) // 7 + 1, 52)
    return df


def month_profile(s: pd.Series) -> pd.DataFrame:
    d = seasonal_profile(s)
    g = d.groupby("month")["value"].agg(["mean", "median", "std", "count"])
    g["index_vs_overall_mean"] = g["mean"] / s.mean()
    return g.reset_index()


def stl_strength(s: pd.Series, period: int = 52) -> dict:
    """Seasonal/trend strength from robust STL (Hyndman): 1 - Var(resid)/Var(x+resid)."""
    res = STL(s.reset_index(drop=True), period=period, robust=True).fit()
    fs = max(0.0, 1 - res.resid.var() / (res.seasonal + res.resid).var())
    ft = max(0.0, 1 - res.resid.var() / (res.trend + res.resid).var())
    return {"seasonal_strength": float(fs), "trend_strength": float(ft), "n": int(len(s)), "period": period,
            "caveat": "only ~5 annual cycles; strength is indicative, not a significance test"}


def event_lift(s: pd.Series, cal: pd.DataFrame, baseline_weeks: tuple[int, int] = (2, 4)) -> pd.DataFrame:
    """Per event-occurrence lift = value in event week / median of baseline weeks around it.

    Baseline weeks are |offset| in [2,4] on both sides (excluding the event week and its neighbours),
    and exclude other events' weeks. Uses only descriptive context (not a forecast feature).
    """
    c = cal.set_index("week_start").reindex(s.index)
    any_event = pd.Series(False, index=s.index)
    for n in EVENT_NAMES:
        any_event |= c[f"{n}_in_week"].astype(bool)
    rows = []
    idx = list(s.index)
    for n in EVENT_NAMES:
        for w in s.index[c[f"{n}_in_week"].astype(bool)]:
            i = idx.index(w)
            base_idx = [j for k in range(baseline_weeks[0], baseline_weeks[1] + 1) for j in (i - k, i + k) if 0 <= j < len(s)]
            base = s.iloc[[j for j in base_idx if not any_event.iloc[j]]]
            if len(base) < 3:
                continue
            nxt = s.iloc[i + 1] if i + 1 < len(s) else np.nan
            prv = s.iloc[i - 1] if i - 1 >= 0 else np.nan
            rows.append({"event": n, "week_start": w, "value": s.iloc[i], "baseline_median": base.median(),
                         "lift": s.iloc[i] / base.median() if base.median() > 0 else np.nan,
                         "lift_prev_week": prv / base.median() if base.median() > 0 else np.nan,
                         "lift_next_week": nxt / base.median() if base.median() > 0 else np.nan})
    return pd.DataFrame(rows).sort_values(["event", "week_start"]).reset_index(drop=True)


def event_lift_summary(lifts: pd.DataFrame) -> pd.DataFrame:
    g = lifts.groupby("event")["lift"]
    out = pd.DataFrame({"occurrences": g.size(), "median_lift": g.median(), "min_lift": g.min(), "max_lift": g.max(),
                        "years_with_lift_gt_1_2": g.apply(lambda x: int((x > 1.2).sum()))})
    return out.reset_index().sort_values("median_lift", ascending=False)


# ----------------------------- regional (relative only) -----------------------------
def regional_rank_table(single_term_index: pd.DataFrame) -> pd.DataFrame:
    """Per term: region index, rank, and a no-data flag. Values from different terms use different
    scale_ids (each is 0-100 against that term's own peak region); they are never merged into one metric."""
    out = []
    for term, g in single_term_index.groupby("term"):
        assert_same_scale(g)  # one export per term
        g = g.copy()
        g["rank_within_term"] = g["value"].rank(ascending=False, method="min")
        g["has_data"] = ~g["is_missing"]
        out.append(g)
    return pd.concat(out, ignore_index=True)


def regional_share_table(share_df: pd.DataFrame) -> pd.DataFrame:
    """Group-A share of each term within a region's 5-term searches (rows sum to ~100 per region)."""
    assert_same_scale(share_df)
    d = share_df.copy()
    d["share_upper_bound"] = d["value"].fillna(d["censor_upper_bound"])
    return d
