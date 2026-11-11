"""Design tokens, CSS and small HTML helpers for the dark rose/purple dashboard."""
from __future__ import annotations

import html

import streamlit as st

import i18n as I
from bidi import isolate

BG, SURFACE, SURFACE2, BORDER = "#121014", "#1b181d", "#241f27", "#33293a"
TEXT, MUTED = "#ece7ee", "#a79fae"
ROSE, ROSE_LIGHT, PURPLE, PURPLE_DIM = "#d9708f", "#f0a0b8", "#a78bda", "#6f56a6"
GOLD, CYAN, NODATA, EVENT = "#e0b36a", "#6cb7c9", "#3a363d", "#8d83a0"
SERIES = [ROSE, PURPLE, GOLD, CYAN, "#9fd6a8"]
ROSE_SCALE = [[0.0, "#2e2433"], [0.35, "#6b3a5b"], [0.7, "#b5547f"], [1.0, "#f4a6bf"]]
FONT = '"Inter","SF Pro Text","Segoe UI",system-ui,"Geeza Pro","Noto Naskh Arabic","Noto Sans Arabic",sans-serif'

CSS = f"""
<style>
html, body, [class*="css"], .stMarkdown, .stApp {{ font-family: {FONT}; }}
.stApp {{ background: radial-gradient(1100px 480px at 12% -8%, rgba(167,139,218,.10), transparent 62%), radial-gradient(900px 420px at 98% -4%, rgba(217,112,143,.08), transparent 60%), {BG}; }}
.block-container {{ max-width: 1180px; padding-top: 3.4rem; padding-bottom: 3rem; }}
h1, h2, h3, h4, h5 {{ letter-spacing: -0.01em; font-weight: 650; }}
h5 {{ font-size: 1.02rem; margin: .9rem 0 .35rem; }}
/* brand */
.brand {{ display:flex; align-items:center; gap:.85rem; margin:0 0 .35rem; }}
.brand svg {{ flex:0 0 auto; }}
.brand .w1 {{ font-size:clamp(1.05rem,3.2vw,1.45rem); font-weight:750; letter-spacing:.24em; line-height:1.1; }}
.brand .w2 {{ font-size:clamp(.62rem,1.9vw,.78rem); font-weight:600; letter-spacing:.5em; color:{ROSE}; margin-top:.28rem; padding-top:.28rem; border-top:1px solid {BORDER}; }}
.tagline {{ color:{MUTED}; font-size:.98rem; margin:.5rem 0 1.1rem; max-width:62ch; }}
/* KPI cards */
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:.8rem; margin:.4rem 0 1.1rem; }}
.kpi {{ position:relative; background:linear-gradient(180deg,{SURFACE2} 0%,{SURFACE} 100%); border:1px solid {BORDER}; border-radius:12px; padding:.9rem 1rem .8rem; overflow:hidden; }}
.kpi::before {{ content:""; position:absolute; left:0; right:0; top:0; height:2px; background:linear-gradient(90deg,{ROSE},{PURPLE}); opacity:.85; }}
.kpi.warn::before {{ background:linear-gradient(90deg,{GOLD},{ROSE}); }}
.kpi .l {{ color:{MUTED}; font-size:.7rem; letter-spacing:.1em; text-transform:uppercase; }}
.kpi .v {{ font-size:1.5rem; font-weight:700; margin:.15rem 0 .1rem; line-height:1.2; overflow-wrap:anywhere; }}
.kpi .s {{ color:{TEXT}; opacity:.82; font-size:.82rem; line-height:1.35; overflow-wrap:anywhere; }}
.kpi .d {{ color:{MUTED}; font-size:.72rem; line-height:1.4; margin-top:.5rem; padding-top:.45rem; border-top:1px dashed {BORDER}; overflow-wrap:anywhere; }}
.callout {{ background:{SURFACE}; border:1px solid {BORDER}; border-left:3px solid {PURPLE}; border-radius:12px; padding:.7rem .95rem; margin:.4rem 0 .9rem; font-size:.92rem; line-height:1.5; }}
.callout.warn {{ border-left-color:{GOLD}; }} .callout.rose {{ border-left-color:{ROSE}; }}
.callout b {{ color:{TEXT}; }} .callout code {{ color:{PURPLE}; background:{SURFACE2}; padding:.05rem .3rem; border-radius:4px; font-size:.85em; }}
.panel {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px; padding:.8rem 1rem; height:100%; }}
.panel h6 {{ margin:0 0 .4rem; font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; color:{PURPLE}; font-weight:650; }}
.panel p, .panel li {{ font-size:.88rem; line-height:1.5; margin:.2rem 0; }} .panel ul {{ padding-left:1.1rem; margin:.2rem 0; }}
.rc-name {{ font-weight:650; font-size:1.05rem; margin:.1rem 0 .5rem; }}
.rc-big {{ font-size:2.5rem; font-weight:760; line-height:1.05; }} .rc-big small {{ font-size:.78rem; color:{MUTED}; font-weight:500; margin-inline-start:.45rem; }}
.bar {{ height:8px; border-radius:999px; background:{SURFACE2}; margin:.55rem 0 .5rem; overflow:hidden; border:1px solid {BORDER}; }}
.bar span {{ display:block; height:100%; background:linear-gradient(90deg,{PURPLE_DIM},{ROSE}); }}
.cap {{ color:{MUTED}; font-size:.82rem; line-height:1.45; margin:.2rem 0 .9rem; }}
.chip {{ display:inline-block; padding:.12rem .55rem; border-radius:999px; font-size:.75rem; border:1px solid {BORDER}; color:{MUTED}; margin-right:.3rem; }}
.chip.ok {{ border-color:{PURPLE_DIM}; color:{PURPLE}; }} .chip.bad {{ border-color:{ROSE}; color:{ROSE_LIGHT}; }}
.legend {{ display:flex; flex-wrap:wrap; gap:.4rem 1.1rem; align-items:center; font-size:.8rem; color:{MUTED}; margin:.2rem 0 .6rem; }}
.legend i {{ display:inline-block; width:.9rem; height:.9rem; border-radius:3px; margin-right:.35rem; vertical-align:-.15rem; border:1px solid {BORDER}; }}
.legend .grad {{ width:5.5rem; background:linear-gradient(90deg,#3b2c45,#9a4f86,#f4a6bf); }}
/* section navigation: radio styled as wrapping pills */
.st-key-section [role="radiogroup"], .st-key-lang [role="radiogroup"] {{ flex-wrap:wrap; gap:.4rem; margin-bottom:.4rem; }}
.st-key-section [data-testid="stRadioOption"], .st-key-lang [data-testid="stRadioOption"] {{ border:1px solid {BORDER}; background:{SURFACE}; border-radius:999px; padding:.3rem .9rem; margin:0; cursor:pointer; }}
.st-key-section [data-testid="stRadioOption"] > div > div:first-child:not([data-testid="stMarkdownContainer"]), .st-key-lang [data-testid="stRadioOption"] > div > div:first-child:not([data-testid="stMarkdownContainer"]) {{ display:none; }}
.st-key-section [data-testid="stRadioOption"][data-selected="true"], .st-key-lang [data-testid="stRadioOption"][data-selected="true"] {{ border-color:{ROSE}; background:{SURFACE2}; box-shadow:0 0 0 1px {ROSE} inset; }}
.st-key-section [data-testid="stRadioOption"][data-selected="true"] p, .st-key-lang [data-testid="stRadioOption"][data-selected="true"] p {{ color:{ROSE_LIGHT}; font-weight:600; }}
.crit {{ display:flex; align-items:center; justify-content:space-between; gap:.6rem; flex-wrap:wrap; background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; padding:.6rem .9rem; margin:.35rem 0; }}
.crit .t {{ flex:1 1 220px; font-size:.92rem; }} .crit .r {{ font-weight:650; }}
[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius:10px; }}
[data-testid="stElementContainer"]:has(iframe[height="1"]) {{ display:none; }}
[data-testid="stExpander"] {{ border:1px solid {BORDER}; border-radius:10px; background:{SURFACE}; }}
@media (min-width: 641px) and (max-width: 980px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} }}  /* tablet: balanced 2x2 instead of 3+1 */
@media (max-width: 640px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); gap:.5rem; }} .kpi {{ padding:.65rem .7rem; }} .kpi .s {{ font-size:.74rem; }} .kpi .d {{ font-size:.66rem; }} .kpi .l {{ font-size:.62rem; }} .block-container {{ padding-left:1rem; padding-right:1rem; padding-top:3.2rem; }} .kpi .v {{ font-size:1.3rem; }} }}
</style>
"""


