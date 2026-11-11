# DATA_DICTIONARY.md

All measures are **Google Trends relative search interest**. Never sales, demand, or search counts.

## Normalization rules (read first)
| Export type | Meaning of the number | Comparable with |
|---|---|---|
| Timeline, group A (5 terms) | Index 0–100; 100 = highest weekly point of **any** of the 5 terms in this export | Only terms inside this export |
| Timeline, group B (4 commercial terms) | Index 0–100; 100 = highest weekly point of any of the 4 terms in this export | Only terms inside this export |
| geoMap group A | % share of each term among the 5 terms' searches within a region (sums ≈ 100 per region) | Only inside this export |
| geoMap single term (5 files) | Index 0–100; 100 = the region with the highest search share for this one term | Only regions of the same term |
| geoMap group B4 (4 commercial terms, `geoMap (6)`) | % share of each term among the 4 commercial terms' searches within a region; censored «<1%» and blank cells are never converted to zero | Only inside this export (own scale, own dataset `region_groupB4_share`) |

Every row carries `scale_id` (`<group>|<kind>|<file>`) and `normalization` text. `bloom.schema.assert_same_scale` raises `ScaleMixError` when frames with different `scale_id` are combined; charts and analysis call it. The same term (e.g. «محل ورد») has **different numbers** in group A (max 15) and group B (max 100): that is normalization, not a data error.

## Files in `data/`
| Path | Contents |
|---|---|
| `data/raw/*.csv` | Byte-identical copies of the 9 Google Trends exports (never overwritten; SHA-256 enforced) |
| `data/manifest.json` / `.csv` | One entry per raw file (below) |
| `data/processed/*.parquet` + `.csv` | Cleaned datasets (below) |
| `data/processed/validation_results.json` | All validation checks |
| `data/processed/phase_a/*` | Phase A analysis outputs and `forecast_status.json` |

## Manifest fields
`file_name, raw_path, sha256, size_bytes, source, retrieved_date, retrieved_date_basis (inferred from file mtime), scale_id, normalization, kind (timeline|geomap), encoding, delimiter, metadata_rows, category, first_column_label, terms, n_data_rows, comparison_group, geographic_scope, granularity, window_start/window_end (geomap only)`.

## `timeline_group{A,B}_long` (tidy; schema `NATIONAL_WEEKLY_COLUMNS`)
| Column | Type | Description |
|---|---|---|
| week_start | datetime | Sunday that starts the weekly Trends bucket |
| term | str | Arabic search term |
| value | float | Published integer 0–100; **NaN if censored or missing** |
| is_censored | bool | Published as «<1» / «أقل من 1» (true value in (0,1)); never converted to a number |
| censor_upper_bound | float | 1.0 when censored, else NaN |
| is_missing | bool | Blank cell |
| is_reported_zero | bool | Published 0 (Trends reports 0 for very low volume; may not be a true zero) |
| comparison_group, scale_id, normalization, source_file | str | Provenance and scale |
| is_edge_partial_week | bool | First/last bucket only partly inside the query window |

## `timeline_group{A,B}_analytic_weekly` (one row per week, one group)
`week_start`, `value__<term>`, `censored__<term>` for each term, `comparison_group`, `scale_id`, all calendar features below, `is_edge_partial_week`.

## Calendar features (`calendar_weekly`, merged into analytic files)
Functions of dates only (no series values) → no leakage. Islamic events use the Umm al-Qura calendar via `hijridate` (computable years ahead), **not** fixed Gregorian dates.
| Column | Description |
|---|---|
| week_start / week_end | Sunday–Saturday |
| year, quarter, month | month of the week's midpoint (Wed) |
| iso_year, iso_week | ISO calendar of the week start |
| week_of_year_sunday | 1–52 from the midpoint's day of year |
| annual_sin / annual_cos | Annual Fourier terms (period 365.25 d) |
| hijri_year / hijri_month | Hijri date of the midpoint |
| `<event>_in_week` | Event date falls in the week. Events: ramadan_start, eid_al_fitr, arafat_day, eid_al_adha, valentines_day, mothers_day_arab (21 Mar, widely observed, not an official Saudi holiday), saudi_founding_day (22 Feb, from 2022), saudi_national_day (23 Sep), new_years_eve |
| `<event>_week_offset` | Signed weeks to the nearest occurrence (positive = upcoming), within ±4, else NaN. A published-calendar covariate |
| ramadan_days_in_week | 0–7 |
| is_ramadan_week | bool |
| known_in_advance | always True |

