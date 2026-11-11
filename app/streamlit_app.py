"""Saudi Bloom Intelligence — bilingual (العربية | English) dashboard, fail-closed.

Run:  PYTHONPATH=src .venv/bin/streamlit run app/streamlit_app.py        (optional: ?lang=ar  ?section=regions)
The app only reads data; it never regenerates or modifies it. If integrity verification fails, no analytics are shown.
One shared analytical data source: the language switch changes text only, never a number, ranking or result.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE)]

import pandas as pd
import streamlit as st
from PIL import Image

import components as K
import i18n as I
import theme as T
from bidi import isolate
from bloom import config as C
from bloom.forecast import GATE_MIN_IMPROVEMENT, HORIZONS, MIN_TRAIN
from bloom.geo import ATTRIBUTION_TEXT, load_geojson, rewind_for_plotly, verify_geo
from bloom.integrity import RERUN_COMMANDS, verify
from bloom.overview import (MIX_TERM_ORDER, eid_weeks, history_coverage, map_text_alternative, month_extremes, ranking_explainer, region_comparison, regions_covered, select_from_map,
                            series_text_alternative, spread_of_available, strongest_seasonal, term_mix_cell_counts, term_mix_order, term_mix_regions, term_mix_table,
                            term_mix_text_alternative, toggle_from_map, top_region, trend_vs_prior_year, yoy_frame)

L = I.L
ROOT = Path(os.environ.get("BLOOM_ROOT", C.ROOT))  # BLOOM_ROOT only used by tests
PATHS = C.paths(ROOT)
TARGET = "محل ورد"  # designated forecast/headline term (flower shop), chosen before any backtest

NAV = ["overview", "trend", "seasonality", "regions", "mix", "forecast", "data"]
NAV_LABEL = {"overview": ("Overview", "نظرة عامة"), "trend": ("National trend", "الاتجاه الوطني"), "seasonality": ("Seasonality", "الموسمية"),
             "regions": ("Regions & map", "المناطق والخريطة"), "mix": ("Commercial-term mix", "تركيبة المصطلحات التجارية"), "forecast": ("Forecast", "التوقع"),
             "data": ("Data engineering", "هندسة البيانات")}

# ------------------------------------------------------------------ language and section state (persist across navigation; ?lang= / ?section= seed the first load)
qp = st.query_params
if "lang" not in st.session_state:
    st.session_state["lang"] = qp.get("lang") if qp.get("lang") in I.LANGS else "en"
if "section" not in st.session_state and qp.get("section") in NAV:
    st.session_state["section"] = qp.get("section")


def _sync_query() -> None:
    st.query_params["lang"] = st.session_state["lang"]
    if st.session_state.get("section") in NAV:
        st.query_params["section"] = st.session_state["section"]


RTL = I.is_rtl()
st.set_page_config(page_title="Saudi Bloom Intelligence", page_icon=Image.open(HERE / "assets" / "brandmark.png"), layout="wide")
T.inject_css(RTL)
# accessibility: expose the active language and direction on the document itself (screen readers, browser text handling)
st.iframe(f"<script>const d=window.parent.document.documentElement;d.lang='{I.lang()}';d.dir='{'rtl' if RTL else 'ltr'}';</script>", height=1)
hb, hl = st.columns([7, 3], vertical_alignment="center")
hb.markdown(T.brand_html(), unsafe_allow_html=True)
hl.radio("Language · اللغة", list(I.LANGS), format_func=I.LANG_NAME.get, horizontal=True, label_visibility="collapsed", key="lang", on_change=_sync_query)
st.markdown('<div class="tagline">' + L("Relative search-interest analytics for flower queries in Saudi Arabia: national seasonality, a 13-region comparison, "
                                         "and a forecast that is published only when it is validated.",
                                         "تحليلات الاهتمام النسبي بالبحث عن الورد في المملكة العربية السعودية: الموسمية على المستوى الوطني، ومقارنة بين 13 منطقة، "
                                         "وتوقّع لا يُنشر إلا بعد اجتياز التحقق.") + '</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ fail-closed integrity gate
report = verify(ROOT)
if not report.ok:
    _no_data = not (PATHS.processed / "validation_results.json").exists() and not PATHS.manifest_json.exists() and not (PATHS.incoming.exists() and any(PATHS.incoming.glob("*.csv")))
    if _no_data:
        T.callout(L("<b>No Google Trends data found.</b> This project does not ship the Google Trends exports (their redistribution terms are not cleared), so you supply your own: "
                    "export the CSV files from trends.google.com (see <i>Bring your own data</i> in the README), put them in <code>incoming_data/</code>, then run the commands below. "
                    "Nothing is shown until the data pass every integrity check.",
                    "<b>لم يتم العثور على بيانات Google Trends.</b> لا يتضمن هذا المشروع ملفات Google Trends (لم تُحسم شروط إعادة توزيعها)، لذا عليك توفير ملفاتك: "
                    "صدّر ملفات CSV من trends.google.com (راجع <i>Bring your own data</i> في ملف README) وضعها في <code>incoming_data/</code> ثم نفّذ الأوامر أدناه. "
                    "لا يُعرض شيء إلا بعد أن تجتاز البيانات كل فحوص السلامة."), "warn")
    T.callout(L("<b>Data integrity check failed — analytics are hidden.</b> The dashboard shows results only when every check passes. "
                "It never regenerates or overwrites data on its own.",
                "<b>فشل فحص سلامة البيانات — التحليلات مخفية.</b> لا تُعرض النتائج إلا عند اجتياز جميع الفحوص، ولا تُعيد اللوحة توليد البيانات أو الكتابة فوقها."), "rose")
    st.dataframe(pd.DataFrame(report.failures).rename(columns={"name": L("Failed check", "الفحص الفاشل"), "detail": L("Diagnostic", "التشخيص")})[[L("Failed check", "الفحص الفاشل"), L("Diagnostic", "التشخيص")]],
                 hide_index=True, width="stretch")
    st.markdown(L("**Safe way to recover** (run these yourself in a terminal; they validate inputs and exit non-zero on failure):",
                  "**طريقة آمنة للتعافي** (نفّذ هذه الأوامر بنفسك في الطرفية؛ فهي تتحقق من المدخلات وتنتهي برمز خطأ عند الفشل):"))
    st.code("\n".join(RERUN_COMMANDS), language="bash")
    T.caption(L("If the pipeline itself fails, fix the reported input problem; do not edit data/raw or the manifest by hand.",
                "إذا فشل خط المعالجة نفسه فأصلح مشكلة المدخلات المذكورة؛ ولا تعدّل data/raw أو ملف manifest يدويًا."))
    with st.expander(L("All checks", "جميع الفحوص")):
        st.dataframe(pd.DataFrame(report.checks).assign(ok=lambda d: d["ok"].map({True: "pass", False: "FAIL"})), hide_index=True, width="stretch")
    st.stop()

PROC, A = PATHS.processed, PATHS.phase_a


@st.cache_data
def load(name: str, phase_a: bool, stamp: float) -> pd.DataFrame:
    return pd.read_parquet((A if phase_a else PROC) / f"{name}.parquet")


def get(name: str, phase_a: bool = False) -> pd.DataFrame:
    f = (A if phase_a else PROC) / f"{name}.parquet"
    return load(name, phase_a, f.stat().st_mtime)


@st.cache_data
def load_map_geojson(root: str) -> dict:
    return rewind_for_plotly(load_geojson(Path(root)))


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


status = jload(A / "forecast_status.json")
gate = status["forecast"]["gate"]
manifest = jload(PATHS.manifest_json)
vres = jload(PROC / "validation_results.json")
prov_p, prov_a = jload(PROC / "_provenance.json"), jload(A / "_provenance.json")
long_a, long_b = get("timeline_groupA_long"), get("timeline_groupB_long")
idx, share = get("regional_index_by_term", True), get("regional_share_groupA", True)
events = get("calendar_events")
month_prof, es_all, stl = get("month_profile", True), get("event_lift_summary", True), get("stl_strength", True)
geo_ok, geo_detail = verify_geo(ROOT)
full_b = long_b[~long_b["is_edge_partial_week"]]
published = bool(status["forecast"]["forecast_published"])

# Pill navigation (wraps on narrow screens; renders only the active section). Stable ids: the label changes with the language, the selection does not.
LANG = I.lang()
# Streamlit derives a widget's identity from its (language-dependent) labels and options, so switching language would reset every selection. To keep the reader's context
# (section, term, selected region, comparison list, …) the selections are mirrored in a canonical dict and re-applied with an explicit set, which also re-syncs the frontend.
KEEP = ["ov_term", "ov_region", "season_term", "reg_measure", "reg_term", "compare", "reg_names", "trend_group", "trend_events", "trend_terms_groupB", "trend_terms_groupA", "mix_order"]
canon = st.session_state.setdefault("_canon", {})
lang_changed = st.session_state.get("_lang_seen") != LANG
if lang_changed:
    for _k, _v in canon.items():
        st.session_state[_k] = _v
if lang_changed or st.session_state.get("section") not in NAV:
    st.session_state["section"] = st.session_state.get("_section_canon", st.session_state.get("section") if st.session_state.get("section") in NAV else "overview")
    st.session_state["_lang_seen"] = LANG
section = st.radio("Section", NAV, format_func=lambda k: L(*NAV_LABEL[k]), horizontal=True, label_visibility="collapsed", key="section", on_change=_sync_query)
st.session_state["_section_canon"] = section
st.session_state.setdefault("compare", [])
st.session_state.setdefault("map_nonce", 0)
st.session_state.setdefault("ov_nonce", 0)
LANG = I.lang()


def alt(text: str) -> None:
    """Visible plain-text description of a chart (text alternative for readers who cannot see it)."""
    T.caption(L("Text alternative · ", "بديل نصي · ") + text)


def go_to(name: str) -> None:
    st.session_state["section"] = name
    _sync_query()


def term_options(frame: pd.DataFrame) -> list[str]:
    return [t for t in [TARGET, "توصيل ورد", "بوكيه ورد", "ورد", "شراء ورد"] if t in set(frame["term"])]


def region_label(names: dict, iso: str) -> str:
    en, ar = names[iso]
    return I.region_name(en, ar)


def rname(en: str, ar: str) -> str:
    return I.region_name(en, ar)


def panel(title: str, items: list[str], foot: str = "", style: str = "") -> str:
    lis = "".join(f"<li>{x}</li>" for x in items)
    return f'<div class="panel" style="{style}"><h6>{title}</h6><ul>{lis}</ul>{f"<p class=cap>{foot}</p>" if foot else ""}</div>'


DEF = {  # KPI definitions (technical details), shown in an expander
    "cov": lambda hc: L(f"Weekly Google Trends buckets analysed (excluding {hc['n_edge_excluded']} partial edge weeks), re-checked against the manifest on every page load. "
                        "The regional exports are one snapshot per region, not a history.",
                        f"فترات Google Trends الأسبوعية المحلَّلة (باستثناء {hc['n_edge_excluded']} من الأسابيع الحدّية الجزئية)، ويُعاد فحصها مقابل ملف manifest عند كل تحميل للصفحة. "
                        "التصديرات الإقليمية لقطة واحدة لكل منطقة وليست سلسلة زمنية."),
    "reg": lambda: L("Administrative regions present in every regional export. Cells Google reported as blank appear as “no data”, never as zero.",
                     "المناطق الإدارية الموجودة في كل تصدير إقليمي. الخلايا التي تركتها Google فارغة تظهر «بلا بيانات» وليست صفرًا أبدًا."),
    "trend": lambda: L("Descriptive comparison of two 52-week averages of the weekly search-interest index (flower shop, one Google Trends scale). It is not a change in searches, sales or demand, "
                       "and Google Trends sampling noise has not been measured, so small differences are not meaningful.",
                       "مقارنة وصفية بين متوسطين لـ 52 أسبوعًا من مؤشر الاهتمام بالبحث (محل ورد، مقياس Google Trends واحد). وهي ليست تغيّرًا في عدد عمليات البحث أو المبيعات أو الطلب، "
                       "ولم تُقَس ضوضاء أخذ العينات في Google Trends، لذا لا تُعدّ الفروق الصغيرة ذات دلالة."),
    "season": lambda ss: L(f"Median ratio of flower-shop search interest in the event week to surrounding weeks. Descriptive: {ss['occurrences']} occurrences, no causal or statistical-significance claim.",
                           f"الوسيط لنسبة الاهتمام بالبحث عن محل ورد في أسبوع المناسبة إلى الأسابيع المحيطة. وصفي: {ss['occurrences']} مرات، دون ادعاء سببية أو دلالة إحصائية."),
}

# =================================================================================================== Overview
if section == "overview":
    tr, rc, hc, ss = top_region(idx, TARGET), regions_covered(idx), history_coverage(long_b), strongest_seasonal(es_all, TARGET)
    tv, n_raw = trend_vs_prior_year(long_b, TARGET), len(manifest)

    # ---- hero: the interactive map is the main visual focus
    left, right = st.columns([8, 5], gap="large")
    with left:
        h1, h2 = st.columns([3, 2], vertical_alignment="center")
        h1.markdown("##### " + L("Regional relative search interest", "الاهتمام النسبي بالبحث حسب المنطقة"))
        ov_term = h2.selectbox(L("Search term", "مصطلح البحث"), term_options(idx), format_func=K.label, key="ov_term", label_visibility="collapsed")
        T.caption(L("Pick a term, then click a region on the map. Darker = lower relative interest, lighter = higher; the colour compares regions inside one Google Trends export.",
                    "اختر مصطلحًا ثم انقر على منطقة في الخريطة. اللون الأغمق = اهتمام نسبي أقل، والأفتح = أعلى؛ ويقارن اللون بين المناطق داخل تصدير Google Trends واحد."))
        dterm = idx[idx["term"] == ov_term]
        names_ov = {r.region_iso: (r.region_en, r.region_ar) for r in dterm.itertuples()}
        st.session_state.setdefault("ov_region", tr["iso"])

        def on_ov_select() -> None:
            ev = st.session_state.get(f"ovmap_{st.session_state['ov_nonce']}")
            pts = ev["selection"]["points"] if ev else []
            st.session_state["ov_region"] = select_from_map(st.session_state.get("ov_region"), [p.get("location") for p in pts if p.get("location")])
            st.session_state["ov_nonce"] += 1  # fresh widget: the next event contains only the next click

        mta = map_text_alternative(dterm, K.label(ov_term), LANG)
        if geo_ok:
            st.plotly_chart(K.region_map(dterm, load_map_geojson(str(ROOT)), ov_term, L("index (100 = peak region)", "المؤشر (100 = أعلى منطقة)"), selected=[st.session_state["ov_region"]], height=560),
                            width="stretch", key=f"ovmap_{st.session_state['ov_nonce']}", on_select=on_ov_select, selection_mode=("points",))
            st.markdown(T.map_legend_html(), unsafe_allow_html=True)
            alt(mta)
            T.caption(L(ATTRIBUTION_TEXT, "الحدود: geoBoundaries (SAU ADM1)، © مساهمو OpenStreetMap، رخصة ODbL 1.0 · إصدار مبسّط دون تعديل"))
        else:
            T.callout(L(f"<b>Map unavailable:</b> boundary file failed verification ({geo_detail}).", f"<b>الخريطة غير متاحة:</b> فشل التحقق من ملف الحدود ({geo_detail})."), "warn")
            alt(mta)
        st.button(L("Compare regions in detail →", "قارن المناطق بالتفصيل ←"), on_click=go_to, args=("regions",), key="go_regions")
    with right:
        sel = st.selectbox(L("Explore a region (or click it on the map)", "استكشف منطقة (أو انقر عليها في الخريطة)"), list(names_ov), format_func=lambda i: region_label(names_ov, i), key="ov_region")
        rcmp = region_comparison(dterm, sel)
        rn = rname(rcmp["region_en"], rcmp["region_ar"])
        pk = rname(rcmp["peak_en"], rcmp["peak_ar"]) if rcmp["peak_en"] else ""
        term_txt = K.label(ov_term)
        if rcmp["status"] == K.AVAILABLE:
            big = f'<div class="rc-big">{rcmp["value"]:.0f}<small>{L("/ 100 relative index", "/ 100 مؤشر نسبي")}</small></div>'
            rank = L(f"Rank <b>{rcmp['rank']}</b> of {rcmp['n_available']} regions with data", f"الترتيب <b>{rcmp['rank']}</b> من {rcmp['n_available']} منطقة لديها بيانات")
            if rcmp["is_peak"]:
                cmp_txt = L("This is the highest-index region for this term.", "هذه هي المنطقة الأعلى مؤشرًا لهذا المصطلح.")
                meaning = L(f"For {term_txt}, {rn} has the highest relative search interest among the regions with data. The index is normalised, so 100 means “highest”, not a number of searches.",
                            f"بالنسبة إلى {term_txt}، لدى {rn} أعلى اهتمام نسبي بالبحث بين المناطق التي لديها بيانات. المؤشر مُطبَّع، فالرقم 100 يعني «الأعلى» وليس عدد عمليات بحث.")
            else:
                cmp_txt = L(f"<b>{rcmp['gap_to_peak']:.0f} points below</b> the highest-index region, {pk} ({rcmp['peak_value']:.0f}).",
                            f"<b>أقل بـ {rcmp['gap_to_peak']:.0f} نقطة</b> من المنطقة الأعلى مؤشرًا، {pk} ({rcmp['peak_value']:.0f}).")
                meaning = L(f"For {term_txt}, relative search interest in {rn} is about {rcmp['ratio_to_peak']:.0%} of the level in {pk}. This compares regions inside one Google Trends export; "
                            "it is not search volume, sales or demand.",
                            f"بالنسبة إلى {term_txt}، يبلغ الاهتمام النسبي بالبحث في {rn} نحو {rcmp['ratio_to_peak']:.0%} من مستواه في {pk}. هذه مقارنة بين المناطق داخل تصدير Google Trends واحد؛ "
                            "وهي ليست حجم بحث ولا مبيعات ولا طلبًا.")
            bar = f'<div class="bar"><span style="width:{rcmp["value"]:.0f}%"></span></div>'
            body = f'{big}{bar}<p>{rank}</p><p>{cmp_txt}</p><p class="cap">{meaning}</p>'
        elif rcmp["status"] == K.CENSORED:
            body = (f'<div class="rc-big">&lt;1%</div><p>{L("Censored by Google Trends: the true share is between 0 and 1%, so no index value is shown.", "مخفية من Google Trends: الحصة الفعلية بين 0 و1%، لذا لا تُعرض قيمة للمؤشر.")}</p>'
                    f'<p class="cap">{L("Censored is not the same as zero or as missing.", "المخفية ليست صفرًا وليست مفقودة.")}</p>')
        else:
            body = (f'<div class="rc-big">—</div><p>{L("No data reported by Google Trends for this region (not zero).", "لم يبلّغ Google Trends عن بيانات لهذه المنطقة (وليست صفرًا).")}</p>'
                    f'<p class="cap">{L("Missing is not the same as zero or as censored.", "المفقودة ليست صفرًا وليست مخفية.")}</p>')
        st.markdown(f'<div class="panel region-card"><h6>{L("Selected region", "المنطقة المحددة")}</h6><div class="rc-name">{T._e(rn)}</div>{body}</div>', unsafe_allow_html=True)

        ex = ranking_explainer(idx, share, ov_term)
        top, rt = ex["top"], K.regional_rank_table(dterm)
        third = rt[rt["status"] == K.AVAILABLE].head(3)["value"].tolist()
        ar_of = dict(zip(dterm["region_en"], dterm["region_ar"]))
        tie = (L(f" (tied with {', '.join(x for x in top['ties'] if x != top['region_en'])})", " (متعادلة مع أخرى)")) if len(top["ties"]) > 1 else ""
        nxt = (L(f"; next {top['runner_up_en']} {top['runner_up_value']:.0f}", f"؛ تليها {ar_of[top['runner_up_en']]} {top['runner_up_value']:.0f}")) if top["runner_up_en"] else ""
        top_name = L(top["region_en"], top["region_ar"])
        st.markdown(f'<div class="panel" style="margin-top:.6rem"><h6>{L("Regional insight · relative search interest", "رؤية إقليمية · الاهتمام النسبي بالبحث")}</h6>'
                    f'<p><b>{L(f"Highest relative search interest for {ov_term}: {top_name}{tie}", f"أعلى اهتمام نسبي بالبحث عن {ov_term}: {top_name}{tie}")}</b> '
                    f'({L("index", "المؤشر")} {top["value"]:.0f}{nxt}).</p>'
                    f'<p class="cap">{L("A relative index, not sales or search volume. The stability of this ranking is not established.", "مؤشر نسبي، وليس مبيعات ولا حجم بحث. ثبات هذا الترتيب غير مُثبَت.")}</p></div>', unsafe_allow_html=True)
        with st.expander(L("Why this ranking needs care", "لماذا يحتاج هذا الترتيب إلى حذر")):
            sh = ex["share_top"]
            share_ar = dict(zip(share["region_en"], share["region_ar"]))
            if sh:
                diff = L(f"**Different metrics can rank differently.** In the five-term share export the highest share for this term is {', '.join(sh['regions'])} ({sh['value']:.0f}%): "
                         "a different question, never merged with the index.",
                         f"**قد تُنتج المقاييس المختلفة ترتيبًا مختلفًا.** في تصدير حصص المصطلحات الخمسة تكون أعلى حصة لهذا المصطلح في {'، '.join(share_ar[x] for x in sh['regions'])} ({sh['value']:.0f}%): "
                         "سؤال مختلف لا يُدمج أبدًا مع المؤشر.")
            else:
                diff = L("**Different metrics can rank differently.** The five-term share export has no numeric value for this term.",
                         "**قد تُنتج المقاييس المختلفة ترتيبًا مختلفًا.** لا توجد قيمة رقمية لهذا المصطلح في تصدير الحصص الخماسي.")
            st.markdown(
                "- " + L("**Relative, normalised ranking.** Google Trends divides each region's searches for the term by that region's total searches and rescales the highest region to 100. "
                         "It does not measure absolute search volume, sales or demand.",
                         "**ترتيب نسبي ومُطبَّع.** يقسم Google Trends عمليات بحث كل منطقة عن المصطلح على إجمالي عمليات بحث تلك المنطقة ثم يعيد قياس أعلى منطقة إلى 100. "
                         "وهو لا يقيس حجم البحث المطلق ولا المبيعات ولا الطلب.") + "\n- " + diff + "\n"
                "- " + L(f"**Sampling stability is not established.** No repeated independent exports exist, and the top values are close ({' / '.join(f'{v:.0f}' for v in third)}).",
                         f"**ثبات أخذ العينات غير مُثبَت.** لا توجد تصديرات مستقلة متكررة، والقيم العليا متقاربة ({' / '.join(f'{v:.0f}' for v in third)}).") + "\n"
                "- " + L("The data do not explain why a region ranks where it does.", "لا تفسّر البيانات سبب احتلال المنطقة موقعها في الترتيب."))

    # ---- KPI cards: main result + short explanation; definitions sit in an expander
    T.kpi_row([
        T.kpi(L("Verified data coverage", "تغطية البيانات الموثّقة"), L(f"{hc['n_weeks']} weeks", f"{hc['n_weeks']} أسبوعًا"),
              L(f"{I.fdate(hc['first'])} → {I.fdate(hc['last'])} · {n_raw} of {n_raw} raw files hash-verified · {len(report.checks)} integrity checks passed",
                f"{I.fdate(hc['first'])} ← {I.fdate(hc['last'])} · {n_raw} من {n_raw} ملفًا خامًا موثّقة بالبصمة · اجتياز {len(report.checks)} من فحوص السلامة")),
        T.kpi(L("Regions covered", "المناطق المشمولة"), L(f"{rc['n_regions']} of 13", f"{rc['n_regions']} من 13"),
              L(f"{rc['n_regions_all_terms']} regions have data for all {rc['n_terms']} terms", f"{rc['n_regions_all_terms']} مناطق لديها بيانات لجميع المصطلحات الـ{rc['n_terms']}"), "purple"),
        T.kpi(L(f"National trend · {TARGET}", f"الاتجاه الوطني · {TARGET}"), I.ltr(f"{tv['pct_change']:+.1%}"),
              L(f"mean weekly index, latest 52 weeks vs the 52 before ({tv['recent_mean']:.1f} vs {tv['prior_mean']:.1f})",
                f"متوسط المؤشر الأسبوعي: آخر 52 أسبوعًا مقابل الـ52 السابقة ({tv['recent_mean']:.1f} مقابل {tv['prior_mean']:.1f})")),
        T.kpi(L("Strongest documented seasonal observation", "أقوى ملاحظة موسمية موثّقة"), L(f"{I.event_label(ss['event'])} weeks", f"أسابيع {I.event_label(ss['event'])}"),
              L(f"{ss['median_lift']:.1f}× baseline · above 1.2× in {ss['years_gt_1_2']} of {ss['occurrences']} years",
                f"{ss['median_lift']:.1f}× من خط الأساس · أعلى من 1.2× في {ss['years_gt_1_2']} من {ss['occurrences']} سنوات")),
    ])
    with st.expander(L("Technical details and caveats for these four numbers", "التفاصيل التقنية والتحفظات لهذه الأرقام الأربعة")):
        st.markdown(f"- **{L('Verified data coverage', 'تغطية البيانات الموثّقة')}:** {DEF['cov'](hc)}\n- **{L('Regions covered', 'المناطق المشمولة')}:** {DEF['reg']()}\n"
                    f"- **{L('National trend', 'الاتجاه الوطني')}:** {DEF['trend']()}\n- **{L('Strongest seasonal observation', 'أقوى ملاحظة موسمية')}:** {DEF['season'](ss)}")

    # ---- national weekly chart and seasonal highlights
    l2, r2 = st.columns([8, 4], gap="large")
    with l2:
        st.markdown("##### " + L(f"National weekly search interest · {K.label(TARGET)}", f"الاهتمام الوطني الأسبوعي بالبحث · {K.label(TARGET)}"))
        dd = full_b[full_b["term"] == TARGET]
        st.plotly_chart(K.series_chart(dd, events=events[events["event"].isin(["eid_al_fitr", "eid_al_adha"])], height=380), width="stretch")
        alt(series_text_alternative(dd, K.label(TARGET), lang=LANG))
    with r2:
        top3 = es_all[es_all["term"] == TARGET].sort_values("median_lift", ascending=False).head(3)
        st.markdown(panel(L("Documented seasonal observations", "ملاحظات موسمية موثّقة"),
                          [L(f"<b>{I.event_label(r.event)}</b> weeks: {r.median_lift:.2f}× baseline (median); above 1.2× in {int(r.years_with_lift_gt_1_2)} of {int(r.occurrences)} years.",
                             f"أسابيع <b>{I.event_label(r.event)}</b>: {r.median_lift:.2f}× من خط الأساس (الوسيط)؛ أعلى من 1.2× في {int(r.years_with_lift_gt_1_2)} من {int(r.occurrences)} سنوات.") for r in top3.itertuples()],
                          L("Descriptive only: five occurrences per event, no causal or significance claim. Dashed † lines mark Umm al-Qura dates not independently verified.",
                            "وصفي فقط: خمس مرات لكل مناسبة، دون ادعاء سببية أو دلالة. الخطوط المتقطعة † تشير إلى تواريخ أم القرى التي لم يُتحقق منها بشكل مستقل.")), unsafe_allow_html=True)
        st.button(L("Open seasonality →", "افتح الموسمية ←"), on_click=go_to, args=("seasonality",), key="go_season")

    # ---- scope, limits and engineering decisions (detail on demand; the disclaimer below stays visible)
    with st.expander(L("Scope, limits and engineering decisions", "النطاق والحدود والقرارات الهندسية")):
        c1, c2, c3 = st.columns(3, gap="medium")
        n_geo = sum(e["kind"] == "geomap" for e in manifest)
        c1.markdown(panel(L("Data scope", "نطاق البيانات"), [
            L(f"Two weekly national exports ({hc['n_weeks']} analysed weeks) and {n_geo} regional snapshots covering 13 regions (index, five-term shares, four-term mix: three separate scales).",
              f"تصديران وطنيان أسبوعيان ({hc['n_weeks']} أسبوعًا محلَّلًا) و{n_geo} لقطات إقليمية تغطي 13 منطقة (المؤشر، حصص المصطلحات الخمسة، تركيبة المصطلحات الأربعة: ثلاثة مقاييس منفصلة)."),
            L("Single-term and five-term exports have different scales and are never combined.", "تصديرات المصطلح الواحد والمصطلحات الخمسة لها مقاييس مختلفة ولا تُدمج أبدًا."),
            L("City-level data (Riyadh, Jeddah, Dammam) is not in the data and not implemented; see the feasibility assessment.",
              "بيانات المدن (الرياض، جدة، الدمام) غير موجودة في البيانات وغير منفّذة؛ راجع تقييم الجدوى.")]), unsafe_allow_html=True)
        c2.markdown(panel(L("Not claimed", "ما لا نزعمه"), [
            L("No sales, demand or purchase volume: Google Trends gives normalised search interest only.", "لا مبيعات ولا طلب ولا حجم شراء: يقدّم Google Trends اهتمامًا بحثيًا مُطبَّعًا فقط."),
            L("No regional time series, regional forecasts or city statistics.", "لا سلاسل زمنية إقليمية ولا توقعات إقليمية ولا إحصاءات مدن."),
            L("No causal claims: event associations are descriptive, with five occurrences each.", "لا ادعاءات سببية: ارتباطات المناسبات وصفية، بخمس مرات لكل منها.")]), unsafe_allow_html=True)
        gain_ltr = I.ltr(f"+{gate['relative_mae_improvement']:.1%}")
        fc_txt = L("published (gate passed)", "منشور (اجتاز بوابة التحقق)") if published else L(f"withheld (+{gate['relative_mae_improvement']:.1%} MAE vs naive; 95% CI includes zero)",
                                                                                                f"محجوب ({gain_ltr} في MAE مقابل النموذج الساذج؛ فاصل الثقة 95% يشمل الصفر)")
        c3.markdown(panel(L("Engineering decisions", "قرارات هندسية"), [
            L(f"{len(report.checks)} integrity checks passed before anything was displayed.", f"اجتياز {len(report.checks)} من فحوص السلامة قبل عرض أي شيء."),
            L(f"National forecast: <b>{fc_txt}</b>.", f"التوقع الوطني: <b>{fc_txt}</b>."),
            L("Independently normalised exports are never combined.", "لا تُدمج أبدًا التصديرات المُطبَّعة بشكل مستقل.")]), unsafe_allow_html=True)
    T.callout(K.disclaimer())
    T.caption(L("Regional level only: city-level data (Riyadh, Jeddah, Dammam) is not in the data and not implemented.", "المستوى الإقليمي فقط: بيانات المدن (الرياض، جدة، الدمام) غير موجودة في البيانات وغير منفّذة."))

# =================================================================================================== National trend
elif section == "trend":
    T.callout(K.disclaimer())
    group = st.radio(L("Comparison group — separate Google Trends scales, never overlaid", "مجموعة المقارنة — مقاييس Google Trends منفصلة ولا تُركَّب فوق بعضها"), ["B", "A"], horizontal=True, key="trend_group",
                     format_func=lambda g: L("B · Commercial terms (4)", "B · المصطلحات التجارية (4)") if g == "B" else L("A · General + commercial (5)", "A · العام + التجارية (5)"))
    stem = "groupB" if group == "B" else "groupA"
    long = get(f"timeline_{stem}_long")
    long = long[~long["is_edge_partial_week"]]
    terms = sorted(long["term"].unique(), key=lambda t: -long.loc[long["term"] == t, "value"].median())
    c1, c2 = st.columns([3, 2])
    pick = c1.multiselect(L("Terms", "المصطلحات"), terms, default=terms[:2] if stem == "groupB" else terms[:1], format_func=K.label, key=f"trend_terms_{stem}", placeholder=L("Choose terms", "اختر المصطلحات"))
    ev_opts = ["eid_al_fitr", "eid_al_adha", "valentines_day", "new_years_eve", "mothers_day_arab"]
    ev_pick = c2.multiselect(L("Event annotations", "علامات المناسبات"), ev_opts, default=["eid_al_fitr", "eid_al_adha"], format_func=I.event_label, key="trend_events", placeholder=L("Choose events", "اختر المناسبات"))
    if pick:
        d = long[long["term"].isin(pick)]
        st.plotly_chart(K.series_chart(d, events=events[events["event"].isin(ev_pick)], height=440), width="stretch")
        K.scale_caption(d)
        for tm in pick[:4]:
            alt(series_text_alternative(d[d["term"] == tm], K.label(tm), lang=LANG))
        T.caption(L("Event lines: solid = date verified against a Saudi announcement (or a fixed calendar date); dashed with † = Umm al-Qura calendar date, "
                    "not independently verified (actual dates follow moon sighting and may differ by a day). Lines show timing only; they do not imply causation.",
                    "خطوط المناسبات: الخط المتصل = تاريخ تم التحقق منه من إعلان سعودي (أو تاريخ ثابت في التقويم)؛ المتقطع مع † = تاريخ بتقويم أم القرى "
                    "لم يُتحقق منه بشكل مستقل (التواريخ الفعلية تتبع رؤية الهلال وقد تختلف بيوم). الخطوط تبيّن التوقيت فقط ولا تدل على سببية."))
    prof = get("series_profile")
    prof = prof[prof["comparison_group"] == long["comparison_group"].iloc[0]].copy()
    st.markdown("##### " + L("Series suitability", "ملاءمة السلاسل"))
    show = pd.DataFrame({L("Term", "المصطلح"): prof["term"].map(K.label), L("Weeks", "الأسابيع"): prof["n_weeks"], L("Median index", "وسيط المؤشر"): prof["median"], L("Peak", "الذروة"): prof["max"],
                         L("Zero weeks", "أسابيع الصفر"): (prof["reported_zero_share"] * 100).round(0), L("Censored", "المخفية"): prof["censored_n"],
                         L("YoY corr.", "ارتباط سنوي"): prof["yoy_corr_52"].round(2), L("Forecast candidate", "مرشّح للتوقع"): prof["candidate_for_forecasting"]})
    st.dataframe(show, hide_index=True, width="stretch", column_config={L("Zero weeks", "أسابيع الصفر"): st.column_config.NumberColumn(format="%d%%"),
                 L("YoY corr.", "ارتباط سنوي"): st.column_config.NumberColumn(help=L("Correlation of each week with the same week one year earlier", "ارتباط كل أسبوع بالأسبوع نفسه قبل سنة"))})
    T.caption(L("Terms that are almost entirely zero weeks (e.g. buy flowers · شراء ورد) are listed for transparency but are not analysable.",
                "المصطلحات التي تكاد تكون أسابيعها كلها صفرًا (مثل شراء ورد) مدرجة للشفافية لكنها غير قابلة للتحليل."))

# =================================================================================================== Seasonality
elif section == "seasonality":
    term = st.selectbox(L("Term", "المصطلح"), ["محل ورد", "توصيل ورد", "بوكيه ورد", "ورد"], format_func=K.label, key="season_term")
    analytic = get("timeline_groupA_analytic_weekly" if term == "ورد" else "timeline_groupB_analytic_weekly")
    mp, es = month_prof[month_prof["term"] == term], es_all[es_all["term"] == term].copy()
    mx = month_extremes(month_prof, term)
    mname = lambda m: I.month_name(m)
    strength = float(stl[stl["term"] == term]["seasonal_strength"].iloc[0])
    top2 = es.sort_values("median_lift", ascending=False).head(2)
    flat = es[es["median_lift"] < 1].sort_values("median_lift")
    ecal = eid_weeks(analytic, events)
    p1, p2, p3 = st.columns(3, gap="medium")
    p1.markdown(panel(L("Observed seasonal patterns", "أنماط موسمية مرصودة"), [
        L(f"Highest monthly averages: {mname(mx['top'][0][0])} ({mx['top'][0][1]:.2f}× the overall mean) and {mname(mx['top'][1][0])} ({mx['top'][1][1]:.2f}×); lowest: {mname(mx['bottom'][-1][0])} ({mx['bottom'][-1][1]:.2f}×).",
          f"أعلى المتوسطات الشهرية: {mname(mx['top'][0][0])} ({mx['top'][0][1]:.2f}× من المتوسط العام) و{mname(mx['top'][1][0])} ({mx['top'][1][1]:.2f}×)؛ الأدنى: {mname(mx['bottom'][-1][0])} ({mx['bottom'][-1][1]:.2f}×)."),
        L(f"Robust STL seasonal strength: {strength:.2f} (0 = none, 1 = fully seasonal), from about 5 annual cycles.",
          f"قوة الموسمية وفق STL المتين: {strength:.2f} (0 = لا موسمية، 1 = موسمية كاملة)، من نحو 5 دورات سنوية.")]), unsafe_allow_html=True)
    p2.markdown(panel(L("Event-associated changes (descriptive)", "تغيّرات مرتبطة بالمناسبات (وصفية)"),
                      [L(f"{I.event_label(r.event)} weeks: {r.median_lift:.2f}× baseline (median); above 1.2× in {int(r.years_with_lift_gt_1_2)} of {int(r.occurrences)} years.",
                         f"أسابيع {I.event_label(r.event)}: {r.median_lift:.2f}× من خط الأساس (الوسيط)؛ أعلى من 1.2× في {int(r.years_with_lift_gt_1_2)} من {int(r.occurrences)} سنوات.") for r in top2.itertuples()]
                      + ([L("No lift observed: " + ", ".join(f"{I.event_label(r.event)} ({r.median_lift:.2f}×)" for r in flat.itertuples()) + ".",
                            "لا ارتفاع ملحوظ: " + "، ".join(f"{I.event_label(r.event)} ({r.median_lift:.2f}×)" for r in flat.itertuples()) + ".")] if len(flat) else [])), unsafe_allow_html=True)
    p3.markdown(panel(L("Hypotheses requiring validation", "فرضيات تحتاج إلى تحقق"), [
        L("Recurring calendar events may be associated with higher flower-shop search interest; this is untested beyond five occurrences per event.",
          "قد ترتبط المناسبات المتكررة باهتمام أعلى بالبحث عن محل ورد؛ وهذا لم يُختبر خارج خمس مرات لكل مناسبة."),
        L("Islamic events move about 11 days earlier each year, so a fixed-month pattern would blur them; the overlay below shows the Eid markers shifting.",
          "تتقدم المناسبات الإسلامية نحو 11 يومًا كل سنة، فيُضعف النمط الشهري الثابت وضوحها؛ ويُظهر الرسم أدناه انزياح علامات العيد."),
        L("Whether searches reflect purchases is unknown: Google Trends contains no sales information.", "لا يُعرف إن كانت عمليات البحث تعكس مشتريات: لا يتضمن Google Trends أي معلومات عن المبيعات.")]), unsafe_allow_html=True)
    st.markdown("##### " + L("Year-over-year overlay", "مقارنة السنوات فوق بعضها"))
    yo = yoy_frame(analytic, term)
    st.plotly_chart(K.yoy_chart(yo, ecal), width="stretch")
    alt(L(f"{K.label(term)}, mean weekly index by calendar year: ", f"{K.label(term)}، متوسط المؤشر الأسبوعي حسب السنة الميلادية: ")
        + ("؛ " if RTL else "; ").join(f"{int(y)} {v:.0f}" for y, v in yo.groupby("year")["value"].mean().items()) + L(" (2021 and 2026 are partial years).", " (2021 و2026 سنتان جزئيتان)."))
    T.caption(L("Each line is a calendar year on the same scale; dotted lines are partial years. Markers: the week containing Eid al-Fitr (◆) and Eid al-Adha (■). "
                "Marker dates are Umm al-Qura calendar dates; the hover text says whether each was verified against a Saudi announcement.",
                "كل خط سنة ميلادية على المقياس نفسه؛ الخطوط النقطية سنوات جزئية. العلامات: الأسبوع الذي يحوي عيد الفطر (◆) وعيد الأضحى (■). "
                "تواريخ العلامات وفق تقويم أم القرى، ويبيّن نص التمرير هل تم التحقق من كل منها من إعلان سعودي."))
    st.markdown("##### " + L("Average by month", "المتوسط حسب الشهر"))
    st.plotly_chart(K.month_chart(mp), width="stretch")
    alt(L(f"Average by month for {K.label(term)}: highest {mname(mx['top'][0][0])} ({mx['top'][0][1]:.2f}× the overall mean) and {mname(mx['top'][1][0])} ({mx['top'][1][1]:.2f}×); lowest {mname(mx['bottom'][-1][0])} ({mx['bottom'][-1][1]:.2f}×).",
          f"المتوسط الشهري لـ {K.label(term)}: الأعلى {mname(mx['top'][0][0])} ({mx['top'][0][1]:.2f}× من المتوسط العام) و{mname(mx['top'][1][0])} ({mx['top'][1][1]:.2f}×)؛ الأدنى {mname(mx['bottom'][-1][0])} ({mx['bottom'][-1][1]:.2f}×)."))
    T.caption(L(f"Data scale: {K.friendly_scale(mp['scale_id'].iloc[0])}. Ratios are within-series (unit-free), so the export's normalisation does not affect them.",
                f"مقياس البيانات: {K.friendly_scale(mp['scale_id'].iloc[0], 'ar')}. النسب داخل السلسلة نفسها (بلا وحدة)، فلا يؤثر تطبيع التصدير فيها."))
    st.markdown("##### " + L("Event-week lift", "ارتفاع أسابيع المناسبات"))
    T.caption(L("Event-week value ÷ median of surrounding baseline weeks (±2–4 weeks, other events excluded). Five occurrences per event: indicative, not significance-tested.",
                "قيمة أسبوع المناسبة ÷ وسيط الأسابيع المحيطة (±2–4 أسابيع دون المناسبات الأخرى). خمس مرات لكل مناسبة: إرشادي وغير مُختبَر إحصائيًا."))
    st.plotly_chart(K.lift_chart(es), width="stretch")
    alt(L("Median event-week lift over baseline: ", "الوسيط لارتفاع أسبوع المناسبة فوق خط الأساس: ")
        + ("؛ " if RTL else "; ").join(f"{I.event_label(r.event)} {r.median_lift:.2f}×" for r in es.sort_values("median_lift", ascending=False).itertuples()) + ".")
    st.dataframe(pd.DataFrame({L("Event", "المناسبة"): es["event"].map(I.event_label), L("Occurrences", "المرات"): es["occurrences"], L("Median lift", "وسيط الارتفاع"): es["median_lift"].round(2),
                               "Min": es["min_lift"].round(2), "Max": es["max_lift"].round(2), L("Years > 1.2×", "سنوات > 1.2×"): es["years_with_lift_gt_1_2"]}), hide_index=True, width="stretch")

# =================================================================================================== Regions & map
elif section == "regions":
    st.markdown("##### " + L("Regional comparison across the 13 regions", "مقارنة المناطق الـ13"))
    m1, m2 = st.columns([3, 2])
    view = m1.radio(L("Measure", "المقياس"), ["index", "share"], key="reg_measure",
                    format_func=lambda v: L("Index per term (100 = highest region for that term)", "مؤشر لكل مصطلح (100 = أعلى منطقة لهذا المصطلح)") if v == "index"
                    else L("Share of the five compared terms (group A)", "حصة المصطلحات الخمسة المقارَنة (المجموعة A)"))
    per_term = view == "index"
    reg = idx if per_term else share
    t = m2.selectbox(L("Search term", "مصطلح البحث"), term_options(reg), format_func=K.label, key="reg_term")
    d = reg[reg["term"] == t]
    names = {r.region_iso: (r.region_en, r.region_ar) for r in d.itertuples()}
    metric_name = L("index (100 = peak region)", "المؤشر (100 = أعلى منطقة)") if per_term else L("% of the five terms' searches", "% من عمليات بحث المصطلحات الخمسة")

    def on_map_select() -> None:
        ev = st.session_state.get(f"regmap_{st.session_state['map_nonce']}")
        pts = ev["selection"]["points"] if ev else []
        st.session_state["compare"] = toggle_from_map(st.session_state.get("compare", []), [p.get("location") for p in pts if p.get("location")])
        st.session_state["map_nonce"] += 1  # fresh widget => the next event contains only the next click

    def clear_compare() -> None:
        st.session_state["compare"] = []
        st.session_state["map_nonce"] += 1

    cc = st.columns([5, 1], vertical_alignment="bottom")
    cc[0].multiselect(L("Compare regions (or click regions on the map; shift-click for several)", "قارن المناطق (أو انقر عليها في الخريطة؛ Shift+نقر لعدة مناطق)"), list(names),
                      format_func=lambda i: region_label(names, i), key="compare", placeholder=L("Choose regions", "اختر المناطق"))
    cc[1].button(L("Clear", "مسح"), on_click=clear_compare, key="clear_cmp")
    selected = [i for i in st.session_state["compare"] if i in names]

    st.markdown(K.coverage_chips(d), unsafe_allow_html=True)
    lo_, hi_, n_ = spread_of_available(d)
    if not per_term and n_ >= 4 and hi_ - lo_ < 6:
        T.callout(L(f"<b>Regions barely differ in this view.</b> The share of this term ranges only {lo_:.0f}–{hi_:.0f}% across regions, within rounding of each other, so the map carries little information. Use the per-term index to compare regions.",
                    f"<b>تكاد المناطق لا تختلف في هذا العرض.</b> تتراوح حصة هذا المصطلح بين {lo_:.0f}% و{hi_:.0f}% فقط عبر المناطق، أي ضمن التقريب، فتحمل الخريطة معلومات قليلة. استخدم مؤشر المصطلح للمقارنة بين المناطق."), "warn")
    T.callout(L("<b>How to read this.</b> Google Trends divides each region's searches for the term by that region's <i>total</i> searches, then rescales to 0–100 "
                + ("against the single highest region for this one term. " if per_term else "as the term's share among the five compared terms in that region. ")
                + "It shows <b>relative interest</b>, not the number of searches, market size or sales. Each export has its own scale, so values are compared only within the current view.",
                "<b>كيف تقرأ هذا العرض.</b> يقسم Google Trends عمليات بحث كل منطقة عن المصطلح على <i>إجمالي</i> عمليات بحث المنطقة، ثم يعيد القياس إلى 0–100 "
                + ("نسبةً إلى أعلى منطقة لهذا المصطلح وحده. " if per_term else "بوصفه حصة المصطلح بين المصطلحات الخمسة المقارَنة في تلك المنطقة. ")
                + "وهو يبيّن <b>اهتمامًا نسبيًا</b> وليس عدد عمليات البحث ولا حجم السوق ولا المبيعات. لكل تصدير مقياسه الخاص، فلا تُقارن القيم إلا ضمن العرض الحالي."))
    left, right = st.columns([6, 5], gap="large")
    with left:
        if geo_ok:
            show_names = st.checkbox(L("Show region names on the map", "إظهار أسماء المناطق على الخريطة"), value=False, key="reg_names")
            st.plotly_chart(K.region_map(d, load_map_geojson(str(ROOT)), t, metric_name, labels=show_names, selected=selected, height=520), width="stretch",
                            key=f"regmap_{st.session_state['map_nonce']}", on_select=on_map_select, selection_mode=("points",))
            st.markdown(T.map_legend_html(), unsafe_allow_html=True)
            T.caption(L(ATTRIBUTION_TEXT + ". Boundaries are an OpenStreetMap-based depiction for thematic display, not an authoritative survey.",
                        "الحدود: geoBoundaries (SAU ADM1)، © مساهمو OpenStreetMap، رخصة ODbL 1.0 · إصدار مبسّط دون تعديل. الحدود تصوير مبني على OpenStreetMap للعرض الموضوعي وليست مسحًا رسميًا."))
        else:
            T.callout(L(f"<b>Map unavailable:</b> boundary file failed verification ({geo_detail}). The ranked comparison is unaffected.",
                        f"<b>الخريطة غير متاحة:</b> فشل التحقق من ملف الحدود ({geo_detail}). المقارنة المرتّبة غير متأثرة."), "warn")
    with right:
        st.markdown("###### " + L("Ranked comparison (all 13 regions)", "المقارنة المرتّبة (المناطق الـ13)"))
        st.plotly_chart(K.region_bar(d, metric_name, selected=selected, height=500), width="stretch")
        alt(map_text_alternative(d, K.label(t), LANG))
    st.markdown("###### " + L("Selected regions", "المناطق المحددة"))
    vlabel = L("Index", "المؤشر") if per_term else L("Share %", "الحصة %")
    if selected:
        st.dataframe(K.compare_table(d, selected, vlabel), hide_index=True, width="stretch")
        if not per_term:  # same export → all five terms can be shown together
            sh = share[share["region_iso"].isin(selected)].copy()
            sh["txt"] = [f"{v:.0f}%" if not c and not m else ("<1%" if c else "—") for v, c, m in zip(sh["value"], sh["is_censored"], sh["is_missing"])]
            pv = sh.pivot(index="region_iso", columns="term", values="txt").reindex(selected)
            pv.columns = [K.label(c) for c in pv.columns]
            pv.insert(0, L("Region", "المنطقة"), [region_label(names, i) for i in pv.index])
            st.markdown(L("Composition of searches in the selected regions (one export, one scale; each row sums to about 100%):",
                          "تركيبة عمليات البحث في المناطق المحددة (تصدير واحد ومقياس واحد؛ مجموع كل صف نحو 100%):"))
            st.dataframe(pv.reset_index(drop=True), hide_index=True, width="stretch")
        elif len(selected) >= 2:
            avail = d[d["region_iso"].isin(selected) & ~d["is_missing"] & ~d["is_censored"]].sort_values("value", ascending=False)
            if len(avail) >= 2:
                T.caption(L(f"Among the selected regions, {avail.iloc[0]['region_en']} has the highest index ({avail.iloc[0]['value']:.0f}); the spread between the highest and lowest selected is "
                            f"{avail.iloc[0]['value'] - avail.iloc[-1]['value']:.0f} index points. Index values are normalised shares, not volumes.",
                            f"بين المناطق المحددة، لدى {avail.iloc[0]['region_ar']} أعلى مؤشر ({avail.iloc[0]['value']:.0f})؛ والفارق بين الأعلى والأدنى بين المحددة "
                            f"{avail.iloc[0]['value'] - avail.iloc[-1]['value']:.0f} نقطة. قيم المؤشر حصص مُطبَّعة وليست أحجامًا."))
    else:
        T.caption(L("Click a region on the map or choose regions above to compare them. Comparisons use only the current term and measure (one export).",
                    "انقر على منطقة في الخريطة أو اخترها أعلاه للمقارنة. تستخدم المقارنات المصطلح والمقياس الحاليين فقط (تصدير واحد)."))
    with st.expander(L("Status of all 13 regions", "حالة المناطق الـ13")):
        K.status_table(d, vlabel)
    with st.expander(L("Ranking check and interpretation", "فحص الترتيب وتفسيره")):
        top = top_region(idx, TARGET)
        sh_t = share[(share["term"] == TARGET) & ~share["is_missing"] & ~share["is_censored"]].sort_values("value", ascending=False)
        ar_of = dict(zip(idx["region_en"], idx["region_ar"]))
        st.markdown(L(f"- **Verified:** the per-term export for {K.label(TARGET)} lists all 13 regions with exact values; **{top['region_en']}** is highest (index {top['value']:.0f}), "
                      f"then {top['runner_up_en']} ({top['runner_up_value']:.0f}). The ranking was recomputed independently from the original CSV (see `REGIONAL_RANKING_VERIFICATION.md`; also asserted in the test suite).\n"
                      f"- **Different measure, different answer:** in the group-A share export the highest share for the same term is {sh_t.iloc[0]['region_en']} ({sh_t.iloc[0]['value']:.0f}%). "
                      "The two exports answer different questions (a term's interest relative to the peak region vs. its share among five terms) and are never merged.\n"
                      "- **Not established:** why a region ranks high, whether the order among the top regions is stable (no repeated independent exports exist), or anything about sales or purchase volume.\n"
                      "- The regional exports contain one aggregate per region for 2021-11-10 → 2026-11-10; regional trends and forecasts are not available.\n"
                      "- City-level comparison (Riyadh, Jeddah, Dammam) is **not** implemented: no verified city data exists in this project, and independently normalised exports cannot be compared. See `CITY_LEVEL_FEASIBILITY.md`.",
                      f"- **تم التحقق:** يسرد تصدير المصطلح الواحد لـ {K.label(TARGET)} المناطق الـ13 كلها بقيم دقيقة؛ و**{ar_of[top['region_en']]}** هي الأعلى (المؤشر {top['value']:.0f})، "
                      f"تليها {ar_of[top['runner_up_en']]} ({top['runner_up_value']:.0f}). أُعيد حساب الترتيب بشكل مستقل من ملف CSV الأصلي (راجع `REGIONAL_RANKING_VERIFICATION.md`؛ ومؤكَّد أيضًا في اختبارات المشروع).\n"
                      f"- **مقياس مختلف، إجابة مختلفة:** في تصدير حصص المجموعة A تكون أعلى حصة للمصطلح نفسه في {ar_of[sh_t.iloc[0]['region_en']]} ({sh_t.iloc[0]['value']:.0f}%). "
                      "يجيب التصديران عن سؤالين مختلفين (اهتمام المصطلح نسبةً إلى أعلى منطقة مقابل حصته بين خمسة مصطلحات) ولا يُدمجان أبدًا.\n"
                      "- **غير مُثبَت:** سبب ارتفاع منطقة ما، ولا هل ثبات الترتيب بين المناطق العليا (لا توجد تصديرات مستقلة متكررة)، ولا أي شيء عن المبيعات أو حجم الشراء.\n"
                      "- تحتوي التصديرات الإقليمية على قيمة إجمالية واحدة لكل منطقة للفترة 2021-11-10 ← 2026-11-10؛ ولا تتوفر اتجاهات أو توقعات إقليمية.\n"
                      "- مقارنة المدن (الرياض، جدة، الدمام) **غير منفّذة**: لا توجد بيانات مدن موثّقة في هذا المشروع، ولا تصح مقارنة تصديرات مُطبَّعة بشكل مستقل. راجع `CITY_LEVEL_FEASIBILITY.md`."))

# =================================================================================================== Commercial-term mix
elif section == "mix":
    mix = get("region_groupB4_share")
    st.markdown("##### " + L("Commercial-term mix across the 13 regions", "تركيبة المصطلحات التجارية عبر المناطق الـ13"))
    mix_order_by = st.selectbox(L("Order regions by", "ترتيب المناطق حسب"), [None, *MIX_TERM_ORDER[:3]], key="mix_order",
                                format_func=lambda x: L("Region name (A → Z)", "اسم المنطقة (أ ← ي)") if x is None else L(f"{K.label(x)} share (largest first)", f"حصة {K.label(x)} (الأكبر أولًا)"))
    cnt = term_mix_cell_counts(mix)
    order = term_mix_order(mix, mix_order_by)
    msum = term_mix_regions(mix)
    T.callout(L("<b>How to read this.</b> Each bar shows how the searches in <i>one region</i> are split among four commercial terms (a relative composition, as published by Google Trends). "
                "It is <b>not</b> search volume, sales, revenue, market size or consumer demand, and it does not say how much people search. "
                "A larger share for a term means that term is a larger part of that region's own four-term mix, not that the region searches for it more than other regions. "
                "This export has its own scale: it is never combined with the regional interest index or with the five-term shares.",
                "<b>كيف تقرأ هذا العرض.</b> يبيّن كل عمود كيف تتوزع عمليات البحث في <i>منطقة واحدة</i> بين أربعة مصطلحات تجارية (تركيبة نسبية كما نشرها Google Trends). "
                "وهو <b>ليس</b> حجم بحث ولا مبيعات ولا إيرادات ولا حجم سوق ولا طلبًا من المستهلكين، ولا يبيّن كم يبحث الناس. "
                "الحصة الأكبر لمصطلح تعني أنه جزء أكبر من تركيبة المصطلحات الأربعة في تلك المنطقة نفسها، لا أن المنطقة تبحث عنه أكثر من غيرها. "
                "لهذا التصدير مقياسه الخاص: لا يُدمج أبدًا مع مؤشر الاهتمام الإقليمي ولا مع حصص المصطلحات الخمسة."))
    st.plotly_chart(K.term_mix_bar(mix, order, height=170 + 38 * len(order)), width="stretch", key="mixbar")
    alt(term_mix_text_alternative(mix, order, LANG))
    T.caption(L(f"Bars show the published shares exactly as exported (axis fixed at 0–100%; nothing is rescaled or redistributed). In this export the published shares of each region total "
                f"{msum['published_sum'].min():.0f}–{msum['published_sum'].max():.0f}%, "
                + ("so no unspecified remainder is shown. " if (msum["unspecified_remainder"] == 0).all() else "the gap to 100% is drawn as an unspecified remainder, not given to any term. ")
                + f"Of {cnt['cells']} cells, {cnt['numeric']} are numeric, {cnt['censored']} are censored by Google (“<1%”, true value between 0 and 1%) and {cnt['missing']} are blank (no data reported). "
                "Censored and blank cells are never drawn as zero; they are marked to the right of the bars.",
                f"تعرض الأعمدة الحصص المنشورة كما صُدّرت تمامًا (المحور ثابت 0–100%؛ لا إعادة قياس ولا إعادة توزيع). في هذا التصدير يبلغ مجموع الحصص المنشورة لكل منطقة "
                f"{msum['published_sum'].min():.0f}–{msum['published_sum'].max():.0f}%، "
                + ("فلا يظهر متبقٍ غير محدد. " if (msum["unspecified_remainder"] == 0).all() else "وتُرسم الفجوة حتى 100% متبقيًا غير محدد دون نسبته إلى أي مصطلح. ")
                + f"من أصل {cnt['cells']} خلية، {cnt['numeric']} رقمية و{cnt['censored']} مخفية من Google («<1%»، القيمة الفعلية بين 0 و1%) و{cnt['missing']} فارغة (لم يُبلَّغ عن بيانات). "
                "لا تُرسم الخلايا المخفية أو الفارغة صفرًا أبدًا؛ بل تُعلَّم يمين الأعمدة."))
    for term in MIX_TERM_ORDER:
        sub = mix[mix["term"] == term]
        if sub["is_censored"].any() or sub["is_missing"].any():
            nc, nm_ = int(sub["is_censored"].sum()), int(sub["is_missing"].sum())
            if not sub["value"].notna().any():
                T.callout(L(f"<b>{K.label(term)} cannot be drawn as a bar in any region</b> — {nc} regions are censored (below 1%) and {nm_} have no data. Its share is therefore unquantified, not zero.",
                            f"<b>لا يمكن رسم {K.label(term)} عمودًا في أي منطقة</b> — {nc} مناطق مخفية (أقل من 1%) و{nm_} بلا بيانات. لذا فحصته غير مُقدَّرة وليست صفرًا."), "warn")
            else:
                T.callout(L(f"<b>{K.label(term)}</b>: {nc} censored and {nm_} blank cells are not drawn.", f"<b>{K.label(term)}</b>: {nc} خلايا مخفية و{nm_} فارغة غير مرسومة."), "warn")
    T.caption(L("One snapshot per region (2021-11-10 → 2026-11-10). No repeated exports exist, so how stable these shares are under Google's sampling is not established. "
                f"Why regions differ is not explained by these data. Data scale: {K.friendly_scale(mix['scale_id'].iloc[0])}.",
                "لقطة واحدة لكل منطقة (2021-11-10 ← 2026-11-10). لا توجد تصديرات متكررة، لذا لا يُعرف مدى ثبات هذه الحصص مع أخذ العينات في Google. "
                f"ولا تفسّر هذه البيانات سبب اختلاف المناطق. مقياس البيانات: {K.friendly_scale(mix['scale_id'].iloc[0], 'ar')}."))
    with st.expander(L("Table of published values (all 13 regions)", "جدول القيم المنشورة (المناطق الـ13)")):
        tt = term_mix_table(mix)
        cell = lambda r: f"{r['value']:.0f}%" if r["status"] == K.AVAILABLE else (L("<1% (censored)", "<1% (مخفية)") if r["status"] == K.CENSORED else L("no data", "بلا بيانات"))
        tt["txt"] = tt.apply(cell, axis=1)
        pv = tt.pivot(index="region_iso", columns="term", values="txt").reindex(order)
        pv = pv[[c for c in MIX_TERM_ORDER if c in pv.columns]]
        pv.columns = [K.label(c) for c in pv.columns]
        pv.insert(0, L("Region", "المنطقة"), [rname(r.region_en, r.region_ar) for r in msum.set_index("region_iso").loc[pv.index].itertuples()])
        pv[L("Published total", "المجموع المنشور")] = [f"{msum.set_index('region_iso').loc[i, 'published_sum']:.0f}%" for i in pv.index]
        st.dataframe(pv.reset_index(drop=True), hide_index=True, width="stretch")

# =================================================================================================== Forecast
elif section == "forecast":
    gain, ci = gate["relative_mae_improvement"], gate["mean_abs_error_diff_ci95"]
    ci_txt = I.ltr(f"[{ci[0]:.2f}, {ci[1]:.2f}]")
    bs = get("backtest_summary", True)
    allrow = bs[(bs["term"] == TARGET) & (bs["h"] == "all")].iloc[0]
    st.markdown("##### " + L("National forecast — ", "التوقع الوطني — ") + K.label(TARGET) + L(" (commercial group B)", " (المجموعة التجارية B)"))
    T.callout(L("<b>Engineering quality decision: the forecast is withheld.</b> No forecast is shown. A forecast is shown only if it demonstrably beats a naive baseline under a rule fixed in advance. "
                "This one did not: publishing it would imply accuracy the evidence does not support. The rule was not adjusted to publish a result."
                if not published else "<b>The forecast passed its pre-set validation gate</b> and is shown with empirical prediction intervals.",
                "<b>قرار جودة هندسي: التوقع محجوب.</b> لا يُعرض أي توقع. لا يُعرض التوقع إلا إذا تفوّق بوضوح على نموذج ساذج وفق قاعدة مُحدَّدة مسبقًا. "
                "هذا التوقع لم يفعل: ونشره يوحي بدقة لا تدعمها الأدلة. ولم تُعدَّل القاعدة لنشر نتيجة."
                if not published else "<b>اجتاز التوقع بوابة التحقق المُحدَّدة مسبقًا</b> ويُعرض مع فترات تنبؤ تجريبية."), "warn" if not published else "")
    k1, k2, k3 = st.columns(3)
    k1.markdown(T.kpi(L("Publication gate", "بوابة النشر"), L("Passed", "اجتازت") if gate["passed"] else L("Not passed", "لم تُجتَز"), L("rule fixed before evaluation", "قاعدة مُحدَّدة قبل التقييم"), "" if gate["passed"] else "warn"), unsafe_allow_html=True)
    k2.markdown(T.kpi(L("MAE vs best naive baseline", "MAE مقابل أفضل خط أساس ساذج"), I.ltr(f"{gain:+.1%}"), L(f"requirement: at least +{GATE_MIN_IMPROVEMENT:.0%}", f"الشرط: {I.ltr(f'+{GATE_MIN_IMPROVEMENT:.0%}')} على الأقل")), unsafe_allow_html=True)
    k3.markdown(T.kpi(L("95% CI of the MAE gain", "فاصل الثقة 95% لمكسب MAE"), ci_txt, L("requirement: entirely above 0", "الشرط: أعلى من 0 بالكامل")), unsafe_allow_html=True)
    T.criteria_rows([(L(f"MAE improvement over the best naive baseline must be ≥ {GATE_MIN_IMPROVEMENT:.0%}", f"يجب أن يكون تحسّن MAE فوق أفضل خط أساس ساذج ≥ {GATE_MIN_IMPROVEMENT:.0%}"), I.ltr(f"{gain:.1%}"), bool(gain >= GATE_MIN_IMPROVEMENT)),
                     (L("95% bootstrap CI of the MAE gain must be above 0", "يجب أن يكون فاصل الثقة 95% (bootstrap) لمكسب MAE أعلى من 0"), ci_txt, bool(ci[0] > 0))])
    w1, w2 = st.columns(2, gap="medium")
    base_name = {"seasonal_naive_52": L("seasonal naive (value from 52 weeks earlier)", "الساذج الموسمي (قيمة قبل 52 أسبوعًا)"), "naive_last": L("last observed week", "آخر أسبوع مرصود")}.get(gate["best_naive_baseline"], gate["best_naive_baseline"])
    w1.markdown(panel(L("What was evaluated", "ما الذي تم تقييمه"), [
        L(f"Target: weekly relative search interest for {K.label(TARGET)} (group B export).", f"الهدف: الاهتمام النسبي الأسبوعي بالبحث عن {K.label(TARGET)} (تصدير المجموعة B)."),
        L(f"Horizons: {HORIZONS[0]}–{HORIZONS[-1]} weeks ahead; rolling-origin, expanding window; first origin after {MIN_TRAIN} weeks; {gate['origins']} origins.",
          f"الآفاق: {HORIZONS[0]}–{HORIZONS[-1]} أسابيع قادمة؛ أصل متحرك ونافذة متوسعة؛ أول أصل بعد {MIN_TRAIN} أسبوعًا؛ {gate['origins']} أصلًا."),
        L("Candidate: ridge regression on calendar covariates known in advance (Umm al-Qura Islamic dates, fixed holidays, annual seasonality) plus a trailing 4-week level.",
          "المرشّح: انحدار ridge على متغيرات تقويمية معروفة مسبقًا (تواريخ أم القرى الإسلامية، الإجازات الثابتة، الموسمية السنوية) مع مستوى آخر 4 أسابيع."),
        L(f"Baselines: last observed week; seasonal naive (52 weeks). Best baseline here: <b>{base_name}</b>.", f"خطوط الأساس: آخر أسبوع مرصود؛ الساذج الموسمي (52 أسبوعًا). أفضل خط أساس هنا: <b>{base_name}</b>.")]), unsafe_allow_html=True)
    w2.markdown(panel(L("Why it was withheld", "لماذا حُجب"), [
        L(f"Mean absolute error: candidate {allrow['calendar_ols']:.2f} vs baseline {allrow['seasonal_naive_52']:.2f} (index points); MASE {gate['mase_calendar_ols']:.2f} vs {gate['mase_best_naive']:.2f}.",
          f"متوسط الخطأ المطلق: المرشّح {allrow['calendar_ols']:.2f} مقابل خط الأساس {allrow['seasonal_naive_52']:.2f} (نقاط مؤشر)؛ MASE {gate['mase_calendar_ols']:.2f} مقابل {gate['mase_best_naive']:.2f}."),
        L(f"The gain ({gain:.1%}) clears the size requirement but its 95% interval [{ci[0]:.2f}, {ci[1]:.2f}] includes zero, so it could be chance.",
          f"يتجاوز المكسب ({I.ltr(f'{gain:.1%}')}) شرط الحجم لكن فاصله 95% {ci_txt} يشمل الصفر، فقد يكون محض صدفة."),
        L("The interval is optimistic (origins overlap) and only about 5 annual cycles exist.", "الفاصل متفائل (الأصول متداخلة) ولا توجد سوى نحو 5 دورات سنوية.")]), unsafe_allow_html=True)
    st.markdown(panel(L("What additional evidence would be needed", "ما الأدلة الإضافية المطلوبة"), [
        L("More annual cycles: each year adds one Eid al-Fitr and one Valentine's Day week, the weeks that matter most.", "مزيد من الدورات السنوية: كل سنة تضيف أسبوع عيد فطر وأسبوع عيد حب، وهما الأسبوعان الأهم."),
        L("Repeated independent exports of the same query to measure Google Trends sampling noise (none have been collected, so stability is unknown).",
          "تصديرات مستقلة متكررة للاستعلام نفسه لقياس ضوضاء أخذ العينات في Google Trends (لم يُجمع أي منها، لذا الثبات مجهول)."),
        L("An evaluation plan registered before looking at new data (for example a block bootstrap by year, event-week vs ordinary-week loss, and a correction for the number of series tested).",
          "خطة تقييم تُسجَّل قبل الاطلاع على بيانات جديدة (مثل bootstrap بالكتل حسب السنة، وخسارة أسابيع المناسبات مقابل الأسابيع العادية، وتصحيح لعدد السلاسل المختبَرة)."),
        L("Thresholds stay as they are; the decision is revisited only when new evidence is available.", "تبقى العتبات كما هي؛ ولا يُعاد النظر في القرار إلا عند توفر أدلة جديدة.")], style="margin-top:.8rem"), unsafe_allow_html=True)
    if published:
        fc = get("forecast_national", True)
        dd = full_b[full_b["term"] == TARGET]
        st.plotly_chart(K.series_chart(dd[dd["week_start"] >= dd["week_start"].max() - pd.Timedelta(weeks=52)], forecast=fc), width="stretch")
    with st.expander(L("Backtest detail — mean absolute error by horizon (index points)", "تفاصيل الاختبار الخلفي — متوسط الخطأ المطلق حسب الأفق (نقاط مؤشر)")):
        t_bs = bs[bs["term"] == TARGET].drop(columns=["term", "stem"]).rename(columns={"h": L("Weeks ahead", "أسابيع قادمة"), "naive_last": L("Last week", "آخر أسبوع"),
                                                                                       "seasonal_naive_52": L("Seasonal naive", "ساذج موسمي"), "calendar_ols": L("Calendar model", "النموذج التقويمي")}).round(2)
        st.dataframe(t_bs, hide_index=True, width="stretch")
        T.caption(gate["caveat"] if not RTL else "الأصول متداخلة (الخطوة أسبوعان، آفاق 4 أسابيع) لذا فإن فاصل الثقة متفائل؛ وتوجد نحو 5 دورات سنوية فقط.")
    with st.expander(L("Other series tested (exploratory, not published)", "سلاسل أخرى اختُبرت (استكشافية، غير منشورة)")):
        rows = [{L("Series", "السلسلة"): isolate(k.split("|")[1]) + " (" + k.split("|")[0] + ")", L("Gate passed", "اجتازت البوابة"): v["passed"], L("MAE gain", "مكسب MAE"): round(v["relative_mae_improvement"], 3),
                 "CI95": f"[{v['mean_abs_error_diff_ci95'][0]:.2f}, {v['mean_abs_error_diff_ci95'][1]:.2f}]"} for k, v in status["all_gates"].items()]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        T.caption(L("The flower-shop term was designated the target before backtesting (best resolution and zero-share profile). Four series were tested, so a single pass "
                    "(e.g. flower delivery, median index 6) may be chance and its integer resolution is poor; it is not published.",
                    "عُيّن مصطلح محل ورد هدفًا قبل الاختبار الخلفي (أفضل دقة وأقل نسبة أصفار). اختُبرت أربع سلاسل، فقد يكون نجاح واحدة "
                    "(مثل توصيل ورد، وسيط المؤشر 6) محض صدفة ودقتها الصحيحة ضعيفة؛ ولذلك لا تُنشر."))

# =================================================================================================== Data engineering
else:
    n_raw = len(manifest)
    mix4 = get("region_groupB4_share")
    T.kpi_row([
        T.kpi(L("Raw data integrity", "سلامة البيانات الخام"), L(f"{n_raw} of {n_raw} files", f"{n_raw} من {n_raw} ملفًا"), L("SHA-256 equals manifest · no un-manifested files", "SHA-256 مطابق لـ manifest · لا ملفات غير مسجّلة"),
              definition=L("Checked on this page load; raw files are never modified or overwritten.", "يُفحص عند تحميل هذه الصفحة؛ ولا تُعدَّل الملفات الخام ولا يُكتب فوقها أبدًا.")),
        T.kpi(L("Validation", "التحقق"), L(f"{vres['summary']['errors']} errors", f"{vres['summary']['errors']} أخطاء"),
              L(f"{vres['summary']['passed']} checks passed · {vres['summary']['warnings']} documented warnings", f"اجتياز {vres['summary']['passed']} فحصًا · {vres['summary']['warnings']} تحذيرات موثّقة"), "purple",
              definition=L("Automated checks run by the pipeline: schema, dates, ranges, 13-region coverage, censoring, scale integrity.", "فحوص آلية يجريها خط المعالجة: البنية، التواريخ، النطاقات، تغطية المناطق الـ13، الإخفاء، سلامة المقاييس.")),
        T.kpi(L("Historical observations", "الملاحظات التاريخية"), L(f"{history_coverage(long_b)['n_weeks']} weeks", f"{history_coverage(long_b)['n_weeks']} أسبوعًا"),
              L(f"{vres['records']['timeline_B_rows'] + vres['records']['timeline_A_rows']:,} weekly rows in two exports", f"{vres['records']['timeline_B_rows'] + vres['records']['timeline_A_rows']:,} صفًا أسبوعيًا في تصديرين"),
              definition=L("Weekly buckets analysed per term (edge partial weeks excluded).", "الفترات الأسبوعية المحلَّلة لكل مصطلح (باستثناء الأسابيع الحدّية الجزئية).")),
        T.kpi(L("Forecast publication", "نشر التوقع"), L("Withheld", "محجوب") if not published else L("Published", "منشور"), L("gate not passed", "لم تُجتَز البوابة") if not published else L("gate passed", "اجتيزت البوابة"),
              "warn" if not published else "", definition=L("Decided by the fixed acceptance gate; verified consistent with the files on disk.", "يُحدَّد بواسطة بوابة القبول الثابتة؛ ويُتحقق من اتساقه مع الملفات على القرص.")),
    ])
    st.markdown("##### " + L("Verification performed on this page load", "التحقق الذي أُجري عند تحميل هذه الصفحة"))
    st.dataframe(pd.DataFrame(report.checks).assign(ok=lambda d: d["ok"].map({True: L("pass", "نجح"), False: L("FAIL", "فشل")})).rename(columns={"name": L("Check", "الفحص"), "ok": L("Result", "النتيجة"), "detail": L("Detail", "التفصيل")}),
                 hide_index=True, width="stretch", height=38 + 35 * min(len(report.checks), 18))
    T.caption(L("Static checks of the files on disk, run each time the page loads. This is not live or real-time monitoring.", "فحوص ساكنة للملفات على القرص تُجرى عند كل تحميل للصفحة. وهي ليست مراقبة حيّة أو فورية."))
    st.markdown("##### " + L("Pipeline run record", "سجل تشغيل خط المعالجة"))
    st.dataframe(pd.DataFrame([
        {L("Stage", "المرحلة"): L("pipeline (ingest → validate → clean)", "خط المعالجة (استيعاب ← تحقق ← تنظيف)"), L("Recorded by the pipeline at", "سجّله خط المعالجة في"): prov_p.get("generated_at_utc", "—"),
         L("Output files hashed", "ملفات المخرجات المُبصَّمة"): len(prov_p["outputs"]), L("Input fingerprint", "بصمة المدخلات"): prov_p["input_fingerprint"][:12] + "…"},
        {L("Stage", "المرحلة"): L("phase_a (analysis, backtest, gate)", "phase_a (التحليل، الاختبار الخلفي، البوابة)"), L("Recorded by the pipeline at", "سجّله خط المعالجة في"): prov_a.get("generated_at_utc", "—"),
         L("Output files hashed", "ملفات المخرجات المُبصَّمة"): len(prov_a["outputs"]), L("Input fingerprint", "بصمة المدخلات"): prov_a["input_fingerprint"][:12] + "…"},
    ]), hide_index=True, width="stretch")
    T.caption(L("Timestamps are written by the pipeline when it runs (UTC). They describe processing time, not when the data were retrieved from Google Trends.",
                "تُكتب الطوابع الزمنية بواسطة خط المعالجة عند تشغيله (UTC). وهي تصف وقت المعالجة لا وقت جلب البيانات من Google Trends."))
    st.markdown("##### " + L("Dataset coverage", "تغطية مجموعات البيانات"))
    ds, rows_, cov_, mc = L("Dataset", "مجموعة البيانات"), L("Rows", "الصفوف"), L("Coverage", "التغطية"), L("Missing / censored", "مفقودة / مخفية")
    snap = L("(one snapshot)", "(لقطة واحدة)")
    wk = lambda df: L(f"{df['week_start'].nunique()} weekly buckets × {df['term'].nunique()} terms", f"{df['week_start'].nunique()} فترة أسبوعية × {df['term'].nunique()} مصطلحات")
    rg = lambda df: L(f"{df['region_iso'].nunique()} regions × {df['term'].nunique()} terms {snap}", f"{df['region_iso'].nunique()} منطقة × {df['term'].nunique()} مصطلحات {snap}")
    cov = [
        {ds: L("Weekly series · group A (5 terms)", "سلسلة أسبوعية · المجموعة A (5 مصطلحات)"), rows_: len(long_a), cov_: wk(long_a), mc: f"{int(long_a['is_missing'].sum())} / {int(long_a['is_censored'].sum())}"},
        {ds: L("Weekly series · group B (4 commercial terms)", "سلسلة أسبوعية · المجموعة B (4 مصطلحات تجارية)"), rows_: len(long_b), cov_: wk(long_b), mc: f"{int(long_b['is_missing'].sum())} / {int(long_b['is_censored'].sum())}"},
        {ds: L("Regional shares · group A", "حصص إقليمية · المجموعة A"), rows_: len(share), cov_: rg(share), mc: f"{int(share['is_missing'].sum())} / {int(share['is_censored'].sum())}"},
        {ds: L("Regional index · 5 single-term exports", "المؤشر الإقليمي · 5 تصديرات لمصطلح واحد"), rows_: len(idx), cov_: rg(idx), mc: f"{int(idx['is_missing'].sum())} / {int(idx['is_censored'].sum())}"},
        {ds: L("Regional shares · four commercial terms (group B4)", "حصص إقليمية · أربعة مصطلحات تجارية (المجموعة B4)"), rows_: len(mix4), cov_: rg(mix4),
         mc: L(f"{int(mix4['is_missing'].sum())} blank / {int(mix4['is_censored'].sum())} censored cells", f"{int(mix4['is_missing'].sum())} فارغة / {int(mix4['is_censored'].sum())} مخفية")},
    ]
    st.dataframe(pd.DataFrame(cov), hide_index=True, width="stretch")
    st.markdown("##### " + L("Raw files", "الملفات الخام"))
    man = pd.DataFrame(manifest)
    short = man["comparison_group"].map(lambda g: (L("A · 5 terms", "A · 5 مصطلحات") if g.startswith("A_") else L("B · 4 terms", "B · 4 مصطلحات") if g.startswith("B_")
                                                   else L("B4 · 4-term regional shares", "B4 · حصص إقليمية لـ4 مصطلحات") if g.startswith("B4_") else L("single · ", "مصطلح واحد · ") + g.split(":", 1)[1]))
    st.dataframe(pd.DataFrame({L("File", "الملف"): man["file_name"], L("Group", "المجموعة"): short.map(isolate), L("Data rows", "صفوف البيانات"): man["n_data_rows"],
                               L("SHA-256 (verified)", "SHA-256 (موثّق)"): man["sha256"].str[:10] + "…", L("File modified (inferred, not verified)", "تاريخ تعديل الملف (مستنتج، غير موثّق)"): man["retrieved_date"]}),
                 hide_index=True, width="stretch", height=38 + 35 * len(man))
    T.caption(L("Google Trends does not state when an export was made. The date shown is the file's modification time, not a verified retrieval date. "
                "Regional exports state their query window in the header: 2021-11-10 → 2026-11-10 (day/month/year).",
                "لا يذكر Google Trends متى أُجري التصدير. والتاريخ المعروض هو وقت تعديل الملف وليس تاريخ جلب موثّقًا. "
                "تذكر التصديرات الإقليمية نافذة الاستعلام في الترويسة: 2021-11-10 ← 2026-11-10 (يوم/شهر/سنة)."))
    with st.expander(L("Normalisation per export (why exports are never combined)", "التطبيع لكل تصدير (لماذا لا تُدمج التصديرات أبدًا)")):
        st.dataframe(man[["file_name", "scale_id", "normalization"]].assign(scale_id=man["scale_id"].map(lambda s: K.friendly_scale(s, LANG)))
                     .rename(columns={"file_name": L("File", "الملف"), "scale_id": L("Scale", "المقياس"), "normalization": L("Normalisation", "التطبيع")}), hide_index=True, width="stretch")
    st.markdown("##### " + L("Scope", "النطاق"))
    T.caption(L("Regional level only (13 administrative regions). City-level analysis (Riyadh, Jeddah, Dammam) is a separately approved future extension; its data availability and comparability have not been verified and nothing is implemented.",
                "المستوى الإقليمي فقط (13 منطقة إدارية). تحليل المدن (الرياض، جدة، الدمام) امتداد مستقبلي يحتاج موافقة منفصلة؛ ولم يُتحقق من توفر بياناته أو قابليتها للمقارنة ولا شيء منه منفّذ."))
    st.markdown("##### " + L("Boundary data", "بيانات الحدود"))
    if geo_ok:
        src = jload(PATHS.geo / "SOURCE.json")
        T.caption(L(f"{src['dataset']} · licence: {src['license']} · upstream: {src['upstream_source']} · retrieved {src['retrieved_date']} · file hash verified. {ATTRIBUTION_TEXT}.",
                    f"{src['dataset']} · الرخصة: {src['license']} · المصدر الأصلي: {src['upstream_source']} · جُلب في {src['retrieved_date']} · تم التحقق من بصمة الملف. الحدود: geoBoundaries (SAU ADM1)، © مساهمو OpenStreetMap، رخصة ODbL 1.0."))
    else:
        T.caption(L(f"Boundary verification failed: {geo_detail}", f"فشل التحقق من الحدود: {geo_detail}"))

# ------------------------------------------------------------------ source attribution (every section)
st.markdown('<div class="cap" style="margin-top:2rem;border-top:1px solid #33293a;padding-top:.8rem">' + L(
    'Data: Google Trends (trends.google.com), manual CSV exports, relative search interest only. Region boundaries: geoBoundaries / © OpenStreetMap contributors (ODbL 1.0). '
    'Analysis and dashboard: Saudi Bloom Intelligence, Phase A. Not affiliated with Google. Nothing here is sales, demand or purchase data.',
    'البيانات: Google Trends (trends.google.com)، ملفات CSV مصدَّرة يدويًا، اهتمام نسبي بالبحث فقط. حدود المناطق: geoBoundaries / © مساهمو OpenStreetMap (ODbL 1.0). '
    'التحليل واللوحة: Saudi Bloom Intelligence، المرحلة A. لا صلة لنا بـ Google. لا شيء هنا يمثل مبيعات أو طلبًا أو بيانات شراء.') + '</div>', unsafe_allow_html=True)

# remember the selections (see KEEP above); the dict lives in session state, so this survives language switches and reruns
for _k in KEEP:
    if _k in st.session_state:
        canon[_k] = st.session_state[_k]
