"""The Settings menu."""

import sys

from .ui import CYAN, RESET, YELLOW, print_green
from .uninstaller import uninstall_menu
from .updater import update_menu

def settings_menu():
    max_attempts = 3
    while True:
        print(f"\n{CYAN}======================================{RESET}")
        print(" Settings")
        print("  1. Update")
        print("  2. Uninstall CATWIZ-ytdl")
        print("  0. Back")
        print(f"{CYAN}--------------------------------------{RESET}")
        attempts = 0
        choice = None
        while attempts < max_attempts:
            choice = input(f"{YELLOW}Select option [1/2/0]:{RESET} ").strip()
            if choice in ('0', '1', '2'):
                break
            attempts += 1
            if attempts < max_attempts:
                print_green("Invalid option selected.")
            else:
                print_green("Too many invalid attempts. Exiting.")
                sys.exit(1)
        if choice == '0':
            return
        if choice == '1':
            update_menu()
        else:
            uninstall_menu()
