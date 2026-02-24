from conftest import StubResult

_BASE = {"council": "A", "meeting_date": "2026-02-17"}


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


def test_normalize_segment_tag_dict_key_order_is_canonicalized(segments_module):
    # Dict keys inside tag items are sorted before hashing, so key order must not matter.
    a = segments_module.normalize_segment({**_BASE, "tag": [{"k": "v", "b": "a"}]})
    b = segments_module.normalize_segment({**_BASE, "tag": [{"b": "a", "k": "v"}]})

    assert a["dedupe_hash"] == b["dedupe_hash"]


def test_normalize_segment_tag_list_order_affects_hash(segments_module):
    # Tag list order is preserved (lists are not sorted), so different orderings
    # of the same items must produce different hashes.
    a = segments_module.normalize_segment({**_BASE, "tag": [{"k": "v"}, {"b": "a"}]})
    b = segments_module.normalize_segment({**_BASE, "tag": [{"b": "a"}, {"k": "v"}]})

    assert a["dedupe_hash"] != b["dedupe_hash"]


def test_normalize_segment_tag_none_vs_empty_list_produce_different_hashes(segments_module):
    # tag=None serialises as JSON null; tag=[] serialises as [].
    # The two must be treated as distinct to avoid false deduplication.
    with_none = segments_module.normalize_segment({**_BASE, "tag": None})
    with_empty = segments_module.normalize_segment({**_BASE, "tag": []})

    assert with_none["dedupe_hash"] != with_empty["dedupe_hash"]


def test_normalize_segment_different_council_values_produce_different_hashes(segments_module):
    # Council is a mandatory field; different values must always differ.
    a = segments_module.normalize_segment({**_BASE, "council": "seoul"})
    b = segments_module.normalize_segment({**_BASE, "council": "busan"})

    assert a["dedupe_hash"] != b["dedupe_hash"]


def test_normalize_segment_meeting_no_int_and_string_produce_different_hashes(segments_module):
    # coerce_meeting_no_int returns None for string inputs and the integer for int inputs.
    # meeting_no_combined also diverges (raw string vs formatted "N차").
    # Both fields enter the hash, so int 3 and string "3" must hash differently.
    with_int = segments_module.normalize_segment({**_BASE, "meeting_no": 3})
    with_str = segments_module.normalize_segment({**_BASE, "meeting_no": "3"})

    assert with_int["dedupe_hash"] != with_str["dedupe_hash"]


def test_normalize_segment_legacy_hash_equals_canonical_when_all_optional_fields_present(segments_module):
    # When every LEGACY_EMPTY_STRING_FIELDS member is already a non-empty string,
    # the legacy hash replaces nothing and must equal the canonical hash.
    full_payload = {
        "council": "A",
        "committee": "budget",
        "session": "301",
        "meeting_no": None,
        "meeting_date": "2026-02-17",
        "content": "some content",
        "summary": "summary text",
        "subject": "subject text",
        "party": "party-a",
        "constituency": "district-1",
        "department": "dept-x",
    }
    normalized = segments_module.normalize_segment(full_payload)

    assert normalized["dedupe_hash"] == normalized["dedupe_hash_legacy"]
