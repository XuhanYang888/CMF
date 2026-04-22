# Awards Web UI for GitHub Pages

This repository contains a static GitHub Pages-ready awards search UI.

## What is included
- `docs/` — static site files ready to publish on GitHub Pages
- `scripts/` — Python utilities for scraping contest exports, building the awards database, and exporting JSON
- `contest_data/` — contest HTML and CSV files plus `awards.sqlite3`

## Deployment
Set GitHub Pages to serve from the `docs/` folder on the `main` branch.

## Notes
- The UI is fully static and uses the prebuilt files in `docs/`.
- Python scripts, contest data folders, and generated backend/runtime files are excluded from the GitHub Pages deployment.
