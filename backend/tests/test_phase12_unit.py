"""Phase 12 deterministic productionization checks."""

import pytest

from app.core.metrics import prometheus_text, record_request

pytestmark = pytest.mark.unit


def test_metrics_are_prometheus_compatible_and_include_request_dimensions():
    record_request("GET", "/api/v1/health", 200, 0.01)
    output = prometheus_text()
    assert "# TYPE apiforge_http_requests_total counter" in output
    assert 'method="GET"' in output
    assert 'path="/api/v1/health"' in output
    assert 'status="200"' in output
