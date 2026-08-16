import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEY_RE = re.compile(
    r"(authorization|proxy[-_]?authorization|cookie|set[-_]?cookie|api[-_]?key|x[-_]?auth[-_]?token|access[-_]?token|refresh[-_]?token|password|passwd|secret|credential|client[-_]?secret|private[-_]?key|token)",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    return bool(SENSITIVE_KEY_RE.search(str(key)))


def redact_mapping(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if is_sensitive_key(key) else redact_mapping(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    return value


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value
    return json.dumps(redact_mapping(parsed), separators=(",", ":"))


def redact_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parts = urlsplit(value)
        query = [
            (key, "[REDACTED]" if is_sensitive_key(key) else val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    except ValueError:
        return value


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: "[REDACTED]" if is_sensitive_key(key) else value
        for key, value in headers.items()
    }
