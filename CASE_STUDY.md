# Saudi Bloom Intelligence — Technical Case Study

*Discovering Saudi Arabia's Flower Search Trends.* A reproducible, integrity-checked analysis of **Google Trends relative search interest** for flower-related Arabic queries in Saudi Arabia: national seasonality, a 13-region comparison, a commercial-term mix, and a forecast that is published only if it passes a rule fixed in advance (it did not).

Author: Morooj Mohammed Alrajhi. Code: MIT. Data: Google Trends, not included (see `DATA_USE_ASSESSMENT.md`).

**Labels.** **[V]** Verified (computed or checked; reproducible by a test or command) · **[D]** Descriptive (what the data show, no explanation claimed) · **[H]** Hypothesis (plausible, untested) · **[U]** Unverified assumption.
Numbers come from `data/processed/` and the test suite and can be regenerated from the exports. Method detail, derived from the code: `DATA_METHODOLOGY.md`.

---

## 1. The analytical problem
Public data on flower demand in Saudi Arabia is scarce. Google Trends offers a proxy for *interest*, but it is hard to use correctly: every export is normalised on its own scale, low values are censored or blank, regional values are single snapshots, and nothing in it measures purchases.

Questions: (1) Is there a stable annual pattern in national search interest, and does it line up with calendar events? (2) How does relative interest differ across the 13 regions, and how should such a ranking be explained honestly? (3) How is the mix of four commercial terms distributed across regions? (4) Can a short-horizon national forecast beat simple baselines convincingly enough to publish? (5) Can the analysis make wrong comparisons (mixing scales, blanks as zero, implying sales) impossible or loudly rejected?

**Scope boundary [V].** Search interest only. No sales, revenue, price or demand data; the product never labels interest as such. Regional time series, city level and regional forecasts are out of scope.

## 2. Why this data was selected
- **[V]** A Phase 1 survey of candidate sources found Google Trends to be the only source giving *public, weekly, national and regional* flower-related signals. The other candidates were either context only (a municipal planting-count file, deliberately not used), not retrievable at the time (several Saudi open-data portals were blocked or unverified), or not about flowers. No verified Saudi source of flower sales or commercial activity was found (`DATA_SOURCES.md`).
- **[V]** Five Arabic queries were chosen to separate the general term (ورد) from four commercial intents: shop (محل ورد), delivery (توصيل ورد), bouquet (بوكيه ورد), buy (شراء ورد).
- **[D]** Trade-off accepted: Trends measures relative search interest, a weaker and noisier signal than sales, in exchange for being available and regionally resolved.
- Region boundaries come from geoBoundaries (ODbL 1.0, OpenStreetMap upstream).

## 3. How the data was collected
- **[V]** Google Trends web interface, **manual CSV exports** (nine files): Saudi Arabia, past five years, all categories; regional files state 10/11/2021 – 10/11/2026 (day/month/year). **[U]** "Web Search" as the search type and the export date come from the operator; the manifest records the file time as *inferred, not verified*.
- **[V]** Nine exports: two weekly national timelines (5-term group A, 4-term commercial group B; 262 weekly buckets each) and seven regional snapshots (5-term share; five single-term indices; one 4-term share added last).
- **[V]** No scraping. One automated request was answered with HTTP 429 and was not retried or worked around.
- A city-level pilot (Riyadh, Jeddah, Dammam) was evaluated and rejected (§9).

## 4. What was actually cleaned or transformed
Cleaning here means **changing representation only**; no value is altered, filled or removed. **[V]** (searched `src/`: no imputation, interpolation, outlier handling or de-duplication of source values. The only bound substitutions are a separate `share_upper_bound` column and a validation sum, described in `DATA_METHODOLOGY.md`.)
- Encoding and delimiter detection; removal of invisible bidirectional control characters; Arabic-Indic digits mapped to ASCII; metadata rows separated from the table.
- Cells parsed into explicit states: exact number, **censored** («<1» / «أقل من 1%» → value NaN + upper bound 1), **blank** (missing). Unrecognised formats raise an error.
- Region names mapped to ISO 3166-2:SA (13 regions) with English/Arabic names; unknown names raise.
- Tidy long format; `comparison_group`, `scale_id`, `normalization` and `source_file` on every row.
- Two **partial edge weeks** (2021-11-07, 2026-11-08) are flagged and excluded from analysis (262 → 260 weeks).
- Calendar features (Umm al-Qura Islamic events, fixed holidays) joined by date.

**Not done [V]:** no imputation, no outlier removal, no smoothing, no correction or rescaling of Google's values, no merging of differently normalised exports, no silent de-duplication.

