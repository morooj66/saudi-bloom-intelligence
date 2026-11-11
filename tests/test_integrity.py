"""C1: the integrity check is fail-closed. Every mutation below is made on a temp COPY of a fully built project."""
import json
import shutil

import pandas as pd
import pytest

from bloom import integrity
from bloom.integrity import verify
from bloom.pipeline import write_provenance


def names(rep):
    return {c["name"] for c in rep.failures}


def test_built_project_verifies(built_project):
    rep = verify(built_project)
    assert rep.ok, rep.failures
    assert len(rep.checks) >= 15  # not vacuous


def test_empty_directory_fails_closed(tmp_path):
    rep = verify(tmp_path)
    assert not rep.ok and "validation report exists" in names(rep)


def test_missing_validation_report(fresh_copy):
    (fresh_copy / "data/processed/validation_results.json").unlink()
    assert "validation report exists" in names(verify(fresh_copy))


def test_validation_errors_nonzero(fresh_copy):
    p = fresh_copy / "data/processed/validation_results.json"
    v = json.loads(p.read_text(encoding="utf-8")); v["summary"]["errors"] = 1
    p.write_text(json.dumps(v), encoding="utf-8")
    assert "validation errors == 0" in names(verify(fresh_copy))


def test_corrupt_json_fails_closed(fresh_copy):
    (fresh_copy / "data/processed/validation_results.json").write_text("{", encoding="utf-8")
    rep = verify(fresh_copy)
    assert not rep.ok and "integrity verification ran without error" in names(rep)


def test_tampered_raw_file(fresh_copy):
    f = fresh_copy / "data/raw/multiTimeline.csv"
    f.write_bytes(f.read_bytes() + b" ")
    assert "raw file hashes match manifest" in names(verify(fresh_copy))


def test_unmanifested_raw_file(fresh_copy):
    shutil.copy2(fresh_copy / "data/raw/multiTimeline.csv", fresh_copy / "data/raw/extra.csv")
    assert "no un-manifested raw files" in names(verify(fresh_copy))


def test_missing_raw_file(fresh_copy):
    (fresh_copy / "data/raw/geoMap.csv").unlink()
    assert "raw file hashes match manifest" in names(verify(fresh_copy))


def test_tampered_processed_dataset(fresh_copy):
    f = fresh_copy / "data/processed/region_groupA_share.parquet"
    f.write_bytes(f.read_bytes() + b"\0")
    assert "processed: output hashes match provenance" in names(verify(fresh_copy))


def test_stale_processed_data_fingerprint(fresh_copy):
    p = fresh_copy / "data/processed/_provenance.json"
    prov = json.loads(p.read_text(encoding="utf-8")); prov["input_fingerprint"] = "0" * 64
    p.write_text(json.dumps(prov), encoding="utf-8")
    assert "processed data derived from current raw inputs" in names(verify(fresh_copy))


def test_missing_required_column_is_detected_even_with_valid_hashes(fresh_copy):
    proc = fresh_copy / "data/processed"
    f = proc / "series_profile.parquet"
    df = pd.read_parquet(f).drop(columns=["candidate_for_forecasting"])
    df.to_parquet(f, index=False)
    prov = json.loads((proc / "_provenance.json").read_text(encoding="utf-8"))
    write_provenance(proc, prov["input_fingerprint"], {"validation_errors": 0})  # hashes now consistent
    rep = verify(fresh_copy)
    assert "processed: required datasets and schemas" in names(rep)
    assert "processed: output hashes match provenance" not in names(rep)


def test_missing_required_dataset(fresh_copy):
    (fresh_copy / "data/processed/calendar_events.parquet").unlink()
    assert {"processed: output hashes match provenance", "processed: required datasets and schemas"} & names(verify(fresh_copy))


def test_phase_a_bound_to_processed_data(fresh_copy):
    """Re-running only the pipeline (new processed provenance) must invalidate the old phase_a outputs."""
    proc = fresh_copy / "data/processed"
    prov = json.loads((proc / "_provenance.json").read_text(encoding="utf-8"))
    write_provenance(proc, prov["input_fingerprint"], {"validation_errors": 0, "rerun": True})
    assert "phase_a bound to current processed data" in names(verify(fresh_copy))


def test_gate_constant_drift_detected(fresh_copy, monkeypatch):
    monkeypatch.setattr(integrity, "GATE_MIN_IMPROVEMENT", 0.01)
    assert "forecast-gate constants unchanged" in names(verify(fresh_copy))


def test_forecast_file_present_while_gate_failed(fresh_copy):
    pd.DataFrame({"target_week": [pd.Timestamp("2026-11-08")], "forecast": [40.0]}).to_parquet(fresh_copy / "data/processed/phase_a/forecast_national.parquet")
    assert "forecast suppression consistent" in names(verify(fresh_copy))


def test_status_claims_published_without_passing_gate(fresh_copy):
    p = fresh_copy / "data/processed/phase_a/forecast_status.json"
    s = json.loads(p.read_text(encoding="utf-8")); s["forecast"]["forecast_published"] = True
    p.write_text(json.dumps(s), encoding="utf-8")
    rep = verify(fresh_copy)
    assert not rep.ok  # either hash mismatch or suppression inconsistency; both are failures


def test_verify_never_modifies_files(fresh_copy):
    def snap():
        return {str(p.relative_to(fresh_copy)): (p.stat().st_mtime_ns, p.stat().st_size) for p in fresh_copy.rglob("*") if p.is_file()}
    before = snap()
    verify(fresh_copy)
    assert snap() == before
