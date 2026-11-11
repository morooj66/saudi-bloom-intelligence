"""Low-level helpers for reading Google Trends CSV exports.

Exports are not uniform: they start with metadata rows, use RTL/LRM control characters,
Arabic labels, and censored cells such as "<1" or "أقل من 1%". Nothing here guesses silently;
unrecognised cell formats raise ``ValueError``.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_BIDI = dict.fromkeys(
    [0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF, 0x200B, 0x200C, 0x200D]
)
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٪", "0123456789.%")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> tuple[str, str]:
    """Return (text, encoding). Tries BOM-aware UTF-8/16, then UTF-8, then Windows-1256."""
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    for enc in ("utf-8", "cp1256"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path}")


def clean_cell(s: str) -> str:
    return s.translate(_BIDI).strip()


def read_rows(path: Path) -> tuple[list[list[str]], str, str]:
    """Return (cleaned rows, encoding, delimiter)."""
    text, enc = read_text(path)
    sample = text[:4096]
    delim = ","
    if sample.count(";") > sample.count(",") and sample.count(";") > 0:
        delim = ";"
    elif sample.count("\t") > sample.count(","):
        delim = "\t"
    rows = [[clean_cell(c) for c in r] for r in csv.reader(io.StringIO(text), delimiter=delim)]
    return rows, enc, delim


def split_metadata_and_table(rows: list[list[str]]) -> tuple[list[list[str]], list[str], list[list[str]]]:
    """Metadata = rows before the first row with >=2 non-empty cells (the header)."""
    for i, r in enumerate(rows):
        if sum(1 for c in r if c) >= 2:
            body = [r2 for r2 in rows[i + 1 :] if any(c for c in r2)]
            return rows[:i], r, body
    raise ValueError("No table header found")


_HEADER_RE = re.compile(r"^(?P<term>.+?):\s*\((?P<scope>.*)\)\s*$")


def parse_term_header(cell: str) -> tuple[str, str]:
    """'ورد: (المملكة العربية السعودية)' -> ('ورد', 'المملكة العربية السعودية')."""
    m = _HEADER_RE.match(cell)
    if not m:
        raise ValueError(f"Unrecognised column header: {cell!r}")
    return m["term"].strip(), m["scope"].strip()


_WINDOW_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})")


def parse_window(scope: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Parse '10/11/2021 - 10/11/2026' as DAY/MONTH/YEAR (Arabic-locale export).

    Day-first is asserted later against the timeline range; see tests.
    """
    m = _WINDOW_RE.search(clean_cell(scope).translate(_ARABIC_DIGITS))
    if not m:
        return None
    d1, m1, y1, d2, m2, y2 = (int(x) for x in m.groups())
    return pd.Timestamp(y1, m1, d1), pd.Timestamp(y2, m2, d2)


@dataclass(frozen=True)
class Cell:
    value: float  # NaN when censored or missing
    censored: bool
    upper_bound: float  # NaN unless censored
    missing: bool


_NUM = r"(\d+(?:\.\d+)?)"
_EXACT_RE = re.compile(rf"^{_NUM}\s*%?$")
_CENSORED_RE = re.compile(rf"^(?:<\s*{_NUM}|أقل من\s*{_NUM})\s*%?$")


def parse_value(raw: str) -> Cell:
    """Parse one data cell. Censored cells keep their bound and have NaN value.

    '' -> missing (Trends had no/insufficient data); '12' / '87%' -> exact;
    '<1' / 'أقل من 1' / 'أقل من 1%' -> censored (true value in (0, bound)).
    """
    s = clean_cell(raw).translate(_ARABIC_DIGITS)
    if s == "":
        return Cell(float("nan"), False, float("nan"), True)
    m = _CENSORED_RE.match(s)
    if m:
        bound = float(m.group(1) or m.group(2))
        return Cell(float("nan"), True, bound, False)
    m = _EXACT_RE.match(s)
    if m:
        return Cell(float(m.group(1)), False, float("nan"), False)
    raise ValueError(f"Unrecognised value format: {raw!r}")


def parse_date(s: str) -> pd.Timestamp:
    """Parse ISO 'YYYY-MM-DD' (weekly/daily) or 'YYYY-MM' (monthly). Raises on anything else."""
    s = clean_cell(s)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return pd.Timestamp(s)
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return pd.Timestamp(s + "-01")
    raise ValueError(f"Unrecognised date: {s!r}")
