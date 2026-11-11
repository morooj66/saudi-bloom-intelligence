"""Shared helpers. Integration tests copy the REAL exports into a temp project root and run the real CLIs there,
so corrupting a copy never touches the project's data."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run_cli(module: str, root: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONWARNINGS": "ignore"}
    return subprocess.run([sys.executable, "-m", module, "--root", str(root), *extra], capture_output=True, text=True, env=env, cwd=str(ROOT))


def make_project(tmp: Path) -> Path:
    """Temp project root containing copies of the real incoming exports (no processed data yet)."""
    if not list((ROOT / "incoming_data").glob("*.csv")):
        pytest.skip("data-dependent test: requires the locally supplied Google Trends exports in incoming_data/ (not part of the repository)")
    inc = tmp / "incoming_data"
    inc.mkdir(parents=True)
    for f in sorted((ROOT / "incoming_data").glob("*.csv")):
        shutil.copy2(f, inc / f.name)
    return tmp


@pytest.fixture
def project(tmp_path):
    return make_project(tmp_path / "proj")


@pytest.fixture(scope="session")
def built_project(tmp_path_factory):
    """A fully built temp project (pipeline + phase_a). Treat as read-only; use `fresh_copy` to mutate."""
    root = make_project(tmp_path_factory.mktemp("built") / "proj")
    assert run_cli("bloom.pipeline", root).returncode == 0
    assert run_cli("bloom.phase_a", root).returncode == 0
    shutil.copytree(ROOT / "data" / "geo", root / "data" / "geo")  # boundary data is a separate, hash-pinned input
    return root


@pytest.fixture
def fresh_copy(built_project, tmp_path):
    dst = tmp_path / "copy"
    shutil.copytree(built_project, dst)
    return dst
