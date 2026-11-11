"""Data model contract, including the Phase-B (regional time series) table that is NOT populated yet.

Normalisation metadata travels with every row (scale_id, comparison_group, normalization).
``assert_same_scale`` is the single guard used by analysis/dashboard code before any
cross-series comparison or overlay.
"""
from __future__ import annotations

import pandas as pd

# Phase A tables (populated)
NATIONAL_WEEKLY_COLUMNS = [
    "week_start", "term", "value", "is_censored", "censor_upper_bound", "is_missing", "is_reported_zero",
    "comparison_group", "scale_id", "normalization", "source_file", "is_edge_partial_week",
]
REGIONAL_SNAPSHOT_COLUMNS = [
    "region_iso", "region_en", "region_ar", "region_name_raw", "term", "value", "is_censored", "censor_upper_bound",
    "is_missing", "metric", "window_start", "window_end", "comparison_group", "scale_id", "normalization", "source_file",
]
# Phase B table (schema only; no data exists). Same keys as the snapshot plus week_start, so dashboard
# components that take (region, term, scale_id) work unchanged once weekly regional exports are ingested.
REGIONAL_WEEKLY_COLUMNS = ["region_iso", "week_start", "term", "value", "is_censored", "censor_upper_bound",
                           "is_missing", "comparison_group", "scale_id", "normalization", "source_file"]


class ScaleMixError(ValueError):
    """Raised when series from different Google Trends normalisations are combined."""


def assert_same_scale(*frames: pd.DataFrame) -> str:
    ids = set()
    for f in frames:
        ids |= set(f["scale_id"].unique())
    if len(ids) != 1:
        raise ScaleMixError(f"Refusing to combine independently normalised exports: {sorted(ids)}")
    return ids.pop()


def validate_columns(df: pd.DataFrame, expected: list[str]) -> list[str]:
    return [c for c in expected if c not in df.columns]
