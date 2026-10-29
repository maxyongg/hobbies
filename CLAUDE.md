# CLAUDE.md — handover

Read this first in every new session. Keep it short and current: update **Status** and **Next steps** at the end of each session instead of appending a log.

## Goal

Alert Max every time a new film is listed at Filmhouse, Shaw Theatres, or the Asian Film Archive (Singapore). Show new films in a web app; a widget is a nice-to-have.

Design for more sources later (gallery openings / things to do from social media; high-scoring new video games), so each source should be a pluggable module, and "film" should be one item type among several.

## Owner preferences

- Max prefers fresh sessions that read this file over long threads. Keep this file the single source of handover truth.
- If something is wrong, fix it directly — no lengthy defence.

## Status (2026-10-29)

- Repo: github.com/maxyongg/hobbies (app working name: whats-on-sg). Scaffolded: README, this file, `docs/sources.md`. **No code yet.**
- Stack and hosting **not decided** — see Open decisions.

## Core loop (agreed shape)

```
schedule → fetch each source → normalise to items → diff against seen-store → new items?
  → notify (push) + publish to web app
```

Item fields (minimum): `source`, `id` (stable per source, e.g. URL slug), `title`, `url`, `first_seen`, optional `poster`, `release_date`, `tags` (e.g. season/festival name).

"New" = an `id` not seen before for that source. Showtime changes are **not** new films.

## Open decisions (ask Max before building)

1. **Hosting / scheduler.** Candidate (proposed by Claude, not agreed): GitHub Actions cron (e.g. every 6h, SGT) runs the scrapers, commits `data/*.json`, and a static page on GitHub Pages renders it. Zero servers, free. Alternatives: a small always-on host (Fly.io/Render/Cloudflare Workers + cron triggers).
2. **Alert channel.** Options: Telegram bot, ntfy.sh push (has an Android widget-ish feed and iOS app), email, web push from a PWA. Pick one for v1.
3. **Widget.** iOS/Android home-screen widget is a separate piece of work; a PWA "add to home screen" + push may be enough for v1.
4. **Language.** Python (requests + BeautifulSoup; Playwright only if needed) vs Node (fetch + cheerio; Playwright). Shaw likely needs JS rendering or its hidden API — see sources.
5. **Scope of "new"** for Shaw: everything Shaw lists will be mainstream releases. Should all of them alert, or only "Coming Soon"/"Advance Sales" additions, or filtered by genre/language?

## Next steps

1. Get Max's answers to Open decisions 1–5.
2. For each source, confirm the cheapest reliable data path (see `docs/sources.md`): try WordPress REST/RSS for Filmhouse and AFA before HTML scraping; find Shaw's JSON endpoint via browser network tab.
3. Build one source end-to-end (suggest AFA or Filmhouse — simplest), with the seen-store and one alert channel.
4. Add the other two sources, then the web page.
5. Seed the seen-store on first run **without** alerting (otherwise the first run alerts on every current film).

## Gotchas

- **Network allowlist in Claude cloud sessions:** the three cinema domains are blocked from the shell by default (`connect_rejected`). Either add `filmhouse.sg`, `shaw.sg`, `asianfilmarchive.org` under claude.ai Settings → Capabilities (allowed domains), or run scrapers locally / in GitHub Actions. `WebFetch` can still read the pages for research.
- Be polite: low polling frequency, a descriptive User-Agent, no hammering. Filmhouse updates general-release showtimes weekly (Tuesdays), so a few polls a day is plenty.
- Sites change markup; keep each scraper small and add a check that alerts if a source suddenly returns zero items.
