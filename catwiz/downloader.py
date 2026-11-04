    
"""Downloading audio, video and thumbnails."""

import subprocess
import glob
import os
import shutil
import sys
import yt_dlp

from .captions import write_sidecar
from .links import fetch_info
from .quality import FORMAT_SORT, announce_quality, resolve_quality
from .sidecar import run_sidecar_step
from .ui import CYAN, GREEN, RESET, YELLOW, print_green
from .utils import (
    QuietLogger,
    clean_filename,
    cleanup_partials,
    ensure_dir,
    item_failed,
    log_error,
    run_ffmpeg,
    safe_remove,
    short_reason,
)

CURRENT_ITEM = {'safe_title': None}


def get_original_video_dimensions(info):
    """Find the largest available original video dimensions."""
    candidates = []

    if not info:
        return None

    width = info.get('width')
    height = info.get('height')

    if (
        isinstance(width, int)
        and isinstance(height, int)
        and width > 0
        and height > 0
    ):
        candidates.append((width, height))

    for fmt in info.get('formats', []):
        if fmt.get('vcodec') == 'none':
            continue

        width = fmt.get('width')
        height = fmt.get('height')

        if (
            isinstance(width, int)
            and isinstance(height, int)
            and width > 0
            and height > 0
        ):
            candidates.append((width, height))

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda dimensions: dimensions[0] * dimensions[1]
    )



def select_custom_video_format(
    info, target_width, target_height, method, with_audio
):
    """Select the smallest source format that avoids upscaling."""

    formats = info.get('formats', []) if info else []
    candidates = []

    target_ratio = target_width / target_height

    for fmt in formats:
        if fmt.get('vcodec') == 'none':
            continue

        width = fmt.get('width')
        height = fmt.get('height')
        format_id = fmt.get('format_id')

        if not (
            isinstance(width, int)
            and isinstance(height, int)
            and width > 0
            and height > 0
            and format_id
        ):
            continue

        source_ratio = width / height

        if method == 'crop':
            # Scale to fill the target without upscaling.
            sufficient = (
                width >= target_width
                and height >= target_height
                and (
                    source_ratio >= target_ratio
                    and height >= target_height
                    or source_ratio < target_ratio
                    and width >= target_width
                )
            )
        else:
            sufficient = (
                width >= target_width
                and height >= target_height
            )

        has_audio = fmt.get('acodec') not in (None, 'none')

        candidates.append({
            'format_id': str(format_id),
            'width': width,
            'height': height,
            'area': width * height,
            'has_audio': has_audio,
            'sufficient': sufficient,
        })

    if not candidates:
        return 'bestvideo+bestaudio/best' if with_audio else 'bestvideo/best'

    sufficient_formats = [
        fmt for fmt in candidates if fmt['sufficient']
    ]

    if sufficient_formats:
        selected = min(
            sufficient_formats,
            key=lambda fmt: fmt['area']
        )
    else:
        selected = max(
            candidates,
            key=lambda fmt: fmt['area']
        )

    format_id = selected['format_id']

    if with_audio and not selected['has_audio']:
        result = f'{format_id}+bestaudio'
    else:
        result = format_id

    print_green(
        f"Selected source resolution: "
        f"{selected['width']}x{selected['height']}"
    )

    if not sufficient_formats:
        print(
            f"{YELLOW}No source resolution was large enough. "
            f"Using the largest available format.{RESET}"
        )

    return result

