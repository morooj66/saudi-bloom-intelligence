"""Reusable dashboard components (charts, map, tables).

Phase-B readiness: every chart takes a tidy frame that carries `scale_id`; `series_chart(region_iso=…)` filters a
regional weekly frame (REGIONAL_WEEKLY_COLUMNS) — not implemented/populated yet. `assert_same_scale` is called by
every component, so independently normalised exports can never be overlaid or compared as absolute volume.
Missing values are never plotted as zero; censored values are shown as censored.
"""
from __future__ import annotations

import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import i18n as I
import theme as T
from bidi import isolate
from bloom.overview import (AVAILABLE, CENSORED, MIX_TERM_ORDER, NO_DATA, friendly_scale, region_status, regional_rank_table,  # noqa: F401 (re-exported)
                            term_mix_regions, term_mix_table)
from bloom.schema import assert_same_scale

TERM_EN = {"ورد": "flowers (general)", "توصيل ورد": "flower delivery", "بوكيه ورد": "flower bouquet",
           "محل ورد": "flower shop", "شراء ورد": "buy flowers"}
EVENT_LABEL = {"eid_al_fitr": "Eid al-Fitr", "eid_al_adha": "Eid al-Adha", "valentines_day": "Valentine's Day",
               "mothers_day_arab": "Mother's Day (21 Mar)", "new_years_eve": "New Year's Eve", "arafat_day": "Arafat Day",
               "ramadan_start": "Ramadan start", "saudi_founding_day": "Founding Day", "saudi_national_day": "National Day"}
EVENT_SHORT = {"eid_al_fitr": "Fitr", "eid_al_adha": "Adha", "valentines_day": "Valentine", "mothers_day_arab": "Mother's", "new_years_eve": "New Year",
               "arafat_day": "Arafat", "ramadan_start": "Ramadan", "saudi_founding_day": "Founding", "saudi_national_day": "National"}
DISCLAIMER = ("<b>Google Trends relative search interest</b> (index 0–100 or % share) — not sales, not demand, not search counts. "
              "Each export is normalised on its own scale; values are comparable only inside the same export.")
YEAR_COLORS = ["#6f56a6", "#a78bda", "#d9708f", "#e0b36a", "#6cb7c9", "#f0a0b8"]  # distinct hues; partial years are dotted


def label(term: str) -> str:
    """English: gloss first, Arabic term bidi-isolated. Arabic: the Arabic term."""
    return term if I.is_rtl() else f"{TERM_EN.get(term, '')} · {isolate(term)}".strip(" ·")


def disclaimer() -> str:
    return I.L(DISCLAIMER, "<b>الاهتمام النسبي بالبحث في Google Trends</b> (مؤشر 0–100 أو حصة %) — وليس مبيعات ولا طلبًا ولا عدد عمليات بحث. "
                           "كل تصدير مُطبَّع على مقياسه الخاص؛ ولا تصح المقارنة إلا بين قيم التصدير نفسه.")


STATUS_AR = {AVAILABLE: "متاحة", CENSORED: "مخفية (<1%)", NO_DATA: "بلا بيانات"}


def status_label(status: str) -> str:
    return STATUS_AR.get(status, status) if I.is_rtl() else status


NORM_AR = {"timeline": "مؤشر 0–100 نسبةً إلى أعلى نقطة أسبوعية بين جميع المصطلحات في هذا التصدير؛ لا تصح المقارنة إلا بين مصطلحات هذا التصدير.",
           "share": "حصة مئوية لكل مصطلح من عمليات بحث المصطلحات المقارَنة داخل كل منطقة؛ لا تصح المقارنة إلا داخل هذا التصدير.",
           "single": "مؤشر 0–100 نسبةً إلى أعلى منطقة لهذا المصطلح وحده؛ لا يقارَن بمصطلحات أو تصديرات أخرى."}


def scale_caption(df: pd.DataFrame) -> None:
    ids = df["scale_id"].unique()
    if I.is_rtl():
        g, kind = ids[0].split("|")[0], ids[0].split("|")[1]
        norm = NORM_AR["timeline"] if kind == "timeline" else (NORM_AR["single"] if g.startswith("S_single:") else NORM_AR["share"])
        T.caption(f"مقياس البيانات: {'؛ '.join(friendly_scale(i, 'ar') for i in ids)}. {norm}")
        return
    norm = df["normalization"].iloc[0] if "normalization" in df.columns and len(df) else ""
    T.caption(f"Data scale: {'; '.join(friendly_scale(i) for i in ids)}. {norm}")


