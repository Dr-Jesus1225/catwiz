"""Downloading audio, video and thumbnails."""

import glob
import os
import shutil
import yt_dlp

from .captions import write_sidecar
from .links import fetch_info
from .quality import FORMAT_SORT, announce_quality, resolve_quality
from .sidecar import run_sidecar_step
from .ui import GREEN, RESET, YELLOW, print_green
from .utils import QuietLogger, clean_filename, cleanup_partials, ensure_dir, item_failed, log_error, run_ffmpeg, safe_remove, short_reason


def get_original_video_dimensions(info):
    """Find the largest available original video dimensions in yt-dlp metadata."""
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

    return max(candidates, key=lambda dimensions: dimensions[0] * dimensions[1])


def choose_custom_thumbnail_method(video_dimensions, target_width, target_height):
    """Choose how to handle a custom resolution with a different aspect ratio."""

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
            f"{YELLOW}Original video dimensions could not be detected."
            f" Choose how to resize the thumbnail manually.{RESET}"
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
            sys.exit(0)

        attempts += 1

        if attempts < 3:
            print_green("Invalid selection.")
        else:
            print_green("Too many invalid attempts. Exiting.")
            sys.exit(1)


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
        print(f"\r{GREEN}[{bar}] {pct * 100:5.1f}%{RESET} {sp} ETA {eta_s}   ", end='', flush=True)
    elif d['status'] == 'finished':
        print(f"\r{GREEN}[{'█' * 20}] 100.0%{RESET}" + " " * 25)


def process_thumbnail_only(item_url, is_playlist, index, total, save_path, photo_quality, pre_info=None):
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

        if method == "crop":
            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:(in_w-{width})/2:(in_h-{height})/2"
            )
        else:
            video_filter = f"scale={width}:{height}"

        ffmpeg_cmd.extend([
            '-vf',
            video_filter
        ])

    ffmpeg_cmd.append(png_path)

    ok, why = run_ffmpeg(ffmpeg_cmd)

    if ok:
        safe_remove(downloaded_thumb)

        print("Thumbnail downloaded")

        if custom_resolution:
            print_green(
                f"Resolution: {width}x{height}"
            )

        print_green(f"Saving to {save_path}")
        print(f"File #{index}/{total} saved")

        return True

    # Conversion failed: keep the original image instead of losing it.
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


def process_single_item(item_url, mode, is_playlist, index, total, save_path, selected_format,
                        pre_info=None, with_audio=True, want_sidecar=False, sidecar_text=None,
                        resolved=None, quality_label=''):
    """mode '1' = audio (.mp3), mode '2' = video (.mp4).
    with_audio=False downloads video only. sidecar_text is lyrics (.lrc) or subtitles (.srt)
    that were already fetched; want_sidecar lets playlist items look for their own."""
    CURRENT_ITEM['safe_title'] = None
    try:
        return _process_single_item(item_url, mode, is_playlist, index, total, save_path, selected_format,
                                    pre_info, with_audio, want_sidecar, sidecar_text, resolved, quality_label)
    except KeyboardInterrupt:
        st = CURRENT_ITEM['safe_title']
        if st:
            cleanup_partials(st, f"{st}.png")
        print(f"\n{YELLOW}Cancelled. Temporary files were removed.{RESET}")
        raise

