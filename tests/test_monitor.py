import pytest

from listing_monitor.__main__ import check_once
from listing_monitor.filters import Query
from listing_monitor.sources import CssSource, Listing, SourceBlocked, parse_price
from listing_monitor.store import SeenStore

PAGE = """
<div class="item"><a href="/itm/1"><span class="t">Silver coin 1921</span></a><span class="p">£12.50</span></div>
<div class="item"><a href="/itm/2?ref=x"><span class="t">Silver coin REPLICA</span></a><span class="p">£2</span></div>
<div class="item"><span class="t">no link here</span></div>
"""


def make_source(html=PAGE):
    source = CssSource("demo", "https://shop.test/s?q={q}", item="div.item", title=".t", link="a", price=".p")
    source.fetch_html = lambda url: html
    return source


@pytest.mark.parametrize("raw, expected", [
    ("£1,234.50", 1234.5),
    ("1.234,50 €", 1234.5),
    ("12,99 €", 12.99),
    ("1 200 ₽", 1200),
    ("", None),
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_parse_skips_cards_without_link_and_strips_tracking():
    items = make_source().search("silver")
    assert [i.item_id for i in items] == ["https://shop.test/itm/1", "https://shop.test/itm/2"]
    assert items[0].price == 12.5


def test_query_filters():
    query = Query("silver", include=["silver"], exclude=["replica"], max_price=20)
    titles = [i.title for i in make_source().search("silver") if query.matches(i)]
    assert titles == ["Silver coin 1921"]


def test_listing_without_price_is_not_filtered_out_by_price():
    assert Query("x", max_price=10).matches(Listing("s", "1", "anything", "u"))


def test_antibot_page_raises():
    with pytest.raises(SourceBlocked):
        make_source("<html><div id='cf-challenge'></div></html>").search("x")


def test_store_returns_only_new(tmp_path):
    store = SeenStore(str(tmp_path / "seen.sqlite"))
    a, b = Listing("s", "1", "a", "u"), Listing("s", "2", "b", "u")
    assert not store.has_history("s", "q")
    assert store.add_new("s", "q", [a]) == [a]
    assert store.add_new("s", "q", [a, b]) == [b]


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, listing, query):
        self.sent.append(listing.title)


def test_first_run_only_remembers_then_notifies_new(tmp_path, monkeypatch):
    monkeypatch.setattr("listing_monitor.__main__.time.sleep", lambda s: None)
    store = SeenStore(str(tmp_path / "seen.sqlite"))
    notifier = FakeNotifier()
    queries = [Query("silver", include=["silver"])]

    assert check_once([make_source()], queries, store, notifier) == 0

    newer = PAGE + '<div class="item"><a href="/itm/3"><span class="t">Silver spoon</span></a></div>'
    assert check_once([make_source(newer)], queries, store, notifier) == 1
    assert notifier.sent == ["Silver spoon"]