# ----------------------------------------------------------------------------------------------- time series
def series_chart(df: pd.DataFrame, value_col: str = "value", height: int = 420, region_iso: str | None = None,
                 events: pd.DataFrame | None = None, forecast: pd.DataFrame | None = None, range_selector: bool = True) -> go.Figure:
    """Weekly lines of one or more terms from ONE scale, with labelled event annotations.

    events: rows (event, date, verification). Solid line = verified against a Saudi announcement or fixed rule;
    dashed line + "†" = Umm al-Qura computed, not independently verified.
    """
    assert_same_scale(df)
    if region_iso is not None:  # Phase B hook; requires a regional weekly frame
        df = df[df["region_iso"] == region_iso]
    fig = go.Figure()
    for i, (term, g) in enumerate(df.groupby("term")):
        g = g.sort_values("week_start")
        fig.add_scatter(x=g["week_start"], y=g[value_col], mode="lines", name=label(term), line=dict(color=T.SERIES[i % 5], width=2),
                        hovertemplate="%{y:.0f}<extra>" + label(term) + "</extra>")
        cen = g[g["is_censored"]] if "is_censored" in g else g.iloc[0:0]
        if len(cen):
            fig.add_scatter(x=cen["week_start"], y=[0.5] * len(cen), mode="markers", name=I.L(f"censored (<1) · {TERM_EN.get(term, term)}", f"مخفية (أقل من 1) · {term}"),
                            marker=dict(symbol="triangle-down", size=8, color=T.SERIES[i % 5], line=dict(color=T.BG, width=1)),
                            hovertemplate=I.L("censored: true value is between 0 and 1", "مخفية: القيمة الفعلية بين 0 و1") + "<extra></extra>")
    has_events = events is not None and len(events) > 0
    if has_events:
        lo, hi = df["week_start"].min(), df["week_start"].max() + pd.Timedelta(days=6)
        for _, r in events[(events["date"] >= lo) & (events["date"] <= hi)].iterrows():
            verified = r["verification"] in ("verified_announced", "fixed_rule")
            short = I.event_short(r["event"]) + ("" if verified else " †")
            status = (I.L("fixed calendar date", "تاريخ ثابت في التقويم") if r["verification"] == "fixed_rule" else
                      (I.L("date verified against a Saudi announcement", "تاريخ تم التحقق منه من إعلان سعودي") if verified else
                       I.L("Umm al-Qura computed date, not independently verified", "تاريخ محسوب بتقويم أم القرى، لم يُتحقق منه بشكل مستقل")))
            hover = f"<b>{I.event_label(r['event'])}</b><br>{I.fdate(r['date'])}<br>{status}"
            fig.add_shape(type="line", x0=r["date"], x1=r["date"], xref="x", y0=0, y1=1, yref="paper",
                          line=dict(color=T.EVENT, width=1.1, dash="solid" if verified else "dash"), opacity=0.75, layer="below")
            fig.add_annotation(x=r["date"], y=1, xref="x", yref="paper", text=short, hovertext=hover, showarrow=False, textangle=-90,
                               xanchor="center", yanchor="bottom", font=dict(size=9, color=T.EVENT), yshift=2)
    if forecast is not None and len(forecast):  # only ever passed when the validation gate passed
        fig.add_scatter(x=forecast["target_week"], y=forecast["forecast"], mode="lines+markers", name=I.L("forecast (validated)", "التوقع (بعد اجتياز التحقق)"), line=dict(color=T.GOLD, dash="dash"))
        fig.add_scatter(x=list(forecast["target_week"]) + list(forecast["target_week"])[::-1], y=list(forecast["hi80"]) + list(forecast["lo80"])[::-1],
                        fill="toself", line=dict(width=0), fillcolor="rgba(224,179,106,0.16)", name=I.L("80% interval", "نطاق 80%"), hoverinfo="skip")
    xaxis = dict(**T.AXIS, hoverformat="Week of %d %b %Y", tickformat="%b %Y", title=None)
    if I.is_rtl():  # Arabic month names are not available in plotly's date formatter: explicit yearly ticks, numeric hover date
        yrs = range(df["week_start"].min().year + (0 if df["week_start"].min().month == 1 and df["week_start"].min().day == 1 else 1), df["week_start"].max().year + 1)
        xaxis.update(hoverformat="أسبوع %d-%m-%Y", tickmode="array", tickvals=[pd.Timestamp(y, 1, 1) for y in yrs], ticktext=[f"{I.MONTHS_AR[0]} {y}" for y in yrs])
    top = 64 if has_events else 18
    if range_selector and not has_events:
        xaxis["rangeselector"] = dict(buttons=[dict(count=1, label=I.L("1y", "سنة"), step="year", stepmode="backward"), dict(count=2, label=I.L("2y", "سنتان"), step="year", stepmode="backward"),
                                               dict(step="all", label=I.L("all", "الكل"))], bgcolor=T.SURFACE2, activecolor=T.PURPLE_DIM, bordercolor=T.BORDER,
                                      font=dict(color=T.TEXT, size=11), x=0, y=1.0, yanchor="bottom")
        top = 48
    fig.update_layout(**T.plotly_layout(height, margin=dict(l=8, r=8, t=top, b=8), hovermode="x unified",
                                        legend=dict(orientation="h", y=-0.16, x=0, font=dict(size=11)),
                                        yaxis=dict(**T.AXIS, rangemode="tozero", title=dict(text=I.L("relative search interest (index)", "الاهتمام النسبي بالبحث (مؤشر)"), font=dict(size=11))), xaxis=xaxis))
    return fig


