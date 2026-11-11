"""Dashboard behaviour (headless AppTest): fail-closed integrity gate, forecast suppression, section rendering."""
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from bloom import config as C
from conftest import ROOT

APP = ROOT / "app" / "streamlit_app.py"
NAV = ["overview", "trend", "seasonality", "regions", "mix", "forecast", "data"]
pytestmark = pytest.mark.skipif(not (C.PROCESSED_DIR / "phase_a" / "forecast_status.json").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


def app(root, monkeypatch):
    monkeypatch.setenv("BLOOM_ROOT", str(root))
    return AppTest.from_file(str(APP), default_timeout=90).run()


def text(at):
    return " ".join([m.value for m in at.markdown] + [m.value for m in at.info] + [c.value for c in at.code])


def charts(at):
    return len(at.get("plotly_chart"))


def test_every_section_renders_without_exceptions(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    assert not at.exception and "integrity checks passed before anything was displayed" in text(at)
    for name in NAV:
        at.radio(key="section").set_value(name).run()
        assert not at.exception, name


def test_forecast_section_shows_no_forecast_when_gate_failed(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    at.radio(key="section").set_value("forecast").run()
    t = text(at)
    assert "No forecast is shown" in t and "Not passed" in t and "forecast (validated)" not in t
    assert charts(at) == 0  # no chart at all on the forecast section


def test_regions_section_renders_map_and_bar_for_every_term_and_view(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    at.radio(key="section").set_value("regions").run()
    for view in ("index", "share"):
        at.radio(key="reg_measure").set_value(view).run()
        for opt in at.selectbox(key="reg_term").options:
            at.selectbox(key="reg_term").select(opt).run()
            assert not at.exception, (view, opt)
            assert charts(at) == 2  # map + ranked bars


@pytest.mark.parametrize("mutate", ["raw", "processed", "validation", "provenance"])
def test_tampered_data_hides_all_analytics(built_project, tmp_path, monkeypatch, mutate):
    root = tmp_path / "p"
    shutil.copytree(built_project, root)
    if mutate == "raw":
        f = root / "data/raw/geoMap.csv"; f.write_bytes(f.read_bytes() + b" ")
    elif mutate == "processed":
        f = root / "data/processed/timeline_groupB_long.parquet"; f.write_bytes(f.read_bytes() + b"\0")
    elif mutate == "validation":
        (root / "data/processed/validation_results.json").unlink()
    else:
        (root / "data/processed/phase_a/_provenance.json").unlink()
    before = {str(p.relative_to(root)): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    at = app(root, monkeypatch)
    t = text(at)
    assert not at.exception
    assert "integrity check failed" in t and "analytics are hidden" in t
    assert "bloom.pipeline" in t  # safe re-run instructions are shown
    assert charts(at) == 0 and "Highest relative search interest" not in t and "Historical data coverage" not in t and not [r for r in at.radio if r.key == "section"]
    after = {str(p.relative_to(root)): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    assert before == after  # the dashboard never regenerates or modifies data


def test_map_is_hidden_but_comparison_remains_if_boundary_file_fails_verification(built_project, tmp_path, monkeypatch):
    root = tmp_path / "p"
    shutil.copytree(built_project, root)
    f = root / "data/geo/saudi_adm1_geoboundaries_simplified.geojson"
    f.write_bytes(f.read_bytes() + b" ")
    at = app(root, monkeypatch)
    at.radio(key="section").set_value("regions").run()
    assert not at.exception and "Map unavailable" in text(at)
    assert charts(at) == 1  # ranked comparison (all 13 regions) still shown; no map


# ---------------------------------------------------------------------------- new in the final refinement
def test_overview_kpis_are_computed_and_defined(built_project, monkeypatch):
    import pandas as pd
    from bloom.overview import top_region
    at = app(built_project, monkeypatch)
    t = text(at)
    idx = pd.read_parquet(built_project / "data/processed/phase_a/regional_index_by_term.parquet")
    top = top_region(idx, "محل ورد")
    for needle in ("Verified data coverage", "Regions covered", "National trend", "Strongest documented seasonal observation", "Selected region"):
        assert needle in t, needle
    assert "Highest relative search interest for" in t and top["region_en"] in t   # carefully labelled regional insight
    assert "13 of 13" in t and "260 weeks" in t
    assert "no causal" in t                                                       # seasonal KPI definition
    assert any("Technical details and caveats" in e.label for e in at.expander)  # definitions and caveats sit in an expander, not removed


def test_overview_regional_insight_carries_all_required_caveats(built_project, monkeypatch):
    t = text(app(built_project, monkeypatch)).lower()
    for needle in ("relative", "normali", "not absolute", "different metrics", "sampling stability"):
        assert needle in t or needle.replace("not absolute", "absolute") in t, needle
    assert "not sales" in t or "not search volume" in t or "sales" in t           # never presented as sales/demand


def test_overview_states_city_level_is_not_implemented_and_has_no_city_charts(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    t = text(at)
    assert "not implemented" in t and "city" in t.lower()
    for city in ("Riyadh", "Jeddah", "Dammam"):          # no city statistics are shown anywhere on the homepage
        assert f"{city}:" not in t


def test_every_chart_section_has_a_text_alternative(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    assert "Text alternative" in text(at)
    for sec in ("trend", "seasonality", "regions", "mix"):
        at.radio(key="section").set_value(sec).run()
        assert not at.exception and "Text alternative" in text(at), sec


def test_overview_region_selection_by_widget_updates_detail_card(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    opts = at.selectbox(key="ov_region").options
    at.selectbox(key="ov_region").set_value(opts[-1]).run()
    assert not at.exception and "Selected region" in text(at)


def test_regional_comparison_updates_from_selection(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    at.radio(key="section").set_value("regions").run()
    at.session_state["compare"] = ["SA-09", "SA-10"]            # what a map click does (toggle_from_map is unit-tested)
    at.run()
    assert not at.exception
    df = [d.value for d in at.dataframe if "Below peak" in list(d.value.columns)]
    assert df and list(df[0]["Region"].str.split(" · ").str[0]) == ["Jazan", "Najran"] and list(df[0]["Rank"]) == ["1/13", "3/13"]
    assert "Among the selected regions, Jazan has the highest index" in text(at)
    at.button(key="clear_cmp").click().run()
    assert at.session_state["compare"] == [] and "Click a region on the map" in text(at)


def test_compare_with_missing_region_shows_no_data_never_zero(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    at.radio(key="section").set_value("regions").run()
    at.selectbox(key="reg_term").select("شراء ورد").run()
    at.session_state["compare"] = ["SA-06", "SA-09"]            # Hail has no data for this term
    at.run()
    d = [x.value for x in at.dataframe if "Below peak" in list(x.value.columns)][0]
    hail = d[d["Region"].str.startswith("Hail")].iloc[0]
    assert hail["Status"] == "No data" and hail["Index"] == "—" and hail["Rank"] == "—"


def test_forecast_section_explains_the_decision(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    at.radio(key="section").set_value("forecast").run()
    t = text(at)
    for needle in ("Engineering quality decision", "What was evaluated", "Why it was withheld", "What additional evidence would be needed", "seasonal naive",
                   "Thresholds stay as they are"):
        assert needle in t, needle
    assert charts(at) == 0


def test_seasonality_separates_observed_event_and_hypothesis(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    at.radio(key="section").set_value("seasonality").run()
    t = text(at)
    assert all(h in t for h in ("Observed seasonal patterns", "Event-associated changes (descriptive)", "Hypotheses requiring validation", "Year-over-year overlay"))
    import re
    assert not re.search(r"\b(causes?|caused by|because of|drives?|driven by|due to|leads? to|results? in)\b", re.sub(r"<[^>]+>", " ", t), re.I)  # no causal claims
    assert charts(at) == 3  # year-over-year, month profile, event lift


def test_data_engineering_does_not_present_inferred_dates_as_verified(built_project, monkeypatch):
    import json
    at = app(built_project, monkeypatch)
    at.radio(key="section").set_value("data").run()
    t = text(at)
    assert "not a verified retrieval date" in t and "not live or real-time monitoring" in t
    cols = [list(d.value.columns) for d in at.dataframe]
    assert any("File modified (inferred, not verified)" in c for c in cols) and not any("Retrieved" in " ".join(c) for c in cols)
    prov = json.loads((built_project / "data/processed/_provenance.json").read_text(encoding="utf-8"))
    assert prov["generated_at_utc"].startswith("20") and prov["generated_at_utc"] in " ".join(str(d.value.values.tolist()) for d in at.dataframe)


def test_all_six_sections_have_no_exceptions_with_selection_state(built_project, monkeypatch):
    at = app(built_project, monkeypatch)
    at.session_state["compare"] = ["SA-01", "SA-09"]
    for name in NAV:
        at.radio(key="section").set_value(name).run()
        assert not at.exception, name


def test_overview_states_scope_country_period_terms_and_source(built_project, monkeypatch):
    """The overview must say where, when, which five terms, which source and that values are relative interest (both languages)."""
    import re
    terms = ["ورد", "محل ورد", "توصيل ورد", "بوكيه ورد", "شراء ورد"]
    clean = lambda s: re.sub("[\u2066-\u2069\u200e\u200f]", "", re.sub("<[^>]+>", "", s)).replace("\xa0", " ")
    en = clean(text(app(built_project, monkeypatch)))
    assert "Study scope: Saudi Arabia" in en and "about five years" in en and "Google Trends" in en
    assert "2021" in en and "2026" in en and all(t in en for t in terms)
    assert "not sales" in en and "relative" in en.lower()
    monkeypatch.setenv("BLOOM_ROOT", str(built_project))
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["lang"] = "ar"
    ar = clean(text(at.run()))
    assert "نطاق الدراسة: المملكة العربية السعودية" in ar and "نحو خمس سنوات" in ar and all(t in ar for t in terms)
    assert "الاهتمام النسبي" in ar and "Google Trends" in ar
