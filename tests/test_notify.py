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


def test_from_env_without_topic_is_log_only(monkeypatch, http):
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    assert notify.from_env(http).configured is False
    monkeypatch.setenv("NTFY_TOPIC", "t")
    assert isinstance(notify.from_env(http), notify.Ntfy)
