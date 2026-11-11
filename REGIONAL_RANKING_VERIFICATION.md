# REGIONAL_RANKING_VERIFICATION.md

Verification date: 2026-11-10. Question: *is Jazan really the region with the highest relative search interest for «محل ورد» (flower shop)?*

## Result
**Confirmed.** Recomputed independently from the original Google Trends CSV, Jazan has the highest value (index 100) for «محل ورد», ahead of Northern Borders (96) and Najran (92). Nothing was altered or suppressed.

**Label used in the dashboard (exact):** “Highest relative search interest for محل ورد”.
This is *normalised search interest*. It is not search volume, sales, purchases or market size, and it says nothing about *why* Jazan ranks first.

## How it was verified
| Step requested | What was done | Outcome |
|---|---|---|
| 1. Reinspect the original regional CSV | Read `incoming_data/geoMap (4).csv` directly (byte-identical to `data/raw/` and to the original download; SHA-256 in `data/manifest.json`) | 13 data rows, header row + category row «جميع الفئات» |
| 2. Verify the selected search term | Parsed the column header | Exactly one term: **«محل ورد»** |
| 3. Verify the comparison group | Header has a single term, so this is a **single-term regional export** (`S_single:محل ورد`); it is *not* part of group A (5-term) or group B (4-term) | Not combined with any other export |
| 4. All 13 regions included | Compared the region column with an independent map of the 13 names | All 13 present, no extras, no duplicates |
| 5. Compatible normalisation | All 13 values come from the same export and the same query window (10/11/2021 – 10/11/2026, day/month/year, stated in the file header) | Compatible; nothing mixed |
| 6. Independent recalculation | `review_assets/verification/verify_regional_ranking_independent.py`: **standard library only**, no project code, own region-name mapping. Re-run as a test on every `pytest` | Ranking identical to the pipeline's output for all 13 regions and all 5 terms |
| 7. Missing and censored values | Counted blanks and «أقل من 1» cells | **None** in this file (13 exact values). Elsewhere: «شراء ورد» has 5 blank regions (Hail, Northern Borders, Najran, Al Bahah, Al Jawf) |
| 8. Exact interpretation of the index | See below | — |

### The ranking (independent recomputation)
| Rank | Region | Index |
|---|---|---|
| 1 | Jazan | 100 |
| 2 | Northern Borders | 96 |
| 3 | Najran | 92 |
| 4 | Asir | 81 |
| 5 | Al Jawf | 79 |
| 6 | Al Bahah | 78 |
| 7 | Madinah | 66 |
| 8 | Tabuk | 62 |
| 8 | Eastern Province | 62 |
| 10 | Hail | 59 |
| 11 | Qassim | 56 |
| 12 | Makkah | 54 |
| 13 | Riyadh | 35 |

Ties are shown as ties (Tabuk and Eastern Province, 62).

## What the regional index means
From Google's own description of Trends (support.google.com/trends/answer/4365533, read 2026-11-10): each region's searches for the term are divided by *that region's total searches*, and the results are then scaled to 0–100 against the highest value. Therefore:
- **100 does not mean “most searches”.** It means “the largest *share* of the region's own searches”. Regions with the same interest can have very different total volumes.
- Jazan = 100 *by definition* of the scale (the peak region is always 100).
- A 96 for Northern Borders means its share is 96% of Jazan's share, not 96 searches or 96% of anything absolute.
- Values are integers (rounded) and based on a **sample** of searches.
- Each export has its own scale; values from different terms or exports are never comparable as quantities.

## Other exports tell a different story (and that is expected)
Independent recomputation of the top region in every regional export:

| Export | Measure | Top region |
|---|---|---|
| geoMap (4) «محل ورد» | index, peak = 100 | **Jazan** (100); then Northern Borders 96 |
| geoMap (1) «ورد» | index | Jazan (100); then Al Bahah 97 |
| geoMap (2) «توصيل ورد» | index | Asir (100); then Tabuk 97 |
| geoMap (3) «بوكيه ورد» | index | Najran **and** Asir (both 100) |
| geoMap (5) «شراء ورد» | index, 5 regions blank | Jazan (100); then Asir 87 |
| geoMap.csv (group A) «محل ورد» | **share of the five terms' searches** | **Northern Borders (13%)**; Najran 11%; Jazan 11% |

The group-A export measures something different (what share of a region's flower-related searches, among five terms, is for «محل ورد»; the general term «ورد» takes ~86–90% everywhere). It ranks Northern Borders first, while the single-term index ranks Jazan first. Both are correct. They answer different questions and are never merged; the dashboard explains this in “Ranking check and interpretation”, and a test pins both facts.

## What can and cannot be said
**Supported:** among the 13 regions, Jazan has the highest relative search interest for «محل ورد» in this export, by 4 index points over Northern Borders; the top three (100 / 96 / 92) are close.
**Not supported / not claimed:**
- That Jazan has the highest flower sales, purchases, demand or search volume.
- Any cause for the ranking (no evidence was examined; none is speculated).
- That the order among the top regions is **stable**: no repeated independent exports were collected, so Google Trends sampling noise has not been measured. A 4-point gap may or may not survive a re-export.
- Anything about trends over time in a region: the regional exports hold one aggregate value for the whole period.

## Reproduce
```bash
cd saudi-bloom-intelligence
python3 -I review_assets/verification/verify_regional_ranking_independent.py /tmp/ranking.json   # stdlib only
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_regional_ranking.py                      # 9 tests
```
Saved result of the run: `review_assets/verification/ranking_independent_results.json`.
