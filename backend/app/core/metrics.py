"""Lightweight Prometheus-compatible application metrics.

Metrics are intentionally dependency-free and process-local. In production,
scale APIForge horizontally and scrape each instance separately or aggregate
at the monitoring layer.
"""

from collections import Counter, defaultdict
from threading import Lock

_lock = Lock()
_request_count: Counter[tuple[str, str, str]] = Counter()
_request_duration_seconds: defaultdict[tuple[str, str], float] = defaultdict(float)


def record_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    key = (method.upper(), path, str(status_code))
    with _lock:
        _request_count[key] += 1
        _request_duration_seconds[(method.upper(), path)] += duration_seconds


def prometheus_text() -> str:
    lines = [
        "# HELP apiforge_http_requests_total Total HTTP requests handled by this process.",
        "# TYPE apiforge_http_requests_total counter",
    ]
    with _lock:
        for (method, path, status), count in sorted(_request_count.items()):
            lines.append(
                f'apiforge_http_requests_total{{method="{_escape(method)}",path="{_escape(path)}",status="{_escape(status)}"}} {count}'
            )
        lines.extend([
            "# HELP apiforge_http_request_duration_seconds_total Total request duration in seconds.",
            "# TYPE apiforge_http_request_duration_seconds_total counter",
        ])
        for (method, path), duration in sorted(_request_duration_seconds.items()):
            lines.append(
                f'apiforge_http_request_duration_seconds_total{{method="{_escape(method)}",path="{_escape(path)}"}} {duration:.6f}'
            )
    return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
