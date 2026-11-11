"""Bilingual interface (العربية | English): one shared analytical source, language changes TEXT only.
AppTest note: widget labels are language dependent, so an Arabic session is built with ONE run from a pre-set session state."""
import re

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import sys
from conftest import ROOT

sys.path[:0] = [str(ROOT / "app")]
import i18n as I  # noqa: E402

from bloom import config as C  # noqa: E402
from bloom.overview import (map_text_alternative, region_comparison, series_text_alternative, term_mix_text_alternative)  # noqa: E402

APP = ROOT / "app" / "streamlit_app.py"
SECTIONS = ["overview", "trend", "seasonality", "regions", "mix", "forecast", "data"]
ARABIC = re.compile(r"[؀-ۿ]")
P = C.PROCESSED_DIR
needs_data = pytest.mark.skipif(not (P / "phase_a" / "forecast_status.json").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


def session(root, monkeypatch, lang, section="overview", **state):
    monkeypatch.setenv("BLOOM_ROOT", str(root))
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.session_state["lang"], at.session_state["section"] = lang, section
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def md(at):
    return " ".join(m.value for m in at.markdown)


def visible(at):
    """Text a reader sees: markdown without <style> blocks and code, plus expander labels."""
    t = re.sub(r"<style>.*?</style>", "", md(at), flags=re.S)
    return t + " " + " ".join(e.label for e in at.expander)


# ------------------------------------------------------------------------------------------------ i18n helpers (no data needed)
def test_every_event_term_and_month_has_an_arabic_name():
    assert set(I.EVENT_EN) == set(I.EVENT_AR) == set(I.EVENT_SHORT_EN) == set(I.EVENT_SHORT_AR)
    assert all(ARABIC.search(v) for v in [*I.EVENT_AR.values(), *I.EVENT_SHORT_AR.values(), *I.MONTHS_AR]) and len(I.MONTHS_AR) == len(I.MONTHS_EN) == 12
    assert set(I.TERM_EN) == {C.GENERAL_TERM, *C.COMMERCIAL_TERMS}


def test_language_defaults_to_english_outside_a_session_and_dates_use_western_digits():
    assert I.lang() == "en" and not I.is_rtl()
    assert I.fdate("2021-11-14") == "14 Nov 2021"
    assert I.event_label("eid_al_fitr") == "Eid al-Fitr" and I.term_label("محل ورد").startswith("flower shop")


# ------------------------------------------------------------------------------------------------ same numbers in both languages
def digits(text):
    return [re.sub(r"^0+(?=\d)", "", x) for x in re.findall(r"\d+(?:\.\d+)?", text)]       # "07 Nov" and "7 نوفمبر" are the same number


@needs_data
def test_text_alternatives_carry_identical_numbers_in_both_languages():
    idx = pd.read_parquet(P / "phase_a" / "regional_index_by_term.parquet")
    d = idx[idx["term"] == "شراء ورد"]
    assert digits(map_text_alternative(d, "x", "en")) == digits(map_text_alternative(d, "x", "ar"))
    assert ARABIC.search(map_text_alternative(d, "x", "ar")) and "regions have values" in map_text_alternative(d, "x", "en")
    b = pd.read_parquet(P / "timeline_groupB_long.parquet").query("term == 'محل ورد'")
    en, ar = series_text_alternative(b, "x", lang="en"), series_text_alternative(b, "x", lang="ar")
    assert digits(en) == digits(ar) and ARABIC.search(ar)
    mix = pd.read_parquet(P / "region_groupB4_share.parquet")
    assert digits(term_mix_text_alternative(mix, lang="en")) == digits(term_mix_text_alternative(mix, lang="ar"))
    assert "مخفية" in term_mix_text_alternative(mix, lang="ar") and "بلا بيانات" in term_mix_text_alternative(mix, lang="ar")


@needs_data
def test_region_comparison_values_and_states():
    idx = pd.read_parquet(P / "phase_a" / "regional_index_by_term.parquet")
    d = idx[idx["term"] == "محل ورد"]
    jaz, asir = region_comparison(d, "SA-09"), region_comparison(d, "SA-14")
    assert jaz["is_peak"] and jaz["rank"] == 1 and jaz["peak_en"] == "Jazan" and jaz["peak_ar"] == "جازان" and jaz["ratio_to_peak"] == 1.0
    assert not asir["is_peak"] and asir["peak_value"] == 100 and asir["ratio_to_peak"] == pytest.approx(asir["value"] / 100) and asir["gap_to_peak"] == 100 - asir["value"]
    miss = idx[idx["term"] == "شراء ورد"]
    hail = region_comparison(miss, "SA-06")
    assert hail["status"] == "No data" and hail["value"] is None and hail["ratio_to_peak"] is None and not hail["is_peak"]   # never a number for a missing region


# ------------------------------------------------------------------------------------------------ the dashboard in Arabic and English
@needs_data
@pytest.mark.parametrize("section", SECTIONS)
def test_every_section_renders_in_arabic_without_exceptions_and_with_rtl_css(built_project, monkeypatch, section):
    at = session(built_project, monkeypatch, "ar", section)
    assert not at.exception
    assert "direction: rtl" in md(at) and "Noto Sans Arabic" in md(at)
    assert ARABIC.search(visible(at))


@needs_data
def test_english_is_ltr_without_rtl_rules(built_project, monkeypatch):
    at = session(built_project, monkeypatch, "en")
    assert "direction: rtl" not in md(at) and not at.exception


@needs_data
def test_navigation_labels_and_language_switch_are_bilingual(built_project, monkeypatch):
    en, ar = session(built_project, monkeypatch, "en"), session(built_project, monkeypatch, "ar")
    assert [o for o in en.radio(key="section").options] == ["Overview", "National trend", "Seasonality", "Regions & map", "Commercial-term mix", "Forecast", "Data engineering"]
    assert ar.radio(key="section").options == ["نظرة عامة", "الاتجاه الوطني", "الموسمية", "المناطق والخريطة", "تركيبة المصطلحات التجارية", "التوقع", "هندسة البيانات"]
    assert en.radio(key="lang").options == ["العربية", "English"] and ar.radio(key="lang").options == ["العربية", "English"]   # the switch itself is identical in both


@needs_data
def test_language_and_section_persist_when_switching_language(built_project, monkeypatch):
    monkeypatch.setenv("BLOOM_ROOT", str(built_project))
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    at.radio(key="section").set_value("regions").run()
    assert at.session_state["section"] == "regions" and "Regional comparison across the 13 regions" in md(at)
    at.radio(key="lang").set_value("ar").run()                        # one switch run; the section is kept
    assert at.session_state["lang"] == "ar" and at.session_state["section"] == "regions" and not at.exception
    assert "قارن المناطق" in " ".join(w.label for w in at.multiselect) and "المقارنة المرتّبة" in md(at)


@needs_data
def test_query_parameters_seed_language_and_section(built_project, monkeypatch):
    monkeypatch.setenv("BLOOM_ROOT", str(built_project))
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["lang"], at.query_params["section"] = "ar", "mix"
    at.run()
    assert at.session_state["lang"] == "ar" and at.session_state["section"] == "mix" and "تركيبة المصطلحات التجارية" in md(at)


@needs_data
def test_no_long_untranslated_english_sentences_in_arabic_mode(built_project, monkeypatch):
    allowed = re.compile(r"Open Data Commons Open Database License")     # licence name copied from the boundary file's own SOURCE.json
    for section in SECTIONS:
        t = re.sub(r"<[^>]+>|`[^`]*`|https?://\S+", " ", visible(session(built_project, monkeypatch, "ar", section)))
        runs = [r for r in re.findall(r"(?:[A-Za-z][A-Za-z'’\-]*\s+){3,}[A-Za-z][A-Za-z'’\-]*", t) if not allowed.search(r)]
        assert not runs, (section, runs[:3])


@needs_data
def test_map_region_card_in_arabic_uses_arabic_names_same_values_and_states(built_project, monkeypatch):
    en = session(built_project, monkeypatch, "en", "overview", ov_region="SA-14")
    ar = session(built_project, monkeypatch, "ar", "overview", ov_region="SA-14")
    card_en = re.search(r'<div class="panel region-card">.*?</div></div>', md(en), re.S).group(0)
    card_ar = re.search(r'<div class="panel region-card">.*?</div></div>', md(ar), re.S).group(0)
    assert digits(re.sub(r"<[^>]+>", " ", card_en)) == digits(re.sub(r"<[^>]+>", " ", card_ar))             # same index, rank, gap, ratio
    assert "عسير" in card_ar and "الترتيب" in card_ar and "Asir" in card_en and "Rank" in card_en
    assert "جازان" in card_ar and "Jazan" in card_en                                                         # compared with the highest-index region
    assert "ليست حجم بحث ولا مبيعات" in card_ar and "not search volume, sales or demand" in card_en           # never implies sales or volume


@needs_data
def test_map_card_distinguishes_censored_missing_and_numeric(built_project, monkeypatch):
    for lang, missing_txt in (("en", "No data reported by Google Trends"), ("ar", "لم يبلّغ Google Trends عن بيانات")):
        at = session(built_project, monkeypatch, lang, "overview", ov_term="شراء ورد", ov_region="SA-06")    # Hail: no data for this term
        assert missing_txt in md(at) and "—" in md(at) and not at.exception


@needs_data
def test_homepage_keeps_jazan_first_and_all_required_caveats_in_both_languages(built_project, monkeypatch):
    en, ar = md(session(built_project, monkeypatch, "en")), md(session(built_project, monkeypatch, "ar"))
    assert "Highest relative search interest for" in en and "Jazan" in en and "not sales or search volume" in en
    assert "أعلى اهتمام نسبي بالبحث عن" in ar and "جازان" in ar and "ليس مبيعات ولا حجم بحث" in ar
    for t in (en, ar):
        assert 'class="kpis"' in t and len(re.findall(r'<div class="kpi(?: [a-z]*)">', t)) == 4   # the four KPI cards (the container is class="kpis")


@needs_data
def test_forecast_stays_withheld_in_arabic(built_project, monkeypatch):
    at = session(built_project, monkeypatch, "ar", "forecast")
    assert len(at.get("plotly_chart")) == 0 and "التوقع محجوب" in md(at) and "لم تُجتَز" in md(at)
