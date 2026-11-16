"""CatWiz command-line entry point."""
import os
import sys

from catwiz.app import main
from catwiz.session_log import start_session_logging, stop_session_logging
from catwiz.logging_service import close_logging, component_logger, get_logger

RESTART_EXIT_CODE = 75


def run():
    get_logger()
    from catwiz.system import ensure_deno
    ensure_deno()
    from catwiz.youtube_support import ensure_youtube_support
    ensure_youtube_support()

    log_handle = start_session_logging()
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
        except Exception:
            component_logger("cli").exception("Unhandled CLI application error")
            raise
    finally:
        stop_session_logging(log_handle)
        close_logging()

    if restart:
        # Replace this process so updated modules are loaded from disk.
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])


if __name__ == "__main__":
    run()
