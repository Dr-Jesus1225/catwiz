"""Privacy-first redaction helpers for CatWiz logs and diagnostic exports."""

import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_SECRET_KEY = re.compile(
    r"(cookie|authorization|proxy-authorization|password|passwd|token|"
    r"api[_-]?key|secret|session|credential|auth)", re.IGNORECASE
)
_ASSIGNMENT = re.compile(
    r"""(?i)(\b(?:cookie|set-cookie|authorization|proxy-authorization|password|passwd|token|api[_-]?key|secret|session(?:id)?|credential)\b\s*[:=]\s*)([^\s,;]+(?:\s+[^,;]+)?)"""
)
_BEARER = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
_SENSITIVE_LINE = re.compile(r"(?im)(\b(?:cookie|set-cookie|authorization|proxy-authorization)\b\s*[:=]\s*)[^\r\n]+")
_URL = re.compile(r"https?://[^\s'\"<>]+")


def redact_url(value):
    """Remove URL query and fragment values, retaining the useful host/path."""
    try:
        parts = urlsplit(value)
        if not parts.scheme or not parts.netloc:
            return value
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        safe_query = urlencode([
            (key, "[REDACTED]" if _SECRET_KEY.search(key) else "[REDACTED]")
            for key, _ in parse_qsl(parts.query, keep_blank_values=True)
        ]) if parts.query else ""
        return urlunsplit((parts.scheme, host, parts.path, safe_query, ""))
    except (TypeError, ValueError):
        return "[REDACTED_URL]"


def redact_text(value):
    """Redact common credential patterns and URL query strings."""
    text = str(value)
    text = _SENSITIVE_LINE.sub(r"\1[REDACTED]", text)
    text = _BEARER.sub(r"\1 [REDACTED]", text)
    text = _ASSIGNMENT.sub(r"\1[REDACTED]", text)
    return _URL.sub(lambda match: redact_url(match.group(0)), text)


def redact_mapping(mapping):
    """Return a shallow sanitized copy of a mapping."""
    if not isinstance(mapping, dict):
        return {}
    clean = {}
    for key, value in mapping.items():
        if _SECRET_KEY.search(str(key)):
            clean[key] = "[REDACTED]"
        elif isinstance(value, str):
            clean[key] = redact_text(value)
        elif isinstance(value, dict):
            clean[key] = redact_mapping(value)
        elif isinstance(value, (list, tuple)):
            clean[key] = [
                redact_text(item) if isinstance(item, str)
                else redact_mapping(item) if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            clean[key] = value
    return clean