## 5. How data quality was checked
Validation is separate from cleaning: it *tests* and refuses to continue; it does not fix.
- **Raw preservation [V].** SHA-256-pinned raw files, an append-only manifest (removing an input is an error; changing one is refused), a test pinning all nine hashes.
- **Pipeline validation [V]: 116 checks, 0 errors, 6 documented warnings.** Schema and terms per group, duplicates, Sunday-start 7-day grid, equal length, values within 0–100, integers, peak = 100, 13-region coverage, shares ≈ 100, censored values never numeric, window consistency between exports. Warnings are facts (e.g. blank regional cells, the two partial edge weeks).
- **Provenance [V].** `_provenance.json` holds an input fingerprint and the hash of every output.
- **Fail-closed integrity (19 checks) [V].** Re-checks hashes, fingerprints, schemas, forecast-gate constants and forecast-suppression consistency on every dashboard load; with any failure the dashboard shows no analytics and never regenerates data. Tamper tests all fail closed.
- **Scale isolation [V].** `ScaleMixError` when frames with different `scale_id` are combined; tests mix on purpose; an integrity check asserts the 4-term share table shares no scale.
- **Islamic event dates [V/U].** 8 dates were checked against Saudi announcements and equal the computed values; the other 12 computed dates were not independently verified.
- **Browser checks [V].** Real Chrome at 1440/768/390 px, English and Arabic.