def run_ffmpeg_with_progress(command, duration=None):
    """Run FFmpeg and display encoding progress."""

    command = [
        'ffmpeg',
        '-loglevel', 'error',
        *command[1:-1],
        '-progress', 'pipe:1',
        '-nostats',
        command[-1],
    ]

    process = None
    last_errors = []
    last_percent = -1

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )

        for line in process.stdout:
            line = line.strip()

            if '=' not in line:
                if line:
                    last_errors.append(line)
                    last_errors = last_errors[-5:]
                continue

            key, value = line.split('=', 1)

            if key not in ('out_time_us', 'out_time'):
                continue

            try:
                if key == 'out_time':
                    hours, minutes, seconds = value.split(':')
                    elapsed = (
                        int(hours) * 3600
                        + int(minutes) * 60
                        + float(seconds)
                    )
                else:
                    elapsed = int(value) / 1_000_000

                if duration and duration > 0:
                    percent = min(100.0, elapsed / duration * 100)

                    if int(percent) != last_percent:
                        last_percent = int(percent)

                        filled = int(percent / 5)
                        bar = (
                            '█' * filled
                            + '░' * (20 - filled)
                        )

                        print(
                            f"\r{GREEN}[{bar}] "
                            f"{percent:5.1f}%{RESET}   ",
                            end='',
                            flush=True
                        )
                else:
                    hours = int(elapsed // 3600)
                    minutes = int((elapsed % 3600) // 60)
                    seconds = int(elapsed % 60)

                    print(
                        f"\r{GREEN}Encoding: "
                        f"{hours:02}:{minutes:02}:{seconds:02}{RESET}   ",
                        end='',
                        flush=True
                    )

            except (ValueError, TypeError):
                continue

        return_code = process.wait()

        print()

        if return_code == 0:
            filled = 20
            bar = '█' * filled

            print(
                f"\r{GREEN}[{bar}] 100.0%{RESET}   "
            )

            return True, ''

        reason = (
            '\n'.join(last_errors)
            or f'FFmpeg exited with code {return_code}'
        )

        return False, reason

    except KeyboardInterrupt:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        raise

    except OSError as e:
        if process and process.poll() is None:
            process.kill()
            process.wait()

        return False, str(e)

def choose_custom_video_method(video_dimensions, target_width, target_height):
    """Choose how to handle a custom video aspect ratio."""

    target_ratio = target_width / target_height

    if video_dimensions:
        video_width, video_height = video_dimensions
        original_ratio = video_width / video_height

        difference = abs(original_ratio - target_ratio) / original_ratio

        if difference <= 0.01:
            print_green(
                "Custom resolution matches the original video aspect ratio."
            )
            return "stretch"

        print()
        print(
            f"Original video: {video_width}x{video_height} "
            f"({original_ratio:.4f})"
        )
        print(
            f"Requested video: {target_width}x{target_height} "
            f"({target_ratio:.4f})"
        )
        print()
        print("The aspect ratios are different.")

    else:
        print()
        print(
            f"{YELLOW}Original video dimensions could not be detected. "
            f"Choose how to resize the video manually.{RESET}"
        )

    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Handle Aspect Ratio:")
    print("  1. Stretch and squeeze")
    print("  2. Crop with respect to the centre")
    print("  0. Cancel")
    print(f"{CYAN}--------------------------------------{RESET}")

    attempts = 0

    while attempts < 3:
        choice = input(
            f"{YELLOW}Select option [1/2/0]:{RESET} "
        ).strip()

        if choice == '1':
            return "stretch"

        if choice == '2':
            return "crop"

        if choice == '0':
            print_green("Operation cancelled.")
            return None

        attempts += 1

        if attempts < 3:
            print_green("Invalid selection.")
        else:
            print_green("Too many invalid attempts. Exiting.")
            return None


def choose_custom_thumbnail_method(video_dimensions, target_width, target_height):
    """Choose how to handle a custom thumbnail aspect ratio."""

    target_ratio = target_width / target_height

    if video_dimensions:
        video_width, video_height = video_dimensions
        original_ratio = video_width / video_height

        difference = abs(original_ratio - target_ratio) / original_ratio

        if difference <= 0.01:
            print_green(
                "Custom resolution matches the original video aspect ratio."
            )
            return "stretch"

        print()
        print(
            f"Original video: {video_width}x{video_height} "
            f"({original_ratio:.4f})"
        )
        print(
            f"Requested thumbnail: {target_width}x{target_height} "
            f"({target_ratio:.4f})"
        )
        print()
        print("The aspect ratios are different.")

    else:
        print()
        print(
            f"{YELLOW}Original video dimensions could not be detected. "
            f"Choose how to resize the thumbnail manually.{RESET}"
        )

    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Handle Aspect Ratio:")
    print("  1. Stretch and squeeze")
    print("  2. Crop with respect to the centre")
    print("  0. Cancel")
    print(f"{CYAN}--------------------------------------{RESET}")

    attempts = 0

    while attempts < 3:
        choice = input(
            f"{YELLOW}Select option [1/2/0]:{RESET} "
        ).strip()

        if choice == '1':
            return "stretch"

        if choice == '2':
            return "crop"

        if choice == '0':
            print_green("Operation cancelled.")
            return None

        attempts += 1

        if attempts < 3:
            print_green("Invalid selection.")
        else:
            print_green("Too many invalid attempts. Exiting.")
            return None


def download_thumbnail_file(item_url, safe_title):
    thumb_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'writethumbnail': True,
        'outtmpl': safe_title.replace('%', '%%'),
        'logger': QuietLogger(),
    }

    with yt_dlp.YoutubeDL(thumb_opts) as ydl:
        try:
            ydl.download([item_url])
        except Exception as e:
            log_error(item_url, f"thumbnail download failed: {e}")

    for ext in ['.webp', '.jpg', '.png']:
        if os.path.exists(f"{safe_title}{ext}"):
            return f"{safe_title}{ext}"

    return None


def progress_hook(d):
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate')

        if not total:
            return

        pct = d.get('downloaded_bytes', 0) / total
        filled = int(pct * 20)
        bar = '█' * filled + '░' * (20 - filled)

        speed = d.get('speed')
        sp = f"{speed / 1048576:.1f} MB/s" if speed else "--"

        eta = d.get('eta')
        eta_s = f"{eta}s" if eta is not None else "--"

        print(
            f"\r{GREEN}[{bar}] {pct * 100:5.1f}%{RESET} "
            f"{sp} ETA {eta_s}   ",
            end='',
            flush=True
        )

    elif d['status'] == 'finished':
        print(
            f"\r{GREEN}[{'█' * 20}] 100.0%{RESET}" + " " * 25
        )


def process_thumbnail_only(
    item_url, is_playlist, index, total, save_path,
    photo_quality, pre_info=None
):
    info = pre_info or fetch_info(item_url)

    if not info:
        return item_failed(
            index, total,
            'video not available (private, deleted, or region-locked)',
            item_url
        )

    title = info.get('title', 'thumbnail')
    safe_title = clean_filename(title)

    if is_playlist:
        print(f"\n[{index}/{total}] {title}")
    else:
        print()

    print("Fetching thumbnail...")

    custom_resolution = (
        isinstance(photo_quality, dict)
        and photo_quality.get("type") == "custom"
    )

    downloaded_thumb = None

    if isinstance(photo_quality, str) and photo_quality.startswith("http"):
        import urllib.request

        temp_img = f"{safe_title}_raw.jpg"

        try:
            urllib.request.urlretrieve(photo_quality, temp_img)
            downloaded_thumb = temp_img
        except Exception as e:
            log_error(
                item_url,
                f"direct thumbnail download failed: {e}"
            )

    if not downloaded_thumb:
        downloaded_thumb = download_thumbnail_file(
            item_url,
            safe_title
        )

    if not downloaded_thumb or not os.path.exists(downloaded_thumb):
        return item_failed(
            index, total,
            'could not download the thumbnail',
            item_url
        )

    if not ensure_dir(save_path):
        safe_remove(downloaded_thumb)
        return item_failed(
            index, total,
            'save folder is not writable',
            item_url
        )

    png_path = os.path.join(save_path, f"{safe_title}.png")

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i',
        downloaded_thumb
    ]

    if custom_resolution:
        width = photo_quality["width"]
        height = photo_quality["height"]

        video_dimensions = get_original_video_dimensions(info)

        method = choose_custom_thumbnail_method(
            video_dimensions,
            width,
            height
        )

        if method is None:
            safe_remove(downloaded_thumb)
            return False
        if method == "crop":
            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:(in_w-{width})/2:(in_h-{height})/2"
            )
        else:
            video_filter = f"scale={width}:{height}"

        ffmpeg_cmd.extend(['-vf', video_filter])

    ffmpeg_cmd.append(png_path)

    ok, why = run_ffmpeg(ffmpeg_cmd)

    if ok:
        safe_remove(downloaded_thumb)

        print("Thumbnail downloaded")

        if custom_resolution:
            print_green(f"Resolution: {width}x{height}")

        print_green(f"Saving to {save_path}")
        print(f"File #{index}/{total} saved")

        return True

    safe_remove(png_path)

    log_error(
        item_url,
        f"png conversion failed: {why}"
    )

    ext = os.path.splitext(downloaded_thumb)[1] or '.jpg'
    kept = os.path.join(save_path, f"{safe_title}{ext}")

    try:
        shutil.move(downloaded_thumb, kept)
    except OSError as e:
        safe_remove(downloaded_thumb)

        return item_failed(
            index, total,
            f"could not convert or keep the thumbnail ({short_reason(e)})",
            item_url
        )

    print(f"{YELLOW}PNG conversion failed ({why}){RESET}")
    print_green(f"Saved the original image instead: {kept}")
    print(f"File #{index}/{total} saved")

    return True