def yoy_chart(yoy: pd.DataFrame, eids: pd.DataFrame, height: int = 400) -> go.Figure:
    """Year-over-year overlay by Sunday-based week of year (one scale). Diamonds/squares mark the week containing Eid."""
    fig = go.Figure()
    years = sorted(yoy["year"].unique())
    for i, y in enumerate(years):
        g = yoy[yoy["year"] == y].sort_values("woy")
        partial = (g["woy"].min() > 3) or (g["woy"].max() < 50)
        fig.add_scatter(x=g["woy"], y=g["value"], mode="lines", name=f"{y}" + (I.L(" (partial year)", " (سنة جزئية)") if partial else ""), line=dict(color=YEAR_COLORS[i % 6], width=1.8, dash="dot" if partial else "solid"),
                        customdata=[I.fdate(x) for x in g["week_start"]], hovertemplate=I.L("week %{x} · starts %{customdata}: <b>%{y:.0f}</b>", "الأسبوع %{x} · يبدأ %{customdata}: <b>%{y:.0f}</b>") + "<extra>" + str(y) + "</extra>")
    for ev, sym in (("eid_al_fitr", "diamond"), ("eid_al_adha", "square")):
        e = eids[eids["event"] == ev] if len(eids) else eids
        for _, r in e.iterrows():
            row = yoy[(yoy["week_start"] == r["week_start"])]
            if not len(row):
                continue
            ver = I.L("verified", "تم التحقق") if r["verification"] == "verified_announced" else I.L("computed †, not independently verified", "محسوب †، لم يُتحقق منه بشكل مستقل")
            fig.add_scatter(x=[r["woy"]], y=[float(row["value"].iloc[0])], mode="markers", showlegend=False,
                            marker=dict(symbol=sym, size=10, color=YEAR_COLORS[years.index(r["year"]) % 6], line=dict(color=T.TEXT, width=1.2)),
                            hovertemplate=f"{I.event_label(ev)} {I.fdate(r['date'])} ({ver})<extra></extra>")
    fig.add_scatter(x=[None], y=[None], mode="markers", name=I.L("◆ Eid al-Fitr week", "◆ أسبوع عيد الفطر"), marker=dict(symbol="diamond", size=9, color=T.MUTED))
    fig.add_scatter(x=[None], y=[None], mode="markers", name=I.L("■ Eid al-Adha week", "■ أسبوع عيد الأضحى"), marker=dict(symbol="square", size=8, color=T.MUTED))
    fig.update_layout(**T.plotly_layout(height, margin=dict(l=8, r=8, t=12, b=8), hovermode="closest", legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=11)),
                                        xaxis=dict(**T.AXIS, title=dict(text=I.L("week of year (Sunday-based; 1 = early January)", "أسبوع السنة (يبدأ الأسبوع الأحد؛ 1 = أوائل يناير)"), font=dict(size=11)), range=[1, 52]),
                                        yaxis=dict(**T.AXIS, rangemode="tozero", title=dict(text=I.L("relative search interest (index)", "الاهتمام النسبي بالبحث (مؤشر)"), font=dict(size=11)))))
    return fig


