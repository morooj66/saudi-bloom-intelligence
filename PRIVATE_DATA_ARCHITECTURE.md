# Private-data deployment architecture (implemented and tested locally; nothing uploaded, nothing deployed)

Status: **implemented in `src/bloom/bootstrap.py` and `scripts/make_data_bundle.py`, tested against a local token-protected server only; not deployed.** The Google Trends data stay out of the public repository. Whether a public app may serve them at all is still unresolved (`DATA_USE_ASSESSMENT.md`); this document only describes how to do it without publishing the data files.

## What the app needs at run time
The fail-closed integrity gate re-checks hashes, so the server needs the whole verified tree, not just the charts:

| Needed | Size | Why |
|---|---|---|
| `data/raw/*.csv` (9 files) + `data/manifest.json` / `.csv` | ~16 KB raw | integrity step 2 hashes every raw file against the manifest |
| `data/processed/` (+ `phase_a/`) Parquet/CSV/JSON + `_provenance.json` | ~1.5 MB | the dashboard reads the Parquet files; provenance is verified |
| `data/geo/` | ~0.45 MB | already public (ODbL, in the repository) |

If any file is missing or altered the dashboard shows no analytics. This is the property to keep.

## Recommended approach: private data bundle fetched at start-up
1. **Build the bundle locally** (as today): `bloom.pipeline`, `bloom.phase_a`, `bloom.integrity` → INTEGRITY VERIFIED. Pack `data/raw`, `data/processed` and the manifests into one archive; record its SHA-256 on your machine.
2. **Store the archive privately**, outside the public repository: a *private* GitHub repository or release asset, or a private object store (an S3-compatible bucket with a read-only credential). Never in `saudi-bloom-intelligence`.
3. **Give the host a read-only credential and the expected SHA-256 as secrets** (Streamlit Community Cloud: app *Settings → Secrets*; a self-hosted container: environment variables or a secret manager). The credential is created by you in your own account; it must not be pasted into chat, code, commits or logs. `.streamlit/secrets.toml` is already git-ignored.
4. **At start-up** the bootstrap (`bloom.bootstrap.ensure_data`, called once at the top of the app) downloads the archive to a temporary directory, checks its SHA-256 against the secret, unpacks it and points the app at it through the existing `BLOOM_ROOT` setting. The existing integrity gate then verifies every raw and processed file against the manifest exactly as it does today. A wrong or tampered archive therefore fails closed.
5. **Nothing about the analysis changes:** pipeline, thresholds, forecast gate and caveats are untouched; the bootstrap only supplies files.

Why this over the alternatives:
| Option | Verdict |
|---|---|
| Data in a **private GitHub repo that also holds the app** (Streamlit Community Cloud deploys private repos) | Simple, but the docs allow **one private app**, and the app's visibility follows the repository; making an app from a private repository public was not verified. Data and code would also live in one repository, which risks a later accidental publication. |
| **Private data bundle fetched at start-up** (above) | Keeps the public repository data-free, verified by hash, works on Cloud and self-hosted. Needs the bootstrap code and a secret. **Recommended.** |
| Data in Streamlit secrets text | Size and format limits unverified; awkward for binary Parquet. Not recommended. |
| Self-hosted container (VPS, Fly.io, Render, Cloud Run) with a data volume | Full control of files, logs and headers; costs money and needs maintenance. Good if Community Cloud's limits (memory, sleep) are a problem. |
| Synthetic data | Not approved; would not be the real project. |

## What this does *not* solve
- **Data in the page.** The browser receives the plotted numbers inside every chart (verified: 13 regional values per map/bar chart, 260 weekly values per series, 520 when two terms are shown). Hiding the download buttons removes convenience, not access: a visitor can read the values from the page data. Private storage keeps the *files* private, not the *displayed values*.
- **Rights.** Hosting and serving these values publicly is not authorised or prohibited by the sources reviewed. This architecture reduces accidental redistribution of files; it does not answer the question.
- **Server copy.** The raw exports and processed tables still exist on the host's disk while the app runs. Keep the app private or restrict viewers until the rights question is answered.

## Operational checklist (for when you approve)
- Rotate or revoke the read-only credential if the app is removed.
- Keep the bundle checksum in secrets so the bundle cannot be swapped silently.
- Do not log file contents; the bootstrap should log only file names and the checksum result.
- Keep `server.enableStaticServing = false` (current default) so nothing under the app folder is served by URL.
- Add the attribution "Data source: Google Trends (https://www.google.com/trends)" wherever values appear (the app footer already credits Google Trends).

## How it works (as implemented)
- **Settings** (environment variables or Streamlit secrets, same names): `BLOOM_DATA_BUNDLE_URL` (https; plain http only for localhost), `BLOOM_DATA_BUNDLE_SHA256` (required), `BLOOM_DATA_BUNDLE_TOKEN` (optional bearer token). With none set, or when data already exist, the bootstrap does nothing, so local use is unchanged.
- **Checks, in order:** 64 MB size cap; SHA-256 of the whole archive; every member must be a regular file under `data/raw/`, `data/processed/` or `data/manifest.json|csv` (absolute paths, `..`, links, devices and anything else are rejected before extraction); extraction to a temporary folder; completeness; atomic move into place; then the existing integrity gate verifies every file against the manifest.
- **Errors** name the host and the HTTP code or error class only; the URL and token never appear in messages. After a failure there is a 60 s cool-down so a broken bundle is not re-downloaded on every click.
- **Packing:** `PYTHONPATH=src python scripts/make_data_bundle.py --out <path outside the repository>` (refuses unless integrity passes, refuses an output inside the project, prints the SHA-256, deterministic archive).
- **Tests** (`tests/test_bootstrap.py`, 17): no-op cases; fetch with token; secrets path; wrong hash; missing hash; wrong token (no leak); http only for localhost; six unsafe-archive cases; incomplete bundle; cool-down; end-to-end bundle → empty root → dashboard passes the full integrity gate; tampered bundle with a recomputed hash still fails closed; the packing script refuses an output inside the project.
- **Local live test:** a bundle of the real data was served from a local token-protected server to an empty root; the dashboard loaded it, and the real-browser checks (English and Arabic at 1440/768/390 px, language switch, map clicks) and the export-control check were run against that instance.
