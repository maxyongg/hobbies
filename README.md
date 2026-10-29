# hobbies

**cinema** — what's showing at Singapore cinemas, and a push when Filmhouse, Shaw or the Asian Film Archive list a new film.

## What it does

Every 6 hours a GitHub Actions job:

1. Checks the listings of **Filmhouse**, **Shaw Theatres**, the **Asian Film Archive**, **Golden Village**, **Carnival Cinemas** and the **Singapore Film Society** (SFS Somerset).
2. Compares them with every film it has seen before (`data/items.json`).
3. For each new film at Filmhouse, Shaw or AFA: sends a push via [ntfy](https://ntfy.sh) and shows it in the iOS widget ([Scriptable](https://scriptable.app)).
4. Publishes the web app: **Now showing** and **Coming soon** across all six (one card per film, with a link to each cinema showing it), plus **New** listings.

The first successful check of each cinema records what's already showing without alerting. If a cinema's scraper breaks (errors or finds nothing twice in a row), you get one warning push.

Live at **https://maxyongg.github.io/hobbies/**. Run it on demand from Actions → update → Run workflow.

## Setup (done 2026-10-29)

1. **Workflows** in `.github/workflows/`: `update.yml` (every 6 h) and `ci.yml` (tests; live dry run on non-`main` pushes).
2. **Pages:** Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. **Alerts:** repo secret `NTFY_TOPIC` = the topic subscribed to in the ntfy app (Settings → Secrets and variables → Actions). Optional: `NTFY_TOKEN` secret and `NTFY_SERVER` variable for a self-hosted or protected server.
4. **Widget:** follow the comment at the top of [`site/widget.js`](site/widget.js) (published at https://maxyongg.github.io/hobbies/widget.js).

## Run locally

```sh
pip install -r requirements.txt pytest
python -m playwright install chromium   # only needed for Shaw
python -m whatson run --dry-run         # fetch and print; writes nothing, alerts nobody
python -m whatson run --source afa      # real run for one source (NTFY_TOPIC=... to push)
python -m pytest
python scripts/probe.py shaw            # what a site exposes, when a scraper breaks
```

## Adding a source

Write `whatson/sources/<name>.py` with a `Source` subclass (`key`, `name`, `url`, `fetch(http) -> list[Item]`) and add it to `SOURCES` in `whatson/sources/__init__.py`. Use `Item.type` for non-film things (e.g. `"exhibition"`, `"game"`).

## Roadmap

- **v1** — new-film alerts for Filmhouse, Shaw, AFA.
- **Later** — gallery openings and things to do in Singapore.
- **Later** — highly rated new video games (currently a separate Claude routine).

Handover notes for Claude sessions: [`CLAUDE.md`](CLAUDE.md). How each site lists films: [`docs/sources.md`](docs/sources.md).
