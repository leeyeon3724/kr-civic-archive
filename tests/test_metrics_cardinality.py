def test_metrics_normalizes_unknown_http_method_to_other(client):
    resp = client.request("BREW", "/health")
    assert resp.status_code == 405

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert 'method="OTHER",path="/health",status_code="405"' in body
    assert 'method="BREW"' not in body
