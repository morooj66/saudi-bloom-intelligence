"""C2: corrupted/invalid input must fail the pipeline (non-zero exit) and must not produce processed analytics."""
import re
import shutil

import pytest

from bloom.integrity import verify
from conftest import run_cli


def _edit(path, fn):
    t = path.read_text(encoding="utf-8")
    new = fn(t)
    assert new != t, "test fixture edit did not change the file"
    path.write_text(new, encoding="utf-8")


def _no_outputs(root):
    proc = root / "data" / "processed"
    return not (proc / "_provenance.json").exists() and not list(proc.glob("timeline_*.parquet"))


def test_clean_input_succeeds_and_verifies(project):
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 0, r.stderr
    assert (project / "data" / "processed" / "_provenance.json").exists()
    assert verify(project, stage="processed").ok


def test_out_of_range_value_fails_with_exit_1(project):
    _edit(project / "incoming_data" / "multiTimeline (1).csv", lambda t: t.replace("2022-02-13,20,20,65,0", "2022-02-13,250,20,65,0"))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 1
    assert "values_in_0_100" in r.stderr and _no_outputs(project)
    assert not verify(project).ok


def test_duplicate_week_fails(project):
    f = project / "incoming_data" / "multiTimeline.csv"
    _edit(f, lambda t: t.replace("2021-11-14,", "2021-11-07,", 1))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 1 and "no_duplicate_dates" in r.stderr and _no_outputs(project)


def test_missing_week_gap_fails(project):
    f = project / "incoming_data" / "multiTimeline.csv"
    _edit(f, lambda t: re.sub(r"2022-03-06,[^\n]*\n", "", t))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 1 and "frequency_constant_7d" in r.stderr


def test_non_sunday_week_start_fails(project):
    f = project / "incoming_data" / "multiTimeline.csv"
    _edit(f, lambda t: t.replace("2022-03-06,", "2022-03-07,"))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 1 and "weeks_start_on_sunday" in r.stderr


def test_dropped_region_fails_coverage(project):
    f = project / "incoming_data" / "geoMap (4).csv"
    _edit(f, lambda t: re.sub(r"منطقة الرياض,\d+\n", "", t))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 1 and "regional_coverage_13" in r.stderr


def test_unknown_region_name_fails_with_exit_2(project):
    f = project / "incoming_data" / "geoMap (4).csv"
    _edit(f, lambda t: t.replace("منطقة الرياض", "إمارة دبي"))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 2 and "Unknown Saudi region" in r.stderr and _no_outputs(project)


def test_unparseable_cell_fails_with_exit_2(project):
    _edit(project / "incoming_data" / "multiTimeline (1).csv", lambda t: t.replace("2022-02-13,20,", "2022-02-13,N/A,"))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 2 and "Unrecognised value format" in r.stderr


def test_wrong_term_set_fails_with_exit_2(project):
    _edit(project / "incoming_data" / "multiTimeline (1).csv", lambda t: t.replace("شراء ورد", "ورد رخيص"))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 2


def test_changed_input_after_first_run_is_rejected(project):
    assert run_cli("bloom.pipeline", project).returncode == 0
    f = project / "incoming_data" / "multiTimeline.csv"
    _edit(f, lambda t: t.replace("2022-03-06,", "2022-03-06,", 1).replace("\n2021-11-14,61", "\n2021-11-14,62"))
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 2 and "Refusing to overwrite" in r.stderr
    # raw copy is untouched
    assert "2021-11-14,61" in (project / "data" / "raw" / "multiTimeline.csv").read_text(encoding="utf-8")


def test_manifest_is_append_only(project):
    assert run_cli("bloom.pipeline", project).returncode == 0
    (project / "incoming_data" / "geoMap (3).csv").unlink()
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 2 and "append-only" in r.stderr


def test_phase_a_refuses_unverified_inputs(project):
    assert run_cli("bloom.pipeline", project).returncode == 0
    p = project / "data" / "processed" / "timeline_groupB_long.csv"
    p.write_bytes(p.read_bytes() + b"\n")
    r = run_cli("bloom.phase_a", project)
    assert r.returncode == 1 and "integrity" in r.stderr.lower()
    assert not (project / "data" / "processed" / "phase_a").exists()


def test_failed_rerun_leaves_integrity_failing(project):
    """After a good run, a failing run must not leave a state the dashboard would accept."""
    assert run_cli("bloom.pipeline", project).returncode == 0
    assert run_cli("bloom.phase_a", project).returncode == 0
    assert verify(project).ok
    # a second timeline export for an already-present comparison group is ambiguous -> pipeline must fail
    shutil.copy2(project / "incoming_data" / "multiTimeline.csv", project / "incoming_data" / "multiTimeline (2).csv")
    r = run_cli("bloom.pipeline", project)
    assert r.returncode == 2 and "would overwrite" in r.stderr
    assert not verify(project).ok  # manifest now lists inputs the validated outputs were not built from
