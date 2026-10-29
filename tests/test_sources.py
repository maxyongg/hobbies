from datetime import datetime, timezone

from whatson.sources import afa
from whatson.sources.afa import AsianFilmArchive, film_id
from whatson.sources.carnival import Carnival
from whatson.sources.filmhouse import Filmhouse
from whatson.sources.gv import GoldenVillage
from whatson.sources.html import harvest_links
from whatson.sources.sfs import items_from_events
from whatson.sources.shaw import Shaw, movie_id

def test_afa_film_id_strips_repeat_suffix_but_keeps_year():
    assert film_id("hush-2016") == "hush-2016"
    assert film_id("hush-2016-1") == "hush-2016"
    assert film_id("hush-2016-1-2") == "hush-2016"
    assert film_id("hush-2016-reciprocal") == "hush-2016-reciprocal"
    assert film_id("2046-2004") == "2046-2004"


def test_afa_rest_merges_repeat_screenings(http):
    # Field names as returned by /wp-json/wp/v2/mep_events?_fields=...
    base = "https://asianfilmarchive.org"
    http.routes[f"{base}/wp-json/wp/v2/mep_events"] = [
        {"slug": "hush-2016-1", "title": {"rendered": "[SOLD OUT] Hush &#8211; Encore"},
         "link": f"{base}/event-calendar/hush-2016-1/",
         "class_list": ["post-1", "mep_events", "tag-singapore-international-film-festival", "mep_cat-screening"],
         "yoast_head_json": {"og_image": [{"url": "https://x/p.jpg"}]}},
        {"slug": "hush-2016", "title": {"rendered": "Hush"}, "link": f"{base}/event-calendar/hush-2016/"},
        {"slug": "mother-2009", "title": {"rendered": "<em>Mother</em>"}, "link": f"{base}/event-calendar/mother-2009/"},
    ]
    items = AsianFilmArchive().fetch(http)
    assert [(i.id, i.title) for i in items] == [("hush-2016", "Hush – Encore"), ("mother-2009", "Mother")]
    assert items[0].tags == ["Screening", "Singapore international film festival"]
    assert "event_informations.event_start_datetime" in afa.FIELDS
    assert items[0].poster == "https://x/p.jpg"


def test_afa_falls_back_to_listing_pages(http):
    base = "https://asianfilmarchive.org"
    http.routes[f"{base}/whatson/"] = """
      <a href="/event-calendar/hush-2016/"><img src="/p.jpg" alt="Hush"></a>
      <a href="/event-calendar/hush-2016/">Buy Tickets</a>
      <a href="https://asianfilmarchive.org/event-calendar/hush-2016-2/">Hush</a>
      <a href="/about/">About</a>"""
    items = AsianFilmArchive().fetch(http)
    assert [(i.id, i.title, i.poster) for i in items] == [("hush-2016", "Hush", f"{base}/p.jpg")]


def test_filmhouse_reads_film_cards_and_tags_coming_soon(http):
    # Shaped like the live listing: bare poster links to http://filmhouse.sg/film/<id>/<slug>,
    # title in the card next to it, plus per-showtime "Book" links.
    def card(fid, slug, title):
        return f"""<div class="film"><a href="http://filmhouse.sg/film/{fid}/{slug}"><img src="https://cdn/{fid}.jpg"></a>
                   <div class="info"><h2>{title}</h2><a href="/filmhouse-singapore/booknow/1{fid}">Book 4:10 pm</a></div></div>"""

    base = "https://filmhouse.sg"
    http.routes[f"{base}/films/"] = "<nav><a href='/films'>All Films</a></nav>" + card(220, "fjord", "Fjord") + \
        card(232, "amlie-25th-anniversary", "Amélie (25th Anniversary)")
    http.routes[f"{base}/films/coming-soon/"] = card(232, "amlie-25th-anniversary", "Amélie (25th Anniversary)")
    items = {i.id: i for i in Filmhouse().fetch(http)}
    assert {k: (v.title, v.tags) for k, v in items.items()} == {
        "220": ("Fjord", []),
        "232": ("Amélie (25th Anniversary)", ["Coming soon"]),
    }
    assert items["220"].url == f"{base}/film/220/fjord"
    assert items["220"].poster == "https://cdn/220.jpg"


def test_filmhouse_falls_back_to_slug_title(http):
    http.routes["https://filmhouse.sg/films/"] = '<a href="/film/245/godzilla-minus-zero"><img src="/p.jpg"></a>'
    [item] = Filmhouse().fetch(http)
    assert (item.id, item.title) == ("245", "Godzilla Minus Zero")


def test_shaw_movie_id_prefers_numeric_segment():
    assert movie_id("https://www.shaw.sg/movie-details/12345/some-title") == "12345"


