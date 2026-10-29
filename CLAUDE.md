# CLAUDE.md — handover

Read this first in every new session. Keep it short and current: update **Status** and **Next steps** at the end of each session instead of appending a log.

## Goal

Alert Max every time a new film is listed at Filmhouse, Shaw Theatres, or the Asian Film Archive (Singapore). Show new films in a web app and an iOS widget.

Design for more sources later (gallery openings / things to do from social media; high-scoring new video games), so each source is a pluggable module, and "film" is one item `type` among several.

## Owner preferences

- Max prefers fresh sessions that read this file over long threads. Keep this file the single source of handover truth.
- If something is wrong, fix it directly — no lengthy defence.

## Decisions (agreed 2026-10-29)

1. **Hosting/scheduler:** GitHub Actions cron (every 6 h) runs the scrapers, commits `data/items.json`, deploys `site/` to GitHub Pages.
2. **Alerts:** ntfy.sh push (topic in repo secret `NTFY_TOPIC`), plus a **Scriptable** iOS widget reading the Pages JSON.
3. **Widget:** Scriptable script (`widget/whats-on-sg.js`), no native app/PWA.
4. **Language:** Python (requests + BeautifulSoup; Playwright for Shaw).
5. **Shaw scope:** alert on every new title.

## Status (2026-10-29)

- v1 code written on branch `claude/zen-hypatia-chjicl`: core loop, store, ntfy, three sources, web page, widget, tests (pass, on hand-written fixtures).
- **Scrapers are unverified against the live sites** — the cloud session couldn't reach them. Data paths are best guesses with fallbacks (see `docs/sources.md`). Shaw is the least certain.
- Workflows are staged in `workflows/`, not yet in `.github/workflows/` (see Gotchas).

## Layout

```
whatson/            Python package: python -m whatson run [--dry-run] [--source KEY]
  runner.py         fetch → diff → alert → save; seeding; broken-source alerts
  store.py          data/items.json (committed; also the web app's data)
  notify.py         ntfy (JSON publish); log-only when NTFY_TOPIC unset
  sources/          one module per source + wordpress.py / html.py helpers; registry in __init__.py
site/               static web app (reads data/items.json + data/status.json)
widget/             Scriptable widget
workflows/          staged GitHub Actions (update.yml, ci.yml)
scripts/probe.py    prints what each site exposes — use when a scraper breaks
```

Behaviour: "new" = `(source, id)` never seen. First successful fetch of a source seeds silently (`alert: "seed"`). Items that vanish stay with `listed: false`. Failed sends stay `pending` and retry next run. A source failing/empty on 2 runs in a row sends one warning push. >5 new from one source → one summary push. Run timestamps live in `data/status.json` (published, not committed) so `items.json` only changes when listings do.

## Next steps

1. **Max (one-off setup):** move `workflows/*.yml` into `.github/workflows/`; Settings → Pages → Source: GitHub Actions; add secret `NTFY_TOPIC` (hard-to-guess name, subscribe to it in the ntfy app); install the Scriptable widget (instructions at the top of `widget/whats-on-sg.js`).
2. **Verify scrapers live.** Once `ci.yml` is in place, any push to a non-`main` branch runs a read-only dry run + `scripts/probe.py` in the `live` job; read it with the GitHub MCP tools (`actions_list` → `get_job_logs`). Fix data paths per source; for Shaw, find the JSON endpoint in the probe output and replace the Playwright path with a direct call.
3. Merge to `main`; trigger `update` manually once (seeds, no alerts), check the Pages site.
4. Later: more sources (galleries, games) as new modules in `whatson/sources/`.

## Gotchas

- **Cinema sites are blocked from Claude cloud sessions** (shell and WebFetch: `connect_rejected`). Allowing them is the cloud environment's *Network access* setting (environment menu in the session title bar → Edit → Network access → Limited/Custom → Allowed domains: `filmhouse.sg`, `asianfilmarchive.org`, `shaw.sg`, `www.shaw.sg`, keep package managers ticked; or Full). Max's account has **two environments both named "Default"**; as of 2026-10-29 13:05 SGT both still blocked the sites and both still read "Default - trusted network access". A change made mid-session never reached that session (even after it resumed in a new container), so start a brand-new session after changing it. Test with `curl -sS -o /dev/null -w '%{http_code}' https://filmhouse.sg/`. Otherwise verify through the `live` CI job.
- **Claude's GitHub access can't create/update `.github/workflows/*`** (no `workflow` scope, via git push or MCP). Edit workflows in `workflows/` and ask Max to copy them across, or have Max make the change.
- Be polite: low polling frequency, a descriptive User-Agent, ≥1 s between requests per host. Filmhouse updates general-release showtimes weekly (Tuesdays).
- Sites change markup; keep each scraper small. The zero-items/failure check alerts after 2 bad runs.