def _process_single_item(item_url, mode, is_playlist, index, total, save_path, selected_format,
                         pre_info, with_audio, want_sidecar, sidecar_text, resolved, quality_label):
    info = pre_info or fetch_info(item_url)
    if not info:
        return item_failed(index, total, 'video not available (private, deleted, or region-locked)', item_url)

    title = info.get('title', 'media')
    safe_title = clean_filename(title)
    CURRENT_ITEM['safe_title'] = safe_title
    png_path = f"{safe_title}.png"
    ext = 'mp3' if mode == '1' else 'mp4'
    video_only = (mode == '2' and not with_audio)
    temp_media = f"temp_{safe_title}.{ext}"
    final_output = os.path.join(save_path, f"{safe_title}.{ext}")

    if is_playlist:
        print(f"\n[{index}/{total}] {title}")
        if mode == '2':
            resolved = resolve_quality(item_url, selected_format)
            announce_quality(resolved, quality_label or 'Best Quality', lead=False)
        if want_sidecar and mode in ('1', '2'):
            sidecar_text = run_sidecar_step('lyrics' if mode == '1' else 'subtitles',
                                            item_url, info, safe_title, ask=False)
    else:
        print()
    known_no_audio = bool(resolved and resolved.get('has_video') and not resolved.get('has_audio'))

    # ---- thumbnail / cover art ----
    print("Fetching thumbnail...")
    have_cover = False
    downloaded_thumb = download_thumbnail_file(item_url, safe_title)
    if downloaded_thumb and os.path.exists(downloaded_thumb):
        if downloaded_thumb == png_path:
            # input and output would be the same file, so move the input aside first
            moved = f"{safe_title}_src.png"
            try:
                os.replace(downloaded_thumb, moved)
                downloaded_thumb = moved
            except OSError:
                pass
        if mode == '1':
            ffmpeg_cmd = ['ffmpeg', '-y', '-i', downloaded_thumb, '-vf', 'crop=ih:ih', png_path]
        else:
            ffmpeg_cmd = ['ffmpeg', '-y', '-i', downloaded_thumb, png_path]
        ok, why = run_ffmpeg(ffmpeg_cmd)
        safe_remove(downloaded_thumb)
        if ok and os.path.exists(png_path):
            have_cover = True
            print("Thumbnail downloaded")
        else:
            safe_remove(png_path)
            print(f"{YELLOW}Thumbnail conversion failed ({why or 'unknown error'}), continuing without cover art{RESET}")
            log_error(item_url, f"thumbnail conversion failed: {why}")
    else:
        print(f"{YELLOW}No thumbnail available, continuing without cover art{RESET}")

    # ---- download ----
    if not ensure_dir(save_path):
        cleanup_partials(safe_title, png_path)
        return item_failed(index, total, 'save folder is not writable', item_url)

    print_green("Starting download")
    out_base = f"temp_{safe_title}".replace('%', '%%')
    if mode == '1':
        dl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_base + '.%(ext)s',
            'postprocessors': [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': selected_format},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
            ],
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'logger': QuietLogger(),
        }
    elif video_only:
        dl_opts = {
            'format': selected_format,
            'format_sort': FORMAT_SORT,
            'outtmpl': out_base + '.%(ext)s',
            'postprocessors': [{'key': 'FFmpegMetadata', 'add_metadata': True, 'add_chapters': True}],
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'logger': QuietLogger(),
        }
    else:
        dl_opts = {
            'format': selected_format,
            'format_sort': FORMAT_SORT,
            'outtmpl': out_base + '.mp4',
            'merge_output_format': 'mp4',
            'postprocessors': [{'key': 'FFmpegMetadata', 'add_metadata': True, 'add_chapters': True}],
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
        return item_failed(index, total, f"download failed ({short_reason(e)})", item_url)

    print("Finished download")

    if video_only:
        # the stream keeps its own extension (mp4, webm...), so find it
        cands = [p for p in glob.glob(glob.escape(f"temp_{safe_title}") + ".*")
                 if not p.lower().endswith(('.part', '.ytdl'))]
        if cands:
            temp_media = max(cands, key=os.path.getmtime)

    if not os.path.exists(temp_media):
        cleanup_partials(safe_title, png_path)
        return item_failed(index, total, 'the download finished but the file is missing (is ffmpeg working?)', item_url)

    # ---- save, with cover art when possible ----
    print_green(f"Saving to {save_path}")
    cover_done = False
    cover_failed = False

    if video_only:
        # Repackage with only the video stream, so the file can never contain audio
        def remux(with_cover):
            cmd = ['ffmpeg', '-y', '-i', temp_media]
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
                print(f"{YELLOW}Adding cover art failed ({why or 'unknown error'}){RESET}")
                log_error(item_url, f"cover art failed: {why}")
        if not ok:
            ok, why = remux(False)
        if ok and os.path.exists(final_output):
            cover_done = True
            safe_remove(temp_media)
            if cover_failed:
                print_green("Saved without cover art")
        else:
            safe_remove(final_output)
            log_error(item_url, f"video-only repackaging failed: {why}")
            if known_no_audio:
                raw_ext = os.path.splitext(temp_media)[1] or '.mp4'
                final_output = os.path.join(save_path, f"{safe_title}{raw_ext}")
                try:
                    shutil.move(temp_media, final_output)
                except OSError as e:
                    cleanup_partials(safe_title, png_path)
                    return item_failed(index, total, f"could not save the file ({short_reason(e)})", item_url)
                print(f"{YELLOW}Could not repackage the video ({why}), saved the original stream instead{RESET}")
                cover_done = True
            else:
                cleanup_partials(safe_title, png_path)
                return item_failed(index, total, f"could not remove the audio track ({why})", item_url)
    elif have_cover and os.path.exists(png_path):
        if mode == '1':
            cmd = [
                'ffmpeg', '-y', '-i', temp_media, '-i', png_path,
                '-map', '0:0', '-map', '1:0', '-c', 'copy',
                '-id3v2_version', '3',
                '-metadata:s:v', 'title="Album cover"',
                '-metadata:s:v', 'comment="Cover (front)"',
                final_output
            ]
        else:
            cmd = [
                'ffmpeg', '-y', '-i', temp_media, '-i', png_path,
                '-map', '0', '-map', '1',
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
            safe_remove(final_output)  # remove the broken partial file
            print(f"{YELLOW}Adding cover art failed ({why or 'unknown error'}){RESET}")
            log_error(item_url, f"cover art failed: {why}")

    if not cover_done:
        try:
            shutil.move(temp_media, final_output)
        except OSError as e:
            cleanup_partials(safe_title, png_path)
            return item_failed(index, total, f"could not save the file ({short_reason(e)})", item_url)
        if cover_failed:
            print_green("Saved without cover art")

    safe_remove(png_path)

    # ---- lyrics / subtitles file, named after the media file ----
    if sidecar_text:
        kind = 'lyrics' if mode == '1' else 'subtitles'
        side_path = os.path.splitext(final_output)[0] + ('.lrc' if mode == '1' else '.srt')
        ok, why = write_sidecar(side_path, sidecar_text, kind)
        if not ok:
            print(f"{YELLOW}{kind.capitalize()} could not be saved ({why}){RESET}")
            log_error(item_url, f"{kind} not saved: {why}")

    print(f"File #{index}/{total} saved")
    return True
