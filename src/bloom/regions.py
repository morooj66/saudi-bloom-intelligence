"""Canonical Saudi administrative regions (13) and Arabic-name standardisation.

ISO 3166-2:SA subdivision codes. Google Trends labels vary ("منطقة الرياض", "القصيم",
"مكة المكرمة", "منطقة المدينة"), so names are normalised and matched via an explicit alias map.
Unknown names raise instead of being passed through.
"""
from __future__ import annotations

import re

# (iso_code, english, arabic_standard)
REGIONS: tuple[tuple[str, str, str], ...] = (
    ("SA-01", "Riyadh", "الرياض"),
    ("SA-02", "Makkah", "مكة المكرمة"),
    ("SA-03", "Madinah", "المدينة المنورة"),
    ("SA-05", "Qassim", "القصيم"),
    ("SA-04", "Eastern Province", "المنطقة الشرقية"),
    ("SA-14", "Asir", "عسير"),
    ("SA-07", "Tabuk", "تبوك"),
    ("SA-06", "Hail", "حائل"),
    ("SA-08", "Northern Borders", "الحدود الشمالية"),
    ("SA-09", "Jazan", "جازان"),
    ("SA-10", "Najran", "نجران"),
    ("SA-11", "Al Bahah", "الباحة"),
    ("SA-12", "Al Jawf", "الجوف"),
)
ISO_CODES = tuple(r[0] for r in REGIONS)
_BY_CODE = {r[0]: r for r in REGIONS}

_ALIASES: dict[str, str] = {
    "الرياض": "SA-01",
    "مكه المكرمه": "SA-02", "مكه": "SA-02",
    "المدينه المنوره": "SA-03", "المدينه": "SA-03",
    "القصيم": "SA-05",
    "الشرقيه": "SA-04",
    "عسير": "SA-14",
    "تبوك": "SA-07",
    "حائل": "SA-06",
    "الحدود الشماليه": "SA-08",
    "جازان": "SA-09", "جيزان": "SA-09",
    "نجران": "SA-10",
    "الباحه": "SA-11",
    "الجوف": "SA-12",
}


def _norm(name: str) -> str:
    s = re.sub(r"[ً-ٰٟـ]", "", name)  # tashkeel, tatweel
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(منطقه|المنطقه|امانه)\s+(?!الشرقيه)", "", s)  # strip 'region of' prefix
    if s in ("المنطقه الشرقيه", "الشرقيه"):
        return "الشرقيه"
    return s


def standardize_region(name: str) -> tuple[str, str, str]:
    """Return (iso_code, english_name, arabic_standard_name) or raise ValueError."""
    key = _norm(name)
    code = _ALIASES.get(key)
    if code is None:
        raise ValueError(f"Unknown Saudi region name: {name!r} (normalised {key!r})")
    return _BY_CODE[code]
