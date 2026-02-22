from conftest import StubResult


def test_normalize_segment_generates_stable_dedupe_hash(segments_module):
    first = segments_module.normalize_segment(
        {
            "council": "A",
            "committee": "Budget",
            "tag": [{"k": "v"}],
            "meeting_date": "2026-02-17",
        }
    )
    second = segments_module.normalize_segment(
        {
            "meeting_date": "2026-02-17",
            "tag": [{"k": "v"}],
            "committee": "Budget",
            "council": "A",
        }
    )

    assert isinstance(first["dedupe_hash"], str)
    assert len(first["dedupe_hash"]) == 64
    assert first["dedupe_hash"] == second["dedupe_hash"]


def test_insert_segments_counts_only_non_conflict_rows(segments_module, make_connection_provider):
    def handler(_statement, _params):
        return StubResult(rows=[{"inserted": 2}])

    connection_provider, _ = make_connection_provider(handler)
    inserted = segments_module.insert_segments(
        [{"council": "A"}, {"council": "A"}, {"council": "B"}],
        connection_provider=connection_provider,
    )
    assert inserted == 2


def test_normalize_segment_blank_and_none_optional_strings_share_dedupe_hash(segments_module):
    blank_payload = {
        "council": "A",
        "committee": "",
        "session": "",
        "meeting_no": None,
        "meeting_date": "2026-02-17",
        "content": "",
        "summary": "",
        "subject": "",
        "party": "",
        "constituency": "",
        "department": "",
    }
    none_payload = {
        "council": "A",
        "committee": None,
        "session": None,
        "meeting_no": None,
        "meeting_date": "2026-02-17",
        "content": None,
        "summary": None,
        "subject": None,
        "party": None,
        "constituency": None,
        "department": None,
    }

    blank_normalized = segments_module.normalize_segment(blank_payload)
    none_normalized = segments_module.normalize_segment(none_payload)

    assert blank_normalized["dedupe_hash"] == none_normalized["dedupe_hash"]
    assert blank_normalized["dedupe_hash_legacy"] == none_normalized["dedupe_hash_legacy"]
    assert blank_normalized["dedupe_hash_legacy"] is not None
