"""Timestamped per-session logging for CatWiz."""

import builtins
import os
import re
import sys
import time
from datetime import datetime

from .system import get_download_dir

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_MENU_OPTION = re.compile(r"^\s*(-?\d+)\.\s+(.+?)\s*$")
_ACTIVE_LOG = None
_ORIGINAL_INPUT = None


def _timestamp():
    now = time.time()
    whole = time.strftime("%H:%M:%S", time.localtime(now))
    centiseconds = int((now % 1) * 100)
    return f"[{whole}.{centiseconds:02d}]"


class _TeeStream:
    """Mirror terminal output and write timestamped, ANSI-free log lines."""

    def __init__(self, terminal, log_file):
        self.terminal = terminal
        self.log_file = log_file
        self.encoding = getattr(terminal, "encoding", None) or "utf-8"
        self.errors = getattr(terminal, "errors", None) or "replace"
        self._pending = ""
        self.menu_options = {}

    def write(self, value):
        written = self.terminal.write(value)
        try:
            clean = _ANSI_ESCAPE.sub("", str(value))
            self._pending += clean
            while "\n" in self._pending:
                line, self._pending = self._pending.split("\n", 1)
                self._write_line(line)
            # Progress bars commonly use carriage returns instead of newlines.
            if "\r" in self._pending:
                parts = self._pending.split("\r")
                self._pending = parts[-1]
                for line in parts[:-1]:
                    if line:
                        self._write_line(line)
        except (OSError, UnicodeError):
            pass
        return written

    def _write_line(self, line):
        match = _MENU_OPTION.match(line)
        if match:
            self.menu_options[match.group(1)] = match.group(2)
        self.log_file.write(f"{_timestamp()} {line}\n")
        self.log_file.flush()

    def log_input(self, prompt, value):
        clean_prompt = _ANSI_ESCAPE.sub("", str(prompt)).strip()
        selected = self.menu_options.get(str(value).strip())
        detail = f"selected={selected!r}; " if selected else ""
        self.log_file.write(
            f"{_timestamp()} [USER INPUT] {detail}"
            f"prompt={clean_prompt!r}; value={value!r}\n"
        )
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        try:
            if self._pending:
                self._write_line(self._pending)
                self._pending = ""
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


def _install_input_logging():
    global _ORIGINAL_INPUT
    if _ORIGINAL_INPUT is not None:
        return
    _ORIGINAL_INPUT = builtins.input

    def logged_input(prompt=""):
        if prompt:
            sys.stdout.write(str(prompt))
            sys.stdout.flush()
        value = _ORIGINAL_INPUT()
        stream = sys.stdout
        if isinstance(stream, _TeeStream):
            stream.log_input(prompt, value)
        return value

    builtins.input = logged_input


def stop_session_logging(log_file):
    """Restore process streams and close this session's log."""
    global _ORIGINAL_INPUT
    if _ORIGINAL_INPUT is not None:
        builtins.input = _ORIGINAL_INPUT
        _ORIGINAL_INPUT = None
    global _ACTIVE_LOG
    if log_file:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            log_file.close()
    _ACTIVE_LOG = None


def write_diagnostic(message):
    """Write an internal diagnostic line to the active session log."""
    if _ACTIVE_LOG:
        for line in str(message).splitlines() or [""]:
            _ACTIVE_LOG.write(f"{_timestamp()} [DIAGNOSTIC] {line}\n")
        _ACTIVE_LOG.flush()


def logged_yt_dlp_call(callback, *args, **kwargs):
    """Run third-party downloader code with stdout/stderr isolated to logs."""
    if not _ACTIVE_LOG:
        return callback(*args, **kwargs)

    class LogSink:
        encoding = "utf-8"
        errors = "replace"

        def write(self, value):
            if value:
                clean = _ANSI_ESCAPE.sub("", str(value))
                for line in clean.splitlines():
                    _ACTIVE_LOG.write(f"{_timestamp()} [YT-DLP] {line}\n")
                _ACTIVE_LOG.flush()
            return len(value)

        def flush(self):
            _ACTIVE_LOG.flush()

        def isatty(self):
            return False

        def writable(self):
            return True

    stdout, stderr = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = LogSink(), LogSink()
        return callback(*args, **kwargs)
    finally:
        sys.stdout, sys.stderr = stdout, stderr


def start_session_logging():
    """Overwrite logs.txt and capture timestamped output and user input."""
    global _ACTIVE_LOG
    try:
        directory = get_download_dir()
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "logs.txt")
        log_file = open(path, "w", encoding="utf-8", errors="replace", buffering=1)
        log_file.write(
            "CatWiz session log\n"
            f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
            f"Platform: {sys.platform}\n"
            "Timestamp format: local HH:MM:SS.centiseconds\n"
            + "=" * 72 + "\n"
        )
        log_file.flush()
    except OSError as error:
        print(f"Warning: could not start session logging: {error}", file=sys.stderr)
        return None

    _ACTIVE_LOG = log_file
    terminal_stdout, terminal_stderr = sys.stdout, sys.stderr
    # Normal CatWiz print/input remains visible on the actual terminal.
    sys.stdout = _TeeStream(terminal_stdout, log_file)
    sys.stderr = _TeeStream(terminal_stderr, log_file)
    _install_input_logging()
    return log_file
