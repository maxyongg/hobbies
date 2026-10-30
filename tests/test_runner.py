import json
from datetime import datetime

from whatson import runner
from whatson.models import Item, screening
from whatson.notify import Ntfy, Notifier
from whatson.sources import SourceError
from whatson.store import Store


class FakeSource:
    def __init__(self, key, batches, alerts=True):
        self.key, self.name, self.url = key, key.title(), f"https://{key}.example/"
        self.batches = list(batches)
        self.alerts = alerts

    def fetch(self, http):
        batch = self.batches.pop(0)
        if isinstance(batch, Exception):
            raise batch
        return [Item(source=self.key, id=i, title=i.upper(), url=f"{self.url}{i}") for i in batch]


def run_once(tmp_path, src, notifier, http, **kw):
    store = Store(tmp_path / "items.json")
    status = runner.run([src], store, notifier, http, status_path=tmp_path / "status.json", **kw)
    return Store(tmp_path / "items.json"), status


def test_first_run_seeds_without_alerting_then_alerts_only_new(tmp_path, http):
    src = FakeSource("fh", [["a", "b"], ["a", "b", "c"]])
    ntfy = Ntfy(http, "topic")

    store, _ = run_once(tmp_path, src, ntfy, http)
    assert http.posts == []
    assert {i.alert for i in store.items.values()} == {"seed"}

    store, _ = run_once(tmp_path, src, ntfy, http)
    assert len(http.posts) == 1
    payload = http.posts[0][1]["json"]
    assert payload["topic"] == "topic" and payload["message"].startswith("C")
    assert store.items[("fh", "c")].alert == "sent"
    assert store.items[("fh", "a")].alert == "seed"


def test_items_that_disappear_are_kept_but_unlisted(tmp_path, http):
    src = FakeSource("fh", [["a", "b"], ["b"]])
    run_once(tmp_path, src, Notifier(), http)
    store, _ = run_once(tmp_path, src, Notifier(), http)
    assert store.items[("fh", "a")].listed is False
    assert store.items[("fh", "b")].listed is True


def test_relisted_item_is_not_new(tmp_path, http):
    src = FakeSource("fh", [["a"], [], ["a"], ["a", "b"]])
    ntfy = Ntfy(http, "t")
    for _ in range(4):
        run_once(tmp_path, src, ntfy, http)
    titles = [p[1]["json"].get("message") for p in http.posts if "warning" not in p[1]["json"]["tags"]]
    assert titles == ["B"]


def test_failed_send_stays_pending_and_retries(tmp_path, http):
    src = FakeSource("fh", [["a"], ["a", "b"], ["a", "b"]])
    ntfy = Ntfy(http, "t")
    run_once(tmp_path, src, ntfy, http)
    http.fail_posts = True
    store, _ = run_once(tmp_path, src, ntfy, http)
    assert store.items[("fh", "b")].alert == "pending"
    http.fail_posts = False
    store, _ = run_once(tmp_path, src, ntfy, http)
    assert store.items[("fh", "b")].alert == "sent"
    assert len(http.posts) == 1


def test_broken_source_alerts_once_after_threshold(tmp_path, http):
    src = FakeSource("fh", [["a"], SourceError("boom"), [], SourceError("boom"), ["a"]])
    ntfy = Ntfy(http, "t")
    statuses = [run_once(tmp_path, src, ntfy, http)[1] for _ in range(5)]
    warnings = [p for p in http.posts if p[1]["json"]["tags"] == ["warning"]]
    assert len(warnings) == 1
    assert statuses[1]["sources"]["fh"]["ok"] is False
    assert statuses[2]["sources"]["fh"]["error"] == "returned 0 items"
    store = Store(tmp_path / "items.json")
    assert store.sources["fh"] == {"consecutive_failures": 0, "last_error": None}


def test_failing_source_does_not_seed_or_block_others(tmp_path, http):
    bad = FakeSource("bad", [RuntimeError("down")])
    good = FakeSource("good", [["x"]])
    store = Store(tmp_path / "items.json")
    status = runner.run([bad, good], store, Notifier(), http, status_path=tmp_path / "s.json")
    assert status["sources"]["good"]["ok"] and not status["sources"]["bad"]["ok"]
    assert not store.has_source("bad") and store.has_source("good")


def test_many_new_items_send_one_summary(tmp_path, http):
    src = FakeSource("fh", [["a"], ["a", "b", "c", "d", "e", "f", "g"]])
    ntfy = Ntfy(http, "t")
    run_once(tmp_path, src, ntfy, http)
    run_once(tmp_path, src, ntfy, http)
    assert len(http.posts) == 1
    assert http.posts[0][1]["json"]["title"] == "6 new at Fh"


def test_dry_run_writes_nothing(tmp_path, http):
    src = FakeSource("fh", [["a"]])
    run_once(tmp_path, src, Ntfy(http, "t"), http, dry_run=True)
    assert not (tmp_path / "items.json").exists()
    assert not (tmp_path / "status.json").exists()
    assert http.posts == []


def test_saved_file_is_stable_and_unicode(tmp_path, http):
    src = FakeSource("fh", [["a"]])
    store, _ = run_once(tmp_path, src, Notifier(), http)
    store.items[("fh", "a")].title = "花樣年華"
    store.save()
    text = (tmp_path / "items.json").read_text(encoding="utf-8")
    assert "花樣年華" in text
    store.save()
    assert (tmp_path / "items.json").read_text(encoding="utf-8") == text
    assert "checked" not in json.loads(text)


def test_quiet_source_records_new_items_without_alerting(tmp_path, http):
    src = FakeSource("gv", [["a"], ["a", "b"]], alerts=False)
    ntfy = Ntfy(http, "t")
    run_once(tmp_path, src, ntfy, http)
    store, status = run_once(tmp_path, src, ntfy, http)
    assert http.posts == []
    assert store.items[("gv", "b")].alert == "quiet"
    assert status["sources"]["gv"]["alerts"] is False


def test_showtimes_go_to_their_own_file_not_the_store(tmp_path, http):
    class WithTimes(FakeSource):
        def fetch(self, http):
            items = super().fetch(http)
            items[0].sessions = [screening(datetime(2099, 1, 2, 19, 30), "https://fh.example/book/2"),
                                 screening(datetime(2099, 1, 1, 16, 10), "https://fh.example/book/1", "Hall 1", "Q&A"),
                                 screening(datetime(2000, 1, 1, 16, 10), "https://fh.example/book/0")]  # past
            return items

    store = Store(tmp_path / "items.json")
    runner.run([WithTimes("fh", [["a", "b"]])], store, Notifier(), http, showtimes_path=tmp_path / "showtimes.json")
    data = json.loads((tmp_path / "showtimes.json").read_text(encoding="utf-8"))
    assert data["items"] == {"fh:a": [
        {"start": "2099-01-01T16:10", "url": "https://fh.example/book/1", "venue": "Hall 1", "note": "Q&A"},
        {"start": "2099-01-02T19:30", "url": "https://fh.example/book/2"},
    ]}
    assert "sessions" not in (tmp_path / "items.json").read_text(encoding="utf-8")
