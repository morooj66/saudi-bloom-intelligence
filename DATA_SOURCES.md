# DATA_SOURCES.md — Saudi Bloom Intelligence (Phase 1)

> **Status update 2026-11-10 (Phase A complete).** This document records the Phase 1 investigation and is kept as written. What changed since:
> - **Google Trends was retrieved** (8 manual CSV exports inspected, hash-pinned): two weekly national exports (262 weekly buckets each, groups A and B) and six regional exports. See `DATA_DICTIONARY.md`, `DATA_VALIDATION_REPORT.md`. The statements below that Trends was "not retrieved" are superseded.
> - **Boundaries added:** geoBoundaries gbOpen SAU ADM1 (13 regions), upstream OpenStreetMap, **ODbL 1.0** (`data/geo/SOURCE.json`, `ATTRIBUTION.md`; area limitation in `data/geo/AREA_DISCREPANCY.md`).
> - **MOMAH "planted flowers and trees" (2022)** was inspected in Phase 1 but is *not* used in the product (public landscaping, single snapshot).
> - Saudi Open Data Portal, Ministry of Commerce and MEWA remain **unverified** (blocked / certificate error / no dataset list at the time).
> - Still no verified Saudi source of flower sales or commercial activity: the product only ever shows relative search interest.

Investigation date: 2026-11-10. Environment: macOS, Python 3.13, web access available but partly blocked (details below).

**Legend:** ✅ Verified = retrieved/inspected by me this session · 🔎 Seen in search/page text only (not downloaded) · ❓ Not verified (assumption / needs manual check)

---

## Summary table

| # | Source | Status | Flower search interest | Regional | Freq | Commercial flower activity | Usable? |
|---|---|---|---|---|---|---|---|
| 1 | Google Trends (web UI / CSV export) | ❓ Not retrieved (HTTP 429 from this machine) | Yes (relative index) | Yes (13 regions, if available) | Daily/weekly/monthly | No | **Yes – primary candidate, manual export** |
| 2 | Google Trends API (alpha) | 🔎 Announcement confirmed via search | Yes | Yes (ISO 3166 sub-regions) | Daily–yearly | No | Only if accepted into alpha |
| 3 | MOMAH "Planted flowers and trees" (2022) | ✅ Downloaded & inspected | No (municipal planting counts) | Yes (19 Amanas) | One snapshot, end-2022 | No (public landscaping) | Context only |
| 4 | Saudi Open Data Portal (open.data.gov.sa) | ❌ Blocked ("Request Rejected" from curl/WebFetch) | Unknown | Unknown | Unknown | Unknown | Needs manual browser check |
| 5 | Ministry of Commerce open data (mc.gov.sa/en/OpenData) | ❌ TLS cert error from fetcher | Unknown | Unknown | Unknown | Possibly (commercial registrations) | Needs manual check |
| 6 | MEWA open data platform | 🔎 Landing page read; platform link is a JS placeholder | Unknown | Unknown | Unknown | Unlikely (production stats) | Needs manual check |
| 7 | GASTAT (stats.gov.sa) | ✅ Site reachable (HTTP 200); no dataset inspected | No | Some | Annual/quarterly | Unknown | Needs manual check |
| 8 | Estidamah / RCU / NCW open data | 🔎 Listing seen via search | No (saffron, AlUla flora, invasive plants) | Narrow | Static | No | Not relevant |
| 9 | Calendar (Islamic/Gregorian events) | ❓ Not fetched | n/a | n/a | Daily | n/a | Yes – derive offline (see below) |

---

## 1. Google Trends (web UI + CSV export)
- **URL:** https://trends.google.com/trends/ (explore with `geo=SA`)
- **Data:** Relative search interest, 0–100, for a term/topic. Official help: https://support.google.com/trends/answer/4365533
- **Geography:** Country (SA), and sub-region breakdown. Whether all 13 administrative regions return values for flower terms is **not verified**.
- **Historical coverage:** Web UI supports 2004–present for broad queries (assumption from general knowledge; not tested here).
- **Columns (CSV export, expected):** date, one column per term (0–100). Regional export: region name, value. *Not verified by download.*
- **Access:** Manual CSV export from UI. Unofficial scrapers (e.g. pytrends) exist but are not endorsed by Google and are rate-limited/fragile.
- **Retrieval attempt:** `curl` and WebFetch to the explore URL returned **HTTP 429** ➜ **no Trends data was retrieved or inspected.**
- **Verified methodology facts (from the Google help page, fetched):**
  - Each point = searches for term ÷ total searches in that place/time, then scaled to 0–100 relative to the peak in the selected window.
  - Data is a **sample**, not the full log; low-volume terms display as 0.
  - ≥30-day ranges are in UTC; granularity is daily/weekly/monthly depending on range.
  - Duplicate searches by the same person in a short period are filtered.
- **Restrictions:** Google terms of service apply; no official public API key. Redistribution of raw data should be reviewed against Google's terms.
- **Limitations:** Relative index only; re-normalizes with every query window; not sales, not search counts; sampling noise; Arabic vs English term variants and spelling must be handled separately; max 5 terms per comparison.