def month_chart(m: pd.DataFrame, height: int = 300) -> go.Figure:
    m = m.sort_values("month")
    fig = go.Figure(go.Bar(x=[I.month_name(x, short=True) for x in m["month"]], y=m["index_vs_overall_mean"], marker_color=T.ROSE,
                           hovertemplate=I.L("%{x}: %{y:.2f}× the overall mean", "%{x}: %{y:.2f}× من المتوسط العام") + "<extra></extra>"))
    fig.add_hline(y=1, line=dict(color=T.PURPLE, dash="dot", width=1.2), annotation_text=I.L("overall mean", "المتوسط العام"), annotation_font=dict(size=10, color=T.PURPLE), annotation_position="top left")
    fig.update_layout(**T.plotly_layout(height, yaxis=dict(**T.AXIS, title=dict(text=I.L("month mean ÷ overall mean", "متوسط الشهر ÷ المتوسط العام"), font=dict(size=11)), rangemode="tozero"), xaxis=dict(**T.AXIS)))
    return fig


def lift_chart(s: pd.DataFrame, height: int = 330) -> go.Figure:
    s = s.sort_values("median_lift")
    names = [I.event_label(e) for e in s["event"]]
    fig = go.Figure(go.Bar(y=names, x=s["median_lift"], orientation="h", marker_color=T.ROSE,
                           error_x=dict(type="data", symmetric=False, array=s["max_lift"] - s["median_lift"], arrayminus=s["median_lift"] - s["min_lift"], color=T.PURPLE, thickness=1.2),
                           hovertemplate=I.L("%{y}: median %{x:.2f}× baseline", "%{y}: الوسيط %{x:.2f}× من خط الأساس") + "<extra></extra>"))
    fig.add_vline(x=1, line=dict(color=T.PURPLE, dash="dot", width=1.2))
    fig.update_layout(**T.plotly_layout(height, xaxis=dict(**T.AXIS, title=dict(text=I.L("event-week ÷ baseline (bar = median; whiskers = min–max of 5 occurrences)", "أسبوع المناسبة ÷ خط الأساس (العمود = الوسيط؛ الخطوط = الأدنى–الأعلى من 5 مرات)"), font=dict(size=11)), rangemode="tozero"),
                                        yaxis=dict(**T.AXIS)))
    return fig


# ----------------------------------------------------------------------------------------------- regions
def region_bar(df: pd.DataFrame, value_title: str, selected: list[str] | tuple = (), height: int = 470) -> go.Figure:
    """All 13 regions on one axis. Bars = available; purple tag = censored; grey tag = no data (never a zero bar).
    Regions selected for comparison are highlighted."""
    d = regional_rank_table(df)
    rn = "region_ar" if I.is_rtl() else "region_en"
    avail = d[d["status"] == AVAILABLE].sort_values("value", ascending=False)
    order = list(avail[rn]) + list(d[d["status"] == CENSORED][rn]) + list(d[d["status"] == NO_DATA][rn])
    vmax = max(100.0, float(avail["value"].max() if len(avail) else 100.0))
    sel = set(selected)
    fig = go.Figure(go.Bar(y=avail[rn], x=avail["value"], orientation="h", text=avail["value"].round(0).astype(int), textposition="outside", cliponaxis=False,
                           marker=dict(color=[T.PURPLE if i in sel else T.ROSE for i in avail["region_iso"]],
                                       line=dict(color=[T.TEXT if i in sel else "rgba(0,0,0,0)" for i in avail["region_iso"]], width=1.5)),
                           customdata=avail["rank"], hovertemplate=I.L("%{y}: <b>%{x:.0f}</b> · rank %{customdata:.0f}", "%{y}: <b>%{x:.0f}</b> · الترتيب %{customdata:.0f}") + "<extra></extra>"))
    for status, color, text in ((CENSORED, T.PURPLE, I.L("censored (<1%)", "مخفية (<1%)")), (NO_DATA, "#7c7584", I.L("no data", "بلا بيانات"))):
        sub = d[d["status"] == status]
        if len(sub):
            fig.add_scatter(y=sub[rn], x=[0.8] * len(sub), mode="text", text=[text] * len(sub), textposition="middle right",
                            textfont=dict(color=color, size=12), showlegend=False, hoverinfo="skip")
    fig.update_layout(**T.plotly_layout(height, margin=dict(l=(124 if I.is_rtl() else 8), r=40, t=10, b=8), showlegend=False,
                                        xaxis=dict(**T.AXIS, title=dict(text=value_title, font=dict(size=11)), range=[0, vmax * 1.18]),
                                        yaxis=dict(**T.AXIS, categoryorder="array", categoryarray=order[::-1], automargin=True)))
    return fig


