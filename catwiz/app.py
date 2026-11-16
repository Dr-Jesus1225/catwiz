"""The terminal flow: main menu, link, quality, download."""

import os
import sys

from .downloader import process_single_item, process_thumbnail_only
from .links import choose_playlist_items, get_validated_url
from .menus import print_main_menu, select_audio_quality, select_photo_quality, select_video_quality
from .quality import announce_quality, resolve_quality
from .settings import settings_menu
from .updater import check_for_updates_on_startup
from .sidecar import run_sidecar_step
from .system import check_ffmpeg, get_category_dir, get_auto_update_check
from .ui import BANNER, CYAN, RESET, YELLOW, ask_yn, print_green
from .utils import clean_filename


def main():
    check_ffmpeg()
    if get_auto_update_check():
        check_for_updates_on_startup()
    print(BANNER)
    max_attempts = 3

    while True:
        print_main_menu()
        attempts = 0
        mode = None

        while attempts < max_attempts:
            mode = input(
                f"{YELLOW}Select option [-1/1/2/3/0]:{RESET} "
            ).strip()

            if mode in ('-1', '0', '1', '2', '3'):
                break

            attempts += 1

            if attempts < max_attempts:
                print_green("Invalid option selected.")
            else:
                print_green("Too many invalid attempts. Exiting.")
                sys.exit(1)

        if mode == '0':
            sys.exit(0)

        if mode == '-1':
            settings_menu()
            print()
            continue

        break

    url, info, playlist_items = get_validated_url(mode)
    is_playlist = playlist_items is not None
    playlist_thumbnail_choice = None

    if mode == '3' and is_playlist:
        print(f"\n{CYAN}--------------------------------------{RESET}")
        print("  1. Playlist/album cover art")
        print("  2. Every item's thumbnail")
        print("  0. Cancel")
        print(f"{CYAN}--------------------------------------{RESET}")
        while True:
            playlist_thumbnail_choice = input(f"{YELLOW}Select option [1/2/0]:{RESET} ").strip()
            if playlist_thumbnail_choice in ('0', '1', '2'):
                break
            print_green("Invalid option selected.")
        if playlist_thumbnail_choice == '0':
            print_green("Operation cancelled.")
            sys.exit(0)

    if is_playlist:
        playlist_items = choose_playlist_items(playlist_items, info)
        if not playlist_items:
            print_green("No playlist items selected. Operation cancelled.")
            return
    with_audio = True
    if mode == '2':
        with_audio = ask_yn("Download audio for the video?")

    quality_label = ''
    resolved = None
    sidecar_text = None
    want_sidecar = False

    if mode == '1':
        selected_quality = select_audio_quality(info, is_playlist)
        save_path = get_category_dir('audio')
        print(f"\n{selected_quality} kbps selected")

        if is_playlist:
            want_sidecar = ask_yn("Download lyrics when available?")
        else:
            sidecar_text = run_sidecar_step(
                'lyrics', url, info,
                clean_filename(info.get('title', 'media')),
                ask=True
            )

    elif mode == '2':
        selected_quality, quality_label = select_video_quality(
            info, is_playlist, with_audio
        )
        save_path = get_category_dir('video')

        if is_playlist:
            announce_quality(None, quality_label)
            want_sidecar = ask_yn("Download subtitles when available?")
        else:
            if not isinstance(selected_quality, dict):
                resolved = resolve_quality(url, selected_quality)
            announce_quality(resolved, quality_label)
            sidecar_text = run_sidecar_step(
                'subtitles', url, info,
                clean_filename(info.get('title', 'media')),
                ask=True
            )

    else:
        if is_playlist and playlist_thumbnail_choice == '1':
            selected_quality = select_photo_quality(
                info, is_playlist, playlist_cover=True
            )
        else:
            selected_quality = select_photo_quality(info, is_playlist)

        save_path = get_category_dir('thumbnail')

    results = []

    if (
        is_playlist
        and mode == '3'
        and playlist_thumbnail_choice == '1'
    ):
        process_thumbnail_only(
            url, False, 1, 1, save_path,
            selected_quality, pre_info=info
        )
        return

    if is_playlist:
        total = len(playlist_items)

        for idx, item in enumerate(playlist_items, 1):
            if mode == '3':
                results.append(
                    process_thumbnail_only(
                        item, True, idx, total,
                        save_path, selected_quality
                    )
                )
            else:
                results.append(
                    process_single_item(
                        item, mode, True, idx, total,
                        save_path, selected_quality,
                        with_audio=with_audio,
                        want_sidecar=want_sidecar,
                        quality_label=quality_label
                    )
                )

        saved = results.count(True)
        failed = results.count(False)
        print()

        if failed:
            print(
                f"{YELLOW}Finished: {saved} saved, "
                f"{failed} failed (review CatWiz logs for details){RESET}"
            )
        else:
            print_green(f"Finished: all {saved} saved")

    else:
        if mode == '3':
            process_thumbnail_only(
                url, False, 1, 1, save_path,
                selected_quality, pre_info=info
            )
        else:
            process_single_item(
                url, mode, False, 1, 1, save_path,
                selected_quality, pre_info=info,
                with_audio=with_audio,
                sidecar_text=sidecar_text,
                resolved=resolved,
                quality_label=quality_label
            )
