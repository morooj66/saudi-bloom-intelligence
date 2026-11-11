"""Private-data start-up: hash-verified, path-safe, token-protected, fail-closed. Uses a local HTTP server only; nothing leaves the machine."""
import gzip
import hashlib
import http.server
import io
import tarfile
import threading
from pathlib import Path

import pytest

from bloom import bootstrap as B

TOKEN = "unit-test-token-not-a-secret"


def bundle(entries: dict[str, bytes | None], links: dict[str, str] | None = None) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tf:
        for name, data in entries.items():
            ti = tarfile.TarInfo(name); ti.size = len(data); ti.mtime = 0
            tf.addfile(ti, io.BytesIO(data))
        for name, target in (links or {}).items():
            ti = tarfile.TarInfo(name); ti.type = tarfile.SYMTYPE; ti.linkname = target
            tf.addfile(ti)
    return gzip.compress(raw.getvalue(), mtime=0)


GOOD = {"data/manifest.json": b"[]", "data/manifest.csv": b"a\n", "data/processed/validation_results.json": b"{}", "data/raw/x.csv": b"1\n"}


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Server:
    def __init__(self, blob: bytes, token: str | None = TOKEN):
        outer = self
        self.seen_auth = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.seen_auth.append(self.headers.get("Authorization"))
                if token and self.headers.get("Authorization") != f"Bearer {token}":
                    self.send_response(401); self.end_headers(); return
                self.send_response(200); self.send_header("Content-Length", str(len(blob))); self.end_headers(); self.wfile.write(blob)

            def log_message(self, *a):
                pass
        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/bundle.tar.gz"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()


@pytest.fixture(autouse=True)
def _reset_cooldown():
    B._last_failure.clear()


def test_noop_when_nothing_configured_or_data_present(tmp_path):
    assert B.ensure_data(tmp_path, env={}) == "not-configured"
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "manifest.json").write_text("[]"); (tmp_path / "data" / "processed" / "validation_results.json").write_text("{}")
    assert B.ensure_data(tmp_path, env={"BLOOM_DATA_BUNDLE_URL": "https://example.invalid/x"}) == "present"


def test_fetch_installs_files_and_sends_token(tmp_path):
    blob = bundle(GOOD); s = Server(blob)
    try:
        r = B.ensure_data(tmp_path, env={"BLOOM_DATA_BUNDLE_URL": s.url, "BLOOM_DATA_BUNDLE_SHA256": sha(blob), "BLOOM_DATA_BUNDLE_TOKEN": TOKEN})
    finally:
        s.close()
    assert r == "fetched" and s.seen_auth == [f"Bearer {TOKEN}"]
    assert (tmp_path / "data" / "raw" / "x.csv").read_bytes() == b"1\n" and B.has_data(tmp_path)
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".bundle_")]


def test_secrets_dict_is_used_when_environment_is_empty(tmp_path):
    blob = bundle(GOOD); s = Server(blob, token=None)
    try:
        assert B.ensure_data(tmp_path, env={}, secrets={"BLOOM_DATA_BUNDLE_URL": s.url, "BLOOM_DATA_BUNDLE_SHA256": sha(blob)}) == "fetched"
    finally:
        s.close()


def test_wrong_hash_is_rejected_and_nothing_is_written(tmp_path):
    blob = bundle(GOOD); s = Server(blob, token=None)
    try:
        with pytest.raises(B.BootstrapError, match="SHA-256"):
            B.ensure_data(tmp_path, env={"BLOOM_DATA_BUNDLE_URL": s.url, "BLOOM_DATA_BUNDLE_SHA256": "0" * 64})
    finally:
        s.close()
    assert not B.has_data(tmp_path) and not (tmp_path / "data" / "raw").exists()


def test_missing_expected_hash_refuses_an_unverified_bundle(tmp_path):
    with pytest.raises(B.BootstrapError, match="SHA-256 is missing"):
        B.ensure_data(tmp_path, env={"BLOOM_DATA_BUNDLE_URL": "https://example.invalid/b"})


def test_wrong_token_is_refused_without_leaking_url_or_token(tmp_path):
    blob = bundle(GOOD); s = Server(blob)
    try:
        with pytest.raises(B.BootstrapError) as e:
            B.ensure_data(tmp_path, env={"BLOOM_DATA_BUNDLE_URL": s.url, "BLOOM_DATA_BUNDLE_SHA256": sha(blob), "BLOOM_DATA_BUNDLE_TOKEN": "wrong-token-value"})
    finally:
        s.close()
    msg = str(e.value)
    assert "401" in msg and "wrong-token-value" not in msg and "bundle.tar.gz" not in msg and not B.has_data(tmp_path)


def test_plain_http_is_allowed_only_for_localhost():
    with pytest.raises(B.BootstrapError, match="https"):
        B.download("http://example.com/b.tar.gz")
    with pytest.raises(B.BootstrapError, match="https"):
        B.download("file:///etc/passwd")


