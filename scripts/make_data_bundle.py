"""Pack the locally verified data into one private bundle for a hosted deployment.

    PYTHONPATH=src .venv/bin/python scripts/make_data_bundle.py --out /path/OUTSIDE/the/repository/bloom_data_bundle.tar.gz

Refuses to run unless `bloom.integrity` passes, refuses an output path inside the project, and prints the archive SHA-256 (the value to store
as BLOOM_DATA_BUNDLE_SHA256). The archive is deterministic (sorted entries, zero timestamps/owners). It contains Google Trends data:
store it only in a private location and never commit it. Nothing is uploaded by this script."""
import argparse
import gzip
import hashlib
import io
import sys
import tarfile
from pathlib import Path

from bloom import config as C
from bloom.integrity import verify

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True, help="output .tar.gz, must be outside the project folder")
ap.add_argument("--root", default=str(C.ROOT))
a = ap.parse_args()
root, out = Path(a.root).resolve(), Path(a.out).resolve()
if root in out.parents or out == root:
    sys.exit("Refusing: the bundle contains Google Trends data and must not be written inside the project folder.")
rep = verify(root)
if not rep.ok:
    sys.exit("Refusing: bloom.integrity does not pass; fix the data first.")
files = sorted([p for d in ("data/raw", "data/processed") for p in (root / d).rglob("*") if p.is_file()] +
               [root / "data" / "manifest.json", root / "data" / "manifest.csv"])
raw = io.BytesIO()
with tarfile.open(fileobj=raw, mode="w") as tf:
    for p in files:
        ti = tarfile.TarInfo(p.relative_to(root).as_posix()); b = p.read_bytes()
        ti.size, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname, ti.mode = len(b), 0, 0, 0, "", "", 0o644
        tf.addfile(ti, io.BytesIO(b))
blob = gzip.compress(raw.getvalue(), mtime=0)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(blob)
print(f"files: {len(files)}  bytes: {len(blob)}\nSHA-256: {hashlib.sha256(blob).hexdigest()}\nwritten: {out.name} (location not printed on purpose; keep it private)")
