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
6. **Web app (2026-10-29):** tabs Now showing / Coming soon / New. One card per film, merged across cinemas by normalised title (in `site/app.js`), with a link per cinema for times and booking.
7. **Cinemas:** alerts for Filmhouse, Shaw, AFA. Golden Village, Carnival Cinemas and Singapore Film Society are web-app only (`alerts = False`). Closed or skipped venues are listed in `docs/sources.md`.
8. **Screening times (2026-10-30):** only for the independent cinemas (Filmhouse, AFA, SFS), where a film may screen a handful of times and the times are already in what we scrape. Not for the chains (GV, Shaw, Carnival): they show a film many times a day, their own apps have live times and seats, and Shaw would need a browser render per film. Max agreed; revisit only if he wants "what's on tonight anywhere".
9. **Want to see + Tickets (2026-11-20):** two personal tabs, stored **in the browser only** (localStorage `cinema.want` / `cinema.tickets`, ticket images in IndexedDB `cinema`), never in the repo, because the site and `data/` are public. Max asked for "Want to see" rather than "wishlist". Booking a film moves it from Want to see to Tickets. Back up / Restore (a JSON file) moves lists between browsers. Not in the widget or pushes (Scriptable can't read Safari storage).
10. **Tickets on sale (2026-11-21, Max chose option A):** one push when a coming-soon film at an alert cinema (Filmhouse, Shaw, AFA) goes on sale; GV/Carnival/SFS only get the web-app badge. Not limited to Want to see (that list is on-device; option B, a public opt-in list, was offered and not chosen).

## Status (2026-10-30)

- **Live.** v1 merged to `main` (PR #1). `update.yml` runs every 6 h (also Actions → update → Run workflow), commits `data/items.json`, deploys https://maxyongg.github.io/hobbies/. `NTFY_TOPIC` secret is set.
- First run (2026-10-29 13:51 UTC) seeded 139 items silently: Filmhouse 34, Shaw 64, AFA 41 (all with posters). Alerts start with the next new listing.
- Six scrapers verified live through CI (2026-10-29): Filmhouse 34, Shaw 64, GV 79, Carnival 7, SFS 11, AFA (upcoming screenings only, latest 100 events). Real data paths in `docs/sources.md`. AFA once returned a non-JSON reply (likely bot protection); `get_json` now logs what came back.
- Now-showing page live (PRs #4, #5). GV/Carnival/SFS seeded silently in the 2026-10-29 14:30 UTC run (79/7/11); from now on their new films are stored as `alert: "quiet"` (New tab only, never pushed, not in the widget). That run: 124 listings now showing, 80 coming soon, all with posters; ~90 now-showing cards after merging the same film across cinemas.
- **Ratings (2026-10-30):** IMDb + Letterboxd ratings on web-app cards (all tabs, plus a "Top rated" sort) and in the widget (medium/large rows: `IMDb 7.8 · LB 3.9`); not in ntfy pushes (Max: not needed). `whatson/ratings.py` runs after the scrapers: listed films are matched once to TMDb by cleaned title (chains GV/Shaw/Carnival prefer recent releases; others the most popular exact title; AFA's bracketed year filters) → IMDb ID; IMDb ratings from IMDb's daily `title.ratings.tsv.gz` (hidden under 100 votes); Letterboxd from `letterboxd.com/tmdb/<id>/` (scraped, best effort; on 403/429 it stops and keeps the last ratings). Ratings refresh once per SGT day, so `data/ratings.json` gets one bot commit a day. Unmatched titles retry after 7 days. Repo secret `TMDB_API_KEY` (v3 API key, verified 2026-10-30) is passed to `update.yml` "Check sources" and the `ci.yml` live dry run.
- **Runtime (2026-11-23, Max asked for it on cards, widget and pushes):** from the same TMDb match (`runtime` in `data/ratings.json` films; TMDb's 0 = unknown → `null`, asked again once a day, since unreleased films get one near opening). Films matched before this were filled in on the first run after it. Cards: before the ratings (`1h 52m`). Widget rows: `2h 46m · IMDb 7.8 · LB 3.9`. Pushes: `Title · 2h 46m`. So pushes can include it, ratings now run **before** alerts (`runner.run(enrich=…)` → `ratings.update`, which sets the transient `Item.runtime`; not stored in `items.json`). A wrong runtime means a wrong match: fix it in `data/rating-overrides.json`.
- **Screening times (2026-10-30, merged in PR #10):** Filmhouse/AFA/SFS scrapers attach `Item.sessions`; the runner writes `data/showtimes.json` (gitignored, published like `status.json`). Cards show the next day's times, tap for all (each links to book; sold out dimmed); "Next screening" sort. Verified in the branch's live job (2026-10-30): Filmhouse 77 screenings / 37 films, AFA 7 / 7, SFS 17 / 11. `scripts/probe.py showtimes` prints the raw markup if one breaks.
- **Want to see + Tickets (merged to `main` 2026-11-21):** ☆ and 🎟 buttons on every poster. Want to see groups the list into Showing now / Coming soon / Not listed right now (films matched by `filmKey`, so a film lights up at any cinema). **Ticket page (rebuilt 2026-11-22):** Max found the first version (a pop-up form) clunky, and it "crashed" on his iPhone when picking a time — most likely its tap-outside-to-close caught the dismissal of iOS's time picker. Now it's a page of its own (`#sheet`; the list is hidden, Back/swipe back cancels through a history entry): the film (fixed from a poster, or search the listings / type any title), tap-a-screening chips for Filmhouse/AFA/SFS, else Day / Hour / Minutes `<select>`s (wheels on iOS; no `<input type="time">`), cinema chips + branch/hall, and folded "Seats, booking ref, e-ticket" (incl. screenshot, shrunk to 1600 px JPEG, shown full-screen at the door). Only film, day and time are required. Tickets tab: upcoming by day (until 3 h after the start), past collapsed, Add to calendar (.ics, 2 h slot, 1 h reminder). Phones show short tab labels ("Now", "Soon") so all five fit at 375 px. Checked in headless Chromium (iPhone emulation) only; the rebuilt page is **not yet confirmed on Max's iPhone**.
- **Tickets on sale (2026-11-21):** each source sets `Item.on_sale` (Shaw: Advance Sales tab or showing; GV: `advancesales`/`nowshowing` list; Carnival: now-playing list; Filmhouse/SFS: has screenings; AFA: always). The store marks `sale_alert: "pending"` when a coming-soon item seen with `on_sale: false` comes back `true`, once per item (`"sent"`; `"skip"` when already on sale at first sight, on quiet sources, or before tracking). The runner sends all of a run's in one push (`tickets` tag; one film: poster + link + "First screening …"/"Opens …"/"Now showing"). A new film already on sale says so in its "New at …" title. Web app: "Tickets on sale" badge; Coming soon splits into Tickets on sale / Not on sale yet. The first run after merging records the current state silently (so films already on sale, like "You Can See Everything", get no push).
- Pages serves the app since Max set the source to GitHub Actions (2026-10-29). Not yet confirmed: Max receiving a real alert; the Scriptable widget on his phone (Claude sessions can't reach github.io either).

## Layout

```
whatson/            Python package: python -m whatson run [--dry-run] [--source KEY]
  runner.py         fetch → diff → ratings/runtimes → alert → save; seeding; broken-source alerts
  store.py          data/items.json (committed; also the web app's data)
  notify.py         ntfy (JSON publish); log-only when NTFY_TOPIC unset
  sources/          one module per source (filmhouse, shaw, afa, gv, carnival, sfs) + wordpress.py / html.py
                    helpers; registry and alerting/quiet split in __init__.py
  ratings.py        TMDb match → runtime + IMDb + Letterboxd ratings → data/ratings.json (never fails the run)
  showtimes.py      Item.sessions → data/showtimes.json (future screenings only; not committed)
site/               static web app (reads data/items.json, status.json, ratings.json, showtimes.json) + widget.js (Scriptable)
                    app.js "Personal lists" section: Want to see / Tickets, on-device only
data/rating-overrides.json  hand fixes: "<title as on the site>": IMDb/TMDb link, or null for no rating
widget/whats-on-sg.js  symlink to site/widget.js, only because update.yml still copies that path
.github/workflows/  update.yml: 6-hourly run + commit data + Pages deploy
                    ci.yml: tests; on non-main pushes also a live dry run + probe
scripts/probe.py    prints what each site exposes — use when a scraper breaks
```

Behaviour: "new" = `(source, id)` never seen. First successful fetch of a source seeds silently (`alert: "seed"`); later new items from `alerts = False` sources get `alert: "quiet"`. Each item has `showing` ("now"/"soon", per source rules in `docs/sources.md`). Items that vanish stay with `listed: false`. A coming-soon item that goes from `on_sale: false` to `true` gets one "tickets on sale" push (`sale_alert`), alert cinemas only. Failed sends stay `pending` and retry next run. A source failing/empty on 2 runs in a row sends one warning push. >5 new from one source → one summary push. Run timestamps live in `data/status.json` and screening times in `data/showtimes.json` (both published, not committed) so `items.json` only changes when listings do. A source that fails a run has no times until its next good run.

## Next steps

1. Tell Max to re-paste `widget.js` into Scriptable to get runtimes in the widget.
1. Ask Max to add a ticket again on his iPhone with the rebuilt page (day/time wheels, swipe back to cancel, attaching a screenshot), plus "Add to calendar" (does iOS offer to add the .ics?) and Back up. Suggest he uses the site from one place (a Home Screen web app has its own storage, separate from Safari) and backs up now and then.
1. Ask Max whether the tickets-on-sale pushes are useful or too many (expected ~1–2 a day, mostly Shaw). If too many: limit to films he opts in to (option B: a public list, e.g. a prefilled GitHub issue per film), or drop Shaw re-issues/event screenings. If too slow (checks are 6-hourly): a more frequent schedule is a `update.yml` cron edit Max makes on github.com.
1. Other possible follow-ups: sync of personal lists between devices.
1. Ask Max how the screening times look on his phone (first published by the post-merge `update` run).
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
- **A merge done through Claude's GitHub access doesn't trigger `update.yml`** (its `push` trigger fires for merges Max makes on github.com, not for PRs #11–#13 merged via the API), so the site isn't redeployed. After merging, start it: `actions_run_trigger` → `run_workflow`, `update.yml`, ref `main` (same as Actions → update → Run workflow). Found 2026-11-22, when Max's iPhone still had the old ticket pop-up 1.5 h after the fix was merged.
- **Scheduled runs fire about twice a day, not four times** (seen 18–22 Nov: ~07:10 and ~19:15–20:40 UTC; the 00:17 and 12:17 slots never ran; GitHub drops or delays busy cron slots). So listings, alerts and the site are effectively ~12-hourly.
- **Pages source must be "GitHub Actions"** (Settings → Pages). On "Deploy from a branch" GitHub republishes the repo (README) on every push and overwrites the app. Max switched it on 2026-10-29.
- `site/index.html` loads `style.css?v=<hash>` / `app.js?v=<hash>` (first 10 hex of sha256) so browsers can't mix a new page with a cached old script (that left the page stuck on "Loading…" in Safari). `tests/test_site.py` fails with the exact string to use when either file changes.
- **Posters are hotlinked** from each cinema's CDN. Shaw's gumlet proxy answers 403 to other sites' Referer, so Shaw stores the Azure CDN URL behind it; Shaw's page swaps failed images for `noimage.png`, so its scraper answers image requests with a 1x1 PNG rather than blocking them. Carnival 404s posters for some coming-soon films. The web app tries each cinema's poster for a film before showing 🎬. `scripts/probe.py posters` re-checks hosts.
- Be polite: low polling frequency, a descriptive User-Agent, ≥1 s between requests per host. Filmhouse updates general-release showtimes weekly (Tuesdays).
- **TMDb v3 keys travel in the URL** (`api_key=`). `Tmdb.get` keeps it out of its own errors, but urllib3 retry warnings can include it; GitHub masks the secret in Actions logs. Never print TMDb request URLs elsewhere.
- **Personal lists live in one browser.** iOS Safari may wipe a site's storage after 7 days without a visit (a Home Screen web app is exempt), and Safari vs a Home Screen web app vs another device are separate stores. The app calls `navigator.storage.persist()` and offers Back up / Restore. Never move these lists into `data/` (public).
- **Forms on iOS:** no pop-up `<dialog>` that closes on a tap outside (dismissing a native picker can count as that tap), and no `<input type="time">`/`type="date"`; use a page in normal flow and `<select>`s. Inputs need `font-size: 16px` or iOS zooms in.
- Sites change markup; keep each scraper small. The zero-items/failure check alerts after 2 bad runs.
- **AFA (SiteGround) answers with a captcha page** (`/.well-known/sgcaptcha/`) after several live runs a few minutes apart (seen 2026-10-30 on the 4th push in 6 min). Batch commits before pushing a branch; docs-only commits can carry `[skip ci]`.