@pytest.mark.parametrize("entries,links", [
    ({**GOOD, "../evil.txt": b"x"}, None),
    ({**GOOD, "/abs.txt": b"x"}, None),
    ({**GOOD, "app/streamlit_app.py": b"x"}, None),
    ({**GOOD, "data/geo/x.json": b"x"}, None),
    (GOOD, {"data/raw/link.csv": "/etc/passwd"}),
])
def test_unsafe_bundles_are_rejected_before_extraction(tmp_path, entries, links):
    blob = bundle(entries, links)
    with pytest.raises(B.BootstrapError):
        B.install_bundle(blob, sha(blob), tmp_path)
    assert not B.has_data(tmp_path) and not (tmp_path / "evil.txt").exists() and not (tmp_path.parent / "evil.txt").exists()


def test_incomplete_bundle_is_rejected(tmp_path):
    blob = bundle({"data/raw/x.csv": b"1\n"})
    with pytest.raises(B.BootstrapError, match="incomplete"):
        B.install_bundle(blob, sha(blob), tmp_path)
    assert not (tmp_path / "data" / "raw").exists()


def test_failure_cooldown_prevents_hammering(tmp_path):
    env = {"BLOOM_DATA_BUNDLE_URL": "http://127.0.0.1:9/none", "BLOOM_DATA_BUNDLE_SHA256": "0" * 64}
    with pytest.raises(B.BootstrapError, match="could not be reached"):
        B.ensure_data(tmp_path, env=env)
    with pytest.raises(B.BootstrapError, match="a moment ago"):
        B.ensure_data(tmp_path, env=env)


# ----------------------------------------------------------------------------- end to end (data-dependent: uses the locally built project)
def test_end_to_end_bundle_to_dashboard(built_project, tmp_path, monkeypatch):
    """Pack the verified data, serve it from a local token-protected server, start the dashboard on an EMPTY root: it must load the
    bundle, pass the full integrity gate and render the real analytics."""
    import shutil
    import subprocess
    import sys

    from conftest import ROOT
    from streamlit.testing.v1 import AppTest

    out = tmp_path / "private" / "bundle.tar.gz"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_data_bundle.py"), "--root", str(built_project), "--out", str(out)],
                       capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    assert r.returncode == 0, r.stderr
    digest = [l.split()[-1] for l in r.stdout.splitlines() if l.startswith("SHA-256")][0]
    assert digest == sha(out.read_bytes()) and str(out.parent) not in r.stdout
    empty = tmp_path / "server_root"; (empty / "data").mkdir(parents=True)
    shutil.copytree(ROOT / "data" / "geo", empty / "data" / "geo")
    s = Server(out.read_bytes())
    try:
        monkeypatch.setenv("BLOOM_ROOT", str(empty))
        monkeypatch.setenv("BLOOM_DATA_BUNDLE_URL", s.url); monkeypatch.setenv("BLOOM_DATA_BUNDLE_SHA256", digest); monkeypatch.setenv("BLOOM_DATA_BUNDLE_TOKEN", TOKEN)
        at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    finally:
        s.close()
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "integrity checks passed before anything was displayed" in page and "Study scope: Saudi Arabia" in page.replace("⁦", "").replace("⁩", "")
    assert not [e for e in at.error] and (empty / "data" / "processed" / "phase_a" / "forecast_status.json").exists()
    assert not (empty / "incoming_data").exists()  # the bundle never contains the manual-export staging folder


def test_bundle_script_refuses_output_inside_the_project(built_project):
    import subprocess
    import sys

    from conftest import ROOT
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_data_bundle.py"), "--root", str(built_project), "--out", str(built_project / "bundle.tar.gz")],
                       capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    assert r.returncode != 0 and "inside the project" in (r.stderr + r.stdout) and not (built_project / "bundle.tar.gz").exists()


def test_tampered_bundle_fails_closed_in_the_dashboard(built_project, tmp_path, monkeypatch):
    """A bundle whose contents were altered but whose archive hash was recomputed is still stopped by the manifest/provenance integrity gate."""
    import shutil
    from conftest import ROOT
    from streamlit.testing.v1 import AppTest

    tampered = tmp_path / "t"; shutil.copytree(built_project, tampered)
    f = next((tampered / "data" / "raw").glob("*.csv")); f.write_bytes(f.read_bytes() + b"\n1,2,3\n")
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tf:
        for p in sorted([*(tampered / "data" / "raw").rglob("*"), *(tampered / "data" / "processed").rglob("*"), tampered / "data" / "manifest.json", tampered / "data" / "manifest.csv"]):
            if p.is_file():
                b = p.read_bytes(); ti = tarfile.TarInfo(p.relative_to(tampered).as_posix()); ti.size = len(b); tf.addfile(ti, io.BytesIO(b))
    blob = gzip.compress(raw.getvalue(), mtime=0)
    empty = tmp_path / "root"; (empty / "data").mkdir(parents=True); shutil.copytree(ROOT / "data" / "geo", empty / "data" / "geo")
    s = Server(blob, token=None)
    try:
        monkeypatch.setenv("BLOOM_ROOT", str(empty)); monkeypatch.setenv("BLOOM_DATA_BUNDLE_URL", s.url); monkeypatch.setenv("BLOOM_DATA_BUNDLE_SHA256", sha(blob))
        at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    finally:
        s.close()
    page = " ".join(m.value for m in at.markdown)
    assert "analytics are hidden" in page and "integrity checks passed before anything was displayed" not in page
