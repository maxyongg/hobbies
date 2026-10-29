# CLAUDE.md — handover

Read this first in every new session. Keep it short and current: update **Status** and **Next steps** at the end of each session instead of appending a log.

## Goal

Alert Max every time a new film is listed at Filmhouse, Shaw Theatres, or the Asian Film Archive (Singapore). Show new films in a web app; a widget is a nice-to-have.

Design for more sources later (gallery openings / things to do from social media; high-scoring new video games), so each source should be a pluggable module, and "film" should be one item type among several.

## Owner preferences

- Max prefers fresh sessions that read this file over long threads. Keep this file the single source of handover truth.
- If something is wrong, fix it directly — no lengthy defence.

## Status (2026-10-29)

- Repo: github.com/maxyongg/hobbies (public). App name: **hobbies** (renamed from whats-on-sg).
- Decisions made (below). **No app code yet** — the build session couldn't reach the cinema sites (see Gotchas), so the scrapers are unbuilt rather than written blind.
- Built so far: `scripts/probe.py` + `scripts/probe-urls.txt` (print live responses from each site), and `ci/workflows/probe.yml` (not yet enabled — see Gotchas).

## Core loop (agreed shape)

```
schedule → fetch each source → normalise to items → diff against seen-store → new items?
  → notify (push) + publish to web app
```

Item fields (minimum): `source`, `id` (stable per source, e.g. URL slug), `title`, `url`, `first_seen`, optional `poster`, `release_date`, `tags` (e.g. season/festival name).

"New" = an `id` not seen before for that source. Showtime changes are **not** new films.

## Decisions (agreed with Max, 2026-10-29)

1. **Hosting / scheduler:** GitHub Actions cron (~every 6h, SGT) runs the scrapers and commits `data/*.json`; a static page on GitHub Pages renders it. Repo is public, so Pages is free.
2. **Alerts:** ntfy.sh push (private topic name in a repo secret), with link + poster where available.
3. **Widget:** the web app must be widget-compatible — publish a small JSON feed (and/or Atom) of recent items that home-screen widget apps can read (e.g. Scriptable on iOS, KWGT on Android), plus a PWA manifest for add-to-home-screen.
4. **Language:** Python (requests + BeautifulSoup; Playwright only if Shaw needs it), pytest for parser tests against saved fixtures.
5. **Shaw scope:** alert on **all** new Shaw films (any id not seen before, across Now Showing / Advance Sales / Coming Soon). Filters can come later.

## Next steps

1. Confirm the cinema domains are reachable from the session shell (`curl -sS https://filmhouse.sg/robots.txt`). If still blocked, see Gotchas.
2. Run `python3 scripts/probe.py` to find each source's cheapest reliable data path (see `docs/sources.md`): WordPress REST/RSS for Filmhouse and AFA before HTML; Shaw's JSON endpoint (`deep` mode greps its JS bundles for API URLs). Save real responses as test fixtures and update `docs/sources.md`.
3. Build the core (item model, seen-store, diff, ntfy notifier, first-run seeding **without** alerting) and one source end-to-end, then the other two.
4. Static web page + widget feed + PWA manifest; scheduled scrape workflow and Pages deploy (staged under `ci/workflows/` for Max to move).
5. Zero-items guard: alert if a source suddenly returns nothing.

## Gotchas

- **Network allowlist in Claude cloud sessions:** the three cinema domains are blocked by default — shell gets `CONNECT tunnel failed, response 403`, WebFetch gets `ENOTFOUND`. Allow them in the cloud environment's settings (session title bar → environment menu → Edit → Network access → Allowed domains): `filmhouse.sg`, `shaw.sg`, `www.shaw.sg`, `asianfilmarchive.org`, `www.asianfilmarchive.org`. Changing this mid-session did **not** take effect in the session where it was changed; start a fresh session after editing it.
- **Claude sessions can't write `.github/workflows/`** (the GitHub token lacks the `workflow` scope; both `git push` and the GitHub MCP tools are refused). Stage workflow files under `ci/workflows/` and ask Max to `git mv` them into `.github/workflows/`.
- Be polite: low polling frequency, a descriptive User-Agent, no hammering. Filmhouse updates general-release showtimes weekly (Tuesdays), so a few polls a day is plenty.
- Sites change markup; keep each scraper small and add a check that alerts if a source suddenly returns zero items.
