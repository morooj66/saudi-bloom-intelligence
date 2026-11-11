# Google Trends — Data-Use and Hosting Assessment

Prepared 2026-11-11. **This is a reading of public documents, not legal advice.** Uncertainty is treated as *not permitted*.

## Official sources consulted
1. **Export, embed, and cite Trends data** — https://support.google.com/trends/answer/4365538 (fetched 2026-11-11)
   - "You can use any information from Google Trends, subject to the Google Terms of Service."
   - "If you reuse Trends data, attribute the information to Google with a citation." Suggested citation for screenshots: "Data source: Google Trends (https://www.google.com/trends)."
   - "To analyze Trends data further, you can export charts as CSV files." Charts can be embedded; links can be shared.
   - The page says nothing about commercial use, or about redistributing downloaded CSV files.
2. **Google Terms of Service** — https://policies.google.com/terms (fetched 2026-11-11)
   - "You may not copy, modify, distribute, sell, or lease any part of our services or software."
   - Prohibits "using automated means to access content from any of our services in violation of the machine-readable instructions on our web pages."
   - Third-party content may not be used "without that person or organization's permission, or as otherwise allowed by law."
   - The terms do not mention Trends data or CSV exports specifically.
3. A Trends API request form that asks whether use is commercial exists (support.google.com/trends/contact/trends_api); it was seen only in search results, not read. Secondary blogs claim commercial reuse needs permission; they are **not** authoritative and were not relied on.

## Assessment by scenario
| Scenario | Assessment | Basis |
|---|---|---|
| Publish **code without data** (this repository) | **Clear to proceed.** Contains no Google content. | No Trends file is included. |
| Publish **screenshots** with the citation | **Reasonably supported**, with attribution. | Source 1 explicitly describes the citation for screenshots. Still subject to the ToS. |
| Display **derived values and charts** in a public dashboard (indices, ranks, shares, seasonal figures) | **Probably consistent with Source 1 ("use any information… with attribution") but not explicitly confirmed** for a hosted application that serves the values interactively. Treat as **unresolved**. | Source 1 does not mention dashboards, applications or commercial use. |
| Publish **processed datasets** (Parquet/CSV with the Trends values) | **Unresolved. Do not publish.** | Redistribution of the data in bulk is not addressed. |
| Publish **raw CSV exports** | **Unresolved. Do not publish.** | Source 1 does not address redistributing the files; ToS bans distributing Google's services content without permission. |

## Blocker
Public display of the derived values from a hosted dashboard is **not explicitly authorised** by the documents found. Hosting the data on a public server requires either written clarification from Google or acceptance of the risk by the owner. No data has been uploaded anywhere.

## Compliant alternatives (safest first)
1. **Code-only public repository + case study + screenshots with citation.** No hosted data; the dashboard shows a clear "bring your own exports" message (already implemented). The portfolio links to the repo and the case study.
2. **Recorded demo** (short screen recording / screenshots) of the local dashboard with the Google citation. Visitors see the product without a data-serving endpoint.
3. **Private or access-controlled deployment** (Streamlit Community Cloud allows private apps with viewer invitations — verify in current docs) for named reviewers such as recruiters, with the citation shown.
4. **Ask Google** (Trends help forum / Trends API form for the stated purpose: non-commercial portfolio display) and wait for a written answer before hosting a public data-serving dashboard.
5. If publishing the dashboard publicly is chosen despite the uncertainty: show only the aggregate values the dashboard already shows, never provide a download of the Trends tables, keep the footer "Data source: Google Trends", and accept that this is the owner's decision.

## Attribution already in the application
The dashboard footer credits Google Trends and states "not affiliated with Google". Add the exact suggested wording ("Data source: Google Trends (https://www.google.com/trends)") to any public page that shows values (README and case study already carry the attribution; the text change in the app is deliberately *not* made because the visual identity is frozen — the existing footer wording is acceptable but not the suggested string).
