# hobbies

**whats-on-sg** — tells me when new films are listed at the Singapore cinemas I care about.

## What it does (v1)

Every 6 hours a GitHub Actions job:

1. Checks the listings of **Filmhouse** (Golden Mile Tower), **Shaw Theatres** and the **Asian Film Archive**.
2. Compares them with every film it has seen before (`data/items.json`).
3. For each new film: sends a push via [ntfy](https://ntfy.sh), and publishes it to the web app (GitHub Pages) and the iOS widget ([Scriptable](https://scriptable.app)).

The first successful check of each cinema records what's already showing without alerting. If a cinema's scraper breaks (errors or finds nothing twice in a row), you get one warning push.

## Setup (one-off)

1. **Workflows:** move `workflows/update.yml` and `workflows/ci.yml` into `.github/workflows/` (see [`workflows/README.md`](workflows/README.md)).
2. **Pages:** Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. **Alerts:** pick a hard-to-guess topic name, subscribe to it in the ntfy app, and add it as the repo secret `NTFY_TOPIC` (Settings → Secrets and variables → Actions). Optional: `NTFY_TOKEN` secret and `NTFY_SERVER` variable for a self-hosted or protected server.
4. **Run once:** Actions → update → Run workflow. The site appears at https://maxyongg.github.io/hobbies/.
5. **Widget:** follow the comment at the top of [`widget/whats-on-sg.js`](widget/whats-on-sg.js).

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