def _bounds(geojson: dict) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for f in geojson["features"]:
        g = f["geometry"]
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            for x, y, *_ in poly[0]:
                xs.append(x); ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def region_map(df: pd.DataFrame, geojson: dict, term: str, metric_name: str, labels: bool = False, selected: list[str] | tuple = (), height: int = 560) -> go.Figure:
    """Choropleth of the 13 regions. Three explicit states: available (rose gradient), censored (purple), no data (grey).
    Regions selected for comparison get a bright outline. Fixed 0–100 colour range so shades are comparable within the export."""
    d = regional_rank_table(df)
    n_avail = int((d["status"] == AVAILABLE).sum())
    sel = set(selected)

    def hov(r) -> str:
        head = (f"<b>{r.region_ar}</b><br>{label(term)}<br>" if I.is_rtl() else f"<b>{r.region_en}</b> · {isolate(r.region_ar)}<br>{label(term)}<br>")
        if r.status == AVAILABLE:
            gap = I.L("peak region", "المنطقة الأعلى") if r.gap_to_peak == 0 else I.L(f"{r.gap_to_peak:.0f} points below the peak region", f"أقل من المنطقة الأعلى بـ {r.gap_to_peak:.0f} نقطة")
            return head + I.L(f"{metric_name}: <b>{r.value:.0f}</b><br>rank {r.rank:.0f} of {n_avail} regions with data · {gap}",
                              f"{metric_name}: <b>{r.value:.0f}</b><br>الترتيب {r.rank:.0f} من {n_avail} منطقة لديها بيانات · {gap}")
        return head + (I.L("censored: true share is between 0 and 1%", "مخفية: الحصة الفعلية بين 0 و1%") if r.status == CENSORED
                       else I.L("no data reported by Google Trends (not zero)", "لم يبلّغ Google Trends عن بيانات (وليست صفرًا)"))

    d["hover"] = [hov(r) for r in d.itertuples()]
    fig = go.Figure()

    def line(sub: pd.DataFrame) -> dict:
        return dict(color=[T.PURPLE if i in sel else T.BG for i in sub["region_iso"]], width=[3.2 if i in sel else 1.0 for i in sub["region_iso"]])

    a = d[d["status"] == AVAILABLE]
    if len(a):
        fig.add_trace(go.Choropleth(geojson=geojson, featureidkey="properties.shapeISO", locations=a["region_iso"], z=a["value"], zmin=0, zmax=100, colorscale=T.ROSE_SCALE,
                                    marker=dict(line=line(a)), text=a["hover"], hovertemplate="%{text}<extra></extra>", selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
                                    colorbar=dict(orientation="h", thickness=10, len=0.62, x=0.5, y=-0.02, yanchor="top", tickvals=[0, 25, 50, 75, 100], outlinewidth=0,
                                                  title=dict(text=metric_name, side="top", font=dict(size=12, color=T.TEXT)), tickfont=dict(color=T.TEXT, size=11))))
    for status, color in ((CENSORED, T.PURPLE_DIM), (NO_DATA, T.NODATA)):
        s = d[d["status"] == status]
        if len(s):
            fig.add_trace(go.Choropleth(geojson=geojson, featureidkey="properties.shapeISO", locations=s["region_iso"], z=[0] * len(s), colorscale=[[0, color], [1, color]], showscale=False,
                                        marker=dict(line=line(s)), text=s["hover"], hovertemplate="%{text}<extra></extra>", selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))))
    if labels:
        from bloom.geo import region_label_points

        pts = region_label_points(geojson)
        fig.add_trace(go.Scattergeo(lon=[pts[i][0] for i in d["region_iso"]], lat=[pts[i][1] for i in d["region_iso"]], mode="text", text=list(d["region_ar" if I.is_rtl() else "region_en"]),
                                    textfont=dict(size=10, color=T.TEXT), hoverinfo="skip", showlegend=False))
    x0, y0, x1, y1 = _bounds(geojson)
    fig.update_geos(lonaxis_range=[x0 - 0.4, x1 + 0.4], lataxis_range=[y0 - 0.4, y1 + 0.4], visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator", showland=False,
                    showcountries=False, showcoastlines=False, showocean=False, showlakes=False, showframe=False, domain=dict(x=[0, 1], y=[0.08, 1]))
    fig.update_layout(**T.plotly_layout(height, margin=dict(l=0, r=0, t=0, b=0), clickmode="event+select", dragmode=False))
    return fig