def test_shaw_reads_movie_links_and_skips_tabs():
    html = """
      <a href="/movie/coming-soon">Coming Soon</a>
      <div><div><a href="/movie-details/12345"><span>NEW RELEASE</span><picture>
             <img data-src="/img/w.jpg" alt="Wicked"></picture></a></div>
           <div><div><h3>Wicked</h3></div><a href="/movie-details/12345"><button>BUY</button></a>
           <span>A witch's story.</span><a href="/movie-details/12345">(Details)</a></div></div>
      <div><a href="/movie-details/678"><span>ADVANCE SALES</span><img alt="Dune: Part Two"></a>
           <h3>Dune: Part Two</h3></div>"""
    found = {}
    Shaw().items_from_html(html, found, tag="Advance Sales")
    assert {k: (v.title, v.tags) for k, v in found.items()} == {
        "12345": ("Wicked", ["Advance Sales"]),
        "678": ("Dune: Part Two", ["Advance Sales"]),
    }
    assert found["12345"].poster == "https://shaw.sg/img/w.jpg"


def test_shaw_unwraps_gumlet_posters():
    html = """<div><a href="/movie-details/1377"><img alt="X"
        src="https://shawsgqk.gumlet.io/fetch/https://snow-shaw-cdn.azureedge.net/prd/content/images/movie/default/en-sg/1377-Poster-1784273656234?w=145&amp;dpr=1.3"></a>
        <h3>X</h3></div>"""
    found = {}
    Shaw().items_from_html(html, found)
    assert found["1377"].poster == ("https://snow-shaw-cdn.azureedge.net/prd/content/images/movie/default/en-sg/"
                                    "1377-Poster-1784273656234")


def test_harvest_ignores_other_hosts_and_button_text():
    html = '<a href="https://other.example/films/x/">X</a><a href="/films/y/">Book now</a>'
    assert harvest_links(html, "https://filmhouse.sg/films/", r"^/films/") == [
        {"url": "https://filmhouse.sg/films/y/", "title": "", "poster": None}]


def test_harvest_prefers_heading_over_whole_card_text():
    html = """<a href="/films/x/"><img src="/x.jpg" alt="Poster for X"><h3>X</h3>
              <p>A long synopsis about the film that goes on.</p></a>"""
    [link] = harvest_links(html, "https://filmhouse.sg/films/", r"^/films/")
    assert (link["title"], link["poster"]) == ("X", "https://filmhouse.sg/x.jpg")


def test_afa_drops_past_screenings_and_sets_showing(http, monkeypatch):
    monkeypatch.setattr(afa, "now", lambda: datetime(2026, 10, 29, 12, 0))
    base = "https://asianfilmarchive.org"

    def ev(slug, start, end):
        return {"slug": slug, "title": {"rendered": slug}, "link": f"{base}/event-calendar/{slug}/",
                "event_informations": {"event_start_datetime": [start], "event_expire_datetime": [end]}}

    http.routes[f"{base}/wp-json/wp/v2/mep_events"] = [
        ev("past-2001", "2026-10-25 13:30:00", "2026-10-25 15:00:00"),
        ev("tonight-2002", "2026-10-29 19:00:00", "2026-10-29 21:00:00"),
        ev("later-2003", "2026-11-20 19:00:00", "2026-11-20 21:00:00"),
        ev("repeat-2004-1", "2026-11-25 19:00:00", "2026-11-25 21:00:00"),
        ev("repeat-2004", "2026-10-30 19:00:00", "2026-10-30 21:00:00"),
        {"slug": "undated-2005", "title": {"rendered": "Undated"}, "link": f"{base}/event-calendar/undated-2005/"},
    ]
    items = {i.id: i.showing for i in AsianFilmArchive().fetch(http)}
    assert items == {"tonight-2002": "now", "later-2003": "soon", "repeat-2004": "now", "undated-2005": None}


def test_gv_lists_and_titles(http):
    # Field names as returned by POST www.gv.com.sg/.gv-api/{nowshowing,advancesales,comingsoon}.
    gv_base = "https://www.gv.com.sg/.gv-api"
    http.routes[f"{gv_base}/nowshowing"] = {"success": True, "data": [
        {"filmCd": "7509", "filmTitle": "LOOK BACK *", "imageLink": "https://media/img7509.jpg",
         "language": "Japanese", "rating": "PG", "type": "Single"},
        {"filmCd": "4510", "filmTitle": "Godzilla Minus Zero *", "language": "Japanese", "rating": "PG13", "type": "Single"},
    ]}
    http.routes[f"{gv_base}/advancesales"] = {"success": True, "data": [
        {"filmCd": "4510", "filmTitle": "Godzilla Minus Zero *", "type": "Single"},
    ]}
    http.routes[f"{gv_base}/comingsoon"] = {"success": True, "data": [
        {"filmCd": "4512", "filmTitle": "(Hindi) Ramayana: Rise Of A Legend *", "language": "Hindi",
         "rating": "Rating to be Advised", "type": "Group"},
    ]}
    items = {i.id: i for i in GoldenVillage().fetch(http)}
    assert {k: (v.title, v.showing, v.tags) for k, v in items.items()} == {
        "7509": ("Look Back", "now", ["Japanese", "PG"]),
        "4510": ("Godzilla Minus Zero", "now", ["Japanese", "PG13"]),
        "4512": ("Ramayana: Rise Of A Legend (Hindi)", "soon", ["Hindi"]),
    }
    assert items["7509"].url == "https://www.gv.com.sg/GVMovieDetails#/movie/7509"
    assert items["4512"].url == "https://www.gv.com.sg/GVGroupSynopsis#/group/4512"
    assert GoldenVillage.alerts is False


