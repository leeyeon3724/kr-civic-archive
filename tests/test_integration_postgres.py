from __future__ import annotations

import os
import time

import pytest
from conftest import (
    assert_payload_guard_metrics_use_route_template,
    assert_payload_too_large_response,
    build_test_config,
    build_test_jwt,
    oversized_echo_body,
)
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import create_app
from app.services.segments_service import normalize_segment

pytestmark = pytest.mark.integration


def _skip_if_not_enabled():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("Integration tests require RUN_INTEGRATION=1 and a running PostgreSQL instance.")


@pytest.fixture(scope="session")
def integration_client():
    _skip_if_not_enabled()
    app = create_app(build_test_config())
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_tables(integration_client):
    _skip_if_not_enabled()
    app = integration_client.app
    with app.state.connection_provider() as conn:
        conn.execute(
            text(
                """
                TRUNCATE TABLE
                  news_articles,
                  council_minutes,
                  council_speech_segments
                RESTART IDENTITY
                """
            )
        )


def test_news_upsert_and_update(integration_client):
    payload = {
        "source": "integration",
        "title": "integration news",
        "url": "https://example.com/news/int-1",
        "published_at": "2026-02-17T10:00:00Z",
    }
    first = integration_client.post("/api/news", json=payload)
    assert first.status_code == 201
    assert first.json() == {"inserted": 1, "updated": 0}

    payload["title"] = "integration news updated"
    second = integration_client.post("/api/news", json=payload)
    assert second.status_code == 201
    assert second.json() == {"inserted": 0, "updated": 1}

    listed = integration_client.get("/api/news", params={"source": "integration"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["title"] == "integration news updated"


def test_news_batch_with_duplicate_url_is_stable(integration_client):
    payload = [
        {
            "source": "integration-dup",
            "title": "integration dup news v1",
            "url": "https://example.com/news/int-dup-1",
            "published_at": "2026-02-17T10:00:00Z",
        },
        {
            "source": "integration-dup",
            "title": "integration dup news v2",
            "url": "https://example.com/news/int-dup-1",
            "published_at": "2026-02-17T10:00:00Z",
        },
    ]
    saved = integration_client.post("/api/news", json=payload)
    assert saved.status_code == 201
    assert saved.json() == {"inserted": 1, "updated": 0}

    listed = integration_client.get("/api/news", params={"source": "integration-dup"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["title"] == "integration dup news v2"


def test_news_date_range_includes_full_to_date(integration_client):
    payload = {
        "source": "integration-date-boundary",
        "title": "integration boundary news",
        "url": "https://example.com/news/int-boundary-1",
        "published_at": "2026-02-17T10:00:00Z",
    }
    saved = integration_client.post("/api/news", json=payload)
    assert saved.status_code == 201
    assert saved.json() == {"inserted": 1, "updated": 0}

    listed = integration_client.get(
        "/api/news",
        params={
            "source": "integration-date-boundary",
            "from": "2026-02-17",
            "to": "2026-02-17",
        },
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["url"] == "https://example.com/news/int-boundary-1"


def test_news_search_matches_non_contiguous_terms_via_fts(integration_client):
    payload = {
        "source": "integration-search",
        "title": "committee budget briefing",
        "url": "https://example.com/news/int-search-1",
        "published_at": "2026-02-17T10:00:00Z",
        "content": "budget policy report and follow-up details",
    }
    saved = integration_client.post("/api/news", json=payload)
    assert saved.status_code == 201

    listed = integration_client.get("/api/news", params={"q": "budget details"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["url"] == "https://example.com/news/int-search-1"


def test_minutes_upsert_and_filter(integration_client):
    payload = {
        "council": "seoul",
        "committee": "budget",
        "session": "301",
        "meeting_no": "301 4th",
        "url": "https://example.com/minutes/int-1",
        "meeting_date": "2026-02-17",
        "content": "minutes integration",
    }
    saved = integration_client.post("/api/minutes", json=payload)
    assert saved.status_code == 201
    assert saved.json() == {"inserted": 1, "updated": 0}

    listed = integration_client.get("/api/minutes", params={"council": "seoul", "from": "2026-02-01"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["council"] == "seoul"


def test_minutes_search_matches_non_contiguous_terms_via_fts(integration_client):
    payload = {
        "council": "seoul",
        "committee": "transport",
        "session": "301",
        "meeting_no": "301 5th",
        "url": "https://example.com/minutes/int-search-1",
        "meeting_date": "2026-02-17",
        "content": "agenda review with multi-step voting outcome",
    }
    saved = integration_client.post("/api/minutes", json=payload)
    assert saved.status_code == 201

    listed = integration_client.get("/api/minutes", params={"q": "agenda outcome"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["url"] == "https://example.com/minutes/int-search-1"


def test_minutes_batch_with_duplicate_url_is_stable(integration_client):
    payload = [
        {
            "council": "seoul",
            "committee": "budget",
            "session": "301",
            "meeting_no": "301 4th",
            "url": "https://example.com/minutes/int-dup-1",
            "meeting_date": "2026-02-17",
            "content": "minutes integration v1",
        },
        {
            "council": "seoul",
            "committee": "plenary",
            "session": "301",
            "meeting_no": "301 4th",
            "url": "https://example.com/minutes/int-dup-1",
            "meeting_date": "2026-02-17",
            "content": "minutes integration v2",
        },
    ]
    saved = integration_client.post("/api/minutes", json=payload)
    assert saved.status_code == 201
    assert saved.json() == {"inserted": 1, "updated": 0}

    listed = integration_client.get("/api/minutes", params={"council": "seoul"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["committee"] == "plenary"


def test_segments_search_matches_non_contiguous_terms_via_fts(integration_client):
    payload = {
        "council": "seoul",
        "committee": "budget",
        "session": "301",
        "meeting_no": "301 4th",
        "meeting_date": "2026-02-17",
        "summary": "finance committee hearing",
        "subject": "timeline update",
        "content": "segment integration with detailed notes",
        "importance": 2,
        "party": "party-a",
    }
    saved = integration_client.post("/api/segments", json=payload)
    assert saved.status_code == 201

    listed = integration_client.get("/api/segments", params={"q": "finance update"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["party"] == "party-a"


def test_segments_insert_and_filter(integration_client):
    payload = {
        "council": "seoul",
        "committee": "budget",
        "session": "301",
        "meeting_no": "301 4th",
        "meeting_date": "2026-02-17",
        "content": "segment integration",
        "importance": 2,
        "party": "party-a",
    }
    saved = integration_client.post("/api/segments", json=payload)
    assert saved.status_code == 201
    assert saved.json() == {"inserted": 1}

    duplicate = integration_client.post("/api/segments", json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json() == {"inserted": 0}

    listed = integration_client.get("/api/segments", params={"importance": 2, "party": "party-a"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["importance"] == 2


def test_segments_insert_skips_existing_legacy_hash_row(integration_client):
    payload = {
        "council": "seoul",
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
    normalized = normalize_segment(payload)
    legacy_hash = normalized["dedupe_hash_legacy"]
    assert legacy_hash is not None

    app = integration_client.app
    with app.state.connection_provider() as conn:
        conn.execute(
            text(
                """
                INSERT INTO council_speech_segments
                  (council, committee, "session", meeting_no, meeting_no_combined, meeting_date,
                   content, summary, subject, tag, importance, moderator, questioner, answerer,
                   party, constituency, department, dedupe_hash)
                VALUES
                  (:council, :committee, :session, :meeting_no, :meeting_no_combined, :meeting_date,
                   :content, :summary, :subject, :tag, :importance, :moderator, :questioner, :answerer,
                   :party, :constituency, :department, :dedupe_hash)
                """
            ),
            {
                "council": normalized["council"],
                "committee": "",
                "session": "",
                "meeting_no": normalized["meeting_no"],
                "meeting_no_combined": "",
                "meeting_date": normalized["meeting_date"],
                "content": "",
                "summary": "",
                "subject": "",
                "tag": None,
                "importance": normalized["importance"],
                "moderator": None,
                "questioner": None,
                "answerer": None,
                "party": "",
                "constituency": "",
                "department": "",
                "dedupe_hash": legacy_hash,
            },
        )

    duplicate = integration_client.post("/api/segments", json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json() == {"inserted": 0}

    listed = integration_client.get("/api/segments", params={"council": "seoul"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_error_schema_contains_standard_fields(integration_client):
    missing = integration_client.get("/api/news/99999")
    assert missing.status_code == 404
    body = missing.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Not Found"
    assert body["error"] == "Not Found"
    assert body.get("request_id")
    assert missing.headers.get("X-Request-Id") == body["request_id"]


def test_request_id_passthrough(integration_client):
    req_id = "integration-request-id-1"
    resp = integration_client.get("/health", headers={"X-Request-Id": req_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") == req_id


def test_metrics_endpoint_available(integration_client):
    resp = integration_client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in (resp.headers.get("content-type") or "")
    assert "civic_archive_http_requests_total" in resp.text


def test_runtime_jwt_authorization_path():
    _skip_if_not_enabled()
    secret = "integration-jwt-secret-0123456789"
    now = int(time.time())
    read_token = build_test_jwt(
        secret,
        {
            "sub": "integration-read",
            "scope": "archive:read",
            "exp": now + 300,
        },
    )
    write_token = build_test_jwt(
        secret,
        {
            "sub": "integration-write",
            "scope": "archive:write archive:read",
            "exp": now + 300,
        },
    )
    app = create_app(build_test_config(REQUIRE_JWT=True, JWT_SECRET=secret))
    with TestClient(app) as client:
        unauthorized = client.post("/api/echo", json={"hello": "world"})
        assert unauthorized.status_code == 401
        assert unauthorized.json()["code"] == "UNAUTHORIZED"

        forbidden = client.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {read_token}"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "FORBIDDEN"

        authorized = client.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {write_token}"},
        )
        assert authorized.status_code == 200
        assert authorized.json() == {"you_sent": {"hello": "world"}}


def test_payload_guard_returns_standard_413_shape():
    _skip_if_not_enabled()
    app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))
    with TestClient(app) as client:
        body = oversized_echo_body()
        response = client.post(
            "/api/echo",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        payload = assert_payload_too_large_response(response, max_request_body_bytes=64)
        assert payload["error"] == "Payload Too Large"
        assert payload["details"]["content_length"] > 64
        assert payload.get("request_id")
        assert response.headers.get("X-Request-Id") == payload["request_id"]


def test_metrics_label_for_guard_failure_uses_route_template():
    _skip_if_not_enabled()
    app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))
    with TestClient(app) as client:
        assert_payload_guard_metrics_use_route_template(client)
