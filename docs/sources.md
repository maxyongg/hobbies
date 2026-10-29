# Sources — how each site lists films

Surveyed 2026-10-29 via WebFetch (shell access to these domains is blocked in Claude cloud sessions). The CI `live` job (non-`main` pushes) prints what the scrapers find and runs `scripts/probe.py`; read it with the GitHub MCP tools.

## Filmhouse — https://filmhouse.sg

- Indie cinema at Golden Mile Tower, Beach Road (former Projector space), three halls.
- **Platform:** WordPress + Elementor. Site and ticketing by JACRO (taposapp.com). Gift cards via cineticketing.com.au (`FILSIN`).
- **Listing pages:**
  - All films: `/films`
  - Coming soon: `/films/coming-soon/`
  - Leaving soon: `/seasons-events/ls/`
  - Seasons/festivals: `/seasons-events/<slug>/` (e.g. `fhh`, `wuxia`, `fff26`, `mif`)
  - Events: `/events/`, community events: `/other-events/`
- Film detail URL pattern: not yet confirmed.
- **Try first:** `/wp-json/` (look for a films post type) and `/feed/`. Fall back to parsing `/films` + `/films/coming-soon/`.
- General-release showtimes update weekly on Tuesdays.
- **Implemented (verified live 2026-10-29, 34 films):** `whatson/sources/filmhouse.py`. No film post type over REST and `/feed/` is empty. Listings are rendered server-side by the JACRO plugin: each film is a `div.jacro-event` card with a poster link and an `a.liveeventtitle` title link to `http://filmhouse.sg/film/<id>/<slug>` (JACRO's numeric id = our id), plus `/filmhouse-singapore/booknow/<n>` showtime links. Reads `/films/` and `/films/coming-soon/` (tagged "Coming soon"). Posters on `cdn.taposapp.com`.

## Shaw Theatres — https://shaw.sg

- Mainstream multiplex chain, several locations.
- **Listing page:** `/movie`, with tabs "New Now Showing", "Ending Soon", "Advance Sales", "Top Movies", "Coming Soon".
- **Movie data is not in the HTML** — it's loaded by JavaScript. Find the JSON endpoint the page calls (browser devtools → Network on `/movie`) and poll that directly. Playwright is the fallback.
- Location pages: `/theatre/location/<id or slug>`.
- **Implemented (verified live 2026-10-29, 64 films):** `whatson/sources/shaw.py`. Next.js site on `shaw.sg` (www redirects). Tabs load JSON from `shaw.sg/internal/get_now_showing_movies`, `get_advance_sale_movies`, `get_top_movies`, `get_coming_soon_movies`, but these return a 404 page to plain `requests` (even with Referer), so the scraper renders `/movie` in Chromium, clicks each tab, and reads `/movie-details/<id>` cards (title in the card's `<h3>`, tag = tab name). Language/format variants are separate ids (e.g. `V [CANTO]`, `V [M]`).

## Asian Film Archive — https://asianfilmarchive.org

- Screenings mostly at Oldham Theatre.
- **Platform:** WordPress + Elementor + an events plugin (taxonomy `mep_cat`, which suggests the "Event Manager for WooCommerce" plugin — post type likely `mep_events`). Tickets sold on the event page itself (WooCommerce cart).
- **Listing pages:** `/whatson/`, `/events-calendar/`, programmes under `/event-archive/programmes/` and `/mep_cat/programme/`.
- **Event detail URL pattern:** `/event-calendar/<title-slug>-<year>/`, e.g. `/event-calendar/hush-2016/`. Repeat screenings get suffixes (`-1`, `-2`); some add a programme tag (`-reciprocal`). → Normalise the id by stripping repeat suffixes so one film = one alert.
- **Try first:** `/wp-json/wp/v2/mep_events?per_page=100&orderby=date` and `/feed/?post_type=mep_events`.
- **Implemented (verified live 2026-10-29):** `whatson/sources/afa.py` — `mep_events` over WP REST (1,770 posts in total), latest 50 with `_fields=id,slug,link,title,date,class_list,yoast_head_json` (~270 KB; with `_embed` it was ~1 MB). Poster = Yoast `og_image`; tags from `class_list` (`mep_cat-*`, `tag-*`). HTML fallback reads `/event-calendar/<slug>/` links on `/whatson/` and `/events-calendar/`. id = slug with repeat suffixes (`-1`, `-2`) stripped; 4-digit years and programme tags are kept. Includes talks and shorts programmes, not just films. "[SOLD OUT]" is stripped from titles. One run (of four, minutes apart) got a non-JSON reply and empty pages — probably bot protection; the next run was fine.

## Future sources (not v1)

- Gallery openings / things to do — social media (Instagram etc.). Scraping Instagram directly is fragile and against its terms; look at official APIs, venue newsletters/RSS, or aggregators first.
- Video games — high scores (e.g. OpenCritic/Metacritic). Max already has a Claude routine for this; decide whether to fold it in.