def coverage_chips(df: pd.DataFrame) -> str:
    d = region_status(df)
    n = d["status"].value_counts()
    return "".join([T.chip(I.L(f"{n.get(AVAILABLE, 0)} available", f"{n.get(AVAILABLE, 0)} متاحة"), "ok"), T.chip(I.L(f"{n.get(CENSORED, 0)} censored", f"{n.get(CENSORED, 0)} مخفية"), ""),
                    T.chip(I.L(f"{n.get(NO_DATA, 0)} no data", f"{n.get(NO_DATA, 0)} بلا بيانات"), "bad" if n.get(NO_DATA, 0) else "")])


def compare_table(df: pd.DataFrame, selected: list[str], value_label: str) -> pd.DataFrame:
    """Rows for the regions selected for comparison (same export/term only), in selection order. Compact: fits 390 px."""
    full = regional_rank_table(df)
    n_avail = int((full["status"] == AVAILABLE).sum())
    d = full[full["region_iso"].isin(selected)].set_index("region_iso")
    d = d.loc[[s for s in selected if s in d.index]].reset_index()
    ok = d["status"] == AVAILABLE
    return pd.DataFrame({I.L("Region", "المنطقة"): [I.region_name(en, ar) for en, ar in zip(d["region_en"], d["region_ar"])],
                         value_label: [f"{v:.0f}" if o else "—" for v, o in zip(d["value"], ok)],
                         I.L("Rank", "الترتيب"): [f"{r:.0f}/{n_avail}" if o else "—" for r, o in zip(d["rank"], ok)],
                         I.L("Below peak", "أقل من الأعلى"): [f"{g:.0f}" if o else "—" for g, o in zip(d["gap_to_peak"], ok)],
                         I.L("Status", "الحالة"): [status_label(x) for x in d["status"]]})


def status_table(df: pd.DataFrame, value_label: str) -> None:
    d = regional_rank_table(df)
    out = pd.DataFrame({"Region": d["region_en"], "الإقليم": d["region_ar"], I.L("Status", "الحالة"): [status_label(x) for x in d["status"]],
                        value_label: [f"{v:.0f}" if s == AVAILABLE else "—" for v, s in zip(d["value"], d["status"])]})
    st.dataframe(out, hide_index=True, width="stretch", height=38 + 35 * 13, column_config={I.L("Status", "الحالة"): st.column_config.TextColumn(width="medium"),
                 value_label: st.column_config.TextColumn(width="small", help=I.L("— = no numeric value (censored or no data); never zero", "— = لا توجد قيمة رقمية (مخفية أو بلا بيانات)؛ ليست صفرًا"))})


# ----------------------------------------------------------------------------------------------- regional commercial-term mix
MIX_COLORS = {"محل ورد": T.ROSE, "بوكيه ورد": T.PURPLE, "توصيل ورد": T.GOLD, "شراء ورد": T.CYAN}


