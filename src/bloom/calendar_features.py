"""Calendar features for weekly series (week_start = Sunday).

Leakage policy: every feature is a pure function of the week's dates (never of series values)
and of calendars that are published in advance. Islamic events use the Umm al-Qura calendar
(computable years ahead) rather than moon-sighting announcements (known ~1 day ahead).
Announced dates are used only to *verify* the Umm al-Qura dates (see EVENT_VERIFICATION).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from hijridate import Gregorian, Hijri

# Saudi announcements located by web search on 2026-11-10 (Supreme Court via SPA / press).
# Everything not listed here is Umm al-Qura-computed and NOT independently verified.
EVENT_VERIFICATION: dict[tuple[str, str], str] = {
    ("eid_al_fitr", "2022-05-02"): "Saudi Supreme Court, via Arab News / Gulf News",
    ("eid_al_fitr", "2024-04-10"): "Saudi Supreme Court, via Saudi Gazette / Time Out Jeddah",
    ("eid_al_fitr", "2025-03-30"): "Royal Court / SPA",
    ("eid_al_fitr", "2026-03-20"): "Gulf News / Arab News",
    ("eid_al_adha", "2023-06-28"): "Saudi Supreme Court, via SPA / Gulf News",
    ("eid_al_adha", "2024-06-16"): "Al Arabiya",
    ("eid_al_adha", "2026-05-27"): "Saudi Supreme Court (reported)",
    ("ramadan_start", "2026-02-18"): "Saudi Supreme Court (reported)",
}

HIJRI_EVENTS = {  # name -> (hijri month, hijri day)
    "ramadan_start": (9, 1),
    "eid_al_fitr": (10, 1),
    "arafat_day": (12, 9),
    "eid_al_adha": (12, 10),
}
FIXED_EVENTS = {  # name -> (month, day, first_year)
    "valentines_day": (2, 14, 1900),
    "mothers_day_arab": (3, 21, 1900),  # widely observed in the Arab world; not an official Saudi holiday
    "saudi_founding_day": (2, 22, 2022),  # established by royal order in Jan 2022
    "saudi_national_day": (9, 23, 1900),
    "new_years_eve": (12, 31, 1900),
}
EVENT_NAMES = [*HIJRI_EVENTS, *FIXED_EVENTS]


def event_dates(year_from: int = 2021, year_to: int = 2027) -> pd.DataFrame:
    rows = []
    for hy in range(1442, 1450):
        for name, (m, d) in HIJRI_EVENTS.items():
            g = Hijri(hy, m, d).to_gregorian()
            date = dt.date(g.year, g.month, g.day)
            if year_from <= date.year <= year_to:
                key = (name, date.isoformat())
                rows.append((name, date, "umm_al_qura", "verified_announced" if key in EVENT_VERIFICATION else "computed_unverified", EVENT_VERIFICATION.get(key, "")))
    for name, (m, d, y0) in FIXED_EVENTS.items():
        for y in range(max(year_from, y0), year_to + 1):
            rows.append((name, dt.date(y, m, d), "gregorian_fixed", "fixed_rule", ""))
    df = pd.DataFrame(rows, columns=["event", "date", "basis", "verification", "source_note"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["date", "event"]).reset_index(drop=True)


def build_weekly_calendar(week_starts, offset_clip: int = 4) -> pd.DataFrame:
    ws = pd.to_datetime(pd.Series(week_starts)).reset_index(drop=True)
    we = ws + pd.Timedelta(days=6)
    mid = ws + pd.Timedelta(days=3)
    iso = ws.dt.isocalendar()
    df = pd.DataFrame(
        {
            "week_start": ws,
            "week_end": we,
            "year": ws.dt.year,
            "quarter": ws.dt.quarter,
            "month": mid.dt.month,
            "iso_year": iso["year"].astype(int),
            "iso_week": iso["week"].astype(int),
            "week_of_year_sunday": ((mid.dt.dayofyear - 1) // 7 + 1).clip(upper=52),
            "annual_sin": np.sin(2 * np.pi * mid.dt.dayofyear / 365.25),
            "annual_cos": np.cos(2 * np.pi * mid.dt.dayofyear / 365.25),
        }
    )
    hij = [Gregorian(d.year, d.month, d.day).to_hijri() for d in mid]
    df["hijri_year"] = [h.year for h in hij]
    df["hijri_month"] = [h.month for h in hij]

    lo, hi = ws.min().year, we.max().year
    ev = event_dates(lo - 1, hi + 1)
    for name in EVENT_NAMES:
        dates = ev.loc[ev["event"] == name, "date"].to_numpy()
        in_week = np.zeros(len(df), dtype=bool)
        offset = np.full(len(df), np.nan)
        for i, (a, b) in enumerate(zip(ws.to_numpy(), we.to_numpy())):
            hit = dates[(dates >= a) & (dates <= b)]
            in_week[i] = len(hit) > 0
            if len(dates):
                # weeks until the nearest event week (negative = event already passed), clipped
                k = np.round((dates - a) / np.timedelta64(7, "D")).astype(int)
                k = k[np.abs(k) <= offset_clip]
                if len(k):
                    offset[i] = k[np.argmin(np.abs(k))]
        df[f"{name}_in_week"] = in_week
        df[f"{name}_week_offset"] = offset  # NaN when no event within +/-offset_clip weeks

    # Ramadan = [ramadan_start, eid_al_fitr - 1 day]
    rs = ev.loc[ev["event"] == "ramadan_start", "date"].sort_values().to_numpy()
    ef = ev.loc[ev["event"] == "eid_al_fitr", "date"].sort_values().to_numpy()
    days = np.zeros(len(df), dtype=int)
    for s in rs:
        e = ef[ef > s][:1]
        if len(e) == 0:
            continue
        for i, (a, b) in enumerate(zip(ws.to_numpy(), we.to_numpy())):
            lo_d, hi_d = max(a, s), min(b, e[0] - np.timedelta64(1, "D"))
            if hi_d >= lo_d:
                days[i] += int((hi_d - lo_d) / np.timedelta64(1, "D")) + 1
    df["ramadan_days_in_week"] = days
    df["is_ramadan_week"] = days > 0
    df["known_in_advance"] = True  # all columns derive from published calendars only
    return df