def process_single_item(
    item_url, mode, is_playlist, index, total, save_path, selected_format,
    pre_info=None, with_audio=True, want_sidecar=False, sidecar_text=None,
    resolved=None, quality_label=''
):
    """Download one audio or video item."""

    CURRENT_ITEM['safe_title'] = None

    try:
        return _process_single_item(
            item_url, mode, is_playlist, index, total, save_path,
            selected_format, pre_info, with_audio, want_sidecar,
            sidecar_text, resolved, quality_label
        )

    except KeyboardInterrupt:
        st = CURRENT_ITEM['safe_title']

        if st:
            cleanup_partials(st, f"{st}.png")

        print(
            f"\n{YELLOW}Cancelled. Temporary files were removed.{RESET}"
        )
        raise


def _process_single_item(
    item_url, mode, is_playlist, index, total, save_path, selected_format,
    pre_info, with_audio, want_sidecar, sidecar_text, resolved, quality_label
):
    info = pre_info or fetch_info(item_url)

    if not info:
        return item_failed(
            index, total,
            'video not available (private, deleted, or region-locked)',
            item_url
        )

    title = info.get('title', 'media')
    safe_title = clean_filename(title)
    CURRENT_ITEM['safe_title'] = safe_title

    png_path = f"{safe_title}.png"
    ext = 'mp3' if mode == '1' else 'mp4'
    video_only = mode == '2' and not with_audio

    custom_resolution = (
        mode == '2'
        and isinstance(selected_format, dict)
        and selected_format.get('type') == 'custom'
    )

    download_format = selected_format

    if custom_resolution:
        download_format = (
            'bestvideo+bestaudio/best'
            if with_audio
            else 'bestvideo/best'
        )

    temp_media = f"temp_{safe_title}.{ext}"
    final_output = os.path.join(save_path, f"{safe_title}.{ext}")

    if is_playlist:
        print(f"\n[{index}/{total}] {title}")

        if mode == '2':
            if custom_resolution:
                print_green(
                    f"Custom resolution: "
                    f"{selected_format['width']}x{selected_format['height']}"
                )
            else:
                resolved = resolve_quality(item_url, selected_format)
                announce_quality(
                    resolved,
                    quality_label or 'Best Quality',
                    lead=False
                )

        if want_sidecar and mode in ('1', '2'):
            sidecar_text = run_sidecar_step(
                'lyrics' if mode == '1' else 'subtitles',
                item_url,
                info,
                safe_title,
                ask=False
            )

    else:
        print()

    known_no_audio = bool(
        resolved
        and resolved.get('has_video')
        and not resolved.get('has_audio')
    )
    custom_method = None

    if custom_resolution:
        width = selected_format['width']
        height = selected_format['height']

        video_dimensions = get_original_video_dimensions(info)

        custom_method = choose_custom_video_method(
            video_dimensions,
            width,
            height
        )
        
        if custom_method is None:
            cleanup_partials(safe_title, png_path)
            return False
        
        download_format = select_custom_video_format(
            info,
            width,
            height,
            custom_method,
            with_audio
        )
    # ---- thumbnail / cover art ----

    print("Fetching thumbnail...")
    have_cover = False

    downloaded_thumb = download_thumbnail_file(
        item_url,
        safe_title
    )

    if downloaded_thumb and os.path.exists(downloaded_thumb):

        if downloaded_thumb == png_path:
            moved = f"{safe_title}_src.png"

            try:
                os.replace(downloaded_thumb, moved)
                downloaded_thumb = moved
            except OSError:
                pass

        if mode == '1':
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', downloaded_thumb,
                '-vf', 'crop=ih:ih', png_path
            ]
        else:
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', downloaded_thumb, png_path
            ]

        ok, why = run_ffmpeg(ffmpeg_cmd)
        safe_remove(downloaded_thumb)

        if ok and os.path.exists(png_path):
            have_cover = True
            print("Thumbnail downloaded")
        else:
            safe_remove(png_path)

            print(
                f"{YELLOW}Thumbnail conversion failed "
                f"({why or 'unknown error'}), continuing without cover art{RESET}"
            )

            log_error(
                item_url,
                f"thumbnail conversion failed: {why}"
            )

    else:
        print(
            f"{YELLOW}No thumbnail available, continuing without cover art{RESET}"
        )

    # ---- download ----

    if not ensure_dir(save_path):
        cleanup_partials(safe_title, png_path)

        return item_failed(
            index, total,
            'save folder is not writable',
            item_url
        )

    print_green("Starting download")

    out_base = f"temp_{safe_title}".replace('%', '%%')

    if mode == '1':
        dl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_base + '.%(ext)s',
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': selected_format
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True
                },
            ],
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'logger': QuietLogger(),
        }

    elif video_only:
        dl_opts = {
            'format': download_format,
            'format_sort': FORMAT_SORT,
            'outtmpl': out_base + '.%(ext)s',
            'postprocessors': [
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                    'add_chapters': True
                }
            ],
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'logger': QuietLogger(),
        }

    else:
        dl_opts = {
            'format': download_format,
            'format_sort': FORMAT_SORT,
            'outtmpl': out_base + '.mp4',
            'merge_output_format': 'mp4',
            'postprocessors': [
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                    'add_chapters': True
                }
            ],
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'logger': QuietLogger(),
        }

    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([item_url])

    except Exception as e:
        print()
        cleanup_partials(safe_title, png_path)

        return item_failed(
            index, total,
            f"download failed ({short_reason(e)})",
            item_url
        )

    print("Finished download")

    if video_only:
        candidates = [
            path
            for path in glob.glob(
                glob.escape(f"temp_{safe_title}") + ".*"
            )
            if not path.lower().endswith(('.part', '.ytdl'))
        ]

        if candidates:
            temp_media = max(candidates, key=os.path.getmtime)

    if not os.path.exists(temp_media):
        cleanup_partials(safe_title, png_path)

        return item_failed(
            index, total,
            'the download finished but the file is missing (is ffmpeg working?)',
            item_url
        )

    
    # ---- custom video resolution ----

    if custom_resolution:
        width = selected_format['width']
        height = selected_format['height']

        if custom_method == "crop":
            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:(in_w-{width})/2:(in_h-{height})/2"
            )
        else:
            video_filter = f"scale={width}:{height}"

        resized_media = f"temp_{safe_title}_resized.mp4"

        resize_cmd = [
            'ffmpeg',
            '-y',
            '-i',
            temp_media,
            '-map',
            '0:v:0',
            '-vf',
            video_filter,
            '-c:v',
            'libx264',
            '-preset',
            'ultrafast',
            '-crf',
            '23',
            '-pix_fmt',
            'yuv420p',
        ]

        if with_audio:
            resize_cmd.extend([
                '-map',
                '0:a?',
                '-c:a',
                'copy'
            ])
        else:
            resize_cmd.append('-an')

        resize_cmd.extend([
            '-movflags',
            '+faststart',
            resized_media
        ])

        print_green(
            f"Resizing video to {width}x{height}..."
        )

        ok, why = run_ffmpeg_with_progress(
            resize_cmd,
            info.get('duration')
        )

        if not ok or not os.path.exists(resized_media):
            safe_remove(resized_media)
            cleanup_partials(safe_title, png_path)

            log_error(
                item_url,
                f"custom video resizing failed: {why}"
            )

            return item_failed(
                index, total,
                f"could not resize video ({short_reason(why)})",
                item_url
            )

        safe_remove(temp_media)
        temp_media = resized_media

        print_green(
            f"Video resized to {width}x{height}"
        )

    # ---- save, with cover art when possible ----

    print_green(f"Saving to {save_path}")

    cover_done = False
    cover_failed = False

    if video_only:

        def remux(with_cover):
            cmd = [
                'ffmpeg',
                '-y',
                '-i',
                temp_media
            ]

            if with_cover:
                cmd += ['-i', png_path]

            cmd += ['-map', '0:v:0']

            if with_cover:
                cmd += ['-map', '1']

            cmd += ['-c', 'copy']

            if with_cover:
                cmd += ['-disposition:v:1', 'attached_pic']

            cmd.append(final_output)

            return run_ffmpeg(cmd)

        ok, why = False, ''

        if have_cover and os.path.exists(png_path):
            ok, why = remux(True)

            if not ok:
                cover_failed = True
                safe_remove(final_output)

                print(
                    f"{YELLOW}Adding cover art failed "
                    f"({why or 'unknown error'}){RESET}"
                )

                log_error(
                    item_url,
                    f"cover art failed: {why}"
                )

        if not ok:
            ok, why = remux(False)

        if ok and os.path.exists(final_output):
            cover_done = True
            safe_remove(temp_media)

            if cover_failed:
                print_green("Saved without cover art")

        else:
            safe_remove(final_output)

            log_error(
                item_url,
                f"video-only repackaging failed: {why}"
            )

            if known_no_audio:
                raw_ext = os.path.splitext(temp_media)[1] or '.mp4'
                final_output = os.path.join(
                    save_path,
                    f"{safe_title}{raw_ext}"
                )

                try:
                    shutil.move(temp_media, final_output)

                except OSError as e:
                    cleanup_partials(safe_title, png_path)

                    return item_failed(
                        index, total,
                        f"could not save the file ({short_reason(e)})",
                        item_url
                    )

                print(
                    f"{YELLOW}Could not repackage the video "
                    f"({why}), saved the original stream instead{RESET}"
                )

                cover_done = True

            else:
                cleanup_partials(safe_title, png_path)

                return item_failed(
                    index, total,
                    f"could not remove the audio track ({why})",
                    item_url
                )

    elif have_cover and os.path.exists(png_path):

        if mode == '1':
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_media,
                '-i', png_path,
                '-map', '0:0',
                '-map', '1:0',
                '-c', 'copy',
                '-id3v2_version', '3',
                '-metadata:s:v', 'title="Album cover"',
                '-metadata:s:v', 'comment="Cover (front)"',
                final_output
            ]

        else:
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_media,
                '-i', png_path,
                '-map', '0',
                '-map', '1',
                '-c', 'copy',
                '-disposition:v:1', 'attached_pic',
                final_output
            ]

        ok, why = run_ffmpeg(cmd)

        if ok and os.path.exists(final_output):
            cover_done = True
            safe_remove(temp_media)

        else:
            cover_failed = True
            safe_remove(final_output)

            print(
                f"{YELLOW}Adding cover art failed "
                f"({why or 'unknown error'}){RESET}"
            )

            log_error(
                item_url,
                f"cover art failed: {why}"
            )

    if not cover_done:
        try:
            shutil.move(temp_media, final_output)

        except OSError as e:
            cleanup_partials(safe_title, png_path)

            return item_failed(
                index, total,
                f"could not save the file ({short_reason(e)})",
                item_url
            )

        if cover_failed:
            print_green("Saved without cover art")

    safe_remove(png_path)

    # ---- lyrics / subtitles ----

    if sidecar_text:
        kind = 'lyrics' if mode == '1' else 'subtitles'

        side_path = os.path.splitext(final_output)[0] + (
            '.lrc' if mode == '1' else '.srt'
        )

        ok, why = write_sidecar(
            side_path,
            sidecar_text,
            kind
        )

        if not ok:
            print(
                f"{YELLOW}{kind.capitalize()} "
                f"could not be saved ({why}){RESET}"
            )

            log_error(
                item_url,
                f"{kind} not saved: {why}"
            )

    print(f"File #{index}/{total} saved")
    return True
