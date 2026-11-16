"""Central, privacy-first logging for CatWiz (CLI and desktop GUI)."""

import logging
import os
import platform
import sys
import threading
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from .logging_context import current_context, new_session_id, set_session_id
from .logging_redaction import redact_text

_LOCK = threading.RLock()
_LOGGER = logging.getLogger("catwiz")
_INITIALIZED = False


def _install_exception_hooks():
    def handle_main_exception(exc_type, exc_value, traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, traceback)
            return
        _LOGGER.error("Unhandled application exception",
                      exc_info=(exc_type, exc_value, traceback),
                      extra={"component": "uncaught"})
        try:
            sys.__stderr__.write("CatWiz encountered an unexpected error. Details were saved in ~/.catwiz/logs/errors.log.\n")
        except Exception:
            pass

    def handle_thread_exception(args):
        _LOGGER.error("Unhandled background-thread exception",
                      exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                      extra={"component": "background"})

    sys.excepthook = handle_main_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception


class _RedactingFormatter(logging.Formatter):
    def formatException(self, exc_info):
        return redact_text(super().formatException(exc_info))


class _ContextFilter(logging.Filter):
    def filter(self, record):
        record.session_id, record.download_id = current_context()
        record.component = getattr(record, "component", "app")
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
        self.max_bytes = 5 * 1024 * 1024

    def emit(self, record):
        try:
            if os.path.isfile(self.baseFilename) and os.path.getsize(self.baseFilename) >= self.max_bytes:
                if self.stream:
                    self.stream.close()
                    self.stream = None
                suffix = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
                archive_name = os.path.join(self.archive_dir, os.path.basename(self.baseFilename) + "." + suffix)
                os.replace(self.baseFilename, archive_name)
        except OSError:
            pass
        super().emit(record)

    def _archive_name(self, default_name):
        return os.path.join(self.archive_dir, os.path.basename(default_name))

    def _open(self):
        stream = super()._open()
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError:
            pass
        return stream


def _cleanup_archive(archive_dir):
    cutoff = datetime.now().timestamp() - 30 * 86400
    try:
        for name in os.listdir(archive_dir):
            path = os.path.join(archive_dir, name)
            try:
                if name == "legacy-logs-migrated.txt":
                    continue
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


def _migrate_legacy_log(paths):
    """Copy the old download-folder log once, sanitized; never delete the original."""
    marker = os.path.join(paths["archive"], "legacy-logs-migrated.txt")
    if os.path.exists(marker):
        return
    try:
        from .system import get_download_dir
        old_path = os.path.join(get_download_dir(), "logs.txt")
        if os.path.isfile(old_path):
            from .logging_redaction import redact_text
            with open(old_path, "r", encoding="utf-8", errors="replace") as source:
                safe_contents = "\n".join(
                    line for line in redact_text(source.read()).splitlines()
                    if "[USER INPUT]" not in line
                )
            with open(os.path.join(paths["archive"], "legacy-logs.txt"), "w", encoding="utf-8") as target:
                target.write(safe_contents)
        with open(marker, "w", encoding="utf-8") as stream:
            stream.write("Legacy log migration checked; original logs.txt was not modified.\n")
    except OSError:
        # A later startup can retry if the user's download folder is unavailable.
        pass


def get_logger():
    global _INITIALIZED
    with _LOCK:
        if _INITIALIZED:
            return _LOGGER
        paths = get_log_paths()
        try:
            os.makedirs(paths["archive"], exist_ok=True)
            os.makedirs(paths["exports"], exist_ok=True)
            try:
                os.chmod(get_log_dir(), 0o700)
                os.chmod(paths["archive"], 0o700)
                os.chmod(paths["exports"], 0o700)
            except OSError:
                pass
            _migrate_legacy_log(paths)
            _LOGGER.setLevel(logging.DEBUG)
            _LOGGER.propagate = False
            formatter = _RedactingFormatter(
                "%(asctime)s %(levelname)-8s [%(name)s:%(component)s] "
                "[session=%(session_id)s download=%(download_id)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            context_filter = _ContextFilter()

            for filename, level, activity_only in (
                (paths["diagnostics"], logging.DEBUG, False),
                (paths["activity"], logging.INFO, True),
                (paths["errors"], logging.WARNING, False),
            ):
                handler = _ArchiveDailyHandler(filename, paths["archive"])
                handler.setLevel(level)
                handler.setFormatter(formatter)
                handler.addFilter(context_filter)
                if activity_only:
                    handler.addFilter(_ActivityOnly())
                _LOGGER.addHandler(handler)

            _INITIALIZED = True
            _install_exception_hooks()
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
        logger.error("%s: %s", message, error,
                     exc_info=(type(error), error, error.__traceback__))


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
