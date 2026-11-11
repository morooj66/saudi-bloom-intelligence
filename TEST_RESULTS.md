# TEST_RESULTS.md

> **Latest (2026-11-11, after the bilingual interface): 231 passed, 0 failed** (project venv). Integrity: INTEGRITY VERIFIED (19/19). Browser check (`scripts/browser_check.py`): ALL PASS in English (LTR) and Arabic (RTL) at 1440/768/390 px, including the language switch (section, term and selected region persist) and map clicks. 20 tests were added in `tests/test_bilingual.py` (Arabic names for every term/event/month, identical numbers in both languages, region-card logic for numeric/censored/missing states, RTL CSS only in Arabic, Arabic navigation labels, language and section persistence, `?lang=`/`?section=` seeding, a guard against untranslated English sentences in Arabic mode, forecast still withheld). `tests/test_empty_install.py` (7 tests) covers a clone without data. **Fresh clone without any Google Trends data: 65 passed, 166 skipped (explicit reason), 0 failed; after supplying the nine exports and running the pipeline: 231 passed and every rebuilt dataset identical to the original build.** Earlier sections below are historical.

> **Latest (2026-11-10, after the regional term-mix feature): 204 passed, 0 failed** (project venv; also 204 passed in a fresh venv installed only from `requirements.lock`, installed set identical to the 46 pins). `python -m bloom.integrity`: INTEGRITY VERIFIED. 29 tests were added in `tests/test_term_mix.py` (hash pin of the new file and of the 8 originals, append-only manifest, 13 regions, 39 numeric / 8 censored / 5 missing cells, no fabricated zeros, remainder handling, text alternative, scale isolation with `ScaleMixError`, integrity tamper cases, chart honesty, dashboard rendering). One existing assertion was updated (manifest scale ids: 8 → 9). Browser check (`scripts/browser_check.py`) ALL PASS at 1440/768/390 px. The earlier 175-test and 165-test sections below are historical.

> **Update 2026-11-10 (dashboard refinement): 175 passed, 0 failed** (main project venv, `PYTHONPATH=src`, 32.8 s; log `reports/pytest_output.txt`). Integrity: INTEGRITY VERIFIED (18/18). 8 of 8 raw files match the manifest and the original exports. Real-browser check (`scripts/browser_check.py`, Chrome at 1440/768/390 px, 6 sections each, plus homepage and comparison map clicks): ALL PASS. The 10 new tests cover the homepage helpers (`trend_vs_prior_year`, `ranking_explainer`, `region_detail`, `select_from_map`, `spread_of_available`, text alternatives) and homepage behaviour (caveats, city-level not implemented, text alternatives in every chart section). The tables below describe the earlier 165-test baseline, which still passes. The fresh `requirements.lock` environment was not re-run in this update.

Final run: 2026-11-10 · Python 3.13.15 · pandas 3.1.1 · streamlit 1.67.0 · plotly 7.1.0 · pytest 9.2.0. Logs: `reports/pytest_output.txt` (main environment), `reports/pytest_output_lockvenv.txt` (fresh environment built from `requirements.lock`).

## Result
| Environment | Result |
|---|---|
| Main project venv | **165 passed**, 0 failed, 0 skipped, 0 errors (30.6 s) |
| Fresh venv installed only from `requirements.lock` | **165 passed**, 0 failed (31.4 s) |
| Runtime integrity (`python -m bloom.integrity`) | **INTEGRITY VERIFIED**, 18/18 checks, exit 0 |

The previous suite (129 tests) is unchanged and still passes; 36 tests were added in this refinement.

> **Correction.** The per-file table in the previous version of this document undercounted parametrized tests (its rows summed to 121, not 129). The table below is counted from the full `pytest -v` log and sums to 165.

| Test file | Tests | Covers |
|---|---|---|
| test_parsing.py | 21 | cell parsing (censored, blank, Arabic digits, garbage → error), windows, dates, region aliases |
| test_ingest.py | 3 | manifest copy/hash, never overwrites raw, group assignment |
| test_pipeline_exit_codes.py | 13 | exit codes 0/1/2 on corrupted copies of the real exports; no processed outputs on failure; append-only manifest; duplicate group rejected |
| test_integrity.py | 17 | fail-closed runtime integrity (tampered raw/processed/provenance/validation, stale fingerprint, schema, gate-constant drift, forecast suppression, never modifies files) |
| test_validators_and_manifest.py | 21 | negative tests for every validator; manifest = incoming = raw; fingerprints |
| test_forecast_gate.py | 10 | gate arithmetic (pass, tie, worse, below threshold, CI includes zero, best baseline), thresholds pinned, suppression, recorded gate result pinned |
| test_calendar_and_forecast.py | 6 | Hijri dates, verified announcements, date-only features, no look-ahead |
| test_real_data_quality.py | 10 | schema, frequency, group separation, censoring, 13 regions, ranges, edge weeks |
| test_geo.py | 10 | boundary file valid and hash-verified, 13 ISO codes, licence recorded, tamper detection, render-time rewind |
| test_components.py | 10 | 13 regions with explicit status, missing/censored never zero, scale-mix refusal, event annotations, bidi |
| **test_overview.py** (new) | 13 | executive KPIs computed from frames and **not hard-coded** (mutated data changes the answer), ties reported, missing ignored, coverage, history, strongest seasonal, rank table, map-click toggling, year-over-year frame, Eid weeks, readable scale names |
| **test_regional_ranking.py** (new) | 9 | **independent stdlib recomputation** from the original CSVs: header/term/window, 13 regions, Jazan #1 (100) then Northern Borders 96, equality with processed data for all 5 terms, blanks stay missing, peak = 100, group-A share ranks the same term differently (Northern Borders 13%) |
| **test_brand_and_copy.py** (new) | 7 | no emoji in the brand/title/icon/source, 8-bar SVG with a user-space gradient (regression: bars were invisible), no sales/volume claims, required KPI wording, non-wrapping Arabic phrases, Google Trends + OSM credited in every section |
| test_app_smoke.py | 15 | every section renders; forecast section has no chart and explains the decision; map + bars for every term and view; tampered data hides all analytics; **overview KPIs and definitions**; **comparison table updates from selection and clears**; **missing region in a comparison shows "No data", never zero**; seasonality separates observed / event-associated / hypothesis and contains no causal wording; data engineering labels inferred dates as unverified and shows the recorded pipeline timestamp |