def test_carnival_lists(http, monkeypatch):
    # Field names as returned by service.carnivalcinemas.sg/api/QuickSearch/*.
    api = "https://service.carnivalcinemas.sg/api/QuickSearch"
    http.routes[f"{api}/GetNowPlayingMovies"] = {"responseMovies": [
        {"code": "Jailer 2 (NC16)", "name": "Jailer 2 (NC16)", "openingDate": "2026-10-15T00:00:00"},
        {"code": "The Execution(M18)", "name": "The Execution(M18)", "openingDate": "2099-11-21T00:00:00"},
    ]}
    http.routes[f"{api}/GetCommingSoonMovies"] = {"responseMovies": [
        {"code": "111", "name": "(TAMIL) Ramayana: Rise Of A Legend", "openingDate": "2099-11-05T00:00:00"},
        {"code": "111", "name": "Scene ", "openingDate": "2099-11-06T00:00:00"},
    ]}
    items = {i.id: i for i in Carnival().fetch(http)}
    assert {k: (v.title, v.showing) for k, v in items.items()} == {
        "jailer-2-nc16": ("Jailer 2 (NC16)", "now"),
        "the-execution-m18": ("The Execution (M18)", "soon"),
        "tamil-ramayana-rise-of-a-legend": ("Ramayana: Rise Of A Legend (TAMIL)", "soon"),
        "scene": ("Scene", "soon"),
    }
    assert items["jailer-2-nc16"].url == "https://carnivalcinemas.sg/Jailer%202%20(NC16)/Jailer%202%20(NC16)"


def test_sfs_events_to_films():
    # Shaped like api.eventive.org/event_buckets/<id>/events?upcoming_only=true
    def ev(start, name, film_id, film_name):
        return {"start_time": start, "name": name,
                "films": [{"id": film_id, "name": film_name, "poster_image": f"https://static/{film_id}.jpg"}]}

    events = [
        ev("2026-10-30T11:30:00.000Z", "SFS Somerset: The Old Man and His Car", "f1", "The Old Man and His Car"),
        ev("2026-11-21T11:30:00.000Z", "SFS Somerset: A Wicked Tale (with Q&A)", "f2", "A Wicked Tale"),
        ev("2026-11-07T08:00:00.000Z", "SFS Spotlight: Roman Holiday (Members-Only)", "f3", "Roman Holiday"),
        ev("2026-11-08T11:30:00.000Z", "SFS Somerset: The Old Man and His Car", "f1", "The Old Man and His Car"),
    ]
    items = {i.id: i for i in items_from_events(events, datetime(2026, 10, 29, 12, tzinfo=timezone.utc))}
    assert {k: (v.title, v.showing, v.tags) for k, v in items.items()} == {
        "f1": ("The Old Man and His Car", "now", ["SFS Somerset"]),
        "f2": ("A Wicked Tale", "soon", ["SFS Somerset"]),
        "f3": ("Roman Holiday", "soon", ["SFS Spotlight"]),
    }
    assert items["f1"].url == "https://events.singaporefilmsociety.com/films/f1"


def test_poster_skips_placeholder_and_uses_picture_source():
    # Shaw swaps a failed poster for /assets/images/noimage.png; the real one stays in <source srcset>.
    html = """<div><a href="/movie-details/1"><picture>
        <source media="(max-width: 480px)" srcset="https://cdn/1-Poster?w=100&amp;dpr=1.3" type="png">
        <img src="/assets/images/noimage.png" alt="X"></picture></a><h3>X</h3></div>
      <div><a href="/movie-details/2"><img src="/assets/images/noimage.png" alt="Y"></a><h3>Y</h3></div>"""
    links = {l["url"]: l["poster"] for l in harvest_links(html, "https://shaw.sg/movie", r"^/movie-details/\d+")}
    assert links == {"https://shaw.sg/movie-details/1": "https://cdn/1-Poster?w=100&dpr=1.3",
                     "https://shaw.sg/movie-details/2": None}
