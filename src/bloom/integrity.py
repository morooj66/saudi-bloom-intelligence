"""Fail-closed data-integrity verification. Read-only: never regenerates or modifies data.

verify(root) returns an IntegrityReport; the dashboard shows analytics only if `report.ok`.
CLI:  PYTHONPATH=src .venv/bin/python -m bloom.integrity   (exit 0 = verified, 1 = failed)

Checks
  1. validation_results.json exists, parses, and has zero errors
  2. manifest exists; every raw file's SHA-256 equals the manifest; no un-manifested raw CSV
  3. processed provenance: input fingerprint equals the current manifest; every processed file's hash matches
  4. phase_a provenance: same fingerprint, bound to the pipeline provenance; every output hash matches;
     forecasting-gate constants equal the code constants
  5. required datasets exist with required columns
  6. forecast suppression consistency (published <=> gate passed <=> forecast file exists)
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config as C
from .forecast import GATE_MIN_IMPROVEMENT, HORIZONS, MIN_TRAIN
from .ingest import fingerprint
from .schema import NATIONAL_WEEKLY_COLUMNS, REGIONAL_SNAPSHOT_COLUMNS

PROV = "_provenance.json"
_ANALYTIC_MIN = ["week_start", "comparison_group", "scale_id", "is_edge_partial_week", "annual_sin", "eid_al_fitr_in_week"]
REQUIRED_PROCESSED: dict[str, list[str]] = {
    "timeline_groupA_long": NATIONAL_WEEKLY_COLUMNS, "timeline_groupB_long": NATIONAL_WEEKLY_COLUMNS,
    "timeline_groupA_analytic_weekly": _ANALYTIC_MIN, "timeline_groupB_analytic_weekly": _ANALYTIC_MIN,
    "region_groupA_share": REGIONAL_SNAPSHOT_COLUMNS, "region_single_term_index": REGIONAL_SNAPSHOT_COLUMNS,
    "region_groupB4_share": REGIONAL_SNAPSHOT_COLUMNS,
    "series_profile": ["comparison_group", "term", "n_weeks", "median", "reported_zero_share", "candidate_for_forecasting"],
    "calendar_weekly": ["week_start", "annual_sin", "annual_cos"],
    "calendar_events": ["event", "date", "basis", "verification", "source_note"],
}
REQUIRED_PHASE_A: dict[str, list[str]] = {
    "month_profile": ["month", "mean", "index_vs_overall_mean", "term", "scale_id"],
    "event_lift": ["event", "week_start", "lift", "term", "scale_id"],
    "event_lift_summary": ["event", "occurrences", "median_lift", "term", "scale_id"],
    "stl_strength": ["term", "scale_id", "seasonal_strength"],
    "backtest_summary": ["h", "term", "stem"],
    "backtest_errors": ["origin", "h", "target_week", "actual", "ae_calendar_ols", "term"],
    "regional_index_by_term": REGIONAL_SNAPSHOT_COLUMNS + ["rank_within_term", "has_data"],
    "regional_share_groupA": REGIONAL_SNAPSHOT_COLUMNS,
}


@dataclass
class IntegrityReport:
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str) -> bool:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c["ok"] for c in self.checks)

    @property
    def failures(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _columns(path: Path) -> list[str]:
    import pyarrow.parquet as pq

    return list(pq.ParquetFile(path).schema_arrow.names)


def _check_outputs(rep: IntegrityReport, label: str, directory: Path, prov: dict, required: dict[str, list[str]]) -> None:
    bad = []
    for name, digest in prov.get("outputs", {}).items():
        f = directory / name
        if not f.exists():
            bad.append(f"{name} missing")
        elif _sha(f) != digest:
            bad.append(f"{name} hash differs from provenance")
    rep.add(f"{label}: output hashes match provenance", not bad and bool(prov.get("outputs")), "; ".join(bad) or f"{len(prov.get('outputs', {}))} files verified")
    problems = []
    for stem, cols in required.items():
        f = directory / f"{stem}.parquet"
        if not f.exists():
            problems.append(f"{stem}.parquet missing")
            continue
        missing = [c for c in cols if c not in _columns(f)]
        if missing:
            problems.append(f"{stem}: missing columns {missing}")
    rep.add(f"{label}: required datasets and schemas", not problems, "; ".join(problems) or f"{len(required)} datasets match expected schema")


def _check_scale_isolation(rep: IntegrityReport, P, man: list[dict]) -> None:
    """The four-term regional share table must keep its own scale: one scale_id, bound to its manifest entry, shared by no other processed regional frame."""
    f = P.processed / "region_groupB4_share.parquet"
    if not f.exists():
        return  # reported by the required-datasets check
    b4 = pd.read_parquet(f, columns=["scale_id", "comparison_group", "source_file"])
    entry = [e for e in man if e.get("comparison_group") == C.GROUP_B4_SHARE]
    ok = (b4["scale_id"].nunique() == 1 and set(b4["comparison_group"]) == {C.GROUP_B4_SHARE} and len(entry) == 1
          and b4["scale_id"].iloc[0] == entry[0]["scale_id"] and set(b4["source_file"]) == {entry[0]["file_name"]})
    others = set()
    for stem in ("region_groupA_share", "region_single_term_index"):
        g = P.processed / f"{stem}.parquet"
        if g.exists():
            others |= set(pd.read_parquet(g, columns=["scale_id"])["scale_id"])
    clash = sorted(others & set(b4["scale_id"]))
    rep.add("four-term regional shares keep their own scale", ok and not clash,
            f"scale_id={b4['scale_id'].iloc[0]}; shared with another dataset: {clash or 'no'}" if len(b4) else "empty dataset")


def verify(root: Path = C.ROOT, stage: str = "all") -> IntegrityReport:
    """stage="processed" stops after the pipeline-output checks (used by phase_a before it starts)."""
    P = C.paths(root)
    rep = IntegrityReport()
    try:
        # 1 ---- validation report
        vpath = P.processed / "validation_results.json"
        if not rep.add("validation report exists", vpath.exists(), str(vpath.relative_to(P.root))):
            return rep
        v = _json(vpath)
        errs = v.get("summary", {}).get("errors")
        rep.add("validation errors == 0", errs == 0, f"errors={errs}")
        # 2 ---- raw vs manifest
        if not rep.add("manifest exists", P.manifest_json.exists(), str(P.manifest_json.relative_to(P.root))):
            return rep
        man = _json(P.manifest_json)
        bad = []
        for e in man:
            f = P.root / e["raw_path"]
            if not f.exists():
                bad.append(f"{e['file_name']} missing")
            elif _sha(f) != e["sha256"]:
                bad.append(f"{e['file_name']} hash differs")
        rep.add("raw file hashes match manifest", not bad and bool(man), "; ".join(bad) or f"{len(man)} raw files verified")
        extra = sorted(p.name for p in P.raw.glob("*.csv") if p.name not in {e["file_name"] for e in man})
        rep.add("no un-manifested raw files", not extra, f"unlisted: {extra}" if extra else "all raw files are in the manifest")
        fp = fingerprint(man)
        rep.add("validation was run on the current inputs", v.get("input_fingerprint") == fp, "validation fingerprint equals manifest fingerprint" if v.get("input_fingerprint") == fp else "validation_results.json is from different inputs")
        # 3 ---- processed provenance
        ppath = P.processed / PROV
        if rep.add("processed provenance exists", ppath.exists(), PROV):
            prov = _json(ppath)
            rep.add("processed data derived from current raw inputs", prov.get("input_fingerprint") == fp, "fingerprints equal" if prov.get("input_fingerprint") == fp else "processed data is stale relative to raw inputs")
            _check_outputs(rep, "processed", P.processed, prov, REQUIRED_PROCESSED)
            _check_scale_isolation(rep, P, man)
            if stage == "processed":
                return rep
            # 4 ---- phase A
            apath = P.phase_a / PROV
            if rep.add("phase_a provenance exists", apath.exists(), PROV):
                a = _json(apath)
                rep.add("phase_a derived from current inputs", a.get("input_fingerprint") == fp, "fingerprints equal" if a.get("input_fingerprint") == fp else "phase_a is stale")
                rep.add("phase_a bound to current processed data", a.get("processed_provenance_sha256") == _sha(ppath), "processed provenance digest equal" if a.get("processed_provenance_sha256") == _sha(ppath) else "phase_a was built from different processed data")
                gc = a.get("gate_constants", {})
                same = gc == {"min_improvement": GATE_MIN_IMPROVEMENT, "min_train": MIN_TRAIN, "horizons": list(HORIZONS)}
                rep.add("forecast-gate constants unchanged", same, f"recorded {gc}" if not same else "min_improvement=%.2f, min_train=%d, horizons=%s" % (GATE_MIN_IMPROVEMENT, MIN_TRAIN, list(HORIZONS)))
                _check_outputs(rep, "phase_a", P.phase_a, a, REQUIRED_PHASE_A)
                # 6 ---- forecast suppression
                spath = P.phase_a / "forecast_status.json"
                if rep.add("forecast status exists", spath.exists(), "forecast_status.json"):
                    st = _json(spath)["forecast"]
                    published, passed = bool(st.get("forecast_published")), bool(st.get("gate", {}).get("passed"))
                    exists = (P.phase_a / "forecast_national.parquet").exists()
                    rep.add("forecast suppression consistent", published == passed == exists,
                            f"published={published}, gate_passed={passed}, forecast_file_exists={exists}")
    except Exception as exc:  # any unexpected problem -> fail closed
        rep.add("integrity verification ran without error", False, f"{type(exc).__name__}: {exc}")
    return rep


RERUN_COMMANDS = [
    "cd saudi-bloom-intelligence",
    "export PYTHONPATH=src",
    ".venv/bin/python -m bloom.pipeline     # validates inputs; exits non-zero on failure",
    ".venv/bin/python -m bloom.phase_a      # analysis + gated forecast",
    ".venv/bin/python -m bloom.integrity    # confirms everything is consistent",
]


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[argv.index("--root") + 1]) if argv and "--root" in argv else C.ROOT
    rep = verify(root)
    for c in rep.checks:
        print(("OK   " if c["ok"] else "FAIL ") + c["name"] + " — " + c["detail"])
    print("INTEGRITY VERIFIED" if rep.ok else "INTEGRITY FAILED")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
