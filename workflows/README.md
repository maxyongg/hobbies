# Staged GitHub Actions workflows

These belong in `.github/workflows/`, but Claude's GitHub access can't create workflow
files (it lacks the `workflow` scope), so they're staged here. Move them once:

- **On github.com:** open each file → pencil (Edit) → change the file name box to
  `.github/workflows/update.yml` (or `ci.yml`) → Commit. Then delete this README.
- **Locally:** `git mv workflows/*.yml .github/workflows/ && git rm workflows/README.md && git push`

| File | What it does |
|---|---|
| `update.yml` | Every 6 h: run scrapers, push alerts, commit `data/items.json`, deploy the web app to GitHub Pages. |
| `ci.yml` | Unit tests on every push/PR; on non-`main` pushes also a read-only live dry run + `scripts/probe.py`. |
