"""Raw-preservation behaviour using temporary directories (tiny parser fixtures, not analysis data)."""
import json
import shutil

import pytest

from bloom import config as C
from bloom.ingest import assign_group, build_manifest

TIMELINE = (
    "الفئة: جميع الفئات\n\nالأسبوع.,توصيل ورد: (المملكة العربية السعودية),بوكيه ورد: (المملكة العربية السعودية),"
    "محل ورد: (المملكة العربية السعودية),شراء ورد: (المملكة العربية السعودية)\n2021-11-07,1,2,3,0\n"
)


def _setup(tmp_path):
    inc, raw = tmp_path / "inc", tmp_path / "raw"
    inc.mkdir()
    (inc / "t.csv").write_text(TIMELINE, encoding="utf-8")
    return inc, raw, tmp_path / "m.json", tmp_path / "m.csv"


def test_manifest_copies_and_hashes(tmp_path):
    inc, raw, mj, mc = _setup(tmp_path)
    entries = build_manifest(inc, raw, mj, mc, root=tmp_path)
    assert entries[0]["comparison_group"] == C.GROUP_B
    assert (raw / "t.csv").read_bytes() == (inc / "t.csv").read_bytes()
    assert len(entries[0]["sha256"]) == 64 and json.loads(mj.read_text(encoding="utf-8"))


def test_never_overwrites_raw(tmp_path):
    inc, raw, mj, mc = _setup(tmp_path)
    build_manifest(inc, raw, mj, mc, root=tmp_path)
    (inc / "t.csv").write_text(TIMELINE.replace("2021-11-07,1", "2021-11-07,9"), encoding="utf-8")
    with pytest.raises(RuntimeError):
        build_manifest(inc, raw, mj, mc, root=tmp_path)
    assert "2021-11-07,1," in (raw / "t.csv").read_text(encoding="utf-8")


def test_group_assignment():
    assert assign_group("timeline", list(C.ALL_TERMS)) == C.GROUP_A
    assert assign_group("timeline", list(C.COMMERCIAL_TERMS)) == C.GROUP_B
    assert assign_group("geomap", ["ورد"]).startswith(C.GROUP_SINGLE_PREFIX)
    with pytest.raises(ValueError):
        assign_group("timeline", ["ورد", "محل ورد"])
