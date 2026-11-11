"""Real-browser check of the running bilingual dashboard (headless Google Chrome over the DevTools protocol).

    PYTHONPATH=src .venv/bin/streamlit run app/streamlit_app.py --server.port 8599 --server.headless true     # in another terminal
    .venv/bin/python scripts/browser_check.py OUT_DIR [URL]                                                     # default URL http://localhost:8599
    CHROME_BIN=/path/to/chrome .venv/bin/python scripts/browser_check.py ...

For English (LTR) and Arabic (RTL) at 1440 / 768 / 390 px it opens every section, saves screenshots, measures layout in the DOM (horizontal overflow, clipped or
overlapping elements, truncated KPI text, hidden navigation), checks direction (RTL/LTR), text alternatives, the 13 map regions, tooltips, the language-switch
interaction and map clicks (homepage region card, regional comparison). Writes OUT_DIR/facts.json and prints PASS/FAIL per language and width; exit code 1 if anything fails.
Needs only Chrome and the `websockets` package that ships with Streamlit. It talks only to the URL you give it."""
import asyncio, base64, json, os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

import websockets

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
URL = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8599").rstrip("/")
PORT = int(os.environ.get("CDP_PORT", "9337"))
CHROME = os.environ.get("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SECTIONS = ["overview", "trend", "seasonality", "regions", "mix", "forecast", "data"]
NAVTXT = {"en": ["Overview", "National trend", "Seasonality", "Regions & map", "Commercial-term mix", "Forecast", "Data engineering"],
          "ar": ["نظرة عامة", "الاتجاه الوطني", "الموسمية", "المناطق والخريطة", "تركيبة المصطلحات التجارية", "التوقع", "هندسة البيانات"]}
REGION = {"en": ("Jazan", "Northern Borders"), "ar": ("جازان", "الحدود الشمالية")}
WIDTHS = {"desktop1440": (1440, 3000, False), "tablet768": (768, 3600, False), "mobile390": (390, 5200, True)}
CHECK_JS = r"""
(() => {
  const W = window.innerWidth, out = {innerWidth: W, scrollWidth: document.documentElement.scrollWidth};
  const R = e => e.getBoundingClientRect();
  const inScroll = e => { let p = e.parentElement; while (p) { const s = getComputedStyle(p); if (/(auto|scroll)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const sel = '.kpi,.panel,.callout,.crit,.brand,.tagline,[data-testid=stPlotlyChart],.legend,[data-testid=stHorizontalBlock]';
  out.overflowing = [...document.querySelectorAll(sel)].filter(e => R(e).right > W + 1 && R(e).left > -1 && !inScroll(e) || R(e).left < -1 && !inScroll(e)).length;
  out.kpi_truncated = [...document.querySelectorAll('.kpi .v,.kpi .s,.kpi .d,.kpi .l')].filter(e => e.scrollWidth > e.clientWidth + 1).length;
  const k = [...document.querySelectorAll('.kpi')].map(R); let ov = 0;
  for (let i = 0; i < k.length; i++) for (let j = i + 1; j < k.length; j++) { const a = k[i], b = k[j]; if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2) ov++; }
  out.kpi_overlaps = ov; out.kpi_count = k.length;
  const nav = [...document.querySelectorAll('.st-key-section [data-testid=stRadioOption]')];
  out.nav = nav.map(n => [n.innerText.trim(), R(n).left >= -1 && R(n).right <= W + 1]);
  out.nav_first_right_of_last = nav.length > 1 ? R(nav[0]).left > R(nav[nav.length - 1]).left : null;
  out.lang_switch = [...document.querySelectorAll('.st-key-lang [data-testid=stRadioOption]')].map(n => n.innerText.trim());
  out.charts_clipped = [...document.querySelectorAll('[data-testid=stPlotlyChart]')].filter(c => R(c).right > W + 1 || R(c).left < -1).length;
  out.plotly_count = document.querySelectorAll('.js-plotly-plot').length;
  out.exceptions = document.querySelectorAll('[data-testid=stException]').length;
  out.emoji_in_brand = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test((document.querySelector('.brand') || {innerText: ''}).innerText);
  out.page_title = document.title;
  out.app_direction = getComputedStyle(document.querySelector('.stApp')).direction;
  out.html_dir = document.documentElement.dir; out.html_lang = document.documentElement.lang;
  out.map_region_shapes = document.querySelectorAll('.geo .choroplethlocation').length;
  out.map_height = (() => { const m = document.querySelector('[data-testid=stPlotlyChart]'); return m ? Math.round(R(m).height) : 0; })();
  out.bar_region_labels = [...document.querySelectorAll('.ytick text')].map(x => x.textContent.trim()).filter(x => x).length;
  out.text_alternatives = (document.body.innerText.match(/Text alternative ·|بديل نصي ·/g) || []).length;
  out.annotation_labels = [...document.querySelectorAll('.annotation-text')].map(x => x.textContent.trim()).filter(x => x).slice(0, 6);
  const T = document.body.innerText;
  out.body_text_has = {withheld: /withheld|محجوب/i.test(T), no_forecast: /No forecast is shown|لا يُعرض أي توقع/.test(T), city_not_implemented: /not implemented|not in the data|غير منفّذة|غير موجودة/i.test(T),
                       arabic: /[؀-ۿ]{4,}/.test(T.replace(/محل ورد|توصيل ورد|بوكيه ورد|شراء ورد|جازان|العربية/g, '')), english_sentence: /(?:\b[A-Za-z']{2,}\b\s+){5,}/.test(T.replace(/Saudi Bloom|SAUDI BLOOM|INTELLIGENCE|Google Trends|OpenStreetMap|geoBoundaries|ODbL/g, ''))};
  return out;
})()
"""
CLICK_PT = """((index) => { const paths = [...document.querySelectorAll('[data-testid=stPlotlyChart] .geo .choroplethlocation')]; const p = paths[index]; if (!p) return null;
  p.scrollIntoView({block: 'center'}); const r = p.getBoundingClientRect(); const svg = p.ownerSVGElement; const m = p.getScreenCTM();
  for (const fx of [.5, .4, .6, .3, .7, .35, .65, .25, .75]) for (const fy of [.5, .4, .6, .3, .7, .25, .75]) { const x = r.left + r.width * fx, y = r.top + r.height * fy; const pt = svg.createSVGPoint(); pt.x = x; pt.y = y;
    if (p.isPointInFill(pt.matrixTransform(m.inverse()))) return [x, y]; } return null; })"""
MIX_JS = r"""
(() => { const W = window.innerWidth, R = e => e.getBoundingClientRect(), pl = document.querySelector('[data-testid=stPlotlyChart]');
  const legend = [...document.querySelectorAll('.legend .traces .legendtext')].map(x => x.textContent.trim());
  const T = document.body.innerText;
  return {innerWidth: W, scrollWidth: document.documentElement.scrollWidth, exceptions: document.querySelectorAll('[data-testid=stException]').length,
    bars: document.querySelectorAll('.barlayer .point').length, markers: document.querySelectorAll('.scatterlayer .point').length, legend,
    chart_clipped: pl ? (R(pl).right > W + 1 || R(pl).left < -1) : true, text_alt: /Text alternative · Commercial-term mix|بديل نصي · تركيبة/.test(T),
    caveat: /not search volume, sales, revenue, market size or consumer demand|ليس<\/b> حجم بحث|ليس حجم بحث ولا مبيعات ولا إيرادات/.test(T), never_zero: /never drawn as zero|صفرًا أبدًا/.test(T),
    ytick_regions: [...document.querySelectorAll('.ytick text')].map(x => x.textContent.trim()).filter(x => x).length}; })()
"""
HOVER_JS = r"""(() => { const p = document.querySelector('.barlayer .point path'); if (!p) return null; p.scrollIntoView({block: 'center'}); const r = p.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()"""

profile = tempfile.mkdtemp(prefix="bloom_browser_check_")
chrome = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}", "--no-first-run", "--disable-gpu", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
tabs = []
for _ in range(60):
    try:
        tabs = json.load(urllib.request.urlopen(f"http://localhost:{PORT}/json")); break
    except Exception:
        time.sleep(0.5)
ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]


