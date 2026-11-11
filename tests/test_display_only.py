"""Display-only release settings: no table export, no chart-image download, exact dependency pins."""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dataframe_export_disabled():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["client"]["disableDataExport"] is True
    assert cfg.get("server", {}).get("enableStaticServing", False) is False


def test_every_plotly_chart_hides_the_image_download_button():
    src = (ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert 'PLOT_CFG = {"modeBarButtonsToRemove": ["toImage"]}' in src
    calls = src.count("st.plotly_chart(")
    assert calls >= 10 and src.count("config=PLOT_CFG") == calls, "every st.plotly_chart call must pass config=PLOT_CFG"


def test_requirements_txt_is_pinned_to_the_lock():
    def pins(name):
        return {l.strip().lower() for l in (ROOT / name).read_text(encoding="utf-8").splitlines() if "==" in l and not l.lstrip().startswith("#")}
    req, lock = pins("requirements.txt"), pins("requirements.lock")
    assert req == lock and len(req) == 46
    assert all(re.fullmatch(r"[a-z0-9_.\-]+==[^=<>~ ]+", p) for p in req)