def term_mix_bar(df: pd.DataFrame, order: list[str], height: int = 600) -> go.Figure:
    """Horizontal stacked bars of the PUBLISHED shares on a fixed 0–100 axis (not rescaled, not forced to total 100).

    Segments = published numeric shares only. Any gap to 100 is a hatched grey "unspecified remainder" (never given to a term).
    Censored (<1%) and blank cells are never drawn as bars; they appear as labelled markers (diamond "<1%" / cross "no data") to the right of the bars.
    """
    t = term_mix_table(df)
    summ = term_mix_regions(df).set_index("region_iso")
    names = {i: summ.loc[i, "region_ar" if I.is_rtl() else "region_en"] for i in order}
    ar = {i: summ.loc[i, "region_ar"] for i in order}
    fig = go.Figure()
    for term in MIX_TERM_ORDER:
        g = t[(t["term"] == term) & (t["status"] == AVAILABLE)].set_index("region_iso").reindex(order).dropna(subset=["value"])
        if g.empty:
            continue
        fig.add_bar(y=[names[i] for i in g.index], x=g["value"], orientation="h", name=label(term), marker=dict(color=MIX_COLORS[term], line=dict(color=T.BG, width=1)),
                    text=[f"{v:.0f}%" for v in g["value"]], textposition="inside", insidetextanchor="middle", textfont=dict(color="#16111a", size=12),
                    customdata=[[names[i], isolate(ar[i])] for i in g.index],
                    hovertemplate=("<b>%{customdata[0]}</b><br>" if I.is_rtl() else "<b>%{customdata[0]} · %{customdata[1]}</b><br>") + label(term)
                                  + I.L(": <b>%{x:.0f}%</b> of the four terms' searches in this region<br>published share, rounded · not search volume or sales",
                                        ": <b>%{x:.0f}%</b> من عمليات بحث المصطلحات الأربعة في هذه المنطقة<br>حصة منشورة مقرّبة · ليست حجم بحث ولا مبيعات") + "<extra></extra>")
    rem = summ.reindex(order)
    if (rem["unspecified_remainder"] > 0).any():
        r = rem[rem["unspecified_remainder"] > 0]
        fig.add_bar(y=[names[i] for i in r.index], x=r["unspecified_remainder"], orientation="h", name=I.L("Unspecified remainder (not assigned to any term)", "متبقٍ غير محدد (لا يُنسب إلى أي مصطلح)"),
                    marker=dict(color=T.NODATA, pattern=dict(shape="/", fgcolor="#7c7584"), line=dict(color=T.BG, width=1)),
                    hovertemplate=I.L("<b>%{y}</b><br>unspecified: %{x:.0f}% (published shares total less than 100%; not assigned to a term)",
                                          "<b>%{y}</b><br>غير محدد: %{x:.0f}% (مجموع الحصص المنشورة أقل من 100%؛ لا يُنسب إلى مصطلح)") + "<extra></extra>")
    for term in MIX_TERM_ORDER:
        for status, symbol, text, nm in ((CENSORED, "diamond", "<1%", I.L("censored (<1%)", "مخفية (<1%)")), (NO_DATA, "x", I.L("no data", "بلا بيانات"), I.L("no data", "بلا بيانات"))):
            sub = t[(t["term"] == term) & (t["status"] == status)].set_index("region_iso").reindex(order).dropna(subset=["region_en"])
            if sub.empty:
                continue
            fig.add_scatter(y=[names[i] for i in sub.index], x=[104] * len(sub), mode="markers+text", text=[text] * len(sub), textposition="middle right",
                            textfont=dict(color=MIX_COLORS[term], size=11), marker=dict(symbol=symbol, size=9, color=MIX_COLORS[term], line=dict(color=MIX_COLORS[term], width=1.5)),
                            name=f"{label(term)} · {nm}", hovertemplate=f"<b>%{{y}}</b><br>{label(term)}: " + ((I.L("censored by Google Trends: true share between 0 and 1%", "مخفية من Google Trends: الحصة الفعلية بين 0 و1%")) if status == CENSORED else I.L("no data reported by Google Trends", "لم يبلّغ Google Trends عن بيانات"))
                                          + I.L("<br>Not zero; excluded from the bars.", "<br>ليست صفرًا؛ مستبعدة من الأعمدة.") + "<extra></extra>")
    fig.update_layout(**T.plotly_layout(height, barmode="stack", margin=dict(l=(124 if I.is_rtl() else 8), r=8, t=8, b=128), uniformtext=dict(minsize=10, mode="hide"),
                                        legend=dict(orientation="h", yref="container", yanchor="bottom", y=0, x=0, font=dict(size=11, color=T.MUTED), bgcolor="rgba(0,0,0,0)"),
                                        xaxis=dict(**T.AXIS, range=[0, 132], tickvals=[0, 25, 50, 75, 100], ticksuffix="%", fixedrange=True,
                                                   title=dict(text=I.L("share of the four terms' searches in the region (published, not rescaled)", "حصة كل مصطلح من عمليات بحث المصطلحات الأربعة في المنطقة (كما نُشرت، دون إعادة قياس)"), font=dict(size=11))),
                                        yaxis=dict(**T.AXIS, categoryorder="array", categoryarray=[names[i] for i in order][::-1], fixedrange=True, automargin=True)))
    fig.add_vline(x=100, line=dict(color=T.BORDER, width=1, dash="dot"))
    return fig
