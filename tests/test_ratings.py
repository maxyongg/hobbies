import gzip
import json
from datetime import date

from conftest import FakeHttp, FakeResponse

from whatson import ratings
from whatson.models import Item
from whatson.ratings import Ratings, Tmdb, clean, title_matches

API = Tmdb.API
TODAY = date(2026, 10, 30)


def film(source, id, title, listed=True):
    return Item(source=source, id=id, title=title, url=f"https://{source}.example/{id}", listed=listed)


def movie(id, title, year, popularity=1.0):
    return {"id": id, "title": title, "original_title": title, "release_date": f"{year}-06-01",
            "popularity": popularity}


SEARCH = {
    "Resident Evil": [movie(1, "Resident Evil", 2002, popularity=50), movie(2, "Resident Evil", 2026, popularity=20)],
    "Before Sunrise": [movie(3, "Before Sunrise", 1995, popularity=30), movie(4, "Before Sunrise", 2026)],
    "Jailer 2": [movie(5, "Jailer", 2023, popularity=40)],
    "Darah-ku": [],
    "My Blood": [movie(6, "My Blood", 1963), movie(7, "My Blood", 2020, popularity=9)],
}
MOVIES = {1: "tt0120804", 2: "tt2000002", 3: "tt0112471", 6: "tt6000006", 8: "tt8000008"}
IMDB = {"tt2000002": (6.9, 5000), "tt0112471": (8.1, 300000), "tt6000006": (7.0, 12)}


def routes(**extra):
    r = {
        f"{API}/search/movie": lambda p: {"results": SEARCH.get(p["query"], [])},
        ratings.IMDB_RATINGS: gzip.compress("tconst\taverageRating\tnumVotes\n".encode()
                                            + "".join(f"{k}\t{r}\t{v}\n" for k, (r, v) in IMDB.items()).encode()),
    }
    for id, imdb_id in MOVIES.items():
        r[f"{API}/movie/{id}"] = {"id": id, "title": f"Film {id}", "release_date": "2026-01-01", "imdb_id": imdb_id}
        r[ratings.LETTERBOXD.format(id)] = FakeResponse(
            f'<meta name="twitter:data2" content="3.{id}7 out of 5" />', url=f"https://letterboxd.com/film/film-{id}/")
    r.update(extra)
    return r


ITEMS = [
    film("gv", "re", "Resident Evil"),
    film("shaw", "re2", "Resident Evil [M]"),
    film("filmhouse", "bs", "Before Sunrise"),
    film("carnival", "j2", "Jailer 2 (NC16)"),
    film("afa", "db", "Darah-ku (My Blood, 1963)"),
    film("gv", "bts", "Bts World Tour `arirang' In São Paulo: Live Viewing"),
    film("afa", "old", "Gone Film", listed=False),
]


def run(tmp_path, http, items=ITEMS, today=TODAY, overrides=None):
    if overrides is not None:
        (tmp_path / "rating-overrides.json").write_text(json.dumps(overrides))
    r = Ratings(tmp_path / "ratings.json")
    r.update(items, http, Tmdb(http, "k" * 32), today=today)
    r.save()
    return json.loads((tmp_path / "ratings.json").read_text())


def test_clean_titles_from_real_listings():
    assert clean("SGIFF 2026 – Amores Perros (2000)") == (["Amores Perros"], 2000)
    assert clean("Darah-ku (My Blood, 1963)") == (["Darah-ku", "My Blood"], 1963)
    assert clean("Marvel Studios’ Avengers: Doomsday (IV)") == (["Avengers: Doomsday"], None)
    assert clean("Halloween Fans' Screening: Clayface") == (["Clayface"], None)
    assert clean("The Glory Hoes present The Rocky Horror Picture Show") == (["The Rocky Horror Picture Show"], None)
    assert clean("GODZILLA MINUS ZERO - IMAX Premiere Screening (JPN)") == (["GODZILLA MINUS ZERO"], None)
    assert clean("Love Letter (4K Restoration)") == (["Love Letter"], None)
    assert clean("Go For Broke 2 重生 2") == (["Go For Broke 2", "重生 2"], None)
    assert clean("V 空枪 (Mand)") == (["空枪"], None)
    assert clean("V [M]") == ([], None)


