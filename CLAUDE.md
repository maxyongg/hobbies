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

- **Live.** v1 merged to `main` (PR #1). `update.yml` runs every 6 h (also Actions → update → Run workflow), commits `data/items.json`, deploys https://maxyongg.github.io/hobbies/. `NTFY_TOPIC` secret is set.
- First run (2026-10-29 13:51 UTC) seeded 139 items silently: Filmhouse 34, Shaw 64, AFA 41 (all with posters). Alerts start with the next new listing.
- All three scrapers verified live; real data paths in `docs/sources.md`. AFA once returned a non-JSON reply (likely bot protection); `get_json` now logs what came back.
- Not yet confirmed: Max receiving a real alert; the Scriptable widget on his phone; the Pages site rendering (Claude sessions can't reach github.io either).

## Layout

```
whatson/            Python package: python -m whatson run [--dry-run] [--source KEY]
  runner.py         fetch → diff → alert → save; seeding; broken-source alerts
  store.py          data/items.json (committed; also the web app's data)
  notify.py         ntfy (JSON publish); log-only when NTFY_TOPIC unset
  sources/          one module per source + wordpress.py / html.py helpers; registry in __init__.py
site/               static web app (reads data/items.json + data/status.json)
widget/             Scriptable widget
.github/workflows/  update.yml: 6-hourly run + commit data + Pages deploy
                    ci.yml: tests; on non-main pushes also a live dry run + probe
scripts/probe.py    prints what each site exposes — use when a scraper breaks
```

Behaviour: "new" = `(source, id)` never seen. First successful fetch of a source seeds silently (`alert: "seed"`). Items that vanish stay with `listed: false`. Failed sends stay `pending` and retry next run. A source failing/empty on 2 runs in a row sends one warning push. >5 new from one source → one summary push. Run timestamps live in `data/status.json` (published, not committed) so `items.json` only changes when listings do.

## Next steps

1. Confirm with Max: first real ntfy alert arrived and looked right; widget installed; site renders.
2. Optional polish: Shaw lists language/format variants as separate films (`V [CANTO]`, `V [M]`) — group them if alerts are noisy; AFA includes talks — filter by `mep_cat` if unwanted.
3. Later: more sources (galleries, games) as new modules in `whatson/sources/`.

To check a scraper change against the real sites: push to a non-`main` branch, then read the `live` job log with the GitHub MCP tools (`actions_list` → `list_workflow_jobs` → `get_job_logs`; the log is large, so save and grep it).

## Gotchas

- **Cinema sites are blocked from Claude cloud sessions** (shell and WebFetch: `connect_rejected`). Allowing them is the cloud environment's *Network access* setting (environment menu in the session title bar → Edit → Network access → Limited/Custom → Allowed domains: `filmhouse.sg`, `asianfilmarchive.org`, `shaw.sg`, `www.shaw.sg`, keep package managers ticked; or Full). Max's account has **two environments both named "Default"**; as of 2026-10-29 13:05 SGT both still blocked the sites and both still read "Default - trusted network access". A change made mid-session never reached that session (even after it resumed in a new container), so start a brand-new session after changing it. Test with `curl -sS -o /dev/null -w '%{http_code}' https://filmhouse.sg/`. Otherwise verify through the `live` CI job.
- **Claude's GitHub access can't create/update `.github/workflows/*`** (no `workflow` scope, via git push or MCP). Give Max the exact edit to make on github.com, or stage a file outside `.github/` for him to move.
- `main` gets a bot commit ("data: update listings") whenever listings change; pull before branching.
- Be polite: low polling frequency, a descriptive User-Agent, ≥1 s between requests per host. Filmhouse updates general-release showtimes weekly (Tuesdays).
- Sites change markup; keep each scraper small. The zero-items/failure check alerts after 2 bad runs.
