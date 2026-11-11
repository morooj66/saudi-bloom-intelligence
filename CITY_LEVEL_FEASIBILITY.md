# CITY_LEVEL_FEASIBILITY.md — Riyadh, Jeddah, Dammam

**Status: assessment only. No city data was collected, requested, scraped or modified. No city chart or number exists anywhere in the project.**
Labels: VERIFIED (read from a source during this work) · NOT VERIFIED (would need data access, which needs your approval) · NOT AVAILABLE.

## 1. Objective
Compare relative search interest for flower queries across Saudi cities, starting with Riyadh, Jeddah and Dammam.

## 2. What the current data can and cannot do
| Question | Answer |
|---|---|
| Does the project contain city-level data? | **No.** The regional exports cover 13 administrative regions only. |
| Can city values be derived from regional values? | **No.** Any split would be invented. |
| Can the 13-region indices be reused as city values? | **No.** Different geography. |

## 3. Candidate sources
| Source | What it gives | Status |
|---|---|---|
| Google Trends web UI, "Interest by region" with city resolution | Google's help describes the map list as "regions or cities"; values are relative to total searches in that place and shown 0–100. | Mechanism VERIFIED in documentation. **Whether Saudi cities (Riyadh/Jeddah/Dammam) appear for these Arabic terms: NOT VERIFIED** — needs a trial export. Secondary sources report city rows are often missing for niche terms. |
| Google Trends official API (alpha) | Region / sub-region (ISO 3166-2) only; 1,800-day rolling window; access limited. | VERIFIED in documentation: **no city level**. Not a route to cities. |
| Low-volume handling | Trends shows 0 / suppresses low-volume places. For a niche term, small cities may be blank or 0 without being true zeros. | VERIFIED in documentation; the project already treats blanks as "no data", never zero. |
| OpenStreetMap `shop=florist` | Real supply-side points of interest (shops), ODbL. | Tag exists (VERIFIED). **Completeness in Saudi cities NOT VERIFIED**; supply, not search interest; a different question. |
| GASTAT 2022 census | Population ranking: Riyadh, Jeddah, Makkah, Madinah, Dammam. | VERIFIED as a ranking; exact city counts for Jeddah/Dammam not retrieved. Usable only as a population denominator context, not as demand. |
| Ministry of Commerce | Aggregate and regional quarterly bulletins. | No open florist-by-city dataset found; one report says registrations no longer specify city. NOT AVAILABLE. |

## 4. The comparability rule (the key risk)
Every Google Trends export is normalised on its own: 100 = the highest point **inside that export**. Therefore:
- A city value from one export is **not comparable** with a value from another export, even for the same term.
- Riyadh, Jeddah and Dammam are comparable **only if they come from the same export** (one query returning a city-level list, or a single multi-location comparison in the Trends UI).
- A multi-location comparison in the UI is limited to a few locations and returns **time series on one shared scale**, which is the only design that would let three cities be compared fairly. This is what a pilot should test.
- Independently downloaded city exports must never be merged. The existing `scale_id` and `ScaleMixError` mechanism would be reused unchanged.
- Small cities will show far lower search volume, so the shared-scale index may be dominated by the largest city and compress the others to near-zero or censored values.

## 5. Recommended pilot (needs your approval; not started)
1. You (or I with your approval) export, from the Trends web UI, one Saudi-wide "interest by region" view for «محل ورد» with city resolution, if offered; and one comparison of Riyadh, Jeddah and Dammam for the same term and the same window (2021-11-10 → 2026-11-10), weekly if allowed.
2. Place the files in `incoming_data/` as new files; raw files already in the project stay untouched (hash-verified).
3. Ingest through the existing manifest (new `scale_id` each), validate, and report: which cities appear, how many values are censored/blank, whether the three cities share one scale.
4. **Go / no-go rule:** build a city chart only if the three cities come from one shared-scale export with exact (uncensored) values for most weeks. Otherwise stay at the 13-region view and state why.

## 6. Verdict
- **City-level comparison: CONDITIONAL — feasibility unproven.** The only credible route is a Trends UI export; the API cannot do it.
- **Not implemented, by design.** The dashboard says so on the homepage and in Data engineering.
- Supply-side (OSM florists) and population context are possible later as separate, clearly labelled panels, but they answer different questions and must not be blended with search interest.

## 7. What would need your approval
Data collection (the pilot exports), any scraping or automation against Google Trends (not recommended; terms-of-use risk), and any OSM download.
