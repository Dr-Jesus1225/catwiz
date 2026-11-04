
"""The Settings menu."""

import subprocess
import sys

from .ui import CYAN, RESET, YELLOW, ask_yes_no, print_green
from .uninstaller import uninstall_menu
from .updater import update_menu


def clear_cache():
    print()
    if not ask_yes_no(
        "Clear yt-dlp cache? Downloaded media will not be affected."
    ):
        print_green("Cancelled.")
        return

    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--rm-cache-dir"],
            capture_output=True,
            text=True,
            errors="replace",
        )

        if result.returncode == 0:
            print_green("yt-dlp cache cleared.")
        else:
            details = (result.stderr or result.stdout or "Unknown error").strip()
            reason = details.splitlines()[-1] if details else "Unknown error"
            print(f"{YELLOW}Could not clear cache: {reason}{RESET}")

    except OSError as e:
        print(f"{YELLOW}Could not clear cache: {e}{RESET}")


def settings_menu():
    max_attempts = 3

    while True:
        print(f"\n{CYAN}======================================{RESET}")
        print(" Settings")
        print("  1. Update")
        print("  2. Uninstall CatWiz")
        print("  3. Clear cache")
        print("  0. Back")
        print(f"{CYAN}--------------------------------------{RESET}")

        attempts = 0
        choice = None

        while attempts < max_attempts:
            choice = input(
                f"{YELLOW}Select option [1/2/3/0]:{RESET} "
            ).strip()

            if choice in ("0", "1", "2", "3"):
                break

            attempts += 1

            if attempts < max_attempts:
                print_green("Invalid option selected.")
            else:
                print_green("Too many invalid attempts. Exiting.")
                sys.exit(1)

        if choice == "0":
            return
        elif choice == "1":
            update_menu()
        elif choice == "2":
            uninstall_menu()
        elif choice == "3":
            clear_cache()
