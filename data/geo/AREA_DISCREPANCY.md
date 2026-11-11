# AREA_DISCREPANCY.md — why the boundary file's total area is lower than commonly cited national figures

Investigation date: 2026-11-10. **No coordinates were modified.** Scripts and raw results: `review_assets/verification/area_investigation.py`, `area_results.json`, `area_inputs_sha256.txt`.

## The discrepancy
The 13 region polygons (geoBoundaries gbOpen SAU ADM1, OpenStreetMap-derived) sum to about **1.93 million km²**. The figure most often quoted for Saudi Arabia is **2,149,690 km²** (UN / CIA Factbook style), i.e. about **11% more**.

## Hypotheses tested
| Hypothesis | Test | Result |
|---|---|---|
| Area computed wrongly (method / projection) | Two independent methods on the same file: spherical-polygon formula and Lambert azimuthal equal-area projection with a planar shoelace | 1,929,379 vs 1,929,365 km² (0.0007% apart). **Not the cause.** |
| Geometry simplification | Full-resolution vs the simplified file stored in the repo | 1,929,379 vs 1,929,360 km² (0.001%); per-region differences ≤ 0.02%. **Not the cause.** |
| Regions overlap or leave gaps among themselves | Provider's own country outline (ADM0) vs the sum of the 13 regions | 1,929,379 vs 1,929,379 km². **Not the cause.** |
| An error specific to one data source | Compared with a *different* source, Natural Earth 50m admin-0 (public domain) | Natural Earth: 1,925,841 km² (spherical), 1,925,840 km² (LAEA). Within 0.2% of geoBoundaries. **Both independent depictions agree at ≈1.93M.** |
| Spatial location of the difference | 0.1° grid comparison, Natural Earth outline vs union of the 13 regions | 17,048 cells in both; only 48 cells (≈5,400 km²) in Natural Earth only and 73 (≈8,300 km²) in the regions only, i.e. scattered edge slivers. The two outlines agree almost everywhere. |
| The provider's own statistics | geoBoundaries metadata `meanAreaSqKM` | ADM0 1,925,091 km² (13 regions: ≈1.925M). Consistent with my computation (+0.2%). |

## What the published figures look like
Totals found in reference sources (read from search results, *not* from primary documents) vary widely: ≈1,960,582 (Geonames) and ≈1,961,000 (Wolfram) at the low end; 2,149,690 (Britannica / Infoplease / CIA Factbook and a UN-derived estimate); 2,217,949 (a Saudi government estimate quoted in Country Studies / Wikipedia); up to ≈2,240,000–2,253,290 (DBpedia). Saudi GASTAT is reported to give "around 2,000,000". Several of these sources state that the exact size is **undefined because the southern and southeastern borders (with Yemen, Oman and the UAE, through the Rub' al Khali) are not fully demarcated**.

## Conclusion
- The discrepancy is **not** caused by geometry, projection, computation or simplification (all ruled out above).
- The most plausible explanation is **boundary definition / territorial coverage**: the national totals differ by up to ~15% between reference sources, the published sources themselves attribute this to unmarked borders in the south and southeast, and two independent boundary products drawn from different sources both land at ≈1.93M, near the low end of the published range (Geonames/Wolfram ≈1.96M are 1.6% above them).
- **Not proven:** which specific area accounts for the missing ≈0.2M km². No reference polygon for the 2,149,690 km² claim was available, so the gap could not be located on a map. This remains **an unresolved limitation**, honestly reported rather than adjusted.
- **Impact on this project: none on any metric.** Areas are not used anywhere (the choropleth colours regional *search-interest* indices; no value is normalised by area). The map is a thematic display of the 13 regions' relative shapes. The file must not be used for legal, cadastral, border-delimitation or area-statistics purposes.

## If this needs to be revisited
Obtain an authoritative boundary polygon with a documented licence (e.g. from the national mapping authority), compare it with this file using the same grid method, and update `SOURCE.json` and the hash. Do not hand-edit coordinates.
