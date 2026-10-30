# CLAUDE.md — handover

Read this first in every new session. Keep it short and current: update **Status** and **Next steps** at the end of each session instead of appending a log.

## Goal

Alert Max every time a new film is listed at Filmhouse, Shaw Theatres, or the Asian Film Archive (Singapore). The web app (GitHub Pages) shows **everything showing in Singapore cinemas** — now showing, coming soon, and new listings — and an iOS widget shows the new films.

Design for more sources later (gallery openings / things to do from social media; high-scoring new video games), so each source is a pluggable module, and "film" is one item `type` among several.

App name: **cinema** (renamed from whats-on-sg on 2026-10-29). The Python package is still `whatson` because the workflows run `python -m whatson`.

## Owner preferences

- Max prefers fresh sessions that read this file over long threads. Keep this file the single source of handover truth.
- If something is wrong, fix it directly — no lengthy defence.

## Decisions (agreed 2026-10-29)

1. **Hosting/scheduler:** GitHub Actions cron (every 6 h) runs the scrapers, commits `data/items.json`, deploys `site/` to GitHub Pages.
2. **Alerts:** ntfy.sh push (topic in repo secret `NTFY_TOPIC`), plus a **Scriptable** iOS widget reading the Pages JSON.
3. **Widget:** Scriptable script (`site/widget.js`, served at `/widget.js`), no native app/PWA.
4. **Language:** Python (requests + BeautifulSoup; Playwright for Shaw).
5. **Shaw scope:** alert on every new title.
6. **Web app (2026-10-29):** tabs Now showing / Coming soon / New. One card per film, merged across cinemas by normalised title (in `site/app.js`), with a link per cinema for times and booking (no showtimes scraped).
7. **Cinemas:** alerts for Filmhouse, Shaw, AFA. Golden Village, Carnival Cinemas and Singapore Film Society are web-app only (`alerts = False`). Closed or skipped venues are listed in `docs/sources.md`.

## Status (2026-10-30)

