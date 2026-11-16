"""YouTube link validation and video/playlist information."""

import re
import sys
import yt_dlp

from .ui import CYAN, RED, RESET, YELLOW, ask_proceed, print_green
from .cookies import apply_browser_cookies
from .utils import format_duration
from .session_log import logged_yt_dlp_call, write_diagnostic

def is_valid_yt_url(url):
    pattern = r'^(https?://)?((www|m|music)\.)?(youtube\.com/(watch\?|playlist\?|shorts/|live/|embed/)|youtu\.be/)[^\s]+$'
    return re.match(pattern, url) is not None

def fetch_playlist_info(url):
    opts = {
        'quiet': True,
        'no_warnings': False,
        'verbose': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(apply_browser_cookies(opts)) as ydl:
        try:
            info = logged_yt_dlp_call(ydl.extract_info, url, download=False)
        except Exception as error:
            write_diagnostic(f"yt-dlp extraction error: {error}")
            print("Could not read the playlist. See logs.txt for technical details.", file=sys.stderr)
            return None
    if not info:
        return None
    name = info.get('title') or 'Unknown'
    creator = info.get('uploader') or info.get('channel')
    if 'entries' in info:
        items = [e['url'] for e in info['entries'] if e and e.get('url')]
    else:
        items = [url]
    return name, creator, items, info


def choose_playlist_items(items, playlist_info):
    """Let users download all, selected, or all except selected playlist items."""
    if not items:
        return []

    entries = (playlist_info or {}).get('entries') or []

    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Playlist Download Options:")
    print("  1. Download the whole playlist")
    print("  2. Download selected items")
    print("  3. Skip selected items")
    print("  0. Cancel")
    print(f"{CYAN}--------------------------------------{RESET}")

    while True:
        choice = input(
            f"{YELLOW}Select option [1/2/3/0]:{RESET} "
        ).strip()

        if choice == '0':
            print_green("Operation cancelled.")
            return []
        if choice == '1':
            return items
        if choice in ('2', '3'):
            break
        print_green("Invalid selection. Choose 1, 2, 3 or 0.")

    print(f"\nPlaylist items ({len(items)}):")
    for index, item_url in enumerate(items, 1):
        entry = entries[index - 1] if index <= len(entries) else {}
        title = (entry or {}).get('title') or (entry or {}).get('id') or 'Untitled'
        title = ' '.join(str(title).split())
        print(f"  {index:>3}. {title}")

    print("\nEnter item numbers separated by commas; ranges are supported.")
    print("Example: 1, 3, 5-8")
    selected = set()

    while True:
        raw = input(
            f"{YELLOW}Item numbers (or 0 to cancel):{RESET} "
        ).strip()
        if raw == '0':
            print_green("Operation cancelled.")
            return []

        try:
            parsed = set()
            for part in raw.split(','):
                part = part.strip()
                if not part:
                    raise ValueError
                if re.fullmatch(r'\d+', part):
                    start = end = int(part)
                else:
                    match = re.fullmatch(r'(\d+)\s*-\s*(\d+)', part)
                    if not match:
                        raise ValueError
                    start, end = map(int, match.groups())
                    if start > end:
                        raise ValueError
                if start < 1 or end > len(items):
                    raise ValueError
                parsed.update(range(start, end + 1))
            if not parsed:
                raise ValueError
            selected = parsed
            break
        except ValueError:
            print_green(
                f"Invalid item numbers. Enter values from 1 to {len(items)}, "
                "for example 1, 3, 5-8."
            )

    if choice == '2':
        chosen = [item for index, item in enumerate(items, 1) if index in selected]
    else:
        chosen = [item for index, item in enumerate(items, 1) if index not in selected]

    print_green(f"{len(chosen)} of {len(items)} playlist items selected.")
    return chosen


def get_validated_url(is_playlist, mode):
    attempts = 0
    max_attempts = 3
    while True:
        url = input(f"\n{YELLOW}Enter YouTube URL (or enter 0 to cancel):{RESET} ").strip()
        if url == '0':
            print_green("Operation cancelled.")
            sys.exit(0)
        print("\nChecking link...")
        result = None
        if not is_valid_yt_url(url):
            print(f"{RED}Not a valid YouTube link{RESET}")
            print("  Expected: youtube.com, music.youtube.com, youtu.be, shorts, or playlist")
        else:
            if not url.startswith('http'):
                url = 'https://' + url
            print_green("Valid YouTube link")
            if is_playlist:
                data = fetch_playlist_info(url)
                if data and data[2]:
                    name, creator, items, playlist_info = data
                    print_green("Playlist found")
                    print(f"  Name:    {name}")
                    if creator:
                        print(f"  Creator: {creator}")
                    print(f"  Items:   {len(items)}")
                    result = (url, playlist_info, items)
            else:
                info = fetch_info(url)
                if info:
                    print_green("Video found")
                    print(f"  Title:    {info.get('title', 'Unknown')}")
                    who = info.get('artist') or info.get('uploader') or info.get('channel') or 'Unknown'
                    print(f"  {'Artist' if mode == '1' else 'Channel'}:".ljust(11) + f" {who}")
                    if mode != '3':
                        print(f"  Duration: {format_duration(info.get('duration'))}")
                    result = (url, info, None)
            if result is None:
                print(f"{RED}Video not available (private, deleted, or region-locked){RESET}")
        if result:
            attempts = 0
            if ask_proceed():
                return result
            continue
        attempts += 1
        if attempts >= max_attempts:
            print_green("Too many invalid attempts. Exiting.")
            sys.exit(1)
        print(f"Attempt {attempts}/{max_attempts}")

def fetch_info(url):
    ydl_info_opts = {
        'quiet': False,
        'no_warnings': False,
        'verbose': True,
    }
    with yt_dlp.YoutubeDL(apply_browser_cookies(ydl_info_opts)) as ydl:
        try:
            return logged_yt_dlp_call(ydl.extract_info, url, download=False)
        except Exception as error:
            write_diagnostic(f"yt-dlp extraction error: {error}")
            print("Could not read this video. See logs.txt for technical details.", file=sys.stderr)
            return None

def fetch_playlist_entries(url):
    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'verbose': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(apply_browser_cookies(ydl_opts)) as ydl:
        try:
            info = logged_yt_dlp_call(ydl.extract_info, url, download=False)
            if not info:
                return []
            if 'entries' in info:
                return [entry['url'] for entry in info['entries'] if entry]
            return [url]
        except Exception as error:
            write_diagnostic(f"yt-dlp extraction error: {error}")
            print("Could not read playlist items. Check logs.txt for diagnostics.")
            return []
