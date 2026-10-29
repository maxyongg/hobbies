from whatson.sources.afa import AsianFilmArchive, film_id
from whatson.sources.filmhouse import Filmhouse
from whatson.sources.html import harvest_links
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


def test_harvest_ignores_other_hosts_and_button_text():
    html = '<a href="https://other.example/films/x/">X</a><a href="/films/y/">Book now</a>'
    assert harvest_links(html, "https://filmhouse.sg/films/", r"^/films/") == [
        {"url": "https://filmhouse.sg/films/y/", "title": "", "poster": None}]


def test_harvest_prefers_heading_over_whole_card_text():
    html = """<a href="/films/x/"><img src="/x.jpg" alt="Poster for X"><h3>X</h3>
              <p>A long synopsis about the film that goes on.</p></a>"""
    [link] = harvest_links(html, "https://filmhouse.sg/films/", r"^/films/")
    assert (link["title"], link["poster"]) == ("X", "https://filmhouse.sg/x.jpg")