- **Live.** v1 merged to `main` (PR #1). `update.yml` runs every 6 h (also Actions → update → Run workflow), commits `data/items.json`, deploys https://maxyongg.github.io/hobbies/. `NTFY_TOPIC` secret is set.
- First run (2026-10-29 13:51 UTC) seeded 139 items silently: Filmhouse 34, Shaw 64, AFA 41 (all with posters). Alerts start with the next new listing.
- Six scrapers verified live through CI (2026-10-29): Filmhouse 34, Shaw 64, GV 79, Carnival 7, SFS 11, AFA (upcoming screenings only, latest 100 events). Real data paths in `docs/sources.md`. AFA once returned a non-JSON reply (likely bot protection); `get_json` now logs what came back.
- Now-showing page live (PRs #4, #5). GV/Carnival/SFS seeded silently in the 2026-10-29 14:30 UTC run (79/7/11); from now on their new films are stored as `alert: "quiet"` (New tab only, never pushed, not in the widget). That run: 124 listings now showing, 80 coming soon, all with posters; ~90 now-showing cards after merging the same film across cinemas.
- **Ratings (2026-10-30):** IMDb + Letterboxd ratings on web-app cards (all tabs, plus a "Top rated" sort) and in the widget (medium/large rows: `IMDb 7.8 · LB 3.9`); not in ntfy pushes (Max: not needed). `whatson/ratings.py` runs after the scrapers: listed films are matched once to TMDb by cleaned title (chains GV/Shaw/Carnival prefer recent releases; others the most popular exact title; AFA's bracketed year filters) → IMDb ID; IMDb ratings from IMDb's daily `title.ratings.tsv.gz` (hidden under 100 votes); Letterboxd from `letterboxd.com/tmdb/<id>/` (scraped, best effort; on 403/429 it stops and keeps the last ratings). Ratings refresh once per SGT day, so `data/ratings.json` gets one bot commit a day. Unmatched titles retry after 7 days. Repo secret `TMDB_API_KEY` (v3 API key, verified 2026-10-30) is passed to `update.yml` "Check sources" and the `ci.yml` live dry run.
- Pages serves the app since Max set the source to GitHub Actions (2026-10-29). Not yet confirmed: Max receiving a real alert; the Scriptable widget on his phone (Claude sessions can't reach github.io either).

## Layout

```
whatson/            Python package: python -m whatson run [--dry-run] [--source KEY]
  runner.py         fetch → diff → alert → save; seeding; broken-source alerts
  store.py          data/items.json (committed; also the web app's data)
  notify.py         ntfy (JSON publish); log-only when NTFY_TOPIC unset
  sources/          one module per source (filmhouse, shaw, afa, gv, carnival, sfs) + wordpress.py / html.py
                    helpers; registry and alerting/quiet split in __init__.py
  ratings.py        TMDb match → IMDb + Letterboxd ratings → data/ratings.json (never fails the run)
site/               static web app (reads data/items.json, status.json, ratings.json) + widget.js (Scriptable)
data/rating-overrides.json  hand fixes: "<title as on the site>": IMDb/TMDb link, or null for no rating
widget/whats-on-sg.js  symlink to site/widget.js, only because update.yml still copies that path
.github/workflows/  update.yml: 6-hourly run + commit data + Pages deploy
                    ci.yml: tests; on non-main pushes also a live dry run + probe
scripts/probe.py    prints what each site exposes — use when a scraper breaks
```

Behaviour: "new" = `(source, id)` never seen. First successful fetch of a source seeds silently (`alert: "seed"`); later new items from `alerts = False` sources get `alert: "quiet"`. Each item has `showing` ("now"/"soon", per source rules in `docs/sources.md`). Items that vanish stay with `listed: false`. Failed sends stay `pending` and retry next run. A source failing/empty on 2 runs in a row sends one warning push. >5 new from one source → one summary push. Run timestamps live in `data/status.json` (published, not committed) so `items.json` only changes when listings do.

## Next steps

1. Confirm with Max: first real ntfy alert arrived and looked right; widget installed (re-paste `widget.js` for ratings); site renders with ratings.
1. Ratings: ask Max which films show a wrong rating and add them to `data/rating-overrides.json`; if Letterboxd blocks GitHub runners (log: "Letterboxd answered HTTP 403"), show TMDb's own rating instead.
2. Ask Max how the Now showing page looks once the first post-merge run has filled GV/Carnival/SFS; tune title merging in `site/app.js` (`filmKey`) if the same film shows as two cards.
3. Optional polish: Shaw lists language/format variants as separate films (`V [CANTO]`, `V [M]`) — group them if alerts are noisy; AFA includes talks — filter by `mep_cat` if unwanted. Objectifs could be added (see `docs/sources.md`).
4. Later: more sources (galleries, games) as new modules in `whatson/sources/`.

To check a scraper change against the real sites: push to a non-`main` branch, then read the `live` job log with the GitHub MCP tools (`actions_list` → `list_workflow_jobs` → `get_job_logs`; the log is large, so save and grep it).

## Gotchas

- **Cinema sites are blocked from Claude cloud sessions** (shell and WebFetch: `connect_rejected`). Allowing them is the cloud environment's *Network access* setting (environment menu in the session title bar → Edit → Network access → Limited/Custom → Allowed domains: `filmhouse.sg`, `asianfilmarchive.org`, `shaw.sg`, `www.shaw.sg`, keep package managers ticked; or Full). Max's account has **two environments both named "Default"**; as of 2026-10-29 13:05 SGT both still blocked the sites and both still read "Default - trusted network access". A change made mid-session never reached that session (even after it resumed in a new container), so start a brand-new session after changing it. Test with `curl -sS -o /dev/null -w '%{http_code}' https://filmhouse.sg/`. Otherwise verify through the `live` CI job.
- **Claude's GitHub access can't create/update `.github/workflows/*`** (no `workflow` scope, via git push or MCP). Give Max the exact edit to make on github.com, or stage a file outside `.github/` for him to move.
- `main` gets a bot commit ("data: update listings") whenever listings change; pull before branching.
- **Pages source must be "GitHub Actions"** (Settings → Pages). On "Deploy from a branch" GitHub republishes the repo (README) on every push and overwrites the app. Max switched it on 2026-10-29.
- `site/index.html` loads `style.css?v=<hash>` / `app.js?v=<hash>` (first 10 hex of sha256) so browsers can't mix a new page with a cached old script (that left the page stuck on "Loading…" in Safari). `tests/test_site.py` fails with the exact string to use when either file changes.
- **Posters are hotlinked** from each cinema's CDN. Shaw's gumlet proxy answers 403 to other sites' Referer, so Shaw stores the Azure CDN URL behind it; Shaw's page swaps failed images for `noimage.png`, so its scraper answers image requests with a 1x1 PNG rather than blocking them. Carnival 404s posters for some coming-soon films. The web app tries each cinema's poster for a film before showing 🎬. `scripts/probe.py posters` re-checks hosts.
- Be polite: low polling frequency, a descriptive User-Agent, ≥1 s between requests per host. Filmhouse updates general-release showtimes weekly (Tuesdays).
- **TMDb v3 keys travel in the URL** (`api_key=`). `Tmdb.get` keeps it out of its own errors, but urllib3 retry warnings can include it; GitHub masks the secret in Actions logs. Never print TMDb request URLs elsewhere.
- Sites change markup; keep each scraper small. The zero-items/failure check alerts after 2 bad runs.