RTL_CSS = f"""
<style>
html, body, [class*="css"], .stMarkdown, .stApp {{ font-family: "Noto Sans Arabic","Geeza Pro","SF Arabic","Segoe UI","Inter",system-ui,sans-serif; }}
.stApp {{ direction: rtl; }}
.stApp [data-testid="stPlotlyChart"], .stApp [data-testid="stDataFrame"], .stApp .brand {{ direction: ltr; }}
.stApp [data-testid="stSelectbox"], .stApp [data-testid="stMultiSelect"], .stApp [data-testid="stRadio"], .stApp [data-testid="stExpander"] {{ text-align: right; }}
.kpi .l, .panel h6 {{ letter-spacing: 0; text-transform: none; font-size: .8rem; }}
.callout {{ border-left: 1px solid {BORDER}; border-right: 3px solid {PURPLE}; }}
.callout.warn {{ border-right-color: {GOLD}; }} .callout.rose {{ border-right-color: {ROSE}; }}
.panel ul {{ padding-left: 0; padding-right: 1.1rem; }}
.chip {{ margin-right: 0; margin-left: .3rem; }}
.legend i {{ margin-right: 0; margin-left: .35rem; }}
.tagline {{ max-width: 62ch; }}
</style>
"""


def inject_css(rtl: bool = False) -> None:
    st.markdown(CSS + (RTL_CSS if rtl else ""), unsafe_allow_html=True)


