from whatson.sources.afa import AsianFilmArchive, film_id
from whatson.sources.filmhouse import Filmhouse
from whatson.sources.html import harvest_links
from whatson.sources.shaw import Shaw, movie_id

TYPES_NO_FILMS = {"post": {"rest_base": "posts"}, "page": {"rest_base": "pages"}}


def wp_post(slug, title, link, image=None, terms=()):
    post = {"slug": slug, "title": {"rendered": title}, "link": link, "_embedded": {}}
    if image:
        post["_embedded"]["wp:featuredmedia"] = [{"source_url": image}]
    if terms:
        post["_embedded"]["wp:term"] = [[{"taxonomy": "mep_cat", "name": t} for t in terms]]
    return post


def test_afa_film_id_strips_repeat_suffix_but_keeps_year():
    assert film_id("hush-2016") == "hush-2016"
    assert film_id("hush-2016-1") == "hush-2016"
    assert film_id("hush-2016-1-2") == "hush-2016"
    assert film_id("hush-2016-reciprocal") == "hush-2016-reciprocal"
    assert film_id("2046-2004") == "2046-2004"


def test_afa_rest_merges_repeat_screenings(http):
    base = "https://asianfilmarchive.org"
    http.routes[f"{base}/wp-json/wp/v2/types"] = {**TYPES_NO_FILMS, "mep_events": {"rest_base": "mep_events"}}
    http.routes[f"{base}/wp-json/wp/v2/mep_events"] = [
        wp_post("hush-2016-1", "Hush &#8211; Encore", f"{base}/event-calendar/hush-2016-1/", terms=["Programme"]),
        wp_post("hush-2016", "Hush", f"{base}/event-calendar/hush-2016/", image="https://x/p.jpg"),
        wp_post("mother-2009", "<em>Mother</em>", f"{base}/event-calendar/mother-2009/"),
    ]
    items = AsianFilmArchive().fetch(http)
    assert [(i.id, i.title) for i in items] == [("hush-2016", "Hush – Encore"), ("mother-2009", "Mother")]
    assert items[0].tags == ["Programme"]


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


def test_shaw_api(http):
    # Field names as returned by shaw.sg/internal/get_now_showing_movies.
    http.routes["https://shaw.sg/internal/get_now_showing_movies"] = [
        {"primaryTitle": "HYBE CINE FEST 2026", "code": "SH-CF-HYPE26", "movieReleaseId": 0,
         "posterUrl": "https://cdn/h.jpg", "releaseDate": "2026-09-30T21:00:00", "isAdvanceSales": False},
        {"primaryTitle": "Clayface", "code": "2085", "movieReleaseId": 5551,
         "posterUrl": "https://cdn/c.jpg", "releaseDate": "2026-10-22T00:00:00", "isAdvanceSales": True},
        {"primaryTitle": "", "code": "1"},
    ]
    items = {i.id: i for i in Shaw().fetch(http)}
    assert set(items) == {"sh-cf-hype26", "2085"}
    clay = items["2085"]
    assert (clay.title, clay.url, clay.release_date, clay.tags) == (
        "Clayface", "https://shaw.sg/movie-details/2085", "2026-10-22", ["Advance sales"])
    assert items["sh-cf-hype26"].url == "https://shaw.sg/movie"


def test_shaw_movie_id_prefers_numeric_segment():
    assert movie_id("https://www.shaw.sg/movie-details/12345/some-title") == "12345"


def test_shaw_reads_movie_links_and_skips_tabs():
    html = """
      <a href="/movie/coming-soon">Coming Soon</a>
      <div><a href="/movie-details/12345"><img data-src="/img/w.jpg" alt="Wicked"></a>
           <a href="/movie-details/12345">Book Now</a></div>
      <div><span>ADVANCE SALES</span><a href="/movie-details/678">Dune: Part Two</a></div>"""
    found = {}
    Shaw().items_from_html(html, found, tag="Advance Sales")
    assert {k: (v.title, v.tags) for k, v in found.items()} == {
        "12345": ("Wicked", ["Advance Sales"]),
        "678": ("Dune: Part Two", ["Advance Sales"]),
    }
    assert found["12345"].poster == "https://shaw.sg/img/w.jpg"


def test_harvest_ignores_other_hosts_and_button_text():
    html = '<a href="https://other.example/films/x/">X</a><a href="/films/y/">Book now</a>'
    assert harvest_links(html, "https://filmhouse.sg/films/", r"^/films/") == [
        {"url": "https://filmhouse.sg/films/y/", "title": "", "poster": None}]


def test_harvest_prefers_heading_over_whole_card_text():
    html = """<a href="/films/x/"><img src="/x.jpg" alt="Poster for X"><h3>X</h3>
              <p>A long synopsis about the film that goes on.</p></a>"""
    [link] = harvest_links(html, "https://filmhouse.sg/films/", r"^/films/")
    assert (link["title"], link["poster"]) == ("X", "https://filmhouse.sg/x.jpg")
