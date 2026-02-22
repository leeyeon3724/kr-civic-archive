"""
E2E tests for live API server.
Run examples:
  pytest -m e2e --base-url http://localhost:8000
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import pytest

requests = pytest.importorskip("requests", reason="Install requests to run E2E tests: pip install requests")

pytestmark = pytest.mark.e2e


class APIClient:
    def __init__(self, base_url: str, timeout: int = 20) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.json_headers = {"Content-Type": "application/json; charset=utf-8"}

    def get(self, path: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None):
        return self.session.get(f"{self.base}{path}", params=params, headers=headers, timeout=self.timeout)

    def post(self, path: str, payload: Any, *, headers: dict[str, str] | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        merged_headers = dict(self.json_headers)
        if headers:
            merged_headers.update(headers)
        return self.session.post(f"{self.base}{path}", headers=merged_headers, data=body, timeout=self.timeout)

    def delete(self, path: str, *, headers: dict[str, str] | None = None):
        return self.session.delete(f"{self.base}{path}", headers=headers, timeout=self.timeout)


@pytest.fixture(scope="module", autouse=True)
def ensure_e2e_target_reachable(request) -> None:
    base_url = request.config.getoption("--base-url").rstrip("/")
    require_target = os.getenv("E2E_REQUIRE_TARGET") == "1"
    probe_url = f"{base_url}/health"
    try:
        requests.get(probe_url, timeout=3)
    except requests.RequestException as exc:
        if require_target:
            pytest.fail(f"E2E target is unreachable: {probe_url} ({exc.__class__.__name__})")
        pytest.skip(f"E2E target is unreachable: {probe_url} ({exc.__class__.__name__})")


@pytest.fixture(scope="module")
def api(request) -> APIClient:
    return APIClient(request.config.getoption("--base-url"))


@pytest.fixture(scope="module")
def token() -> str:
    return f"TESTRUN-{uuid.uuid4()}"


@pytest.fixture(scope="module")
def created_ids() -> dict[str, list[int]]:
    return {"news": [], "minutes": [], "segments": []}


def _extract_ids(payload: dict[str, Any]) -> list[int]:
    items = payload.get("items", [])
    return [item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), int)]


def test_health(api: APIClient):
    response = api.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("X-Request-Id")


def test_request_id_roundtrip(api: APIClient):
    request_id = "e2e-request-id-1"
    response = api.get("/health", headers={"X-Request-Id": request_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-Id") == request_id


def test_news_upsert_single(api: APIClient, token: str):
    payload = {
        "title": f"[E2E] news single :: {token}",
        "url": f"https://example.com/e2e-news-a-{token.lower()}",
        "published_at": "2024-06-15T09:00:00Z",
        "source": "e2e-source",
        "author": "e2e-author",
        "content": f"e2e content {token}",
    }
    response = api.post("/api/news", payload)
    assert response.status_code == 201
    body = response.json()
    assert body["inserted"] == 1
    assert body["updated"] == 0


def test_news_upsert_batch(api: APIClient, token: str):
    payload = [
        {
            "title": f"[E2E] news batch 1 :: {token}",
            "url": f"https://example.com/e2e-news-b1-{token.lower()}",
            "published_at": "2024-06-16T10:30:00Z",
            "source": "e2e-source",
            "content": f"e2e batch 1 {token}",
        },
        {
            "title": f"[E2E] news batch 2 :: {token}",
            "url": f"https://example.com/e2e-news-b2-{token.lower()}",
            "published_at": "2024-06-17T11:45:00Z",
            "source": "e2e-source",
            "content": f"e2e batch 2 {token}",
        },
    ]
    response = api.post("/api/news", payload)
    assert response.status_code == 201
    assert response.json()["inserted"] == 2


def test_news_list_and_detail(api: APIClient, token: str, created_ids: dict[str, list[int]]):
    listed = api.get("/api/news", params={"q": token, "size": 100})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1

    ids = _extract_ids(body)
    created_ids["news"].extend(ids)
    assert ids

    detail = api.get(f"/api/news/{ids[0]}")
    assert detail.status_code == 200
    assert detail.json()["id"] == ids[0]


def test_news_delete(api: APIClient, created_ids: dict[str, list[int]]):
    for item_id in created_ids["news"]:
        response = api.delete(f"/api/news/{item_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
    created_ids["news"].clear()


def test_minutes_upsert_single(api: APIClient, token: str):
    payload = {
        "council": "seoul",
        "committee": "budget",
        "session": "301",
        "meeting_no": "301 1th",
        "url": f"https://example.com/meetings/e2e-{token.lower()}",
        "meeting_date": "2024-06-15",
        "content": f"[E2E] minutes content {token}",
        "tag": ["e2e"],
        "attendee": {"count": 1},
        "agenda": [f"agenda-1-{token}"],
    }
    response = api.post("/api/minutes", payload)
    assert response.status_code == 201
    assert response.json()["inserted"] == 1


def test_minutes_upsert_batch(api: APIClient, token: str):
    payload = [
        {
            "council": "seoul",
            "committee": "plenary",
            "session": "301",
            "meeting_no": "301 2th",
            "url": f"https://example.com/meetings/e2e-b1-{token.lower()}",
            "meeting_date": "2024-06-16",
            "content": f"[E2E] minutes b1 {token}",
        },
        {
            "council": "busan",
            "committee": "budget",
            "session": "100",
            "meeting_no": "100 1th",
            "url": f"https://example.com/meetings/e2e-b2-{token.lower()}",
            "meeting_date": "2024-07-01",
            "content": f"[E2E] minutes b2 {token}",
        },
    ]
    response = api.post("/api/minutes", payload)
    assert response.status_code == 201
    assert response.json()["inserted"] == 2


def test_minutes_list_and_detail(api: APIClient, token: str, created_ids: dict[str, list[int]]):
    listed = api.get("/api/minutes", params={"q": token, "size": 100})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1

    ids = _extract_ids(body)
    created_ids["minutes"].extend(ids)
    assert ids

    detail = api.get(f"/api/minutes/{ids[0]}")
    assert detail.status_code == 200
    assert detail.json()["id"] == ids[0]


def test_minutes_delete(api: APIClient, created_ids: dict[str, list[int]]):
    for item_id in created_ids["minutes"]:
        response = api.delete(f"/api/minutes/{item_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
    created_ids["minutes"].clear()


def test_segments_insert_single(api: APIClient, token: str):
    payload = {
        "council": "seoul",
        "committee": "plenary",
        "session": "301",
        "meeting_no": "301 1th",
        "meeting_date": "2024-06-15",
        "content": f"[E2E] segment content a {token}",
        "summary": "e2e summary a",
        "subject": f"[E2E] segment subject a {token}",
        "importance": 2,
        "questioner": {"name": "member"},
        "answerer": [{"name": "official", "title": "director"}],
    }
    response = api.post("/api/segments", payload)
    assert response.status_code == 201
    assert response.json()["inserted"] == 1


def test_segments_insert_batch(api: APIClient, token: str):
    payload = [
        {
            "council": "seoul",
            "meeting_date": "2024-06-15",
            "content": f"[E2E] segment b1 {token}",
            "importance": 1,
        },
        {
            "council": "busan",
            "meeting_date": "2024-07-01",
            "content": f"[E2E] segment b2 {token}",
            "importance": 3,
        },
    ]
    response = api.post("/api/segments", payload)
    assert response.status_code == 201
    assert response.json()["inserted"] == 2


def test_segments_list_and_detail(api: APIClient, token: str, created_ids: dict[str, list[int]]):
    listed = api.get("/api/segments", params={"q": token, "size": 100})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1

    ids = _extract_ids(body)
    created_ids["segments"].extend(ids)
    assert ids

    detail = api.get(f"/api/segments/{ids[0]}")
    assert detail.status_code == 200
    assert detail.json()["id"] == ids[0]


def test_segments_delete(api: APIClient, created_ids: dict[str, list[int]]):
    for item_id in created_ids["segments"]:
        response = api.delete(f"/api/segments/{item_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
    created_ids["segments"].clear()
