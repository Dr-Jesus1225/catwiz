"""Capture each CatWiz session in a fresh logs.txt beside downloaded files."""

import os
import re
import sys
from datetime import datetime

from .system import get_download_dir

_ANSI_ESCAPE = re.compile(r"\x1b\\[[0-?]*[ -/]*[@-~]")


class _TeeStream:
    """Write to the original terminal and the current session log."""

    def __init__(self, terminal, log_file):
        self.terminal = terminal
        self.log_file = log_file
        self.encoding = getattr(terminal, "encoding", None) or "utf-8"
        self.errors = getattr(terminal, "errors", None) or "replace"

    def write(self, value):
        written = self.terminal.write(value)
        try:
            clean = _ANSI_ESCAPE.sub("", value)
            self.log_file.write(clean)
            self.log_file.flush()
        except (OSError, UnicodeError):
            pass
        return written

    def flush(self):
        self.terminal.flush()
        try:
            self.log_file.flush()
        except OSError:
            pass

    def isatty(self):
        return self.terminal.isatty()

    def fileno(self):
        return self.terminal.fileno()

    def writable(self):
        return True

    def __getattr__(self, name):
        return getattr(self.terminal, name)


def start_session_logging():
    """Overwrite logs.txt and tee all subsequent stdout/stderr to it."""
    try:
        directory = get_download_dir()
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "logs.txt")
        log_file = open(path, "w", encoding="utf-8", errors="replace", buffering=1)
        log_file.write(
            "CatWiz session log\n"
            f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
            f"Platform: {sys.platform}\n"
            + "=" * 72 + "\n"
        )
        log_file.flush()
    except OSError as error:
        print(f"Warning: could not start session logging: {error}", file=sys.stderr)
        return None

    sys.stdout = _TeeStream(sys.stdout, log_file)
    sys.stderr = _TeeStream(sys.stderr, log_file)
    return log_file
