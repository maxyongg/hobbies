# Sources — how each site lists films

Surveyed 2026-10-29 via WebFetch (shell access to these domains is blocked in Claude cloud sessions). Verify before relying on any of this.

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

## Shaw Theatres — https://shaw.sg

- Mainstream multiplex chain, several locations.
- **Listing page:** `/movie`, with tabs "New Now Showing", "Ending Soon", "Advance Sales", "Top Movies", "Coming Soon".
- **Movie data is not in the HTML** — it's loaded by JavaScript. Find the JSON endpoint the page calls (browser devtools → Network on `/movie`) and poll that directly. Playwright is the fallback.
- Location pages: `/theatre/location/<id or slug>`.

## Asian Film Archive — https://asianfilmarchive.org

- Screenings mostly at Oldham Theatre.
- **Platform:** WordPress + Elementor + an events plugin (taxonomy `mep_cat`, which suggests the "Event Manager for WooCommerce" plugin — post type likely `mep_events`). Tickets sold on the event page itself (WooCommerce cart).
- **Listing pages:** `/whatson/`, `/events-calendar/`, programmes under `/event-archive/programmes/` and `/mep_cat/programme/`.
- **Event detail URL pattern:** `/event-calendar/<title-slug>-<year>/`, e.g. `/event-calendar/hush-2016/`. Repeat screenings get suffixes (`-1`, `-2`); some add a programme tag (`-reciprocal`). → Normalise the id by stripping repeat suffixes so one film = one alert.
- **Try first:** `/wp-json/wp/v2/mep_events?per_page=100&orderby=date` and `/feed/?post_type=mep_events`.

## Future sources (not v1)

- Gallery openings / things to do — social media (Instagram etc.). Scraping Instagram directly is fragile and against its terms; look at official APIs, venue newsletters/RSS, or aggregators first.
- Video games — high scores (e.g. OpenCritic/Metacritic). Max already has a Claude routine for this; decide whether to fold it in.