def _e(text: str) -> str:
    # English mode: Arabic runs are bidi-isolated. Arabic mode: whole sentences are Arabic, so no isolates/NBSP (they would stop lines from wrapping).
    return html.escape(text if I.is_rtl() else isolate(text), quote=False)


def kpi(label: str, value: str, sub: str = "", accent: str = "", definition: str = "") -> str:
    d = f'<div class="d">{_e(definition)}</div>' if definition else ""
    return f'<div class="kpi {accent}"><div class="l">{_e(label)}</div><div class="v">{_e(value)}</div><div class="s">{_e(sub)}</div>{d}</div>'


def kpi_row(cards: list[str]) -> None:
    st.markdown(f'<div class="kpis">{"".join(cards)}</div>', unsafe_allow_html=True)


def callout(text: str, kind: str = "") -> None:
    """text may contain <b>…</b>; everything else is escaped. Arabic runs are bidi-isolated."""
    safe = _e(text)
    for tag in ("b", "i", "code"):
        safe = safe.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    st.markdown(f'<div class="callout {kind}">{safe}</div>', unsafe_allow_html=True)


def caption(text: str) -> None:
    st.markdown(f'<div class="cap">{_e(text)}</div>', unsafe_allow_html=True)


def chip(text: str, kind: str = "") -> str:
    return f'<span class="chip {kind}">{_e(text)}</span>'


def plotly_layout(height: int = 380, **kw) -> dict:
    base = dict(height=height, margin=dict(l=8, r=8, t=18, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=MUTED, family=FONT, size=12), hoverlabel=dict(bgcolor=SURFACE2, font=dict(color=TEXT, family=FONT), bordercolor=BORDER))
    base.update(kw)
    return base


AXIS = dict(gridcolor="#2a2430", zerolinecolor="#2a2430", linecolor=BORDER, tickfont=dict(color=MUTED))


def criteria_rows(rows: list[tuple[str, str, bool]]) -> None:
    """Acceptance criteria as stacked rows (wrap on mobile): (text, result, met)."""
    out = "".join(f'<div class="crit"><div class="t">{_e(text)}</div><div class="r">{_e(res)}</div>{chip(I.L("met", "محقق") if ok else I.L("not met", "غير محقق"), "ok" if ok else "bad")}</div>' for text, res, ok in rows)
    st.markdown(out, unsafe_allow_html=True)


BAR_LENGTHS = [17, 11, 20, 13, 18, 10, 21, 14]  # same geometry as app/assets/brandmark.png; decorative, encodes no data


def brand_html() -> str:
    """Geometric mark (eight radial rounded bars: a bloom that also reads as a radial bar chart) + typographic wordmark."""
    import math

    bars = []
    for i, L in enumerate(BAR_LENGTHS):
        a = math.radians(i * 45 - 90)
        x0, y0, x1, y1 = (24 + math.cos(a) * 6.5, 24 + math.sin(a) * 6.5, 24 + math.cos(a) * L, 24 + math.sin(a) * L)
        bars.append(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}"/>')
    svg = (f'<svg width="46" height="46" viewBox="0 0 48 48" role="img" aria-label="Saudi Bloom Intelligence mark"><defs><linearGradient id="bg" gradientUnits="userSpaceOnUse" x1="4" y1="4" x2="44" y2="44">'
           f'<stop offset="0" stop-color="{ROSE}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient></defs>'
           f'<g stroke="url(#bg)" stroke-width="3.4" stroke-linecap="round">{"".join(bars)}</g></svg>')
    return f'<div class="brand">{svg}<div><div class="w1">SAUDI BLOOM</div><div class="w2">INTELLIGENCE</div></div></div>'


def map_legend_html() -> str:
    return ('<div class="legend">' + f'<span><i class="grad"></i>{I.L("available · relative interest (low → high)", "متاحة · الاهتمام النسبي (من الأقل إلى الأعلى)")}</span>'
            f'<span><i style="background:{PURPLE_DIM}"></i>{I.L("censored (&lt;1%, value unknown)", "مخفية (&lt;1%، القيمة غير معروفة)")}</span>'
            f'<span><i style="background:{NODATA}"></i>{I.L("no data reported", "لم يُبلَّغ عن بيانات")}</span>'
            f'<span><i style="background:transparent;border:2px solid {PURPLE}"></i>{I.L("selected for comparison", "محددة للمقارنة")}</span></div>')
