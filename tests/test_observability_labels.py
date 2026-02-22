from unittest.mock import patch

from fastapi.testclient import TestClient
from conftest import StubResult, assert_payload_guard_metrics_use_route_template, build_test_config

from app import create_app

def test_metrics_uses_route_template_label_for_payload_guard_failure(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))

    with TestClient(app) as tc:
        assert_payload_guard_metrics_use_route_template(tc)
