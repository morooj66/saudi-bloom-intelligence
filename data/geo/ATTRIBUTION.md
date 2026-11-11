# Attribution and licence — Saudi administrative boundaries

**Dataset:** geoBoundaries gbOpen, Saudi Arabia (SAU) ADM1 — 13 administrative regions, boundary ID `SAU-ADM1-25081817`.
**Provider:** geoBoundaries, https://www.geoboundaries.org (Runfola, D. et al. (2020), *geoBoundaries: A global database of political administrative boundaries*, PLOS ONE 15(4): e0231866, doi:10.1371/journal.pone.0231866).
**Upstream data:** OpenStreetMap, Wambacher (https://wambachers-osm.website/boundaries/) — **© OpenStreetMap contributors**.
**Licence:** Open Data Commons Open Database License 1.0 — https://opendatacommons.org/licenses/odbl/1-0/ (see also https://www.openstreetmap.org/copyright).

## What this means for this project
- Attribution "© OpenStreetMap contributors; boundaries from geoBoundaries (ODbL 1.0)" is displayed under every map in the dashboard and on the Data tab.
- `saudi_adm1_geoboundaries_simplified.geojson` is redistributed **unmodified** (geoBoundaries' own simplified release) and remains under ODbL 1.0.
- The dashboard joins Google Trends values to the geometry **at render time only**; no combined database is saved or redistributed. Anyone who publishes a derived *database* from this file must offer it under ODbL (share-alike).
- Rendered maps are "produced works": attribution is required, share-alike is not.
- This is not legal advice; see the licence text.

## Limitations
Boundaries are an OpenStreetMap-based depiction (year represented 2017, source updated 2023). Computed total area is ~1.93M km2, about 10% below commonly cited national figures; the file is suitable for thematic visualisation, not for legal, cadastral or border-delimitation use. ISO 3166-2:SA codes are supplied by the dataset (`shapeISO`).

Area question (computed total ~11% below commonly cited national figures): investigated in `AREA_DISCREPANCY.md`; not a geometry or computation error; no coordinates were changed.
