"""Private-data start-up: fetch the verified data bundle for a hosted deployment, without ever putting the data in the public repository.

Nothing here runs unless the data are missing AND a bundle is configured (environment variables or Streamlit secrets):

    BLOOM_DATA_BUNDLE_URL      https URL of a .tar.gz bundle (http only for localhost, used by the tests). For a file in a private GitHub repository:
                               https://api.github.com/repos/<owner>/<repo>/contents/<file>?ref=main   (release asset: .../releases/assets/<id>)
    BLOOM_DATA_BUNDLE_SHA256   expected SHA-256 of that archive (hex)             <- the bundle cannot be swapped silently
    BLOOM_DATA_BUNDLE_TOKEN    optional read-only bearer token for a private store  <- never logged, never put in an error message

Order of checks: size limit while downloading -> SHA-256 of the whole archive -> member-by-member safety checks (only regular files under
data/raw, data/processed, data/manifest.json|csv; no absolute paths, '..', links or devices) -> extraction to a temporary directory ->
atomic move into place. The existing fail-closed `bloom.integrity.verify` then re-checks every raw and processed file against the manifest
exactly as it does for local data, so a wrong bundle still shows no analytics.

The bundle is created locally with `scripts/make_data_bundle.py`. This module changes no analysis, threshold or pipeline code.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KEYS = ("BLOOM_DATA_BUNDLE_URL", "BLOOM_DATA_BUNDLE_SHA256", "BLOOM_DATA_BUNDLE_TOKEN")
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 200
ALLOWED_TOP = ("data/raw/", "data/processed/")
ALLOWED_FILES = ("data/manifest.json", "data/manifest.csv")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_COOLDOWN_S = 60
_last_failure: dict[str, float] = {}


class BootstrapError(RuntimeError):
    """A safe, user-presentable message: it never contains the URL, the token or file contents."""


def has_data(root: Path) -> bool:
    root = Path(root)
    return (root / "data" / "manifest.json").exists() and (root / "data" / "processed" / "validation_results.json").exists()


def settings(env: dict | None = None, secrets: dict | None = None) -> dict:
    """Environment wins over secrets. Returns only the recognised keys that are set and non-empty."""
    out = {}
    for k in KEYS:
        v = (env if env is not None else os.environ).get(k) or (secrets or {}).get(k)
        if v:
            out[k] = str(v).strip()
    return out


def _check_url(url: str) -> urllib.parse.ParseResult:
    u = urllib.parse.urlparse(url)
    if u.scheme == "https" and u.hostname:
        return u
    if u.scheme == "http" and u.hostname in _LOCAL_HOSTS:
        return u
    raise BootstrapError("The data bundle URL must use https (plain http is allowed only for localhost).")


def accept_for(url: str) -> str:
    """GitHub serves a private repository FILE as raw bytes through the contents API (Accept: raw) and a release ASSET as bytes
    only with Accept: octet-stream. Everything else gets octet-stream."""
    u = urllib.parse.urlparse(url)
    if u.hostname == "api.github.com" and "/contents/" in u.path:
        return "application/vnd.github.raw+json"
    return "application/octet-stream"


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Private stores (e.g. GitHub release assets) redirect to a signed URL on another host. Follow only https/localhost targets and
    never forward the bearer token to a different host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = _check_url(newurl)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and target.hostname != urllib.parse.urlparse(req.full_url).hostname:
            new.remove_header("Authorization")
        return new


def download(url: str, token: str | None = None, timeout: float = 30.0) -> bytes:
    u = _check_url(url)
    req = urllib.request.Request(url, headers={"Accept": accept_for(url), "User-Agent": "saudi-bloom-intelligence-bootstrap"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.build_opener(_SafeRedirect).open(req, timeout=timeout) as r:  # noqa: S310 - scheme restricted above
            buf = io.BytesIO()
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                buf.write(chunk)
                if buf.tell() > MAX_BUNDLE_BYTES:
                    raise BootstrapError("The data bundle is larger than the allowed size.")
            return buf.getvalue()
    except BootstrapError:
        raise
    except urllib.error.HTTPError as e:
        raise BootstrapError(f"The data store at {u.hostname} refused the request (HTTP {e.code}).") from None
    except Exception as e:  # network errors: report the host and the error class only
        raise BootstrapError(f"The data store at {u.hostname} could not be reached ({type(e).__name__}).") from None


def _safe_members(tf: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = tf.getmembers()
    if not members or len(members) > MAX_MEMBERS:
        raise BootstrapError("The data bundle has an unexpected number of entries.")
    for m in members:
        name = m.name
        if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
            raise BootstrapError("The data bundle contains an unsafe path and was rejected.")
        if m.isdir():
            if not (name.rstrip("/") + "/").startswith(("data/",)):
                raise BootstrapError("The data bundle contains an unexpected folder and was rejected.")
            continue
        if not m.isreg():
            raise BootstrapError("The data bundle contains a link or special file and was rejected.")
        if not (name in ALLOWED_FILES or name.startswith(ALLOWED_TOP)):
            raise BootstrapError("The data bundle contains an unexpected file and was rejected.")
    return members


def install_bundle(blob: bytes, expected_sha256: str, root: Path) -> None:
    """Verify the archive hash, check every member, extract to a temporary folder, then move into place."""
    got = hashlib.sha256(blob).hexdigest()
    if got != expected_sha256.strip().lower():
        raise BootstrapError("The data bundle failed its SHA-256 check and was rejected.")
    root = Path(root)
    (root / "data").mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".bundle_", dir=root))
    try:
        try:
            with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
                members = _safe_members(tf)
                tf.extractall(tmp, members=members, filter="data")
        except BootstrapError:
            raise
        except Exception as e:
            raise BootstrapError(f"The data bundle could not be unpacked ({type(e).__name__}).") from None
        if not ((tmp / "data" / "manifest.json").exists() and (tmp / "data" / "processed" / "validation_results.json").exists()):
            raise BootstrapError("The data bundle is incomplete (manifest or validation report missing).")
        for rel in ("data/raw", "data/processed"):
            if (tmp / rel).exists():
                dst = root / rel
                if dst.exists():
                    shutil.rmtree(dst)
                os.replace(tmp / rel, dst)
        for rel in ALLOWED_FILES:
            if (tmp / rel).exists():
                os.replace(tmp / rel, root / rel)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ensure_data(root: Path, env: dict | None = None, secrets: dict | None = None) -> str:
    """'present' (nothing to do), 'not-configured' (no bundle settings), or 'fetched'. Raises BootstrapError with a safe message."""
    root = Path(root)
    if has_data(root):
        return "present"
    cfg = settings(env, secrets)
    if "BLOOM_DATA_BUNDLE_URL" not in cfg:
        return "not-configured"
    key = hashlib.sha256(cfg["BLOOM_DATA_BUNDLE_URL"].encode()).hexdigest()
    if time.time() - _last_failure.get(key, 0) < _COOLDOWN_S:
        raise BootstrapError("The private data bundle could not be loaded a moment ago; retrying shortly.")
    expected = cfg.get("BLOOM_DATA_BUNDLE_SHA256")
    if not expected:
        raise BootstrapError("A data bundle URL is set but its expected SHA-256 is missing; refusing to load an unverified bundle.")
    try:
        blob = download(cfg["BLOOM_DATA_BUNDLE_URL"], cfg.get("BLOOM_DATA_BUNDLE_TOKEN"))
        install_bundle(blob, expected, root)
    except BootstrapError:
        _last_failure[key] = time.time()
        raise
    return "fetched"
