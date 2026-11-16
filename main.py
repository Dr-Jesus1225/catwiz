"""CatWiz entry point."""
import sys

from catwiz.app import main
from catwiz.session_log import start_session_logging, stop_session_logging


def run():
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_file = start_session_logging()
    try:
        try:
            main()
        except KeyboardInterrupt:
            return
    finally:
        if log_file:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                stop_session_logging(log_file)


if __name__ == '__main__':
    run()
