
"""The Settings menu."""

import subprocess
import sys
import os
import shutil

from .ui import CYAN, RESET, YELLOW, ask_yes_no, print_green
from .uninstaller import uninstall_menu
from .updater import update_menu
from .system import (
    get_default_download_dir,
    get_download_dir,
    set_download_dir
)


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


AUDIO_EXTENSIONS = {
    '.mp3', '.m4a', '.aac', '.flac',
    '.wav', '.opus', '.ogg', '.wma'
}

VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.webm', '.mov',
    '.avi', '.m4v', '.flv', '.wmv'
}

THUMBNAIL_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp',
    '.avif', '.bmp', '.gif'
}


def get_file_category(filename):
    ext = os.path.splitext(filename)[1].lower()

    if ext in AUDIO_EXTENSIONS:
        return 'Audios'

    if ext in VIDEO_EXTENSIONS:
        return 'Videos'

    if ext in THUMBNAIL_EXTENSIONS:
        return 'Thumbnails'

    return None


def move_downloaded_files(new_location):
    """Move recognised existing CatWiz downloads into the new folder structure."""

    default_dir = get_default_download_dir()
    old_catwiz_dir = os.path.join(default_dir, 'CatWiz')

    sources = []

    # Previous CatWiz layout: videos directly inside Downloads.
    try:
        for filename in os.listdir(default_dir):
            source = os.path.join(default_dir, filename)

            if not os.path.isfile(source):
                continue

            category = get_file_category(filename)

            if category:
                sources.append((source, category))
    except OSError:
        pass

    # Previous audio and thumbnail folders.
    for folder, category in (
        ('Music', 'Audios'),
        ('Thumbnails', 'Thumbnails')
    ):
        directory = os.path.join(default_dir, folder)

        if os.path.isdir(directory):
            for filename in os.listdir(directory):
                source = os.path.join(directory, filename)

                if os.path.isfile(source) and get_file_category(filename):
                    sources.append((source, category))

    # Existing CatWiz folder structure, if present.
    for category in ('Audios', 'Videos', 'Thumbnails'):
        directory = os.path.join(old_catwiz_dir, category)

        if os.path.isdir(directory):
            for filename in os.listdir(directory):
                source = os.path.join(directory, filename)

                if os.path.isfile(source) and get_file_category(filename):
                    sources.append((source, category))

    moved = 0
    failed = 0

    for source, category in sources:
        try:
            destination_dir = os.path.join(new_location, category)
            os.makedirs(destination_dir, exist_ok=True)

            destination = os.path.join(
                destination_dir,
                os.path.basename(source)
            )

            # Avoid overwriting files with the same name.
            if os.path.exists(destination):
                name, ext = os.path.splitext(destination)
                counter = 1

                while os.path.exists(f"{name}_{counter}{ext}"):
                    counter += 1

                destination = f"{name}_{counter}{ext}"

            # Do not attempt to move a file onto itself.
            if os.path.abspath(source) == os.path.abspath(destination):
                continue

            shutil.move(source, destination)
            moved += 1

        except OSError:
            failed += 1

    return moved, failed


def change_download_location():
    print(f"\nCurrent download location:")
    print(get_download_dir())
    print()

    new_location = input(
        f"{YELLOW}Enter new download location (0 to cancel):{RESET} "
    ).strip()

    if new_location == '0':
        print_green("Cancelled.")
        return

    new_location = os.path.abspath(
        os.path.expanduser(os.path.expandvars(new_location.strip('"')))
    )

    if not new_location:
        print_green("Invalid location.")
        return

    current_location = os.path.abspath(get_download_dir())

    if new_location == current_location:
        print_green("This is already your download location.")
        return

    if os.path.isfile(new_location):
        print_green("The selected location is a file, not a folder.")
        return

    try:
        os.makedirs(new_location, exist_ok=True)
    except OSError as e:
        print(f"{YELLOW}Could not create folder: {e}{RESET}")
        return

    # Save the new location.
    try:
        set_download_dir(new_location)
    except OSError as e:
        print(f"{YELLOW}Could not save download location: {e}{RESET}")
        return

    print_green(f"Download location changed to: {new_location}")

    # Check for existing downloads without announcing the scan.
    default_dir = get_default_download_dir()

    has_downloads = False

    try:
        for filename in os.listdir(default_dir):
            if get_file_category(filename):
                has_downloads = True
                break

        if not has_downloads:
            for folder in ('Music', 'Thumbnails', 'CatWiz'):
                directory = os.path.join(default_dir, folder)

                if not os.path.isdir(directory):
                    continue

                for root, _, files in os.walk(directory):
                    if any(get_file_category(f) for f in files):
                        has_downloads = True
                        break

                if has_downloads:
                    break
    except OSError:
        pass

    if has_downloads:
        if ask_yes_no("Move downloaded files to new location?"):
            moved, failed = move_downloaded_files(new_location)

            print_green(f"Moved {moved} downloaded files.")

            if failed:
                print(
                    f"{YELLOW}{failed} files could not be moved. "
                    f"Check file permissions or whether they are in use.{RESET}"
                )
        else:
            print_green("Existing downloads were left in their original locations.")


def settings_menu():
    max_attempts = 3

    while True:
        print(f"\n{CYAN}======================================{RESET}")
        print(" Settings")
        print("  1. Update")
        print("  2. Uninstall CatWiz")
        print("  3. Clear cache")
        print("  4. Change download location")
        print("  0. Back")
        print(f"{CYAN}--------------------------------------{RESET}")

        attempts = 0
        choice = None

        while attempts < max_attempts:
            choice = input(
                f"{YELLOW}Select option [1/2/3/4/0]:{RESET} "
            ).strip()

            if choice in ("0", "1", "2", "3", "4"):
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
        elif choice == "4":
            change_download_location()
