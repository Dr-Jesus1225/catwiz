"""CatWiz entry point."""
import sys

from catwiz.app import main


def run():
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    run()
