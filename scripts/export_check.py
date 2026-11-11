"""Real-browser check that data-export controls are absent in the display-only release (headless Chrome over the DevTools protocol).

    PYTHONPATH=src .venv/bin/streamlit run app/streamlit_app.py --server.port 8599 --server.headless true      # in another terminal
    .venv/bin/python scripts/export_check.py [URL]            # default http://localhost:8599 ; exit code 1 if any export control is found

For several sections in English and Arabic it hovers every chart and every table and lists the visible toolbar buttons:
  * Plotly mode bar: the image-download ("camera") button must be absent, zoom/pan/reset must remain;
  * Streamlit table toolbar: no download / copy button.
It also reports whether the page contains any <a download> link or blob/data download anchors.
Run it against a server started with `--client.disableDataExport false` to see the detector find the controls (positive control)."""
import asyncio, json, os, subprocess, sys, tempfile, time, urllib.request

import websockets

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8599").rstrip("/")
PORT = int(os.environ.get("CDP_PORT", "9347"))
CHROME = os.environ.get("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SECTIONS = ["overview", "trend", "seasonality", "regions", "mix", "forecast", "data"]
PAGES = [(l, s) for l in ("en", "ar") for s in SECTIONS]

profile = tempfile.mkdtemp(prefix="bloom_export_check_")
chrome = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}", "--no-first-run", "--disable-gpu",
                           "--window-size=1440,1600", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
tabs = []
for _ in range(60):
    try:
        tabs = json.load(urllib.request.urlopen(f"http://localhost:{PORT}/json")); break
    except Exception:
        time.sleep(0.5)
ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]

CENTERS_JS = r"""(sel => [...document.querySelectorAll(sel)].map((e, i) => { e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect();
  return {i, x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 120), w: r.width, h: r.height}; }).filter(c => c.w > 40 && c.h > 40))"""
BUTTONS_JS = r"""(() => {
  const mode = [...document.querySelectorAll('.modebar-btn')].map(b => (b.getAttribute('data-title') || b.getAttribute('aria-label') || '').trim());
  const tb = [...document.querySelectorAll('[data-testid="stElementToolbar"] button, [data-testid="stElementToolbarButton"], [data-testid="stElementToolbar"] [role="button"]')]
      .map(b => (b.getAttribute('aria-label') || b.getAttribute('title') || b.innerText || b.getAttribute('data-testid') || '').trim());
  const anchors = [...document.querySelectorAll('a[download]')].length;
  return {mode, tb, anchors}; })()"""


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

    async def hover(x, y):
        await call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        await asyncio.sleep(0.7)

    await call("Page.enable"); await call("Emulation.setDeviceMetricsOverride", width=1440, height=1600, deviceScaleFactor=1, mobile=False)
    results, bad = [], []
    for lang, sec in PAGES:
        await call("Page.navigate", url=f"{URL}/?lang={lang}&section={sec}")
        await asyncio.sleep(7)
        modes, tbs, charts, tables = set(), set(), 0, 0
        anchors = 0
        for sel, kind in (('.js-plotly-plot', "chart"), ('[data-testid="stDataFrame"]', "table")):
            for c in await js(f"({CENTERS_JS})('{sel}')") or []:
                await hover(c["x"], c["y"])
                b = await js(BUTTONS_JS)
                modes |= {x for x in b["mode"] if x}; tbs |= {x for x in b["tb"] if x}; anchors = max(anchors, b["anchors"])
                charts += kind == "chart"; tables += kind == "table"
        row = {"lang": lang, "section": sec, "charts": charts, "tables": tables, "modebar": sorted(modes), "table_toolbar": sorted(tbs), "download_anchors": anchors}
        results.append(row)
        low = " ".join(modes | tbs).lower()
        if "png" in low or "download" in low or "csv" in low or "copy" in low or "تنزيل" in low or anchors:
            bad.append(row)
        print(f"{lang}/{sec:11s} charts={charts} tables={tables} modebar={sorted(modes)} table_toolbar={sorted(tbs)} anchors={anchors}", flush=True)
    await ws.close()
    total_c = sum(r["charts"] for r in results); total_t = sum(r["tables"] for r in results)
    print(f"\nhovered {total_c} charts and {total_t} tables; export controls found on {len(bad)} page(s)")
    print("RESULT:", "FAIL (export controls present)" if bad else "PASS (no export controls)")
    return 1 if bad else 0

try:
    code = asyncio.run(main())
finally:
    chrome.terminate()
sys.exit(code)