## 6. Engineering challenges
| Challenge | Solution |
|---|---|
| Independently normalised exports can be silently mixed | `scale_id` on every row, `ScaleMixError`, deliberate-mix tests, integrity check |
| Censored vs blank vs reported zero | Three explicit states from parsing to charts and text alternatives; tests prove no zero is fabricated |
| Silent bad data in a dashboard | Fail-closed integrity gate on every load; pipeline exit codes (0 ok · 1 validation errors, nothing written · 2 input failure) |
| Adding a ninth file must not change earlier results | Every earlier processed/analysis dataset compared before/after: identical; forecast status identical |
| Map polygons rendered inverted | Found only in a browser; fixed with a render-time ring reversal, geometry untouched and hash-pinned |
| Arabic/English mixed text | Unicode isolates, directional wrapping of numerals, RTL layout; checked at three widths |
| Streamlit resets widgets whose labels change (language switch lost the reader's place) | Canonical language-independent state re-applied on switch; browser-tested |
| Defects invisible to unit tests | DevTools-protocol checks found a CSS rule hiding navigation labels, invisible SVG bars and a legend overlapping an axis title |
| Automated access blocked (HTTP 429) | Stopped; manual export instructions; no circumvention |
| Empty installations | Plain-language errors without weakening checks; data-dependent tests skip with an explicit reason |

## 7. Decisions and trade-offs
- **Files, not a database [V].** Series are tiny and single-user; Parquet + CSV with hashes is simpler to verify.
- **Fail closed over friendly.** A dashboard that shows nothing when integrity fails is less pleasant than one that shows numbers, and was chosen deliberately.
- **Withhold the forecast.** The point-estimate gain met the size rule but the interval included zero (§8). Publishing would imply accuracy the evidence does not support; the threshold was not changed after the result.
- **Non-rescaled composition chart.** A conventional 100% stacked bar would rescale and imply published shares must total 100. The chart draws shares exactly as exported on a fixed 0–100 axis, shows any gap as a hatched "unspecified remainder" (zero here), and marks censored and blank cells distinctly.
- **No city level.** The city export lacked Riyadh, Jeddah and Dammam and held within-city shares, so ranking cities would be indefensible (§9).
- **Data not shipped.** Redistribution of Trends exports is not cleared; readers bring their own exports (`DATA_USE_ASSESSMENT.md`).
- **Streamlit over a custom front end.** Faster to verify and enough for a read-only dashboard; the cost is limited control over widget behaviour (see the language-switch workaround).
- **No LLM or AI agent** in the product; classical statistics only.

## 8. Verified analytical findings
**National and seasonal («محل ورد», 4-term index export).**
- **[D]** 260 analysed weeks; mean 43.7, median 41; the highest week is 15 Mar 2026 (100). The last-52-week mean is 3.1% below the prior 52 (43.9 vs 45.3): descriptive, not a change in searches or sales; sampling noise unmeasured.
- **[D]** Highest monthly averages: June (1.33× the overall mean), May (1.30×); lowest September (0.82×). Robust STL seasonal strength 0.55; year-over-year correlation 0.54; only ~5 annual cycles.
- **[D]** Event-week lift (event week ÷ median of surrounding weeks, 5 occurrences each): Eid al-Fitr 1.97× (above 1.2× in 5 of 5 years), Valentine's Day 1.73× (5 of 5), New Year's Eve 1.49× (3 of 5), Arafat Day 1.29×, Eid al-Adha 1.29× (3 of 5), Mother's Day (21 Mar) 1.08×, National Day 0.90×, Ramadan start 0.86×, Founding Day 0.76×.
- **[V] Confounding.** The Mother's Day maximum equals the Eid al-Fitr maximum (2.60×): in 2026 both fall in the same Sunday–Saturday week, so the data cannot separate them.
- **[H]** Eid and Valentine's Day weeks raise interest; the May–June peak reflects Eid al-Adha and/or other occasions. Untested: five occurrences, no significance test, no causal design.
- **[V]** «شراء ورد» is 0 in 254 of 260 weeks (unusable as a series); «توصيل ورد» and «بوكيه ورد» have medians of 6 and 8 (low resolution).

**Regional index (per term, 100 = highest region for that term).**
- **[V]** For «محل ورد»: Jazan 100, Northern Borders 96, Najran 92; Riyadh lowest (35). Recomputed independently from the original CSV and asserted in tests.
- **[V]** The 5-term *share* export ranks a different region first (Northern Borders, 13%): a different question, never merged. For the general term the share is 86–90% everywhere, carrying almost no information.
- **[U]** Why Jazan ranks first is not explained; rank stability is not established (no repeated exports; 100/96/92 are close).

**Commercial-term composition (share of four terms within each region).**
- **[V]** 52 cells: 39 numeric, 8 censored, 5 blank; all censored and blank cells are «شراء ورد».
- **[D]** «محل ورد» is 65–86% of every region's mix (lowest Riyadh 65%, highest Al Jawf 86%); «توصيل ورد» 4–15% (highest Riyadh); «بوكيه ورد» 9–21% (highest Asir).
- **[H]** A larger shop share means the shop term is a larger part of that region's own mix, not that the region searches more.

**Forecast evaluation [V].** Target «محل ورد» (weekly). Models: last value; seasonal naive (52 weeks earlier); calendar ridge regression (calendar covariates known in advance + trailing 4-week mean, per horizon). Rolling origin, expanding window, first origin after 130 weeks, horizons 1–4, 63 origins. Gate fixed in advance: beat the best baseline by ≥ 5% MAE **and** bootstrap 95% CI entirely above zero.

| | MAE (index points) |
|---|---|
| Last value | 12.03 |
| Seasonal naive (best baseline) | 7.96 |
| Calendar ridge regression | 7.54 |

Improvement **+5.33%** (size rule met); 95% CI **[−0.89, +1.90]** (must be > 0: not met) ⇒ **gate not passed; no forecast file exists.** Reasons for withholding: the interval includes zero; the interval is optimistic (overlapping origins); only five annual cycles; four series were tested (the 4-term delivery series passed at +14.5%, CI [0.10, 0.42], but is not the designated target, has a median of 6 and is one of four tested; not published); thresholds were not changed after the result.

## 9. Limitations
- **[V]** Relative interest only; spelling variants and dialects not modelled.
- **[V]** ~5 annual cycles; event findings are descriptive. Regional values are single snapshots: no regional time series or forecasts.
- **[U]** Rank stability and Trends sampling noise are not measured; the search type and export date are operator-stated.
- **[V]** The shipped boundary geometry's area (~1.93 M km²) is ~10–11% below commonly cited figures (a boundary-definition difference, `data/geo/AREA_DISCREPANCY.md`): thematic use only.
- **[V] City level not supported.** The Trends city export listed 200 places, only 15 with any value, and Riyadh, Jeddah and Dammam were absent; values were within-city shares. The original city file was not retained, so this finding rests on pasted text.
- **[U]** Not tested: Safari/Firefox, real devices, screen readers, keyboard-only use.
- Public hosting of Trends-derived values is not cleared (`DATA_USE_ASSESSMENT.md`).

## 10. Lessons learned
Each lesson names the evidence that produced it.
1. **Normalisation belongs in the data model, not in documentation.** The same term peaks at 15 in one export and 100 in another; carrying `scale_id` on every row and failing on mixing removed a whole class of mistakes, and a deliberate-mix test proves it.
2. **Browser checks find what unit tests cannot.** Inverted map polygons, a CSS rule hiding navigation labels, invisible SVG bars and a legend overlapping an axis were all found only in a real browser.
3. **State your gate before you look.** The forecast beat the baseline by 5.33%, over the 5% line, yet the interval crossed zero. Having the rule fixed in advance made "do not publish" a mechanical decision instead of a judgement call.
4. **Be explicit about missing data.** Treating «<1%» or a blank as zero would have silently distorted the 4-term composition, where all 13 non-numeric cells belong to one term.
5. **Do not recreate lost evidence.** A city export that could not be found was not reconstructed as an original; the finding is labelled as resting on pasted text.
6. **Frameworks have sharp edges.** Streamlit resets widgets whose labels change; making the language switch keep the reader's place required canonical state and a browser test.
7. **Check licences and terms early.** The question of whether Trends-derived values may be displayed publicly surfaced at release time and is still open; it should have been asked at the start.

*No machine-learning model beyond ridge regression and no LLM or AI agent is part of the product.*
