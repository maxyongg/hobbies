from whatson import notify
from whatson.models import Item


def test_ntfy_payload_has_click_poster_and_auth(http):
    n = notify.Ntfy(http, "secret-topic", server="https://ntfy.example/", token="tk")
    item = Item(source="afa", id="hush-2016", title="Hush", url="https://afa/hush", poster="https://afa/p.jpg",
                tags=["Programme"])
    n.new_items("Asian Film Archive", [item], "https://site/")
    url, kw = http.posts[0]
    assert url == "https://ntfy.example"
    assert kw["headers"] == {"Authorization": "Bearer tk"}
    assert kw["json"] == {"topic": "secret-topic", "title": "New at Asian Film Archive",
                          "message": "Hush\nProgramme", "click": "https://afa/hush",
                          "attach": "https://afa/p.jpg", "tags": ["clapper"]}


def test_new_coming_soon_film_already_on_sale_says_so(http):
    n = notify.Ntfy(http, "t")
    item = Item(source="shaw", id="1", title="Dune: Part Three", url="https://shaw/1", showing="soon", on_sale=True)
    n.new_items("Shaw Theatres", [item], "https://site/")
    assert http.posts[0][1]["json"]["title"] == "New at Shaw Theatres · tickets on sale"


def test_on_sale_push_one_film_or_a_list(http):
    n = notify.Ntfy(http, "t")
    a = Item(source="shaw", id="1", title="You Can See Everything", url="https://shaw/1", poster="https://p/1.webp")
    b = Item(source="filmhouse", id="2", title="Fjord", url="https://fh/2")
    n.on_sale([notify.Sale(a, "Shaw Theatres", "")], "https://site/")
    assert http.posts[0][1]["json"] == {"topic": "t", "title": "Tickets on sale at Shaw Theatres",
                                        "message": "You Can See Everything", "click": "https://shaw/1",
                                        "attach": "https://p/1.webp", "tags": ["tickets"]}
    n.on_sale([notify.Sale(b, "Filmhouse", "First screening Sun 6 Dec, 7:30 pm"), notify.Sale(a, "Shaw Theatres", "")],
              "https://site/")
    assert http.posts[1][1]["json"] == {
        "topic": "t", "title": "Tickets on sale for 2 films", "click": "https://site/", "tags": ["tickets"],
        "message": "• Fjord (Filmhouse, first screening Sun 6 Dec, 7:30 pm)\n• You Can See Everything (Shaw Theatres)"}


def test_pushes_give_the_runtime_when_known(http):
    n = notify.Ntfy(http, "t")
    a = Item(source="shaw", id="1", title="Dune: Part Three", url="https://shaw/1", tags=["English", "PG13"],
             runtime=166)
    b = Item(source="filmhouse", id="2", title="Fjord", url="https://fh/2", runtime=60)
    n.new_items("Shaw Theatres", [a], "https://site/")
    assert http.posts[0][1]["json"]["message"] == "Dune: Part Three · 2h 46m\nEnglish, PG13"
    n.on_sale([notify.Sale(b, "Filmhouse", "Opens Thu 4 Dec")], "https://site/")
    assert http.posts[1][1]["json"]["message"] == "Fjord · 1h\nOpens Thu 4 Dec"
    n.on_sale([notify.Sale(b, "Filmhouse", ""), notify.Sale(a, "Shaw Theatres", "")], "https://site/")
    assert http.posts[2][1]["json"]["message"] == "• Fjord · 1h (Filmhouse)\n• Dune: Part Three · 2h 46m (Shaw Theatres)"


def test_from_env_without_topic_is_log_only(monkeypatch, http):
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    assert notify.from_env(http).configured is False
    monkeypatch.setenv("NTFY_TOPIC", "t")
    assert isinstance(notify.from_env(http), notify.Ntfy)