def test_title_matches_needs_same_numbers():
    assert title_matches("Minions & Monsters", "Minions and Monsters")
    assert title_matches("Amelie", "Amélie")
    assert not title_matches("Jailer 2", "Jailer")
    assert not title_matches("Dune: Part Three", "Dune: Part Two")


def test_matches_films_and_fetches_ratings(tmp_path):
    http = FakeHttp(routes())
    data = run(tmp_path, http)

    # Chains prefer the recent remake; repertory takes the best-known film; AFA's year picks 1963.
    assert data["items"] == {"gv:re": "2", "shaw:re2": "2", "filmhouse:bs": "3", "afa:db": "6"}
    assert data["films"]["2"] == {"title": "Film 2", "year": 2026, "imdb_id": "tt2000002", "imdb": 6.9,
                                  "letterboxd": 3.3, "letterboxd_url": "https://letterboxd.com/film/film-2/"}
    assert data["films"]["6"]["imdb"] is None  # 12 votes: too few to show
    assert data["matches"]["jailer 2"]["tmdb"] is None  # Jailer is not Jailer 2
    assert data["matches"]["bts world tour arirang in sao paulo live viewing"]["tmdb"] is None
    assert data["updated"] == "2026-10-30"
    assert not any("Gone" in u for u in http.gets)


def test_same_day_reruns_make_no_requests_and_next_day_refreshes(tmp_path):
    run(tmp_path, FakeHttp(routes()))
    again = FakeHttp(routes())
    run(tmp_path, again)
    assert again.gets == []

    IMDB["tt0112471"] = (8.2, 300001)
    try:
        tomorrow = FakeHttp(routes())
        data = run(tmp_path, tomorrow, today=date(2026, 10, 31))
    finally:
        IMDB["tt0112471"] = (8.1, 300000)
    assert data["films"]["3"]["imdb"] == 8.2
    assert f"{API}/search/movie" not in tomorrow.gets  # matches are kept


def test_unmatched_titles_are_retried_after_a_week(tmp_path):
    items = [film("carnival", "j2", "Jailer 2")]
    run(tmp_path, FakeHttp(routes()), items)
    soon = FakeHttp(routes())
    run(tmp_path, soon, items, today=date(2026, 11, 3))
    assert f"{API}/search/movie" not in soon.gets
    later = FakeHttp(routes())
    run(tmp_path, later, items, today=date(2026, 11, 7))
    assert f"{API}/search/movie" in later.gets


def test_overrides_fix_matches(tmp_path):
    http = FakeHttp(routes(**{f"{API}/find/tt8000008": {"movie_results": [{"id": 8}]}}))
    data = run(tmp_path, http, overrides={
        "_help": "ignored",
        "Jailer 2": "https://www.imdb.com/title/tt8000008/",
        "Resident Evil": None,
        "Before Sunrise": "https://www.themoviedb.org/movie/1-resident-evil",
    })
    assert data["items"]["carnival:j2"] == "8"
    assert "gv:re" not in data["items"]
    assert data["items"]["filmhouse:bs"] == "1"


def test_letterboxd_block_keeps_last_ratings(tmp_path):
    run(tmp_path, FakeHttp(routes()))
    blocked = routes(**{ratings.LETTERBOXD.format(id): FakeResponse("Just a moment...", 403) for id in MOVIES})
    http = FakeHttp(blocked)
    data = run(tmp_path, http, today=date(2026, 10, 31))
    assert data["films"]["3"]["letterboxd"] == 3.4
    assert sum("letterboxd" in u for u in http.gets) == 1  # stops at the first block


def test_update_never_raises_and_skips_without_key(tmp_path, monkeypatch):
    class Store:
        items = {i.key: i for i in ITEMS}

    monkeypatch.setenv("TMDB_API_KEY", "k" * 32)
    ratings.update(Store, FakeHttp({}), tmp_path / "ratings.json")  # TMDb answers 404 to everything
    data = json.loads((tmp_path / "ratings.json").read_text())
    assert data["items"] == {}

    monkeypatch.delenv("TMDB_API_KEY")
    ratings.update(Store, FakeHttp(routes()), tmp_path / "other.json")
    assert not (tmp_path / "other.json").exists()
