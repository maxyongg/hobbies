# Sources — how each site lists films

Surveyed and verified 2026-10-29 through the CI `live` job (Claude cloud sessions can't reach these sites). The job prints what every scraper finds on non-`main` pushes; `scripts/probe.py <name>` shows what a site exposes. Showing status: "now" or "soon" per item (see each source).

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
- **Implemented (verified live 2026-10-29, 34 films; alerts):** `whatson/sources/filmhouse.py`. Showing: coming-soon page → soon, else now. No film post type over REST and `/feed/` is empty. Listings are rendered server-side by the JACRO plugin: each film is a `div.jacro-event` card with a poster link and an `a.liveeventtitle` title link to `http://filmhouse.sg/film/<id>/<slug>` (JACRO's numeric id = our id), plus `/filmhouse-singapore/booknow/<n>` showtime links. Reads `/films/` and `/films/coming-soon/` (tagged "Coming soon"). Posters on `cdn.taposapp.com`.

## Shaw Theatres — https://shaw.sg

- Mainstream multiplex chain, several locations.
- **Listing page:** `/movie`, with tabs "New Now Showing", "Ending Soon", "Advance Sales", "Top Movies", "Coming Soon".
- **Movie data is not in the HTML** — it's loaded by JavaScript. Find the JSON endpoint the page calls (browser devtools → Network on `/movie`) and poll that directly. Playwright is the fallback.
- Location pages: `/theatre/location/<id or slug>`.
- **Implemented (verified live 2026-10-29, 64 films; alerts):** `whatson/sources/shaw.py`. Showing: Coming Soon / Advance Sales tabs → soon (unless also on a now-showing tab). Next.js site on `shaw.sg` (www redirects). Tabs load JSON from `shaw.sg/internal/get_now_showing_movies`, `get_advance_sale_movies`, `get_top_movies`, `get_coming_soon_movies`, but these return a 404 page to plain `requests` (even with Referer), so the scraper renders `/movie` in Chromium, clicks each tab, and reads `/movie-details/<id>` cards (title in the card's `<h3>`, tag = tab name). Language/format variants are separate ids (e.g. `V [CANTO]`, `V [M]`).

## Asian Film Archive — https://asianfilmarchive.org

- Screenings mostly at Oldham Theatre.
- **Platform:** WordPress + Elementor + an events plugin (taxonomy `mep_cat`, which suggests the "Event Manager for WooCommerce" plugin — post type likely `mep_events`). Tickets sold on the event page itself (WooCommerce cart).
- **Listing pages:** `/whatson/`, `/events-calendar/`, programmes under `/event-archive/programmes/` and `/mep_cat/programme/`.
- **Event detail URL pattern:** `/event-calendar/<title-slug>-<year>/`, e.g. `/event-calendar/hush-2016/`. Repeat screenings get suffixes (`-1`, `-2`); some add a programme tag (`-reciprocal`). → Normalise the id by stripping repeat suffixes so one film = one alert.
- **Try first:** `/wp-json/wp/v2/mep_events?per_page=100&orderby=date` and `/feed/?post_type=mep_events`.
- **Implemented (verified live 2026-10-29; alerts):** `whatson/sources/afa.py` — showing from the plugin's `event_informations` meta (`event_upcoming_datetime`/`event_start_datetime`, `event_expire_datetime`): ended screenings dropped, start within 7 days → now, later → soon; `mep_events` over WP REST (1,770 posts in total), latest 50 with `_fields=id,slug,link,title,date,class_list,yoast_head_json` (~270 KB; with `_embed` it was ~1 MB). Poster = Yoast `og_image`; tags from `class_list` (`mep_cat-*`, `tag-*`). HTML fallback reads `/event-calendar/<slug>/` links on `/whatson/` and `/events-calendar/`. id = slug with repeat suffixes (`-1`, `-2`) stripped; 4-digit years and programme tags are kept. Includes talks and shorts programmes, not just films. "[SOLD OUT]" is stripped from titles. One run (of four, minutes apart) got a non-JSON reply and empty pages — probably bot protection; the next run was fine.

## Golden Village — https://www.gv.com.sg (web app only, no alerts)

- Biggest chain. AngularJS site behind Cloudflare: headless Chromium gets a bot challenge, but plain `requests` POSTs (JSON body `{}`, Origin/Referer set) to `/.gv-api/nowshowing`, `/.gv-api/advancesales`, `/.gv-api/comingsoon` return JSON (`filmCd`, `filmTitle`, `imageLink`, `language`, `rating`, `type` Single/Group, `specialEvent`). Don't try to get past the challenge if plain requests start failing.
- **Implemented (verified live 2026-10-29):** `whatson/sources/gv.py`. Titles lose the trailing `*`, "(Hindi) X" → "X (Hindi)", ALL-CAPS → capitalised. Detail URL `GVMovieDetails#/movie/<filmCd>` (Group → `GVGroupSynopsis#/group/`, events → `GVEventDetails#/event/`).

## Carnival Cinemas — https://carnivalcinemas.sg (web app only)

- Indian-language films at Golden Mile Tower. AngularJS; data from `service.carnivalcinemas.sg/api/QuickSearch/GetNowPlayingMovies` and `GetCommingSoonMovies` (sic), plain GET with `location=Mumbai` (what the site itself sends). Codes aren't unique (coming soon all "111"), so id = slug of the name. Posters: `carnivalcinemas.sg/upload/movie/<imageURL>`. Booking URL `/<name>/<name>`.
- **Implemented (verified live 2026-10-29):** `whatson/sources/carnival.py`. Showing: now-playing with opening date ≤ today → now, else soon.

## Singapore Film Society — https://www.singaporefilmsociety.com (web app only)

- SFS Somerset (GV Cineleisure Hall 6) plus SFS Spotlight/Showcase screenings at other halls. Site on Duda; tickets via Eventive (bucket `6a277454f068b0ba9c60baae`, frontend `events.singaporefilmsociety.com`). `api.eventive.org` refuses requests without the client header the page sends, so the scraper loads the SFS homepage in Chromium and reads `/event_buckets/<id>/events?upcoming_only=true` as the page fetches it. One item per film (`films[].id`), URL `events.singaporefilmsociety.com/films/<id>`, poster `films[].poster_image`, tag = series ("SFS Somerset", "SFS Spotlight"). Showing: a session within 7 days → now.

## Looked at, not included (2026-10-29)

- **Closed:** Cathay Cineplexes (ceased 2025), WE Cinemas, Filmgarde, The Projector.
- **Alliance Française** (`alliancefrancaise.org.sg`): TLS certificate failed verification from GitHub's runners; not worked around.
- **Objectifs** (`objectifs.com.sg`, WordPress): mostly workshops/exhibitions; film screenings are occasional. Could be added from its "What's On" category if wanted.
- **SGIFF** (`sgiff.com`): festival 21 Oct–1 Nov 2026; its screenings are at the cinemas above (AFA lists them). WP REST is 403.

## Future sources (not v1)

- Gallery openings / things to do — social media (Instagram etc.). Scraping Instagram directly is fragile and against its terms; look at official APIs, venue newsletters/RSS, or aggregators first.
- Video games — high scores (e.g. OpenCritic/Metacritic). Max already has a Claude routine for this; decide whether to fold it in.
