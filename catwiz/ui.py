"""Colors, the banner and the yes/no prompts (everything the terminal shows or asks)."""

import os
import sys
import warnings

if os.name == 'nt':
    os.system('')  # enables ANSI colors in Windows terminals

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

warnings.filterwarnings("ignore", category=SyntaxWarning)

GREEN = '\033[92m'

CYAN = '\033[96m'

YELLOW = '\033[93m'

RED = '\033[91m'

RESET = '\033[0m'

BANNER = f"""{CYAN}
  /\\_/\\
 ( o.o )
  > ^ <
   ___   _  _____ __      _____ _____
  / __| /_\\|_   _\\ \\    / /_ _|__  /
 | (__ / _ \\ | |   \\ \\/\\/ / | |  / /
  \\___/_/ \\_\\|_|    \\_/\\_/ |___|/___|
{RESET}"""

def print_green(message):
    print(f"{GREEN}{message}{RESET}")

def ask_proceed():
    while True:
        ans = input(f"\n{YELLOW}Proceed? [y/n]:{RESET} ").strip().lower()
        if ans in ('y', 'n'):
            return ans == 'y'

def ask_yn(prompt):
    while True:
        ans = input(f"{YELLOW}{prompt} [y/n]:{RESET} ").strip().lower()
        if ans in ('y', 'n'):
            return ans == 'y'

def ask_yes_no(prompt):
    while True:
        ans = input(f"\n{YELLOW}{prompt} [y/n]:{RESET} ").strip().lower()
        if ans in ('y', 'n'):
            return ans == 'y'
