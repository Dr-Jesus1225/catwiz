"""CatWiz entry point."""
import os
import sys

from catwiz.app import main
from catwiz.session_log import start_session_logging, stop_session_logging
from catwiz.logging_service import close_logging, component_logger, get_logger, log_activity

RESTART_EXIT_CODE = 75


def run():
    get_logger()
    # Prefer the desktop GUI when PySide6 is installed. The CLI remains
    # available everywhere through --cli and as a dependency fallback.
    if "--cli" not in sys.argv:
        from catwiz.system import platform_key
        if platform_key() != "termux":
            try:
                from gui.app import run as run_gui
            except ImportError:
                component_logger("startup").info("GUI dependencies unavailable; using CLI")
            else:
                log_activity("Desktop application started", component="gui")
                try:
                    return run_gui()
                except Exception:
                    component_logger("gui").exception("Unhandled desktop application error")
                    raise
                finally:
                    log_activity("Desktop application closed", component="gui")
                    close_logging()

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
    finally:
        stop_session_logging(log_handle)
        close_logging()

    if restart:
        # Replace this process so updated modules are loaded from disk.
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])


if __name__ == "__main__":
    run()
