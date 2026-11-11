"""Brand identity and copy guards (no emoji in the brand; no sales/volume claims; SVG mark renders every bar)."""
import re
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import theme as T  # noqa: E402
from bidi import NBSP, isolate  # noqa: E402

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]")


def test_brand_has_no_emoji_and_names_the_product():
    html = T.brand_html()
    assert not EMOJI.search(html) and "SAUDI BLOOM" in html and "INTELLIGENCE" in html


def test_page_title_and_icon_are_not_emoji():
    src = (APP / "streamlit_app.py").read_text(encoding="utf-8")
    cfg = re.search(r"st\.set_page_config\((.*?)\)\n", src, re.S).group(1)
    assert "page_icon=Image.open" in cfg and not EMOJI.search(cfg)
    assert not EMOJI.search(src.split("st.set_page_config")[0])  # nothing decorative in the title area
    assert (APP / "assets" / "brandmark.png").exists()


def test_svg_mark_has_eight_bars_and_a_gradient_that_works_on_straight_lines():
    html = T.brand_html()
    assert html.count("<line ") == 8
    # regression: objectBoundingBox gradients are invalid on horizontal/vertical lines (bars vanished); needs user-space units
    assert 'gradientUnits="userSpaceOnUse"' in html


def test_source_has_no_emoji_anywhere_in_app_modules():
    for f in APP.glob("*.py"):
        assert not EMOJI.search(f.read_text(encoding="utf-8")), f.name


def test_copy_never_claims_sales_or_volume():
    forbidden = re.compile(r"highest (sales|demand|purchase)|most (sales|purchases)|sells more|buy(s)? more|market size of|sales volume (is|of)", re.I)
    for f in APP.glob("*.py"):
        assert not forbidden.search(f.read_text(encoding="utf-8")), f.name
    kpi_source = (APP / "streamlit_app.py").read_text(encoding="utf-8")
    assert "Highest relative search interest for" in kpi_source  # required wording for the ranking KPI


def test_arabic_phrases_do_not_wrap():
    assert f"محل{NBSP}ورد" in isolate("flower shop · محل ورد")


def test_every_section_credits_google_trends_and_osm():
    src = (APP / "streamlit_app.py").read_text(encoding="utf-8")
    tail = src.split("source attribution (every section)")[1]
    assert "Google Trends" in tail and "OpenStreetMap" in tail and "Not affiliated with Google" in tail
    assert "elif section" not in tail and "if section" not in tail  # outside the section chain => shown everywhere