async def main():
    ws = await websockets.connect(ws_url, max_size=2 ** 27); n = 0

    async def call(method, **params):
        nonlocal n
        n += 1; mid = n
        await ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            r = json.loads(await ws.recv())
            if r.get("id") == mid:
                return r.get("result", r)

    async def js(expr):
        r = await call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    async def shot(name, beyond):
        r = await call("Page.captureScreenshot", format="png", captureBeyondViewport=beyond)
        (OUT / f"{name}.png").write_bytes(base64.b64decode(r["data"]))

    async def nav(lang, sec):
        label = NAVTXT[lang][SECTIONS.index(sec)]
        await js("(()=>{const l=[...document.querySelectorAll('.st-key-section [data-testid=stRadioOption]')].find(l=>l.innerText.trim()==%s); l&&l.click(); return !!l})()" % json.dumps(label))
        await asyncio.sleep(4.5)

    async def click_region(i):
        pt = await js(f"{CLICK_PT}({i})")
        if not pt:
            return False
        await asyncio.sleep(0.4)
        for typ in ("mouseMoved", "mousePressed", "mouseReleased"):
            await call("Input.dispatchMouseEvent", type=typ, x=pt[0], y=pt[1], button="left", clickCount=1)
        await asyncio.sleep(3.5)
        return True

    facts = {}
    for lang in ("en", "ar"):
        for label, (w, h, mobile) in WIDTHS.items():
            key = f"{lang}|{label}"
            await call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=mobile)
            await call("Page.navigate", url=f"{URL}/?lang={lang}"); await asyncio.sleep(9)
            for i, sec in enumerate(SECTIONS, start=1):
                if sec != "overview":
                    await nav(lang, sec)
                await shot(f"{lang}_{label}_{i}_{sec}", mobile)
                facts[f"{key}|{sec}"] = await js(CHECK_JS)
            # homepage: map click -> selected-region card
            await nav(lang, "overview")
            card = "(()=>{const p=document.querySelector('.region-card'); return p?p.innerText.replace(/\\s+/g,' ').trim():null})()"
            before = await js(card); ok = await click_region(1); after = await js(card)
            await shot(f"{lang}_{label}_1b_overview_region_selected", mobile)
            facts[f"{key}|overview_click"] = {"clicked": ok, "card_before": before, "card_after": after}
            # regional comparison: map clicks add and remove regions
            await nav(lang, "regions")
            chips = lambda: js("(document.querySelector('[data-testid=stMultiSelect]')||{innerText:''}).innerText")
            c0 = await chips(); ok1 = await click_region(0); c1 = await chips(); ok2 = await click_region(1); c2 = await chips()
            await shot(f"{lang}_{label}_4b_regions_two_selected", mobile)
            ok3 = await click_region(0); c3 = await chips()
            jz, nb = REGION[lang]
            facts[f"{key}|compare_click"] = {"clicked": [ok1, ok2, ok3], "names_after": [[x for x in (jz, nb) if x in c] for c in (c0, c1, c2, c3)]}
            # commercial-term mix: bars, markers, legend, tooltip
            await nav(lang, "mix")
            mixf = await js(MIX_JS); pt = await js(HOVER_JS); hover = None
            if pt:
                await asyncio.sleep(0.4)
                await call("Input.dispatchMouseEvent", type="mouseMoved", x=pt[0], y=pt[1]); await asyncio.sleep(1.0)
                hover = await js("[...document.querySelectorAll('.hoverlayer .hovertext')].map(h => h.textContent.replace(/\\s+/g, ' ').trim()).join(' | ')")
            mixf["hover"] = hover
            await shot(f"{lang}_{label}_5b_mix_tooltip", mobile)
            facts[f"{key}|term_mix"] = mixf
        # language-switch interaction (desktop): stay on a section, switch both ways, section and state persist
        await call("Emulation.setDeviceMetricsOverride", width=1440, height=1800, deviceScaleFactor=1, mobile=False)
        await call("Page.navigate", url=f"{URL}/?lang={lang}"); await asyncio.sleep(9)
        other = "ar" if lang == "en" else "en"
        pick = lambda name: js("(()=>{const l=[...document.querySelectorAll('.st-key-lang [data-testid=stRadioOption]')].find(l=>l.innerText.trim()==%s); l&&l.click(); return !!l})()" % json.dumps(name))
        # context: pick a region on the homepage map, switch language, the same region stays selected
        card = "(()=>{const p=document.querySelector('.region-card'); return p?p.innerText.replace(/\\s+/g,' ').trim():null})()"
        await click_region(1); card_before = await js(card)
        await pick("العربية" if other == "ar" else "English"); await asyncio.sleep(5)
        card_after = await js(card)
        await pick("English" if other == "ar" else "العربية"); await asyncio.sleep(5)
        await nav(lang, "regions")
        await pick("العربية" if other == "ar" else "English"); await asyncio.sleep(5)
        after1 = await js("({dir: document.documentElement.dir, nav: [...document.querySelectorAll('.st-key-section [data-testid=stRadioOption]')].map(n => n.innerText.trim()), sel: (document.querySelector('.st-key-section [data-selected=true]')||{innerText:''}).innerText.trim(), url: location.search})")
        await pick("English" if other == "ar" else "العربية"); await asyncio.sleep(5)
        after2 = await js("({dir: document.documentElement.dir, sel: (document.querySelector('.st-key-section [data-selected=true]')||{innerText:''}).innerText.trim(), url: location.search})")
        facts[f"{lang}|switch"] = {"to_other": after1, "back": after2, "card_before": card_before, "card_after": card_after}
    (OUT / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    await ws.close()

    failed = []
    for lang in ("en", "ar"):
        for label in WIDTHS:
            before_n = len(failed)
            tag = f"{lang}/{label}"
            for sec in SECTIONS:
                F = facts[f"{lang}|{label}|{sec}"]
                chk = {
                    "no horizontal overflow": F["scrollWidth"] <= F["innerWidth"], "nothing wider than the viewport": F["overflowing"] == 0,
                    "no truncated KPI text": F["kpi_truncated"] == 0, "no overlapping KPI cards": F["kpi_overlaps"] == 0,
                    "navigation fully visible (7 items)": all(v for _, v in F["nav"]) and len(F["nav"]) == 7, "navigation labels in the active language": [x for x, _ in F["nav"]] == NAVTXT[lang],
                    "RTL/LTR direction": (F["app_direction"] == "rtl" and F["html_dir"] == "rtl" and F["html_lang"] == "ar") if lang == "ar" else (F["app_direction"] == "ltr" and F["html_dir"] == "ltr" and F["html_lang"] == "en"),
                    "navigation starts at the reading edge": (F["nav_first_right_of_last"] is True) == (lang == "ar") or F["nav_first_right_of_last"] is None,
                    "language switch visible": F["lang_switch"] == ["العربية", "English"], "no clipped charts": F["charts_clipped"] == 0, "no exceptions": F["exceptions"] == 0,
                    "no emoji in the brand": not F["emoji_in_brand"], "title": F["page_title"] == "Saudi Bloom Intelligence",
                    "no untranslated English sentence in Arabic": not (lang == "ar" and F["body_text_has"]["english_sentence"] and sec not in ("data",)),
                    "Arabic text present in Arabic mode": lang != "ar" or F["body_text_has"]["arabic"]}
                if sec == "overview":
                    chk |= {"4 KPI cards": F["kpi_count"] == 4, "13 map regions": F["map_region_shapes"] == 13, "map is the main visual (height >= 440)": F["map_height"] >= 440,
                            "text alternatives for map and chart": F["text_alternatives"] >= 2, "city level stated as not implemented": F["body_text_has"]["city_not_implemented"],
                            "short event labels": any(a.startswith(("Fitr", "Adha", "الفطر", "الأضحى")) for a in F["annotation_labels"])}
                if sec in ("trend", "seasonality"):
                    chk["text alternative present"] = F["text_alternatives"] >= 1
                if sec == "regions":
                    chk |= {"13 map regions and 13 bar labels": F["map_region_shapes"] == 13 and F["bar_region_labels"] == 13, "text alternative present": F["text_alternatives"] >= 1}
                if sec == "forecast":
                    chk["forecast withheld, no chart"] = F["plotly_count"] == 0 and F["body_text_has"]["no_forecast"]
                failed += [f"{tag}/{sec}: {k}" for k, v in chk.items() if not v]
            oc, cc, mf = facts[f"{lang}|{label}|overview_click"], facts[f"{lang}|{label}|compare_click"], facts[f"{lang}|{label}|term_mix"]
            jz, nb = REGION[lang]
            extra = {"homepage map click updates the region card": oc["clicked"] and nb in (oc["card_after"] or "") and jz in (oc["card_before"] or "") and (("rank 2 of 13" in oc["card_after"].lower()) if lang == "en" else ("الترتيب 2 من 13" in oc["card_after"])),
                     "comparison clicks add and remove regions": cc["names_after"] == [[], [jz], [jz, nb], [nb]],
                     "term-mix: 39 bar segments, 13 status markers (8 censored + 5 no data)": mf["bars"] == 39 and mf["markers"] == 13,
                     "term-mix: legend names censored and no-data states": any(("censored" in x or "مخفية" in x) for x in mf["legend"]) and any(("no data" in x or "بلا بيانات" in x) for x in mf["legend"]),
                     "term-mix: 13 region labels": mf["ytick_regions"] == 13, "term-mix: no overflow/clipping/exceptions": mf["scrollWidth"] <= mf["innerWidth"] and not mf["chart_clipped"] and mf["exceptions"] == 0,
                     "term-mix: caveats and text alternative visible": mf["text_alt"] and mf["caveat"] and mf["never_zero"],
                     "term-mix: tooltip states share and not volume/sales": bool(mf["hover"]) and (("of the four terms" in mf["hover"] and "not search volume or sales" in mf["hover"]) if lang == "en" else ("المصطلحات الأربعة" in mf["hover"] and "ليست حجم بحث ولا مبيعات" in mf["hover"]))}
            failed += [f"{tag}: {k}" for k, v in extra.items() if not v]
            print(f"{tag:16s} {'PASS' if len(failed) == before_n else 'FAIL'}")
        sw = facts[f"{lang}|switch"]; other = "ar" if lang == "en" else "en"
        sw_ok = {"switch changes direction and navigation language": sw["to_other"]["dir"] == ("rtl" if other == "ar" else "ltr") and sw["to_other"]["nav"] == NAVTXT[other],
                 "section is kept after switching": sw["to_other"]["sel"] == NAVTXT[other][SECTIONS.index("regions")], "language is kept in the URL": f"lang={other}" in sw["to_other"]["url"],
                 "selected region survives the switch (same region, other language)": REGION[lang][1] in (sw["card_before"] or "") and REGION[other][1] in (sw["card_after"] or ""),
                 "switching back restores the language and section": sw["back"]["dir"] == ("rtl" if lang == "ar" else "ltr") and sw["back"]["sel"] == NAVTXT[lang][SECTIONS.index("regions")]}
        failed += [f"{lang}/switch: {k}" for k, v in sw_ok.items() if not v]
        print(f"{lang}/language-switch {'PASS' if all(sw_ok.values()) else 'FAIL'}")
    print("ALL PASS" if not failed else "FAILED:\n  " + "\n  ".join(failed))
    sys.exit(1 if failed else 0)

try:
    asyncio.run(main())
finally:
    chrome.terminate()
