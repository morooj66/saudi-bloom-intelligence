"""Raw-data preservation: checksum, copy-without-overwrite, manifest, comparison-group assignment."""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import pandas as pd

from . import config as C
from .trends_io import (
    parse_term_header,
    parse_window,
    read_rows,
    sha256_file,
    split_metadata_and_table,
)


def assign_group(kind: str, terms: list[str]) -> str:
    s = set(terms)
    if s == set(C.ALL_TERMS) and len(terms) == 5:
        return C.GROUP_A
    if s == set(C.COMMERCIAL_TERMS) and len(terms) == 4:
        # the same four terms exist as a weekly timeline (index) and as a regional share table: different measures, different groups
        return C.GROUP_B4_SHARE if kind == "geomap" else C.GROUP_B
    if len(terms) == 1 and terms[0] in C.ALL_TERMS:
        return f"{C.GROUP_SINGLE_PREFIX}{terms[0]}"
    raise ValueError(f"Cannot assign comparison group to {kind} with terms {terms}")


def missing_exports(entries: list[dict]) -> list[str]:
    """Human-readable list of the Google Trends exports the pipeline needs but does not have (empty list = complete set of nine)."""
    have = {(e["comparison_group"], e["kind"]) for e in entries}
    need = [(C.GROUP_A, "timeline", "weekly timeline, 5 terms (group A)"), (C.GROUP_B, "timeline", "weekly timeline, 4 commercial terms (group B)"),
            (C.GROUP_A, "geomap", "regional shares, 5 terms (group A)"), (C.GROUP_B4_SHARE, "geomap", "regional shares, 4 commercial terms (group B4)")]
    need += [(f"{C.GROUP_SINGLE_PREFIX}{t}", "geomap", f"regional index for the single term «{t}»") for t in C.ALL_TERMS]
    return [f"{label} [{g}|{k}]" for g, k, label in need if (g, k) not in have]


def inspect_file(path: Path) -> dict:
    """Read metadata only (no value parsing): kind, terms, geo/window, encoding, category."""
    rows, enc, delim = read_rows(path)
    meta_rows, header, body = split_metadata_and_table(rows)
    first = header[0]
    parsed = [parse_term_header(c) for c in header[1:] if c]
    terms = [t for t, _ in parsed]
    scopes = {s for _, s in parsed}
    kind = "geomap" if first == "منطقة" or first.lower() in ("region", "subregion") else "timeline"
    info = {
        "kind": kind,
        "encoding": enc,
        "delimiter": delim,
        "metadata_rows": [" ".join(r) for r in meta_rows if any(r)],
        "category": next((r[0].split(":", 1)[1].strip() for r in meta_rows if r and ":" in r[0]), None),
        "first_column_label": first,
        "terms": terms,
        "n_data_rows": len(body),
        "comparison_group": assign_group(kind, terms),
    }
    if kind == "timeline":
        info["geographic_scope"] = sorted(scopes)
        info["granularity"] = "weekly" if "أسبوع" in first or first.lower().startswith("week") else "unknown"
    else:
        wins = {parse_window(s) for s in scopes}
        if len(wins) != 1 or None in wins:
            raise ValueError(f"{path.name}: inconsistent/unparseable windows {scopes}")
        w = wins.pop()
        info["window_start"], info["window_end"] = str(w[0].date()), str(w[1].date())
        info["geographic_scope"] = ["SA sub-regions (13 expected)"]
        info["granularity"] = "none (period aggregate by region)"
    return info


def normalization_note(group: str, kind: str) -> str:
    if kind == "timeline":
        return (
            "Index 0-100 relative to the single highest point across ALL terms in this export "
            "(same query window); comparable only among terms of this export."
        )
    if group == C.GROUP_B4_SHARE:
        return ("Percent share of each of the FOUR commercial terms among those four terms' searches within each region (relative composition). "
                "Not an index, not volume; comparable only inside this export; never combined with the regional index or the five-term shares.")
    if group in (C.GROUP_A, C.GROUP_B):
        return "Percent share of the compared terms' searches within each region; comparable only within this export."
    return "Index 0-100 relative to the highest region for this ONE term; not comparable to other terms/exports."


def build_manifest(
    incoming: Path = C.INCOMING_DIR,
    raw: Path = C.RAW_DIR,
    manifest_json: Path = C.MANIFEST_JSON,
    manifest_csv: Path = C.MANIFEST_CSV,
    root: Path = C.ROOT,
) -> list[dict]:
    """Copy new files to data/raw (never overwrite), verify hashes, update the manifest.

    Raises if a raw file or manifest entry exists with a different checksum, or if a file recorded in
    the manifest is no longer present in the incoming folder (the manifest is append-only).
    """
    raw.mkdir(parents=True, exist_ok=True)
    manifest_json.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if manifest_json.exists():
        existing = {e["file_name"]: e for e in json.loads(manifest_json.read_text(encoding="utf-8"))}

    present = {p.name for p in incoming.glob("*.csv")}
    vanished = sorted(set(existing) - present)
    if vanished:
        raise RuntimeError(f"Manifest lists files missing from {incoming}: {vanished}. Restore them; the manifest is append-only.")
    entries = []
    for src in sorted(incoming.glob("*.csv")):
        digest = sha256_file(src)
        dst = raw / src.name
        if dst.exists():
            if sha256_file(dst) != digest:
                raise RuntimeError(f"Refusing to overwrite {dst}: checksum differs from incoming file")
        else:
            shutil.copy2(src, dst)
        prev = existing.get(src.name)
        if prev and prev["sha256"] != digest:
            raise RuntimeError(f"Manifest checksum mismatch for {src.name}")
        info = inspect_file(dst)
        mtime = dt.datetime.fromtimestamp(src.stat().st_mtime).date().isoformat()
        entry = {
            "file_name": src.name,
            "raw_path": str(dst.relative_to(root)),
            "sha256": digest,
            "size_bytes": src.stat().st_size,
            "source": C.SOURCE_NAME,
            "retrieved_date": prev["retrieved_date"] if prev else mtime,
            "retrieved_date_basis": "file modification time (inferred, not stated in export)",
            "scale_id": f"{info['comparison_group']}|{info['kind']}|{src.name}",
            "normalization": normalization_note(info["comparison_group"], info["kind"]),
            **info,
        }
        entries.append(entry)

    manifest_json.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = pd.DataFrame(entries)
    for c in ("terms", "metadata_rows", "geographic_scope"):
        flat[c] = flat[c].map(lambda v: " | ".join(v))
    flat.to_csv(manifest_csv, index=False, encoding="utf-8-sig")
    return entries


def fingerprint(entries: list[dict]) -> str:
    """Stable digest of the exact raw inputs (file names + SHA-256)."""
    import hashlib

    h = hashlib.sha256()
    for e in sorted(entries, key=lambda e: e["file_name"]):
        h.update(f"{e['file_name']}:{e['sha256']}\n".encode("utf-8"))
    return h.hexdigest()
