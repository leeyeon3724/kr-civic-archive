from typing import Any, Callable, Dict, List, Optional
import base64
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Config


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        default="http://localhost:8000",
        help="E2E 테스트 대상 서버 URL (기본: http://localhost:8000)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: 라이브 서버 대상 E2E 테스트")
    config.addinivalue_line("markers", "integration: PostgreSQL 컨테이너 기반 통합 테스트")


def build_test_config(**overrides: Any) -> Config:
    defaults: dict[str, Any] = {
        "APP_ENV": "test",
        "LOG_LEVEL": "WARNING",
        "LOG_JSON": False,
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": 5432,
        "POSTGRES_USER": "app_user",
        "POSTGRES_PASSWORD": "change_me",
        "POSTGRES_DB": "civic_archive",
        "REQUIRE_API_KEY": False,
        "REQUIRE_JWT": False,
        "RATE_LIMIT_PER_MINUTE": 0,
        "RATE_LIMIT_BACKEND": "memory",
        "SECURITY_STRICT_MODE": False,
    }
    defaults.update(overrides)
    return Config.model_validate(defaults)


def build_test_jwt(secret: str, claims: Dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}

    def _encode(value: Dict[str, Any]) -> str:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    header_b64 = _encode(header)
    payload_b64 = _encode(claims)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def extract_first_select_params(engine: "StubEngine") -> Dict[str, Any]:
    first_select = next(
        c for c in engine.connection.calls if isinstance(c.get("params"), dict) and "limit" in c["params"]
    )
    return first_select["params"]


def oversized_echo_body(*, payload_size: int = 200) -> str:
    return '{"payload":"' + ("x" * payload_size) + '"}'


def assert_payload_too_large_response(response: Any, *, max_request_body_bytes: int) -> Dict[str, Any]:
    assert response.status_code == 413
    payload = response.json()
    assert payload["code"] == "PAYLOAD_TOO_LARGE"
    assert payload["message"] == "Payload Too Large"
    assert payload["details"]["max_request_body_bytes"] == max_request_body_bytes
    return payload


def metric_counter_value(metrics_text: str, *, method: str, path: str, status_code: str) -> float:
    prefix = (
        "civic_archive_http_requests_total{"
        f'method="{method}",path="{path}",status_code="{status_code}"'
        "} "
    )
    for line in metrics_text.splitlines():
        if line.startswith(prefix):
            return float(line[len(prefix) :])
    return 0.0


