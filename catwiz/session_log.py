"""Compatibility wrappers routing existing CLI and yt-dlp diagnostics centrally."""

from .logging_service import component_logger, get_logger, log_activity


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
    with yt_dlp.YoutubeDL(options) as ydl:
        return action(ydl, *args, **kwargs)
