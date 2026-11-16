"""Context identifiers shared by CatWiz logging components."""

import contextvars
import uuid

_session_id = contextvars.ContextVar("catwiz_session_id", default="-")
_download_id = contextvars.ContextVar("catwiz_download_id", default="-")


def new_session_id():
    return uuid.uuid4().hex[:12]


def new_download_id():
    return uuid.uuid4().hex[:8]


def set_session_id(value):
    return _session_id.set(value)


def set_download_id(value):
    return _download_id.set(value)


def reset_context(token, kind="session"):
    ( _session_id if kind == "session" else _download_id).reset(token)


def current_context():
    return _session_id.get(), _download_id.get()
