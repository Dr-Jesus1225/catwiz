"""Central, privacy-first logging for CatWiz (CLI and desktop GUI)."""

import logging
import os
import platform
import shutil
import sys
import threading
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

from .logging_context import current_context, new_session_id, set_session_id
from .logging_redaction import redact_text

_LOCK = threading.RLock()
_LOGGER = logging.getLogger("catwiz")
_INITIALIZED = False
_LOG_DIR = None


class _ContextFilter(logging.Filter):
    def filter(self, record):
        record.session_id, record.download_id = current_context()
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


class _ActivityOnly(logging.Filter):
    def filter(self, record):
        return getattr(record, "activity_event", False)


class _ArchiveDailyHandler(TimedRotatingFileHandler):
    def __init__(self, filename, archive_dir):
        self.archive_dir = archive_dir
        super().__init__(
            filename, when="midnight", interval=1, backupCount=30,
            encoding="utf-8", delay=True, utc=False
        )
        self.namer = self._archive_name

    def _archive_name(self, default_name):
        return os.path.join(self.archive_dir, os.path.basename(default_name))


def _cleanup_archive(archive_dir):
    cutoff = datetime.now().timestamp() - 30 * 86400
    try:
        for name in os.listdir(archive_dir):
            path = os.path.join(archive_dir, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                continue
    except OSError:
        pass


def get_log_dir():
    return os.path.join(os.path.expanduser("~"), ".catwiz", "logs")


def get_log_paths():
    root = get_log_dir()
    return {
        "activity": os.path.join(root, "activity.log"),
        "diagnostics": os.path.join(root, "diagnostics.log"),
        "errors": os.path.join(root, "errors.log"),
        "archive": os.path.join(root, "archive"),
        "exports": os.path.join(root, "exports"),
    }


def get_logger():
    global _INITIALIZED, _LOG_DIR
    with _LOCK:
        if _INITIALIZED:
            return _LOGGER
        paths = get_log_paths()
        try:
            os.makedirs(paths["archive"], exist_ok=True)
            os.makedirs(paths["exports"], exist_ok=True)
            _LOG_DIR = os.path.dirname(paths["activity"])
            _LOGGER.setLevel(logging.DEBUG)
            _LOGGER.propagate = False
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)-8s [%(name)s:%(component)s] "
                "[session=%(session_id)s download=%(download_id)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            context_filter = _ContextFilter()

            diagnostics = _ArchiveDailyHandler(paths["diagnostics"], paths["archive"])
            diagnostics.setLevel(logging.DEBUG)
            diagnostics.setFormatter(formatter)
            diagnostics.addFilter(context_filter)
            _LOGGER.addHandler(diagnostics)

            activity = _ArchiveDailyHandler(paths["activity"], paths["archive"])
            activity.setLevel(logging.INFO)
            activity.setFormatter(formatter)
            activity.addFilter(context_filter)
            activity.addFilter(_ActivityOnly())
            _LOGGER.addHandler(activity)

            errors = _ArchiveDailyHandler(paths["errors"], paths["archive"])
            errors.setLevel(logging.WARNING)
            errors.setFormatter(formatter)
            errors.addFilter(context_filter)
            _LOGGER.addHandler(errors)

            _INITIALIZED = True
            _cleanup_archive(paths["archive"])
            set_session_id(new_session_id())
            _LOGGER.info(
                "Session started; platform=%s architecture=%s python=%s",
                sys.platform, platform.machine(), platform.python_version(),
                extra={"component": "startup"},
            )
            try:
                import yt_dlp
                _LOGGER.info("yt-dlp version=%s", yt_dlp.version.__version__,
                             extra={"component": "startup"})
            except Exception:
                _LOGGER.debug("yt-dlp version unavailable", extra={"component": "startup"})
        except OSError:
            # Logging is best-effort: it must never prevent CatWiz from starting.
            for handler in list(_LOGGER.handlers):
                _LOGGER.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass
            _INITIALIZED = False
        return _LOGGER


class _ComponentAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = dict(kwargs.get("extra") or {})
        extra.setdefault("component", self.extra.get("component", "app"))
        kwargs["extra"] = extra
        return redact_text(msg), kwargs


def component_logger(component):
    return _ComponentAdapter(get_logger(), {"component": component})


def log_activity(message, component="app", level=logging.INFO):
    logger = get_logger()
    logger.log(level, redact_text(message),
               extra={"component": component, "activity_event": True})


def log_exception(message, component="app", error=None):
    logger = component_logger(component)
    if error is None:
        logger.exception(message)
    else:
        logger.error("%s: %s", message, error, exc_info=(type(error), error, error.__traceback__))


def close_logging():
    global _INITIALIZED
    with _LOCK:
        for handler in list(_LOGGER.handlers):
            try:
                handler.flush()
                handler.close()
            finally:
                _LOGGER.removeHandler(handler)
        _INITIALIZED = False
