"""Pure, UI-free logic behind the executive overview and the regional comparison. Everything is derived from validated
outputs passed in as DataFrames (nothing is hard-coded), so it is unit-tested independently of Streamlit.

All values are Google Trends relative search interest. Regional index: 0-100, where 100 = the region with the highest
relative search interest for that ONE term in that export (each region is normalised by its own total search volume).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import assert_same_scale

NO_DATA, CENSORED, AVAILABLE = "No data", "Censored (<1%)", "Available"


# ------------------------------------------------------------------------------------------------ regional status
def region_status(df: pd.DataFrame) -> pd.DataFrame:
    """One row per region (exactly 13) of ONE export/term with an explicit status. Missing/censored are never zero."""
    assert_same_scale(df)
    d = df.copy()
    d["status"] = AVAILABLE
    d.loc[d["is_censored"], "status"] = CENSORED
    d.loc[d["is_missing"], "status"] = NO_DATA
    assert len(d) == 13 and d["region_iso"].nunique() == 13, "all 13 regions must be present"
    return d


def regional_rank_table(d: pd.DataFrame) -> pd.DataFrame:
    """Status frame plus rank among regions WITH data (ties share the best rank) and gap to the peak region."""
    s = region_status(d)
    avail = s["status"] == AVAILABLE
    s["rank"] = np.nan
    s.loc[avail, "rank"] = s.loc[avail, "value"].rank(ascending=False, method="min")
    peak = s.loc[avail, "value"].max() if avail.any() else np.nan
    s["gap_to_peak"] = np.where(avail, peak - s["value"], np.nan)
    return s.sort_values(["status", "rank"], ascending=[True, True]).reset_index(drop=True)


def top_region(idx: pd.DataFrame, term: str) -> dict:
    """Highest relative search interest for `term` (single-term regional index export)."""
    d = idx[(idx["term"] == term) & ~idx["is_missing"] & ~idx["is_censored"]].sort_values("value", ascending=False)
    top = d.iloc[0]
    ties = d.loc[d["value"] == top["value"], "region_en"].tolist()
    lower = d[d["value"] < top["value"]]
    out = {"term": term, "region_en": top["region_en"], "region_ar": top["region_ar"], "iso": top["region_iso"], "value": float(top["value"]),
           "ties": ties, "n_with_data": int(len(d)), "scale_id": top["scale_id"], "runner_up_en": None, "runner_up_value": None}
    if len(lower):
        out["runner_up_en"], out["runner_up_value"] = lower.iloc[0]["region_en"], float(lower.iloc[0]["value"])
    return out


def regions_covered(idx: pd.DataFrame) -> dict:
    """Region coverage across every term in the single-term regional exports."""
    terms = sorted(idx["term"].unique())
    ok = idx[~idx["is_missing"] & ~idx["is_censored"]].groupby("region_iso")["term"].nunique()
    return {"n_regions": int(idx["region_iso"].nunique()), "n_terms": len(terms), "n_regions_all_terms": int((ok == len(terms)).sum()),
            "missing_cells": int(idx["is_missing"].sum())}


def history_coverage(long_df: pd.DataFrame) -> dict:
    """Weekly history excluding the two partial edge buckets."""
    d = long_df[~long_df["is_edge_partial_week"]]
    first, last = d["week_start"].min(), d["week_start"].max()
    n = int(d["week_start"].nunique())
    return {"n_weeks": n, "first": first, "last": last, "years": round(n / 52.18, 1), "n_edge_excluded": int(long_df.loc[long_df["is_edge_partial_week"], "week_start"].nunique())}


def strongest_seasonal(summary: pd.DataFrame, term: str) -> dict:
    """Event with the highest median event-week lift (descriptive; 5 occurrences each)."""
    s = summary[summary["term"] == term].sort_values("median_lift", ascending=False)
    r = s.iloc[0]
    return {"term": term, "event": r["event"], "median_lift": float(r["median_lift"]), "occurrences": int(r["occurrences"]),
            "years_gt_1_2": int(r["years_with_lift_gt_1_2"]), "min_lift": float(r["min_lift"]), "max_lift": float(r["max_lift"])}


# ------------------------------------------------------------------------------------------------ map <-> comparison
def toggle_from_map(compare: list[str], clicked: list[str]) -> list[str]:
    """Toggle each clicked region in/out of the comparison list (order of first selection preserved).

    The map widget is re-keyed after every click, so a selection event only ever contains the regions just clicked
    (several when shift-clicking). An empty event changes nothing. Unknown codes are ignored.
    """
    from .regions import ISO_CODES

    out = list(compare)
    for r in clicked:
        if r not in ISO_CODES:
            continue
        out.remove(r) if r in out else out.append(r)
    return out


# ------------------------------------------------------------------------------------------------ seasonality
def yoy_frame(analytic: pd.DataFrame, term: str) -> pd.DataFrame:
    """Weekly values by calendar year and Sunday-based week of year (edge partial weeks excluded). Same-scale series."""
    d = analytic[~analytic["is_edge_partial_week"]]
    mid = d["week_start"] + pd.Timedelta(days=3)
    out = pd.DataFrame({"week_start": d["week_start"].values, "value": d[f"value__{term}"].astype(float).values,
                        "year": mid.dt.year.values, "woy": np.minimum((mid.dt.dayofyear.values - 1) // 7 + 1, 52)})
    return out


def eid_weeks(analytic: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Weeks containing Eid al-Fitr / Eid al-Adha with verification status (for markers on the year-over-year chart)."""
    ev = events[events["event"].isin(["eid_al_fitr", "eid_al_adha"])]
    rows = []
    for _, e in ev.iterrows():
        hit = analytic[(analytic["week_start"] <= e["date"]) & (analytic["week_start"] + pd.Timedelta(days=6) >= e["date"]) & ~analytic["is_edge_partial_week"]]
        if len(hit):
            ws = hit["week_start"].iloc[0]; mid = ws + pd.Timedelta(days=3)
            rows.append({"event": e["event"], "date": e["date"], "week_start": ws, "year": mid.year, "woy": min((mid.dayofyear - 1) // 7 + 1, 52),
                         "verification": e["verification"]})
    return pd.DataFrame(rows)


def month_extremes(month_profile: pd.DataFrame, term: str) -> dict:
    m = month_profile[month_profile["term"] == term].sort_values("index_vs_overall_mean", ascending=False)
    return {"top": [(int(r.month), float(r.index_vs_overall_mean)) for r in m.head(2).itertuples()],
            "bottom": [(int(r.month), float(r.index_vs_overall_mean)) for r in m.tail(2).itertuples()]}


# ------------------------------------------------------------------------------------------------ labels
_MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
_TERM_EN = {"محل ورد": "flower shop", "بوكيه ورد": "flower bouquet", "توصيل ورد": "flower delivery", "شراء ورد": "buy flowers"}


def _fd(ts, lang: str = "en") -> str:
    """'14 Nov 2021' or '14 نوفمبر 2021' (Western digits)."""
    t = pd.Timestamp(ts)
    return f"{t.day} {_MONTHS_AR[t.month - 1]} {t.year}" if lang == "ar" else f"{t:%d %b %Y}"


def friendly_scale(scale_id: str, lang: str = "en") -> str:
    """Readable description of a scale_id (`<group>|<kind>|<file>`)."""
    group, kind, fname = scale_id.split("|", 2)
    ar = lang == "ar"
    if group.startswith("S_single:"):
        return (f"مؤشر إقليمي لمصطلح واحد · {group.split(':', 1)[1]} ({fname})" if ar else f"single-term regional index · {group.split(':', 1)[1]} ({fname})")
    en_name = {"A_general_5terms": "group A · 5 terms", "B_commercial_4terms": "group B · 4 commercial terms", "B4_commercial_4terms_regional_share": "group B4 · 4 commercial terms, regional shares"}
    ar_name = {"A_general_5terms": "المجموعة A · 5 مصطلحات", "B_commercial_4terms": "المجموعة B · 4 مصطلحات تجارية", "B4_commercial_4terms_regional_share": "المجموعة B4 · 4 مصطلحات تجارية، حصص إقليمية"}
    name = (ar_name if ar else en_name).get(group, group)
    what = ({"timeline": "سلسلة أسبوعية", "geomap": "حصص إقليمية"} if ar else {"timeline": "weekly series", "geomap": "regional shares"}).get(kind, kind)
    return f"{name} · {what} ({fname})"


# ------------------------------------------------------------------------------------------------ executive homepage helpers
def trend_vs_prior_year(long_df: pd.DataFrame, term: str, weeks: int = 52) -> dict | None:
    """Mean weekly index of the latest `weeks` full weeks vs the `weeks` before them (one scale, edge partial weeks excluded).
    Descriptive only: Google Trends sampling noise is not measured, so small differences are not meaningful."""
    d = long_df[(long_df["term"] == term) & ~long_df["is_edge_partial_week"]].sort_values("week_start")
    v = d["value"].astype(float).to_numpy()
    if len(v) < 2 * weeks or np.isnan(v[-2 * weeks:]).any():
        return None
    recent, prior = v[-weeks:], v[-2 * weeks:-weeks]
    ws = d["week_start"].to_numpy()
    return {"term": term, "weeks": weeks, "recent_mean": float(recent.mean()), "prior_mean": float(prior.mean()),
            "pct_change": float(recent.mean() / prior.mean() - 1) if prior.mean() > 0 else float("nan"),
            "recent_start": pd.Timestamp(ws[-weeks]), "recent_end": pd.Timestamp(ws[-1]), "prior_start": pd.Timestamp(ws[-2 * weeks]), "prior_end": pd.Timestamp(ws[-weeks - 1])}


def ranking_explainer(idx: pd.DataFrame, share: pd.DataFrame, term: str) -> dict:
    """Everything the 'regional insight' card says, computed from the two regional exports (never merged)."""
    top = top_region(idx, term)
    s = share[(share["term"] == term) & ~share["is_missing"] & ~share["is_censored"]]
    st_top = None
    if len(s):
        m = float(s["value"].max())
        st_top = {"regions": s.loc[s["value"] == m, "region_en"].tolist(), "value": m, "n": int(len(s))}
    return {"top": top, "share_top": st_top, "same_leader": bool(st_top and top["region_en"] in st_top["regions"] and len(st_top["regions"]) == 1)}


def region_detail(d: pd.DataFrame, iso: str) -> dict:
    """One region of ONE export/term: status, value, rank among regions with data, points below the peak region."""
    t = regional_rank_table(d)
    r = t[t["region_iso"] == iso].iloc[0]
    n_avail = int((t["status"] == AVAILABLE).sum())
    ok = r["status"] == AVAILABLE
    return {"iso": iso, "region_en": r["region_en"], "region_ar": r["region_ar"], "status": r["status"], "value": float(r["value"]) if ok else None,
            "rank": int(r["rank"]) if ok else None, "n_available": n_avail, "gap_to_peak": float(r["gap_to_peak"]) if ok else None}


def select_from_map(current: str | None, clicked: list[str]) -> str | None:
    """Single-region selection for the homepage map: the most recently clicked valid region wins; an empty event changes nothing."""
    from .regions import ISO_CODES

    valid = [c for c in clicked if c in ISO_CODES]
    return valid[-1] if valid else current


def spread_of_available(d: pd.DataFrame) -> tuple[float, float, int]:
    """(min, max, n) of the exact values in one regional export/term."""
    v = d.loc[~d["is_missing"] & ~d["is_censored"], "value"]
    return (float(v.min()), float(v.max()), int(len(v))) if len(v) else (float("nan"), float("nan"), 0)


def series_text_alternative(df: pd.DataFrame, label: str, value_col: str = "value", lang: str = "en") -> str:
    """Plain-text description of a weekly series chart (for readers who cannot see it)."""
    d = df.dropna(subset=[value_col]).sort_values("week_start")
    if d.empty:
        return f"{label}: لا توجد بيانات." if lang == "ar" else f"{label}: no data."
    pk, lt = d.loc[d[value_col].idxmax()], d.iloc[-1]
    if lang == "ar":
        return (f"{label}: {len(d)} قيمة أسبوعية من {_fd(d['week_start'].iloc[0], lang)} إلى {_fd(lt['week_start'], lang)}؛ الوسيط {d[value_col].median():.0f}، "
                f"المدى {d[value_col].min():.0f}–{d[value_col].max():.0f}؛ الأعلى في أسبوع {_fd(pk['week_start'], lang)} ({pk[value_col]:.0f})؛ الأحدث {lt[value_col]:.0f}.")
    return (f"{label}: {len(d)} weekly values from {d['week_start'].iloc[0]:%d %b %Y} to {lt['week_start']:%d %b %Y}; median {d[value_col].median():.0f}, "
            f"range {d[value_col].min():.0f}–{d[value_col].max():.0f}; highest in the week of {pk['week_start']:%d %b %Y} ({pk[value_col]:.0f}); latest {lt[value_col]:.0f}.")


def map_text_alternative(d: pd.DataFrame, label: str, lang: str = "en") -> str:
    """Plain-text description of the regional map / ranked chart of ONE export/term."""
    t = regional_rank_table(d)
    a = t[t["status"] == AVAILABLE].sort_values("rank")
    n_cen, n_no = int((t["status"] == CENSORED).sum()), int((t["status"] == NO_DATA).sum())
    ar = lang == "ar"
    nm = (lambda r: r.region_ar) if ar else (lambda r: r.region_en)
    if a.empty:
        return (f"{label}: لا توجد قيمة رقمية في أي من المناطق الـ13 ({n_cen} مخفية، {n_no} بلا بيانات)." if ar
                else f"{label}: none of the 13 regions has a numeric value ({n_cen} censored, {n_no} no data).")
    top3 = ("، " if ar else ", ").join(f"{nm(r)} {r.value:.0f}" for r in a.head(3).itertuples())
    low = a.iloc[-1]
    if ar:
        extra = ("؛ " + "، ".join(p for p in (f"{n_cen} مخفية (أقل من 1%)" if n_cen else "", f"{n_no} بلا بيانات" if n_no else "") if p)) if (n_cen or n_no) else ""
        return f"{label}: لدى {len(a)} من 13 منطقة قيم رقمية. الأعلى: {top3}. الأدنى: {low['region_ar']} {low['value']:.0f}{extra}."
    extra = ("; " + ", ".join(p for p in (f"{n_cen} censored" if n_cen else "", f"{n_no} with no data" if n_no else "") if p)) if (n_cen or n_no) else ""
    return f"{label}: {len(a)} of 13 regions have values. Highest: {top3}. Lowest: {low['region_en']} {low['value']:.0f}{extra}."


def region_comparison(d: pd.DataFrame, iso: str) -> dict:
    """Everything the 'selected region' card says, for ONE export/term: index, rank, the highest-index region and how the selected one compares.

    `ratio_to_peak` = index / peak index: by Google's definition the index is a region's normalised interest as a fraction of the highest region's, so this is a
    statement about relative interest only (never volume, sales or demand)."""
    t = regional_rank_table(d)
    r = region_detail(d, iso)
    avail = t[t["status"] == AVAILABLE].sort_values("rank")
    peak = avail.iloc[0] if len(avail) else None
    tied = avail[avail["value"] == peak["value"]]["region_en"].tolist() if peak is not None else []
    r.update({"peak_en": None if peak is None else peak["region_en"], "peak_ar": None if peak is None else peak["region_ar"], "peak_value": None if peak is None else float(peak["value"]),
              "peak_ties": tied, "ratio_to_peak": (r["value"] / float(peak["value"])) if (r["value"] is not None and peak is not None and peak["value"] > 0) else None,
              "is_peak": bool(r["status"] == AVAILABLE and peak is not None and r["value"] == float(peak["value"]))})
    return r


# ------------------------------------------------------------------------------------------------ regional commercial-term mix (4 terms)
MIX_TERM_ORDER = ("محل ورد", "بوكيه ورد", "توصيل ورد", "شراء ورد")  # fixed display order (largest published shares first); not a ranking
MIX_EN = {"محل ورد": "flower shop", "بوكيه ورد": "flower bouquet", "توصيل ورد": "flower delivery", "شراء ورد": "buy flowers"}


def _assert_mix_frame(df: pd.DataFrame) -> None:
    from . import config as C

    assert_same_scale(df)  # one scale_id only: raises ScaleMixError if the index / five-term frames are mixed in
    if set(df["comparison_group"]) != {C.GROUP_B4_SHARE}:
        from .schema import ScaleMixError

        raise ScaleMixError(f"term-mix view accepts only the four-term regional share export, got {sorted(set(df['comparison_group']))}")


def term_mix_table(df: pd.DataFrame) -> pd.DataFrame:
    """Long table (13 regions × 4 terms) with an explicit status per cell. Censored and blank cells keep value NaN: never zero, never redistributed."""
    _assert_mix_frame(df)
    d = df.copy()
    d["status"] = AVAILABLE
    d.loc[d["is_censored"], "status"] = CENSORED
    d.loc[d["is_missing"], "status"] = NO_DATA
    assert d["region_iso"].nunique() == 13 and len(d) == 13 * d["term"].nunique(), "13 regions × every term must be present"
    return d


def term_mix_regions(df: pd.DataFrame) -> pd.DataFrame:
    """One row per region: published numeric shares, their sum, the UNSPECIFIED remainder (100 − sum, never negative) and the unquantified terms.

    The remainder is reported as unspecified; it is never assigned to a term. If the published values exceed 100 (rounding) the excess is recorded, not hidden.
    """
    t = term_mix_table(df)
    rows = []
    for iso, g in t.groupby("region_iso", sort=False):
        pub = g[g["status"] == AVAILABLE]
        total = float(pub["value"].sum())
        rows.append({"region_iso": iso, "region_en": g["region_en"].iloc[0], "region_ar": g["region_ar"].iloc[0], "published_sum": total,
                     "unspecified_remainder": max(0.0, 100.0 - total), "rounding_excess": max(0.0, total - 100.0), "n_numeric": int(len(pub)),
                     "censored_terms": g.loc[g["status"] == CENSORED, "term"].tolist(), "missing_terms": g.loc[g["status"] == NO_DATA, "term"].tolist()})
    return pd.DataFrame(rows)


def term_mix_cell_counts(df: pd.DataFrame) -> dict:
    t = term_mix_table(df)
    return {"cells": int(len(t)), "numeric": int((t["status"] == AVAILABLE).sum()), "censored": int((t["status"] == CENSORED).sum()),
            "missing": int((t["status"] == NO_DATA).sum()), "regions": int(t["region_iso"].nunique()), "terms": int(t["term"].nunique())}


def term_mix_order(df: pd.DataFrame, by: str | None = None) -> list[str]:
    """Region ISO codes for display: alphabetical by English name (neutral default) or by one term's published share (largest first; regions without a value last)."""
    t = term_mix_table(df)
    names = t.drop_duplicates("region_iso").set_index("region_iso")["region_en"]
    if by is None:
        return names.sort_values().index.tolist()
    v = t[(t["term"] == by)].set_index("region_iso")["value"]
    key = pd.DataFrame({"v": v.reindex(names.index), "n": names}).assign(isna=lambda x: x["v"].isna())
    return key.sort_values(["isna", "v", "n"], ascending=[True, False, True]).index.tolist()


MIX_AR = {"محل ورد": "محل ورد", "بوكيه ورد": "بوكيه ورد", "توصيل ورد": "توصيل ورد", "شراء ورد": "شراء ورد"}


def term_mix_text_alternative(df: pd.DataFrame, order: list[str] | None = None, lang: str = "en") -> str:
    """Plain-text description of the stacked-bar chart: every region, every published share, and each censored / blank cell stated as such."""
    t = term_mix_table(df)
    summ = term_mix_regions(df).set_index("region_iso")
    ar = lang == "ar"
    nm = (lambda k: MIX_AR[k]) if ar else (lambda k: MIX_EN.get(k, k))
    parts = []
    for iso in (order or term_mix_order(df)):
        g = t[t["region_iso"] == iso].set_index("term")
        bits = [f"{nm(k)} {g.loc[k, 'value']:.0f}%" for k in MIX_TERM_ORDER if k in g.index and g.loc[k, "status"] == AVAILABLE]
        bits += [(f"{nm(k)} مخفية (أقل من 1%)" if ar else f"{nm(k)} censored (below 1%)") for k in MIX_TERM_ORDER if k in g.index and g.loc[k, "status"] == CENSORED]
        bits += [(f"{nm(k)} بلا بيانات" if ar else f"{nm(k)} no data reported") for k in MIX_TERM_ORDER if k in g.index and g.loc[k, "status"] == NO_DATA]
        rem = summ.loc[iso, "unspecified_remainder"]
        rem_txt = (f"، المتبقي غير المحدد {rem:.0f}%" if ar else f", unspecified remainder {rem:.0f}%") if rem > 0 else ""
        parts.append(f"{summ.loc[iso, 'region_ar' if ar else 'region_en']}: " + ("، " if ar else ", ").join(bits) + rem_txt)
    head = ("تركيبة المصطلحات التجارية: حصة كل مصطلح بين المصطلحات الأربعة داخل كل منطقة (ليست حجم بحث ولا مبيعات). " if ar
            else "Commercial-term mix, share of each term among the four terms' searches within each region (not volume or sales). ")
    return head + ("؛ " if ar else "; ").join(parts) + "."
