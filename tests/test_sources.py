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


def test_filmhouse_uses_film_post_type_when_present(http):
    base = "https://filmhouse.sg"
    http.routes[f"{base}/wp-json/wp/v2/types"] = {**TYPES_NO_FILMS, "film": {"rest_base": "films"}}
    http.routes[f"{base}/wp-json/wp/v2/films"] = [wp_post("perfect-days", "Perfect Days", f"{base}/films/perfect-days/")]
    [item] = Filmhouse().fetch(http)
    assert (item.id, item.url) == ("perfect-days", f"{base}/films/perfect-days/")


def test_filmhouse_listing_pages_tag_coming_soon(http):
    base = "https://filmhouse.sg"
    http.routes[f"{base}/wp-json/wp/v2/types"] = TYPES_NO_FILMS
    http.routes[f"{base}/films/"] = """
      <a href="/films/">Films</a><a href="/films/coming-soon/">Coming soon</a>
      <a href="/films/perfect-days/"><h3>Perfect Days</h3></a>
      <a href="/films/all-we-imagine-as-light/">All We Imagine as Light</a>"""
    http.routes[f"{base}/films/coming-soon/"] = """
      <a href="/films/all-we-imagine-as-light/">All We Imagine as Light</a>
      <a href="/films/sp%C3%A9cial/">Spécial</a>"""
    items = {i.id: i for i in Filmhouse().fetch(http)}
    assert set(items) == {"perfect-days", "all-we-imagine-as-light", "spécial"}
    assert items["all-we-imagine-as-light"].tags == ["Coming soon"]
    assert items["perfect-days"].tags == []


def test_shaw_movie_id_prefers_numeric_segment():
    assert movie_id("https://www.shaw.sg/movie-details/12345/some-title") == "12345"
    assert movie_id("https://www.shaw.sg/movie/some-title") == "some-title"


def test_shaw_reads_movie_links_and_skips_tabs():
    html = """
      <a href="/movie/coming-soon">Coming Soon</a>
      <a href="/movie-details/12345/wicked"><img data-src="/img/w.jpg" alt="Wicked"></a>
      <a href="/movie-details/12345/wicked">Book Now</a>
      <a href="/movie-details/678/dune">Dune: Part Two</a>"""
    found = {}
    Shaw().items_from_html(html, found, tag="Advance Sales")
    assert {k: (v.title, v.tags) for k, v in found.items()} == {
        "12345": ("Wicked", ["Advance Sales"]),
        "678": ("Dune: Part Two", ["Advance Sales"]),
    }
    assert found["12345"].poster == "https://www.shaw.sg/img/w.jpg"


def test_harvest_ignores_other_hosts_and_button_text():
    html = '<a href="https://other.example/films/x/">X</a><a href="/films/y/">Book now</a>'
    assert harvest_links(html, "https://filmhouse.sg/films/", r"^/films/") == []


def test_harvest_prefers_heading_over_whole_card_text():
    html = """<a href="/films/x/"><img src="/x.jpg" alt="Poster for X"><h3>X</h3>
              <p>A long synopsis about the film that goes on.</p></a>"""
    [link] = harvest_links(html, "https://filmhouse.sg/films/", r"^/films/")
    assert (link["title"], link["poster"]) == ("X", "https://filmhouse.sg/x.jpg")
