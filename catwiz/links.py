"""YouTube link validation and video/playlist information."""

import re
import sys
import yt_dlp

from .ui import RED, RESET, YELLOW, ask_proceed, print_green
from .utils import QuietLogger, format_duration

def is_valid_yt_url(url):
    pattern = r'^(https?://)?((www|m|music)\.)?(youtube\.com/(watch\?|playlist\?|shorts/|live/|embed/)|youtu\.be/)[^\s]+$'
    return re.match(pattern, url) is not None

def fetch_playlist_info(url):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'logger': QuietLogger(),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception:
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
        'quiet': True,
        'no_warnings': True,
        'logger': QuietLogger(),
    }
    with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
        try:
            return ydl.extract_info(url, download=False)
        except Exception:
            return None

def fetch_playlist_entries(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'logger': QuietLogger(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []
            if 'entries' in info:
                return [entry['url'] for entry in info['entries'] if entry]
            return [url]
        except Exception:
            return []
