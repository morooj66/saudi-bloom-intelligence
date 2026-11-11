"""Behaviour of a fresh clone that has NO Google Trends data (the exports are not shipped). These tests need no data and always run.
They also guard the policy that an empty installation must fail closed with a clear message, never pass quietly."""
import json

import pytest
from streamlit.testing.v1 import AppTest

from bloom import config as C
from bloom.ingest import missing_exports
from bloom.integrity import verify
from conftest import ROOT, run_cli


def _entry(group, kind):
    return {"comparison_group": group, "kind": kind}


FULL = ([_entry(C.GROUP_A, "timeline"), _entry(C.GROUP_B, "timeline"), _entry(C.GROUP_A, "geomap"), _entry(C.GROUP_B4_SHARE, "geomap")]
        + [_entry(f"{C.GROUP_SINGLE_PREFIX}{t}", "geomap") for t in C.ALL_TERMS])


def test_complete_set_of_nine_exports_has_no_gaps():
    assert len(FULL) == 9 and missing_exports(FULL) == []


def test_missing_exports_are_named_in_plain_language():
    gaps = missing_exports(FULL[:-2])
    assert len(gaps) == 2 and all("regional index for the single term" in g for g in gaps)
    assert len(missing_exports([])) == 9


def test_pipeline_on_a_folder_without_exports_exits_2_with_instructions_and_writes_nothing(tmp_path):
    r = run_cli("bloom.pipeline", tmp_path)
    assert r.returncode == 2 and "No Google Trends exports found" in r.stderr and "incoming_data" in r.stderr
    assert not (tmp_path / "data").exists()


def test_pipeline_with_a_partial_set_names_what_is_missing(tmp_path):
    inc = tmp_path / "incoming_data"; inc.mkdir()
    real = ROOT / "incoming_data" / "geoMap.csv"
    if not real.exists():
        pytest.skip("data-dependent test: needs one real export to build a partial set")
    (inc / "geoMap.csv").write_bytes(real.read_bytes())
    r = run_cli("bloom.pipeline", tmp_path)
    assert r.returncode == 2 and "Incomplete set of Google Trends exports" in r.stderr and "group B4" in r.stderr


def test_integrity_of_an_empty_installation_fails_closed():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        rep = verify(Path(d))
    assert not rep.ok and any(c["name"] == "validation report exists" for c in rep.failures)


def test_dashboard_without_data_shows_a_clear_message_and_no_analytics(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOOM_ROOT", str(tmp_path))
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    text = " ".join(m.value for m in at.markdown)
    assert not at.exception
    assert "No Google Trends data found" in text and "incoming_data" in text and "Bring your own data" in text
    assert "analytics are hidden" in text
    assert len(at.get("plotly_chart")) == 0 and not [r for r in at.radio if r.key == "section"]
    assert any("bloom.pipeline" in c.value for c in at.code)          # the recovery commands are shown


def test_shipped_boundary_data_is_present_and_verified_without_any_trends_data():
    from bloom.geo import verify_geo
    ok, detail = verify_geo(ROOT)
    assert ok, detail
