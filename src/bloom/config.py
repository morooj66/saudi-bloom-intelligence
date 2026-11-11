"""Paths and domain constants shared across the pipeline."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
INCOMING_DIR = ROOT / "incoming_data"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
MANIFEST_JSON = ROOT / "data" / "manifest.json"
MANIFEST_CSV = ROOT / "data" / "manifest.csv"
REPORTS_DIR = ROOT / "reports"

SOURCE_NAME = "Google Trends (manual CSV export from trends.google.com)"
GEO_SCOPE = "SA"  # Saudi Arabia, as labelled in the exports

GENERAL_TERM = "ورد"
COMMERCIAL_TERMS = ("توصيل ورد", "بوكيه ورد", "محل ورد", "شراء ورد")
ALL_TERMS = (GENERAL_TERM, *COMMERCIAL_TERMS)

GROUP_A = "A_general_5terms"
GROUP_B = "B_commercial_4terms"
GROUP_B4_SHARE = "B4_commercial_4terms_regional_share"  # regional share export of the 4 commercial terms (own scale; never merged)
GROUP_SINGLE_PREFIX = "S_single:"

TERM_EN = {
    "ورد": "flowers (general)",
    "توصيل ورد": "flower delivery",
    "بوكيه ورد": "flower bouquet",
    "محل ورد": "flower shop",
    "شراء ورد": "buy flowers",
}

# Trends rounds to integers; a published value <1 is shown as "<1" (censored).
CENSORED_UPPER_BOUND = 1.0
# Weekly Trends buckets start on Sunday (observed in the exports; verified by tests).
WEEK_START_WEEKDAY = 6  # Monday=0 ... Sunday=6
EXPECTED_REGION_COUNT = 13


def paths(root: Path = ROOT) -> SimpleNamespace:
    """All project locations derived from one root (lets tests run the pipeline in a temp directory)."""
    root = Path(root)
    return SimpleNamespace(
        root=root, incoming=root / "incoming_data", raw=root / "data" / "raw", processed=root / "data" / "processed",
        phase_a=root / "data" / "processed" / "phase_a", manifest_json=root / "data" / "manifest.json",
        manifest_csv=root / "data" / "manifest.csv", geo=root / "data" / "geo",
    )
