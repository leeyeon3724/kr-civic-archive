import json

from conftest import StubResult


def test_news_upsert_batch_dedupes_same_url_with_last_item_wins(news_module, make_connection_provider):
    captured_items = {}

    def handler(_statement, params):
        parsed_items = json.loads(params["items"])
        captured_items["payload"] = parsed_items
        return StubResult(rows=[{"inserted": 1, "updated": 0}])

    connection_provider, _ = make_connection_provider(handler)
    inserted, updated = news_module.upsert_articles(
        [
            {"title": "first", "url": "https://example.com/n/1"},
            {"title": "second", "url": "https://example.com/n/1"},
        ],
        connection_provider=connection_provider,
    )

    assert inserted == 1
    assert updated == 0
    deduped_items = captured_items["payload"]
    assert len(deduped_items) == 1
    assert deduped_items[0]["url"] == "https://example.com/n/1"
    assert deduped_items[0]["title"] == "second"


def test_minutes_upsert_batch_dedupes_same_url_with_last_item_wins(minutes_module, make_connection_provider):
    captured_items = {}

    def handler(_statement, params):
        parsed_items = json.loads(params["items"])
        captured_items["payload"] = parsed_items
        return StubResult(rows=[{"inserted": 1, "updated": 0}])

    connection_provider, _ = make_connection_provider(handler)
    inserted, updated = minutes_module.upsert_minutes(
        [
            {"council": "A", "url": "https://example.com/m/1", "committee": "budget"},
            {"council": "A", "url": "https://example.com/m/1", "committee": "plenary"},
        ],
        connection_provider=connection_provider,
    )

    assert inserted == 1
    assert updated == 0
    deduped_items = captured_items["payload"]
    assert len(deduped_items) == 1
    assert deduped_items[0]["url"] == "https://example.com/m/1"
    assert deduped_items[0]["committee"] == "plenary"
