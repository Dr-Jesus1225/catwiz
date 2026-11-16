"""Compatibility wrappers routing existing CLI and yt-dlp diagnostics centrally."""

from .logging_service import component_logger, get_logger, log_activity
from .logging_context import new_download_id, set_download_id, reset_context


def start_session_logging():
    """Initialize central logging without capturing terminal output or input."""
    get_logger()
    log_activity("CLI session started", component="cli")
    return True


def stop_session_logging(log_handle=None):
    """Record session end; process shutdown owns handler cleanup."""
    log_activity("CLI session ended", component="cli")


def write_diagnostic(message):
    component_logger("diagnostic").debug("%s", message)


class YtDlpSessionLogger:
    """Adapter accepted by yt-dlp; technical messages stay out of the terminal."""

    def debug(self, message):
        component_logger("yt-dlp").debug("%s", message)

    def info(self, message):
        component_logger("yt-dlp").info("%s", message)

    def warning(self, message):
        component_logger("yt-dlp").warning("%s", message)

    def error(self, message):
        component_logger("yt-dlp").error("%s", message)


def run_yt_dlp(options, action, *args, **kwargs):
    """Construct YoutubeDL and execute the requested action."""
    import yt_dlp

    options = dict(options)
    options.setdefault("logger", YtDlpSessionLogger())
    download_token = set_download_id(new_download_id())
    log_activity("Downloader operation started", component="downloader")
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            result = action(ydl, *args, **kwargs)
        log_activity("Downloader operation completed", component="downloader")
        return result
    except Exception:
        component_logger("downloader").exception("Downloader operation failed")
        log_activity("Downloader operation failed", component="downloader", level=40)
        raise
    finally:
        reset_context(download_token, kind="download")