## 2. Google Trends API (alpha)
- **URL:** https://developers.google.com/search/blog/2025/07/trends-api (announcement; surfaced via search)
- **Reported facts (search snippets, secondary sources partly disagree):** announced 2025-07-24; application-based alpha; rolling window ≈1,800 days (≈5 years); daily/weekly/monthly/yearly aggregation; region/sub-region by ISO 3166 codes; no pricing/GA date published.
- **Status:** Not applied for; not tested. 🔎 Only the announcement was confirmed.
- **Implication:** Not a dependable data source for an MVP unless the user obtains alpha access.

## 3. MOMAH — "Planted flowers and trees" (✅ downloaded)
- **Page:** https://momah.gov.sa/en/open-data (listing page 13)
- **File downloaded:** https://momah.gov.sa/sites/default/files/2023-06/planted-trees-and-flowers-for-2022.csv (also .pdf/.xlsx)
- **Saved copy:** `evidence/momah_planted_trees_flowers_2022.csv` — 3,041 bytes, 134 lines, SHA-256 `db564d06…a17981`. Encoding is **Windows-1256 (Arabic)**, delimiter `;`, CRLF.
- **Content actually inspected:** Title "Trees and flowers planted at end of 2022". Table with columns: *entity (Amana)*, *number of trees*, *number of flowers planted*, for **18 municipal entities** (Amanas/governorates) plus a total row: **24,522,014 trees; 79,601,535 flowers**.
  Examples: Qassim Amana 23,585,129 flowers; Eastern Province 16,143,452; Tabuk 12,161,538; Madinah 7,277,364.
- **Data quality problems found:** the same file also contains unrelated tables (cemeteries, corpse-washing facilities) with `#REF!` Excel errors; irregular multi-block layout; unit/definition of "flowers planted" (plants? stock? per year?) undocumented. Geographic unit is municipalities, **not** the 13 administrative regions (some are cities: Jeddah, Taif, Al-Ahsa, Hafr Al-Batin).
- **License:** not shown on the dataset entry; page links an "Open Data Usage Policy" (`/en/node/3445`) that I did **not** open. ❓
- **Coverage in time:** a single 2022 snapshot. Cannot be used for forecasting.
- **Relevance:** Reflects public landscaping by municipalities, **not** retail flower demand or sales. Possible use: static contextual layer, clearly labeled.

## 4. Saudi Open Data Portal (SDAIA)
- **URL:** https://open.data.gov.sa
- **Attempts:** `curl https://open.data.gov.sa/` returns HTTP 200 but the body is an F5-style *"Request Rejected"* page; the catalog API probe also returned the same; WebFetch on `/en/datasets` was rejected. **No catalog content was seen.**
- **Search-engine evidence only:** no data.gov.sa dataset with "flowers"/"plants" in its title was surfaced. Agency portals (MOMAH, RCU, Estidamah, NCW) appeared instead.
- **Action for user:** search the portal manually in a browser for: زهور، ورد، مشاتل، زراعة، تجزئة، سجلات تجارية.

## 5. Ministry of Commerce
- **URL:** https://mc.gov.sa/en/OpenData
- **Attempt:** WebFetch failed with "unable to verify the first certificate". Not inspected. ❓
- **Assumption (unverified):** may publish commercial-registration or e-commerce statistics; whether any are flower/florist specific is unknown.

## 6. Ministry of Environment, Water & Agriculture (MEWA)
- **URL:** https://www.mewa.gov.sa/en/InformationCenter/Researchs/OpenDataSite/Pages/default.aspx
- **Seen:** Landing page states it publishes datasets in reusable formats; the platform link was a `javascript:` placeholder; no dataset list. No flower/nursery data confirmed. Phone 939 listed.
- **Assumption:** agricultural statistics (crop areas, production) are probably annual and not ornamental-specific. Unverified.

## 7. GASTAT
- **URL:** https://www.stats.gov.sa/en — reachable (HTTP 200). No dataset reviewed. Retail/household-spending tables might help as macro context but nothing flower-specific is confirmed. ❓

## 8. Other agency datasets (search results only)
Estidamah (saffron), RCU (AlUla plants/flora, date palm area), NCW (invasive plants). Not about consumer flower demand. Excluded.

## 9. Seasonal / calendar information
No dataset needed: Gregorian holidays (Valentine's Day, Mother's Day 21 Mar) are fixed; Hijri events (Eid al-Fitr, Eid al-Adha, Ramadan start, Saudi National Day 23 Sep—Gregorian, Founding Day 22 Feb) can be computed with a Hijri conversion library (e.g., `hijri-converter`; Umm al-Qura tables). **Not yet implemented or verified.** Note that Hijri dates shift ~11 days earlier per Gregorian year, so a naive monthly seasonal dummy will blur Eid effects.

---

## What is NOT available (as far as verified)
- No verified Saudi dataset of flower **sales**, imports, retail revenue or florist counts.
- No verified official time series of flower commercial activity.
- Therefore the only candidate time series is **Google Trends search interest**, which must always be labeled as a relative search-interest index.
