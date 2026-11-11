"""Parse Trends timeline and geoMap exports into tidy long tables.

Every row carries ``comparison_group``, ``scale_id`` and ``source_file`` so independently
normalised exports can never be silently merged. Censored cells keep NaN value + upper bound.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .ingest import inspect_file, normalization_note
from .regions import standardize_region
from .trends_io import parse_date, parse_term_header, parse_value, parse_window, read_rows, split_metadata_and_table


def _cell_frame(raw_cells: list[str]) -> pd.DataFrame:
    cells = [parse_value(x) for x in raw_cells]
    return pd.DataFrame(
        {
            "value": [c.value for c in cells],
            "is_censored": [c.censored for c in cells],
            "censor_upper_bound": [c.upper_bound for c in cells],
            "is_missing": [c.missing for c in cells],
        }
    )


def parse_timeline(path: Path, entry: dict | None = None) -> pd.DataFrame:
    info = entry or inspect_file(path)
    if info["kind"] != "timeline":
        raise ValueError(f"{path.name} is not a timeline export")
    rows, _, _ = read_rows(path)
    _, header, body = split_metadata_and_table(rows)
    terms = [parse_term_header(c)[0] for c in header[1:]]
    out = []
    for j, term in enumerate(terms, start=1):
        cf = _cell_frame([r[j] if j < len(r) else "" for r in body])
        cf.insert(0, "week_start", [parse_date(r[0]) for r in body])
        cf.insert(1, "term", term)
        out.append(cf)
    df = pd.concat(out, ignore_index=True)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["is_reported_zero"] = (df["value"] == 0) & ~df["is_censored"]
    df["comparison_group"] = info["comparison_group"]
    df["scale_id"] = f"{info['comparison_group']}|timeline|{path.name}"
    df["normalization"] = normalization_note(info["comparison_group"], "timeline")
    df["source_file"] = path.name
    return df.sort_values(["term", "week_start"], kind="stable").reset_index(drop=True)


def parse_geomap(path: Path, entry: dict | None = None) -> pd.DataFrame:
    info = entry or inspect_file(path)
    if info["kind"] != "geomap":
        raise ValueError(f"{path.name} is not a geoMap export")
    rows, _, _ = read_rows(path)
    _, header, body = split_metadata_and_table(rows)
    terms = [parse_term_header(c)[0] for c in header[1:]]
    has_pct = any("%" in c for r in body for c in r[1:])
    metric = "share_pct_of_compared_terms" if has_pct else "index_0_100_peak_region"
    out = []
    for j, term in enumerate(terms, start=1):
        cf = _cell_frame([r[j] if j < len(r) else "" for r in body])
        std = [standardize_region(r[0]) for r in body]
        cf.insert(0, "region_name_raw", [r[0] for r in body])
        cf.insert(1, "region_iso", [s[0] for s in std])
        cf.insert(2, "region_en", [s[1] for s in std])
        cf.insert(3, "region_ar", [s[2] for s in std])
        cf.insert(4, "term", term)
        out.append(cf)
    df = pd.concat(out, ignore_index=True)
    df["metric"] = metric
    df["window_start"] = pd.Timestamp(info["window_start"])
    df["window_end"] = pd.Timestamp(info["window_end"])
    df["comparison_group"] = info["comparison_group"]
    df["scale_id"] = f"{info['comparison_group']}|geomap|{path.name}"
    df["normalization"] = normalization_note(info["comparison_group"], "geomap")
    df["source_file"] = path.name
    # Phase-B-ready key: a regional TIME series would add week_start with the same other columns.
    return df.reset_index(drop=True)


def timeline_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """Wide view of ONE comparison group: values + censor flags per term. Refuses mixed groups."""
    if long_df["scale_id"].nunique() != 1:
        raise ValueError("timeline_wide requires a single scale_id (never mix normalisations)")
    w = long_df.pivot(index="week_start", columns="term", values="value")
    c = long_df.pivot(index="week_start", columns="term", values="is_censored")
    w.columns = [f"value__{t}" for t in w.columns]
    c.columns = [f"censored__{t}" for t in c.columns]
    wide = pd.concat([w, c], axis=1).sort_index().reset_index()
    wide["comparison_group"] = long_df["comparison_group"].iloc[0]
    wide["scale_id"] = long_df["scale_id"].iloc[0]
    return wide


def edge_partial_flags(week_starts: pd.Series, window_start: pd.Timestamp, window_end: pd.Timestamp) -> pd.Series:
    """True for weeks whose 7-day span is not fully inside the query window (Trends partial buckets)."""
    ws = pd.to_datetime(week_starts)
    return (ws < window_start) | (ws + pd.Timedelta(days=6) > window_end)


def is_close(a: float, b: float, tol: float = 1e-9) -> bool:
    return bool(np.isclose(a, b, atol=tol))
