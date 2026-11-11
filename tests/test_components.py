"""Dashboard components: all 13 regions, missing/censored never zero, scale guard, event annotations, bidi."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import components as K  # noqa: E402
from bidi import FSI, PDI, isolate, strip_isolates  # noqa: E402
from bloom import config as C  # noqa: E402
from bloom.geo import load_geojson, rewind_for_plotly  # noqa: E402
from bloom.regions import ISO_CODES  # noqa: E402
from bloom.schema import ScaleMixError  # noqa: E402

P = C.PROCESSED_DIR
pytestmark = pytest.mark.skipif(not (P / "phase_a" / "forecast_status.json").exists(), reason="data-dependent: supply your own Google Trends exports, then run bloom.pipeline and bloom.phase_a (README: Bring your own data)")


@pytest.fixture(scope="module")
def idx():
    return pd.read_parquet(P / "phase_a" / "regional_index_by_term.parquet")


@pytest.fixture(scope="module")
def share():
    return pd.read_parquet(P / "phase_a" / "regional_share_groupA.parquet")


def test_every_term_view_has_13_regions_with_explicit_status(idx, share):
    for frame in (idx, share):
        for term, d in frame.groupby("term"):
            s = K.region_status(d)
            assert set(s["region_iso"]) == set(ISO_CODES) and len(s) == 13
            assert set(s["status"]) <= {"Available", "Censored (<1%)", "No data"}


def test_missing_and_censored_values_are_never_zero(idx, share):
    seen = 0
    for frame in (idx, share):
        for _, d in frame.groupby("term"):
            s = K.region_status(d)
            nonavail = s[s["status"] != "Available"]
            seen += len(nonavail)
            assert nonavail["value"].isna().all()
    assert seen >= 10  # the real data do contain missing and censored cells


def test_region_status_refuses_to_mix_terms_or_scales(idx):
    with pytest.raises(ScaleMixError):
        K.region_status(idx)  # five single-term exports = five different normalisations


def test_coverage_chips_report_real_counts(idx):
    html = K.coverage_chips(idx[idx["term"] == "شراء ورد"])
    assert "8 available" in html and "5 no data" in html and "0 censored" in html and "bad" in html
    assert "13 available" in K.coverage_chips(idx[idx["term"] == "محل ورد"])


def test_known_missing_regions_for_buy_flowers(idx):
    s = K.region_status(idx[idx["term"] == "شراء ورد"])
    assert sorted(s.loc[s["status"] == "No data", "region_iso"]) == sorted(["SA-06", "SA-08", "SA-10", "SA-11", "SA-12"])


def test_bar_chart_lists_all_13_and_draws_no_bar_for_missing(idx):
    d = idx[idx["term"] == "شراء ورد"]
    fig = K.region_bar(d, "index")
    order = list(fig.layout.yaxis.categoryarray)
    assert len(order) == 13 and set(order) == set(d["region_en"])
    bars = [t for t in fig.data if t.type == "bar"][0]
    missing_names = set(K.region_status(d).query("status == 'No data'")["region_en"])
    assert not (set(bars.y) & missing_names)  # missing regions are not drawn as bars
    assert all(v > 0 for v in bars.x)


def test_map_covers_all_13_regions_across_available_censored_nodata(idx, share):
    gj = rewind_for_plotly(load_geojson())
    for frame, term in ((idx, "شراء ورد"), (share, "توصيل ورد"), (idx, "محل ورد")):
        d = frame[frame["term"] == term]
        fig = K.region_map(d, gj, term, "metric")
        locs = [l for t in fig.data if t.type == "choropleth" for l in t.locations]
        assert sorted(locs) == sorted(ISO_CODES)  # exactly the 13 regions, each once
    d = share[share["term"] == "توصيل ورد"]  # has censored cells
    fig = K.region_map(d, gj, "توصيل ورد", "metric")
    grey_or_purple = [t for t in fig.data if t.type == "choropleth" and list(t.z) == [0] * len(t.z)]
    assert grey_or_purple  # censored/no-data are drawn as explicit non-scale colours, not as value 0 on the scale


def test_series_chart_refuses_mixed_scales():
    a = pd.read_parquet(P / "timeline_groupA_long.parquet").query("term == 'ورد'")
    b = pd.read_parquet(P / "timeline_groupB_long.parquet").query("term == 'محل ورد'")
    with pytest.raises(ScaleMixError):
        K.series_chart(pd.concat([a, b]))
    K.series_chart(b)  # single scale is fine


def test_event_annotations_are_labelled_and_distinguish_unverified():
    b = pd.read_parquet(P / "timeline_groupB_long.parquet").query("term == 'محل ورد'")
    ev = pd.read_parquet(P / "calendar_events.parquet").query("event in ['eid_al_fitr', 'eid_al_adha']")
    fig = K.series_chart(b, events=ev)
    texts = [a.text for a in fig.layout.annotations]
    assert any(t.startswith("Fitr") for t in texts) and any(t.startswith("Adha") for t in texts)
    hovers = [a.hovertext for a in fig.layout.annotations if a.hovertext]
    assert any("Eid al-Fitr" in h and "verified against a Saudi announcement" in h for h in hovers) and any("not independently verified" in h for h in hovers)  # full name, date and status on hover
    assert any(t.endswith("†") for t in texts)  # computed-but-unverified dates are marked
    dashes = {s.line.dash for s in fig.layout.shapes}
    assert dashes == {"solid", "dash"}
    verified_n = (ev["verification"] == "verified_announced").sum()
    in_range = ev[(ev["date"] >= b["week_start"].min()) & (ev["date"] <= b["week_start"].max() + pd.Timedelta(days=6))]
    assert sum(s.line.dash == "solid" for s in fig.layout.shapes) == (in_range["verification"] == "verified_announced").sum() and verified_n > 0


def test_bidi_isolation():
    s = isolate("flower shop · محل ورد, 98%")
    assert FSI in s and PDI in s and s.count(FSI) == 1 and strip_isolates(s).replace("\u00a0", " ") == "flower shop · محل ورد, 98%"
    assert "محل\u00a0ورد" in s  # Arabic phrase cannot wrap across lines
    assert isolate(s) == s  # idempotent
    assert isolate("plain english 12%") == "plain english 12%"
    assert K.label("محل ورد").startswith("flower shop") and FSI in K.label("محل ورد")
