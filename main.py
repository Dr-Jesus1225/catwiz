"""CatWiz entry point."""
import os
import sys

from catwiz.app import main
from catwiz.session_log import start_session_logging, stop_session_logging

RESTART_EXIT_CODE = 75


def run():
    # Prefer the desktop GUI when PySide6 is installed. The CLI remains
    # available everywhere through the --cli argument and as a fallback.
    if "--cli" not in sys.argv:
        try:
            from catwiz.system import platform_key
            if platform_key() != "termux":
                from gui.app import run as run_gui
                raise SystemExit(run_gui())
        except ImportError:
            pass

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_file = start_session_logging()
    restart = False
    try:
        try:
            main()
        except KeyboardInterrupt:
            return
        except SystemExit as error:
            if error.code == RESTART_EXIT_CODE:
                restart = True
            else:
                raise
    finally:
        if log_file:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                stop_session_logging(log_file)

    if restart:
        # Replace this process so updated modules are loaded from disk.
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])


if __name__ == '__main__':
    run()
