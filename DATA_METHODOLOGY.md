# Data Methodology (factual; derived from the code)

Every statement below was checked against the source file named in brackets. Where something is **not** done, it says so.
Cleaning (changing how a value is represented) and validation (testing it and refusing to continue) are kept apart.

## 1. Data collection
| Item | Fact |
|---|---|
| Source | Google Trends web interface (trends.google.com), **manual CSV exports** |
| Number of original datasets | **9** CSV files (2 weekly timelines, 7 regional snapshots) |
| Geography | Saudi Arabia (file headers: «المملكة العربية السعودية») |
| Period | Regional files state 10/11/2021 – 10/11/2026 (day/month/year). Weekly files: 262 weekly buckets (Sunday-start); 260 after excluding two partial edge weeks |
| Category | All categories (stated in the file headers) |
| Search type | "Web Search" and the export date are **operator-stated**, not in the files; the manifest marks the date *inferred* |
| Terms (Arabic) | ورد · محل ورد · توصيل ورد · بوكيه ورد · شراء ورد |
| Group A | timeline + regional share, 5 terms |
| Group B | timeline, 4 commercial terms (without ورد) |
| Regional | 5 single-term index exports; one 4-term regional share export (`B4`) |
| Automation | None. One automated request got HTTP 429 and was not retried |

## 2. Cleaning — what the code actually changes
Only **representation** changes. Values are never altered, filled or removed. [`src/bloom/trends_io.py`, `transform.py`]
1. Encoding detection (UTF-8/BOM, UTF-16, UTF-8, Windows-1256) and delimiter detection.
2. Removal of invisible bidirectional control characters and surrounding whitespace from cells.
3. Arabic-Indic digits and the Arabic decimal/percent signs are mapped to ASCII.
4. Metadata rows above the table are separated from the table.
5. Cell parsing into explicit states: exact number; **censored** («<1», «أقل من 1%» → value NaN, upper bound 1); **blank** → missing flag. Anything unrecognised raises `ValueError`.
6. Region names are mapped to ISO 3166-2:SA with English/Arabic names; an unknown name raises an error.
7. Tidy long format with `comparison_group`, `scale_id`, `normalization` and `source_file` on every row; rows sorted by term and week.
8. Two partial edge weeks (7-day span not fully inside the query window) are **flagged** (`is_edge_partial_week`) and excluded from profiling and analysis.
9. Calendar features (Umm al-Qura Islamic events, fixed holidays) are joined by date.

**Not done (verified by search of `src/`):** no imputation or interpolation of source values; no outlier removal or winsorising; no de-duplication (duplicates are a validation *error*, not silently dropped); no smoothing of the source data; no statistical correction or rescaling of Google's values; no merging of differently normalised exports.

**Two places a bound is substituted for a missing value, both bookkeeping and neither writes into the value column:**
- `analysis.regional_share_table` adds a separate column `share_upper_bound` = the value, or the censor bound (1) where the cell is censored. `value` itself stays NaN.
- The validation check `shares_sum_to_about_100` computes a lower sum (exact values only) and an upper sum (censored cells at their bound, blanks as 0) purely to test that the published shares are consistent with totalling ≈ 100. The blank-as-0 there is a test calculation, not data, and nothing is stored.

## 3. Validation — what the code tests (116 checks, 0 errors, 6 documented warnings)
[`src/bloom/validate.py`, `integrity.py`]
- **File integrity:** SHA-256 of each raw file at ingest, stored in an append-only manifest; later runs refuse a changed or removed input; `raw_checksum_unchanged`.
- **Schema:** expected terms per comparison group; one `scale_id` per group (`single_scale_id`, `no_group_mixing`).
- **Duplicates:** none for (term, week) and (region, term).
- **Missing and censored values:** reported as warnings/facts; `censored_not_treated_as_exact`.
- **Value rules:** within 0–100, integers, group peak = 100; regional shares sum to about 100; peak region = 100 in index exports.
- **Temporal continuity:** valid dates, weeks start on Sunday, constant 7-day frequency, equal length per term, same week grid across groups.
- **Geographic consistency:** all 13 regions present once per term; regional window equals the weekly window.
- **Scale isolation:** `scale_id` on every row; `ScaleMixError` on mixing; an integrity check that the 4-term share table shares no scale with another table.
- **Runtime integrity (19 checks):** processed file hashes and provenance, forecast-gate constants, forecast-suppression consistency. The dashboard shows no analytics if any fails.

## 4. Processing and outputs
`incoming_data/` → `data/raw/` (byte-identical copies) + manifest → `data/processed/*.parquet|csv` + `_provenance.json` (hash of every output) → `data/analysis/` (phase A). Processed data are written only when validation has zero errors. No weekly aggregation is performed: the weekly series are used as exported. Monthly and week-of-year profiles are descriptive groupings (mean/median) of those weekly values.

## 5. Analysis [`src/bloom/analysis.py`, `overview.py`]
- **National trend:** descriptive comparison of the mean of the last 52 weeks with the prior 52 (not a statistical test).
- **Seasonality:** monthly means relative to the overall mean; robust STL (period 52) strength measures; event-week lift (event week ÷ median of surrounding weeks); only about five annual cycles exist.
- **Regional indices:** per-term index (100 = highest region *for that term*), rank among regions with a numeric value; the 5-term share export is a separate metric and never merged with it.
- **Commercial-term composition:** shares from the 4-term regional export drawn exactly as published; censored and blank cells shown as such; any gap shown as "unspecified", never distributed to a term.

## 6. Forecast evaluation [`src/bloom/forecast.py`]
- **Models evaluated:** (1) last value; (2) seasonal naive (value 52 weeks earlier); (3) calendar ridge regression (penalty 1.0, intercept unpenalised) on calendar features known in advance plus a trailing 4-week mean, fitted separately per horizon; predictions below 0 are clipped to 0.
- **Method:** rolling origin, expanding window, first origin after 130 weeks, horizons 1–4 weeks, 63 origins.
- **Gate (fixed in advance):** beat the best baseline by ≥ 5% MAE **and** bootstrap (2000 draws, seed 0, over origins) 95% CI entirely above zero.
- **Result:** +5.33% MAE; CI [−0.89, +1.90] → **not passed**; no forecast file is written and the dashboard shows none.
- **Why withheld:** the interval includes zero, the interval is optimistic (overlapping origins), only five annual cycles, four series were tested, and the thresholds were not changed after seeing the result.
