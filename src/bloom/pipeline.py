"""End-to-end ETL: incoming CSV -> data/raw (+manifest) -> validated, analysis-ready data/processed.

Run:  PYTHONPATH=src .venv/bin/python -m bloom.pipeline [--root DIR]

Exit codes: 0 = success, 1 = validation errors (processed data NOT written), 2 = input/parse/manifest failure.
Fail-closed: analytic outputs and the provenance file are written only when validation has zero errors.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

from . import config as C
from .calendar_features import build_weekly_calendar, event_dates
from .ingest import build_manifest, fingerprint, missing_exports
from .transform import edge_partial_flags, parse_geomap, parse_timeline, timeline_wide
from .validate import profile_series, validate_cross, validate_geomap, validate_timeline

PROVENANCE = "_provenance.json"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def _save(df: pd.DataFrame, directory: Path, stem: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    df.to_parquet(directory / f"{stem}.parquet", index=False)
    df.to_csv(directory / f"{stem}.csv", index=False, encoding="utf-8-sig")


def write_provenance(directory: Path, input_fp: str, extra: dict | None = None) -> dict:
    """Record the SHA-256 of every output file in `directory` (top level only) plus the input fingerprint."""
    outputs = {p.name: sha256_path(p) for p in sorted(directory.iterdir()) if p.is_file() and p.name != PROVENANCE
               and p.suffix in (".parquet", ".csv", ".json")}
    prov = {"input_fingerprint": input_fp, "outputs": outputs, **(extra or {})}
    (directory / PROVENANCE).write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    return prov


def run(root: Path = C.ROOT) -> dict:
    P = C.paths(root)
    if not P.incoming.exists() or not any(P.incoming.glob("*.csv")):
        raise FileNotFoundError(f"No Google Trends exports found in {P.incoming}. Export the nine CSV files from trends.google.com into that folder first "
                                "(see README, 'Bring your own data'). Nothing was written.")
    P.processed.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(P.incoming, P.raw, P.manifest_json, P.manifest_csv, root=P.root)
    gaps = missing_exports(manifest)
    if gaps:
        raise RuntimeError("Incomplete set of Google Trends exports; missing: " + "; ".join(gaps))
    fp = fingerprint(manifest)
    by_group_tl: dict[str, pd.DataFrame] = {}
    geos: dict[str, pd.DataFrame] = {}
    for e in manifest:
        path = P.root / e["raw_path"]
        if e["kind"] == "timeline":
            if e["comparison_group"] in by_group_tl:
                raise ValueError(f"Two timeline exports for comparison group {e['comparison_group']}: {e['file_name']} would overwrite the other")
            by_group_tl[e["comparison_group"]] = parse_timeline(path, e)
        else:
            if any(g["scale_id"].iloc[0].split("|")[0] == e["comparison_group"] for g in geos.values()):
                raise ValueError(f"Two regional exports for comparison group {e['comparison_group']}: {e['file_name']}")
            geos[e["file_name"]] = parse_geomap(path, e)

    checks: list[dict] = []
    for g, df in by_group_tl.items():
        checks += validate_timeline(df, g)
    for name, df in geos.items():
        checks += validate_geomap(df, name)
    checks += validate_cross(by_group_tl, geos, manifest, root=P.root, incoming=P.incoming)
    summary = {
        "errors": sum(1 for c in checks if not c["passed"] and c["level"] == "error"),
        "warnings": sum(1 for c in checks if not c["passed"] and c["level"] == "warning"),
        "passed": sum(1 for c in checks if c["passed"]),
    }
    result = {"records": {}, "checks": checks, "summary": summary, "input_fingerprint": fp}

    if summary["errors"] == 0:
        window_start = geos["geoMap.csv"]["window_start"].iloc[0]
        window_end = geos["geoMap.csv"]["window_end"].iloc[0]
        profiles = []
        for g, df in by_group_tl.items():
            stem = "timeline_" + ("groupA" if g == C.GROUP_A else "groupB")
            df = df.copy()
            df["is_edge_partial_week"] = edge_partial_flags(df["week_start"], window_start, window_end)
            _save(df, P.processed, f"{stem}_long")
            wide = timeline_wide(df)
            analytic = wide.merge(build_weekly_calendar(wide["week_start"]), on="week_start", how="left", validate="1:1")
            analytic["is_edge_partial_week"] = edge_partial_flags(analytic["week_start"], window_start, window_end)
            _save(analytic, P.processed, f"{stem}_analytic_weekly")
            profiles.append(profile_series(df, window_start, window_end))
        region_a = geos["geoMap.csv"]
        _save(region_a, P.processed, "region_groupA_share")
        b4 = [d for d in geos.values() if d["comparison_group"].iloc[0] == C.GROUP_B4_SHARE]
        if len(b4) != 1:
            raise ValueError(f"Expected exactly one four-term regional share export, found {len(b4)}")
        region_b4 = b4[0]
        _save(region_b4, P.processed, "region_groupB4_share")  # own file, own scale_id: never concatenated with the index or five-term frames
        singles = pd.concat([d for n, d in geos.items() if n != "geoMap.csv" and d["comparison_group"].iloc[0] != C.GROUP_B4_SHARE], ignore_index=True)
        _save(singles, P.processed, "region_single_term_index")
        _save(pd.concat(profiles, ignore_index=True), P.processed, "series_profile")
        _save(build_weekly_calendar(sorted(by_group_tl[C.GROUP_A]["week_start"].unique())), P.processed, "calendar_weekly")
        _save(event_dates(2021, 2027), P.processed, "calendar_events")
        result["records"] = {
            "timeline_A_rows": len(by_group_tl[C.GROUP_A]), "timeline_B_rows": len(by_group_tl[C.GROUP_B]),
            "weeks": int(by_group_tl[C.GROUP_A]["week_start"].nunique()),
            "geo_A_rows": len(region_a), "geo_B4_rows": len(region_b4), "geo_single_rows": len(singles), "raw_files": len(manifest),
        }

    (P.processed / "validation_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if summary["errors"] == 0:
        write_provenance(P.processed, fp, {"validation_errors": 0, "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(C.ROOT), help="project root (default: this project)")
    args = ap.parse_args(argv)
    try:
        r = run(Path(args.root))
    except Exception as exc:  # parse errors, unknown regions, checksum/manifest conflicts, ...
        print(f"PIPELINE FAILED (input/parse/manifest): {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"records": r["records"], "summary": r["summary"]}, indent=2))
    for c in r["checks"]:
        if not c["passed"]:
            print(f"[{c['level'].upper()}] {c['name']} {c['scope']}: {c['detail']}", file=sys.stderr)
    if r["summary"]["errors"]:
        print(f"PIPELINE FAILED: {r['summary']['errors']} validation error(s); processed data not written.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
