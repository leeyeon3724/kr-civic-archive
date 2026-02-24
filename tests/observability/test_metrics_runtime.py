def test_metrics_endpoint_exposes_prometheus_text(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in (resp.headers.get("content-type") or "")
    body = resp.text
    assert "civic_archive_http_requests_total" in body
    assert "civic_archive_http_request_duration_seconds" in body
    assert "civic_archive_db_query_duration_seconds" in body


def test_metrics_uses_low_cardinality_label_for_unmatched_route(client):
    unmatched_path = "/no-such-route-cardinality-unique-case"
    missing = client.get(unmatched_path)
    assert missing.status_code == 404

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert 'path="/_unmatched"' in body
    assert f'path="{unmatched_path}"' not in body