def assert_payload_guard_metrics_use_route_template(client: Any) -> None:
    before_metrics = client.get("/metrics")
    assert before_metrics.status_code == 200
    before_echo_413 = metric_counter_value(
        before_metrics.text, method="POST", path="/api/echo", status_code="413"
    )
    before_unmatched_413 = metric_counter_value(
        before_metrics.text, method="POST", path="/_unmatched", status_code="413"
    )

    oversized = client.post(
        "/api/echo",
        content=oversized_echo_body(),
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 413
    assert oversized.json()["code"] == "PAYLOAD_TOO_LARGE"

    after_metrics = client.get("/metrics")
    assert after_metrics.status_code == 200
    after_echo_413 = metric_counter_value(
        after_metrics.text, method="POST", path="/api/echo", status_code="413"
    )
    after_unmatched_413 = metric_counter_value(
        after_metrics.text, method="POST", path="/_unmatched", status_code="413"
    )

    assert after_echo_413 == before_echo_413 + 1
    assert after_unmatched_413 == before_unmatched_413


class StubResult:
    def __init__(
        self,
        *,
        rowcount: int = 0,
        rows: Optional[List[Dict[str, Any]]] = None,
        scalar_value: Optional[Any] = None,
    ) -> None:
        self.rowcount = rowcount
        self._rows = rows or []
        self._scalar_value = scalar_value

    def mappings(self) -> "StubResult":
        return self

    def all(self) -> List[Dict[str, Any]]:
        return self._rows

    def first(self) -> Optional[Dict[str, Any]]:
        return self._rows[0] if self._rows else None

    def scalar(self) -> Optional[Any]:
        return self._scalar_value


class StubConnection:
    def __init__(self, handler: Callable[[Any, Optional[Dict[str, Any]]], StubResult]) -> None:
        self._handler = handler
        self.calls: List[Dict[str, Any]] = []

    def execute(self, statement: Any, params: Optional[Dict[str, Any]] = None) -> StubResult:
        self.calls.append(
            {
                "statement": str(statement),
                "statement_obj": statement,
                "params": params,
            }
        )
        return self._handler(statement, params)


class StubBeginContext:
    def __init__(self, connection: StubConnection) -> None:
        self._connection = connection

    def __enter__(self) -> StubConnection:
        return self._connection

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


class StubEngine:
    def __init__(self, handler: Optional[Callable[[Any, Optional[Dict[str, Any]]], StubResult]] = None) -> None:
        if handler is None:
            def _default_handler(_statement, _params):
                return StubResult()

            handler = _default_handler
        self.connection = StubConnection(handler)

    def begin(self) -> StubBeginContext:
        return StubBeginContext(self.connection)


class ResponseAdapter:
    def __init__(self, response):
        self._response = response

    @property
    def status_code(self):
        return self._response.status_code

    def get_json(self):
        return self._response.json()

    def json(self):
        return self._response.json()

    def __getattr__(self, item):
        return getattr(self._response, item)


class ClientAdapter:
    def __init__(self, client: TestClient):
        self._client = client

    @staticmethod
    def _normalize_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(kwargs)
        content_type = normalized.pop("content_type", None)
        if content_type:
            headers = dict(normalized.get("headers") or {})
            headers["Content-Type"] = content_type
            normalized["headers"] = headers
            if "data" in normalized and "content" not in normalized:
                normalized["content"] = normalized.pop("data")
        return normalized

    def get(self, *args, **kwargs):
        return ResponseAdapter(self._client.get(*args, **self._normalize_kwargs(kwargs)))

    def post(self, *args, **kwargs):
        return ResponseAdapter(self._client.post(*args, **self._normalize_kwargs(kwargs)))

    def delete(self, *args, **kwargs):
        return ResponseAdapter(self._client.delete(*args, **self._normalize_kwargs(kwargs)))

    def request(self, *args, **kwargs):
        return ResponseAdapter(self._client.request(*args, **self._normalize_kwargs(kwargs)))


@pytest.fixture(scope="session")
def app_instance():
    import_engine = StubEngine()
    with patch("app.database.create_engine", return_value=import_engine):
        from app import create_app

        api = create_app(build_test_config())
    api._bootstrap_engine_for_test = import_engine
    return api


@pytest.fixture(scope="session")
def db_module():
    from app import database

    return database


@pytest.fixture(scope="session")
def utils_module():
    from app import utils

    return utils


@pytest.fixture(scope="session")
def news_module():
    from app.services import news_service as news

    return news


@pytest.fixture(scope="session")
def minutes_module():
    from app.services import minutes_service as minutes

    return minutes


@pytest.fixture(scope="session")
def segments_module():
    from app.services import segments_service as segments

    return segments


@pytest.fixture
def client(app_instance):
    with TestClient(app_instance) as tc:
        yield ClientAdapter(tc)


@pytest.fixture
def override_dependency(app_instance):
    def _override(dependency, provider):
        app_instance.dependency_overrides[dependency] = provider

    yield _override
    app_instance.dependency_overrides.clear()


@pytest.fixture
def make_engine():
    def _factory(handler: Callable[[Any, Optional[Dict[str, Any]]], StubResult]) -> StubEngine:
        return StubEngine(handler=handler)

    return _factory


@pytest.fixture
def make_connection_provider(make_engine):
    def _factory(handler: Callable[[Any, Optional[Dict[str, Any]]], StubResult]):
        engine = make_engine(handler)
        return engine.begin, engine

    return _factory


@pytest.fixture
def use_stub_connection_provider(app_instance, make_engine):
    original_provider = app_instance.state.connection_provider
    original_engine = getattr(app_instance.state, "db_engine", None)

    def _use(handler: Callable[[Any, Optional[Dict[str, Any]]], StubResult]) -> StubEngine:
        engine = make_engine(handler)
        app_instance.state.connection_provider = engine.begin
        app_instance.state.db_engine = engine
        return engine

    yield _use
    app_instance.state.connection_provider = original_provider
    app_instance.state.db_engine = original_engine
