"""Bilingual (English / Arabic) support. One shared analytical data source: only TEXT depends on the language, never a number.

    L("English text", "النص العربي")   -> the string for the active language
    lang(), is_rtl()                  -> "en" | "ar", direction

The active language lives in st.session_state["lang"] (set by the language switch, or by ?lang=ar|en on first load), so it persists across navigation.
Outside a Streamlit run (unit tests that call chart builders directly) the language is English.
"""
from __future__ import annotations

import pandas as pd

from bidi import isolate

LANGS = ("ar", "en")
LANG_NAME = {"ar": "العربية", "en": "English"}

TERM_EN = {"ورد": "flowers (general)", "توصيل ورد": "flower delivery", "بوكيه ورد": "flower bouquet", "محل ورد": "flower shop", "شراء ورد": "buy flowers"}

EVENT_EN = {"eid_al_fitr": "Eid al-Fitr", "eid_al_adha": "Eid al-Adha", "valentines_day": "Valentine's Day", "mothers_day_arab": "Mother's Day (21 Mar)", "new_years_eve": "New Year's Eve",
            "arafat_day": "Arafat Day", "ramadan_start": "Ramadan start", "saudi_founding_day": "Founding Day", "saudi_national_day": "National Day"}
EVENT_AR = {"eid_al_fitr": "عيد الفطر", "eid_al_adha": "عيد الأضحى", "valentines_day": "عيد الحب", "mothers_day_arab": "عيد الأم (21 مارس)", "new_years_eve": "ليلة رأس السنة",
            "arafat_day": "يوم عرفة", "ramadan_start": "بداية رمضان", "saudi_founding_day": "يوم التأسيس", "saudi_national_day": "اليوم الوطني"}
EVENT_SHORT_EN = {"eid_al_fitr": "Fitr", "eid_al_adha": "Adha", "valentines_day": "Valentine", "mothers_day_arab": "Mother's", "new_years_eve": "New Year",
                  "arafat_day": "Arafat", "ramadan_start": "Ramadan", "saudi_founding_day": "Founding", "saudi_national_day": "National"}
EVENT_SHORT_AR = {"eid_al_fitr": "الفطر", "eid_al_adha": "الأضحى", "valentines_day": "الحب", "mothers_day_arab": "الأم", "new_years_eve": "رأس السنة",
                  "arafat_day": "عرفة", "ramadan_start": "رمضان", "saudi_founding_day": "التأسيس", "saudi_national_day": "الوطني"}
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def lang() -> str:
    try:
        import streamlit as st

        v = st.session_state.get("lang", "en")
    except Exception:  # no Streamlit runtime (plain unit tests)
        return "en"
    return v if v in LANGS else "en"


def is_rtl() -> bool:
    return lang() == "ar"


def L(en: str, ar: str) -> str:
    return ar if lang() == "ar" else en


def term_label(term: str) -> str:
    """English: 'flower shop · <Arabic term>'. Arabic: the Arabic term only. (Callers bidi-isolate the result where needed.)"""
    return term if lang() == "ar" else f"{TERM_EN.get(term, '')} · {term}".strip(" ·")


def term_name(term: str) -> str:
    """Short plain name without the Arabic original in English mode (used where space is tight)."""
    return term if lang() == "ar" else TERM_EN.get(term, term)


def event_label(ev: str) -> str:
    return (EVENT_AR if lang() == "ar" else EVENT_EN).get(ev, ev)


def event_short(ev: str) -> str:
    return (EVENT_SHORT_AR if lang() == "ar" else EVENT_SHORT_EN).get(ev, ev)


def month_name(m: int, short: bool = False) -> str:
    if lang() == "ar":
        return MONTHS_AR[int(m) - 1]
    n = MONTHS_EN[int(m) - 1]
    return n[:3] if short else n


def fdate(d, with_day: bool = True) -> str:
    """'14 Nov 2021' / '14 نوفمبر 2021' (Western digits in both languages)."""
    d = pd.Timestamp(d)
    mon = month_name(d.month, short=True) if lang() == "en" else MONTHS_AR[d.month - 1]
    return f"{d.day} {mon} {d.year}" if with_day else f"{mon} {d.year}"


def region_name(en: str, ar: str) -> str:
    """Region as displayed in the active language (Arabic name only in Arabic mode; 'English · Arabic' in English mode)."""
    return ar if lang() == "ar" else f"{en} · {isolate(ar)}"


def region_short(en: str, ar: str) -> str:
    return ar if lang() == "ar" else en


def ltr(text: str) -> str:
    """Keep a numeric expression (sign, brackets, %) in left-to-right order inside right-to-left text: '-3.1%', '[-0.89, 1.90]'."""
    return f"\u2066{text}\u2069" if is_rtl() else text
