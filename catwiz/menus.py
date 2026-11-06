
"""The quality menus and the main menu."""

import re
import sys

from .quality import make_video_format
from .ui import CYAN, RESET, YELLOW, print_green


def select_video_quality(info, is_playlist, with_audio=True):
    found = set()

    def collect_resolutions(video_info):
        if not isinstance(video_info, dict):
            return

        for fmt in video_info.get('formats', []):
            if fmt.get('vcodec') == 'none':
                continue

            height = fmt.get('height')

            if isinstance(height, int) and height > 0:
                found.add(height)

        if is_playlist:
            for entry in video_info.get('entries') or []:
                collect_resolutions(entry)

    collect_resolutions(info)

    heights = sorted(found)
    options = []

    for index, height in enumerate(heights):
        label = f"{height}p"

        if index == len(heights) - 1:
            label += " (Best quality)"

        options.append((
            label,
            make_video_format(height, with_audio)
        ))

    if not options:
        options.append((
            "Best available (Best quality)",
            make_video_format(None, with_audio)
        ))

    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Select Video Quality:")

    for idx, (label, _) in enumerate(options, 1):
        print(f"  {idx}. {label}")

    print("  W. Custom resolution")
    print("  0. Cancel")
    print(f"{CYAN}--------------------------------------{RESET}")

    attempts = 0

    while attempts < 3:
        choice = input(
            f"{YELLOW}Select option [1-{len(options)}/W/0]:{RESET} "
        ).strip().lower()

        if choice == '0':
            print_green("Operation cancelled.")
            sys.exit(0)

        if choice == 'w':
            resolution = input(
                f"{YELLOW}Enter custom resolution (WIDTHxHEIGHT):{RESET} "
            ).strip()

            if resolution == '0':
                print_green("Operation cancelled.")
                sys.exit(0)

            match = re.fullmatch(
                r"(\d+)\s*[xX×]\s*(\d+)",
                resolution
            )

            if match:
                width = int(match.group(1))
                height = int(match.group(2))

                if (
                    2 <= width <= 16384
                    and 2 <= height <= 16384
                    and width % 2 == 0
                    and height % 2 == 0
                ):
                    return {
                        "type": "custom",
                        "width": width,
                        "height": height
                    }, f"{width}x{height} (Custom)"

            print_green(
                "Invalid resolution. Use even dimensions, e.g. 1920x1080."
            )
            attempts += 1
            continue

        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return (
                options[int(choice) - 1][1],
                options[int(choice) - 1][0]
            )

        attempts += 1

        if attempts < 3:
            print_green("Invalid selection.")
        else:
            print_green("Too many invalid attempts. Exiting.")
            sys.exit(1)


def select_audio_quality(info, is_playlist):
    options = [
        ("128 kbps", "128"),
        ("192 kbps", "192"),
        ("256 kbps", "256"),
        ("320 kbps (Best)", "320")
    ]

    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Select Audio Quality:")

    for idx, (label, _) in enumerate(options, 1):
        print(f"  {idx}. {label}")

    print("  0. Cancel")
    print(f"{CYAN}--------------------------------------{RESET}")

    attempts = 0

    while attempts < 3:
        choice = input(
            f"{YELLOW}Select option [1-{len(options)}/0]:{RESET} "
        ).strip()

        if choice == '0':
            print_green("Operation cancelled.")
            sys.exit(0)

        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1][1]

        attempts += 1

        if attempts < 3:
            print_green("Invalid selection.")
        else:
            print_green("Too many invalid attempts. Exiting.")


def select_photo_quality(info, is_playlist, playlist_cover=False):
    thumbnails = (info or {}).get('thumbnails') or []

    if playlist_cover:
        # Playlist metadata may expose the cover as either a thumbnail
        # list or a single "thumbnail" URL.
        if info and info.get('thumbnail'):
            thumbnails = list(thumbnails)
            thumbnails.append({
                'url': info['thumbnail'],
                'width': info.get('width'),
                'height': info.get('height')
            })

        valid_thumbnails = [
            thumbnail for thumbnail in thumbnails
            if thumbnail and thumbnail.get('url')
        ]

        dims = []

        for thumbnail in valid_thumbnails:
            width = thumbnail.get('width')
            height = thumbnail.get('height')

            if width and height:
                dims.append((width, height, thumbnail['url']))

        dims = sorted(
            set(dims),
            key=lambda item: item[0] * item[1]
        )

        if dims:
            options = [
                (f"{width}x{height}", url)
                for width, height, url in dims
            ]
            options.append(("Best Available", dims[-1][2]))
        elif valid_thumbnails:
            options = [
                ("Best Available", valid_thumbnails[-1]['url'])
            ]
        else:
            print_green("Playlist/album cover art is not available.")
            sys.exit(0)

    elif is_playlist or not info or not info.get('thumbnails'):
        options = [
            ("Standard Quality", "standard"),
            ("High Quality", "hq"),
            ("Best Available", "best")
        ]

    else:
        dims = []

        for thumbnail in info['thumbnails']:
            width = thumbnail.get('width')
            height = thumbnail.get('height')

            if width and height:
                dims.append((width, height, thumbnail.get('url')))

        dims = sorted(
            set(dims),
            key=lambda item: item[0] * item[1]
        )

        if not dims:
            options = [
                ("Standard Quality", "standard"),
                ("High Quality", "hq"),
                ("Best Available", "best")
            ]
        else:
            options = [
                (f"{width}x{height}", url)
                for width, height, url in dims
            ]
            options.append(("Best Available", "best"))

    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Select Photo Resolution (LxB):")

    for idx, (label, _) in enumerate(options, 1):
        print(f"  {idx}. {label}")

    print("  W. Custom resolution")
    print("  0. Cancel")
    print(f"{CYAN}--------------------------------------{RESET}")

    attempts = 0

    while attempts < 3:
        choice = input(
            f"{YELLOW}Select option [1-{len(options)}/W/0]:{RESET} "
        ).strip().lower()

        if choice == '0':
            print_green("Operation cancelled.")
            sys.exit(0)

        if choice == 'w':
            resolution = input(
                f"{YELLOW}Enter custom resolution (WIDTHxHEIGHT):{RESET} "
            ).strip()

            if resolution == '0':
                print_green("Operation cancelled.")
                sys.exit(0)

            match = re.fullmatch(
                r"(\d+)\s*[xX×]\s*(\d+)",
                resolution
            )

            if match:
                width = int(match.group(1))
                height = int(match.group(2))

                if 1 <= width <= 16384 and 1 <= height <= 16384:
                    return {
                        "type": "custom",
                        "width": width,
                        "height": height
                    }

            print_green("Invalid resolution. Example: 1920x1080")
            attempts += 1
            continue

        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1][1]

        attempts += 1

        if attempts < 3:
            print_green("Invalid selection.")
        else:
            print_green("Too many invalid attempts. Exiting.")
            sys.exit(1)
def print_main_menu():
    print(f"{CYAN}======================================{RESET}")
    print(" -1. Settings")
    print("  1. Audio (.mp3)")
    print("  2. Video (.mp4)")
    print("  3. Extract Thumbnail (.png)")
    print("  0. Exit")
    print(f"{CYAN}--------------------------------------{RESET}")