`calendar_events` lists every event date with `basis`, `verification` and `source_note`. **Verified against Saudi announcements (web, 2026-11-10):** Eid al-Fitr 2022-05-02, 2024-04-10, 2025-03-30, 2026-03-20; Eid al-Adha 2023-06-28, 2024-06-16, 2026-05-27; Ramadan start 2026-02-18 — all equal the Umm al-Qura dates (a test enforces this). The remaining Islamic dates (12) are Umm al-Qura-computed and **not independently verified**. Actual Saudi dates follow moon sighting and may differ by a day from the computed calendar.

## `region_groupA_share`, `region_single_term_index` (schema `REGIONAL_SNAPSHOT_COLUMNS`)
| Column | Description |
|---|---|
| region_iso / region_en / region_ar / region_name_raw | ISO 3166-2:SA code, English, standardised Arabic, name as exported |
| term | search term |
| value | share % (`region_groupA_share`) or 0–100 index; NaN if censored/missing |
| is_censored, censor_upper_bound | «أقل من 1%» → censored, bound 1 |
| is_missing | Blank = Google reported no data (not zero) |
| metric | `share_pct_of_compared_terms` or `index_0_100_peak_region` |
| window_start, window_end | Query window (day/month/year parsed day-first) |
| comparison_group, scale_id, normalization, source_file | provenance |

## Phase B (planned, not populated): `REGIONAL_WEEKLY_COLUMNS`
`region_iso, week_start, term, value, is_censored, censor_upper_bound, is_missing, comparison_group, scale_id, normalization, source_file`. Same keys as the snapshot plus `week_start`; needs weekly exports per region. Not available in the current data.

## `series_profile`
Per (group, term): n_weeks (edge weeks excluded), censored_n, reported_zero_n/share, mean, median, std, max, p5, p95, acf_lag1, acf_lag52, yoy_corr_52, usable_resolution (median ≥ 10), low_zero_share (≤ 10%), low_censoring (≤ 5%), candidate_for_forecasting.

## `phase_a/` outputs
`month_profile`, `event_lift`, `event_lift_summary`, `stl_strength`, `backtest_errors`, `backtest_summary`, `regional_index_by_term`, `regional_share_groupA`, `forecast_status.json`, and `forecast_national` **only if the validation gate passes** (currently absent).

## Addenda (final refinement)
**Provenance files** (`data/processed/_provenance.json`, `data/processed/phase_a/_provenance.json`): `input_fingerprint` (digest of raw file names + SHA-256), `outputs` (SHA-256 of every output file), `generated_at_utc` (time the pipeline wrote the file; **processing time, not retrieval time**), plus `processed_provenance_sha256` and `gate_constants` in the phase_a file.

**Manifest `retrieved_date`**: the file's modification time. Google Trends does not state when an export was made, so it is **inferred and unverified**; the dashboard labels it "File modified (inferred, not verified)". Regional exports do state their *query window* in the header (2021-11-10 → 2026-11-10, day/month/year).

**Executive-overview KPIs** (computed by `bloom.overview` from `regional_index_by_term`, `timeline_groupB_long`, `event_lift_summary`):
| KPI | Definition |
|---|---|
| Highest relative search interest for «محل ورد» | Region with the maximum exact index in the single-term export for that term. 100 = peak region by definition; ties are reported; blank/censored regions are excluded. Not volume, sales or purchases. |
| Regions covered | Distinct regions in the regional exports (13) and how many have exact values for all five terms (8). |
| Historical data coverage | Weekly buckets excluding the two partial edge weeks (260), first and last analysed week. |
| Strongest documented seasonal observation | Event with the highest median event-week lift for «محل ورد» (median of 5 occurrences; years above 1.2×). Descriptive only. |

**Boundary data**: `data/geo/` (`saudi_adm1_geoboundaries_simplified.geojson`, `SOURCE.json`, `ATTRIBUTION.md`, `AREA_DISCREPANCY.md`). Ring order is reversed at render time only (`rewind_for_plotly`).


## Addendum: regional commercial-term mix (`region_groupB4_share`)
Source: `geoMap (6).csv` (SHA-256 `c5e37404…536820`), the ninth raw file, appended to the manifest. `comparison_group = B4_commercial_4terms_regional_share`; `scale_id = B4_commercial_4terms_regional_share|geomap|geoMap (6).csv`; `metric = share_pct_of_compared_terms`. Schema: `REGIONAL_SNAPSHOT_COLUMNS`. 13 regions × 4 terms (محل ورد, توصيل ورد, بوكيه ورد, شراء ورد): 39 numeric, 8 censored («أقل من 1%», bound 1), 5 blank cells; all censored/blank cells are in شراء ورد. Values are the share of each term among these four terms' searches **within one region**; the published numbers of every region total 100. It is not an index, not volume, not comparable with `region_single_term_index` or `region_groupA_share`, and is never concatenated with them (`ScaleMixError`; integrity check "four-term regional shares keep their own scale"). The weekly four-term timeline keeps group `B_commercial_4terms`.