## Pipeline and data verification (executed)
- Clean regeneration: deleted `data/processed` (generated data only), re-ran pipeline → phase_a → report → integrity: **exit 0 each**; **all 18 compared output files byte-identical** to the previously validated results.
- Records: 1,310 + 1,048 weekly rows (262 buckets), 65 + 65 regional rows, 8 raw files; 104 checks passed, 0 errors, 5 documented warnings.
- **Forecast gate unchanged** (JSON identical to the original validated snapshot): not passed, +5.3% MAE vs best naive, 95% CI [−0.89, 1.90]; `forecast_national` does not exist.
- **Raw data**: all 8 files match the hash list taken before any change in this phase and are byte-identical to the original downloads.

## Real-browser verification (headless Google Chrome via the DevTools protocol; Streamlit on port 8599)
Screenshots: `review_assets/final_v2/` (3 widths × 6 sections + 2-region selection). Machine-readable facts: `review_assets/final_v2/browser_layout_facts.json`; script: `capture_and_layout_check_cdp.py`.
| Check | 1440 px | 768 px | 390 px |
|---|---|---|---|
| Horizontal page overflow | none | none | none |
| Elements wider than viewport (outside scroll containers) | none | none | none |
| Truncated KPI text / overlapping KPI cards | none | none | none |
| Navigation labels fully visible | yes | yes | yes |
| Clipped charts | none | none | none |
| Streamlit exceptions | 0 | 0 | 0 |
| Regions section: map shapes / bar labels | 13 / 13 | 13 / 13 | 13 / 13 |
| Map click → compare: click Jazan, click Northern Borders, click Jazan again | [Jazan] → [Jazan, NB] → [NB] | same | same |
| Forecast section charts | 0 | 0 | 0 |
Layout issues: **0 of 18** (3 widths × 6 sections). Streamlit log: 0 warnings, 0 errors.

## Defects found during this pass (and fixed)
1. Brand mark bars invisible: an SVG gradient in default bounding-box units is invalid on perfectly horizontal/vertical lines (found only in the browser; regression test added).
2. Arabic phrases wrapping across lines on narrow screens ("محل / ورد"): fixed with non-breaking spaces (test added).
3. Two assertions of mine were vacuous (`… or True`) and one test expectation was wrong; all were corrected rather than left to pass.
4. The app credited OpenStreetMap but not Google Trends: a source footer was added to every section (test added).

## Limitations of this verification
- Visual/CSS correctness rests on screenshots inspected manually plus DOM measurements; the automated tests do not cover CSS.
- Only headless Chrome was used. **Safari, Firefox, real phones/tablets, keyboard-only navigation and screen readers were not tested.**
- The 768 px "tablet" was a desktop-engine viewport, not a real tablet.
- Map-click behaviour was verified with synthetic mouse events in headless Chrome, not on a touch device.
- Bootstrap CIs in the forecast gate overlap across origins (optimistic); unchanged by design.

## Final release verification (2026-11-11)
- Project venv: **231 passed**; `bloom.integrity` VERIFIED; browser check ALL PASS (EN/AR × 1440/768/390 + language switch).
- Cloud-like clean install (fresh Python 3.13 venv from `requirements.txt` only, files that would be committed): data-less 65 passed / 166 skipped / 0 failed; with the nine exports supplied, pipeline 116 checks 0 errors, integrity VERIFIED, **231 passed**, 20 output files byte-identical to the original build.
- Repository scan of 91 would-be-committed files: 0 data/pilot/evidence/venv paths, 0 personal paths, 0 secret patterns, 0 e-mail addresses.

## Display-only preparation (2026-11-11)
- `.streamlit/config.toml`: `client.disableDataExport = true`; every `st.plotly_chart` hides the image-download button (`modeBarButtonsToRemove=["toImage"]`); `requirements.txt` pinned to the 46 versions of `requirements.lock`.
- Project venv: **234 passed** (3 new tests in `tests/test_display_only.py`); `bloom.integrity` VERIFIED. Fresh Python 3.13.15 venv from `requirements.txt` only: installed set equals the 46 pins exactly; with the nine exports supplied the pipeline (116 checks, 0 errors), integrity and **231** tests pass and all 20 outputs are byte-identical to the original build; data-less clone: 68 passed / 166 skipped / 0 failed.
- Browser (`scripts/browser_check.py`): ALL PASS in English and Arabic at 1440/768/390 px, language switch, map clicks, selectors.
- Export controls (`scripts/export_check.py`): 18 charts and 22 tables hovered across all sections in both languages: no "Download as CSV", no table copy, no "Download plot as a PNG", no download links. Positive control on the previous commit: the detector finds "Download as CSV" and "Download plot as a PNG" on 14 pages.
- Not removed by design: the values drawn in charts remain in the page data (see `PRIVATE_DATA_ARCHITECTURE.md`).
