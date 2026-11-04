"""Video format selection and the "actual resolution" lookup."""

import yt_dlp

from .utils import QuietLogger, log_error

FORMAT_SORT = ['res', 'vcodec:h264', 'acodec:aac']

def make_video_format(height, with_audio):
    cap = f"[height<={height}]" if height else ''
    if with_audio:
        return f"bestvideo{cap}+bestaudio/best{cap}"
    return f"bestvideo{cap}/best{cap}"

def _has(codec):
    return codec not in (None, 'none')

def resolve_quality(url, fmt):
    """Ask yt-dlp which format(s) this selection really picks. Returns a dict or None."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'format': fmt,
        'format_sort': FORMAT_SORT,
        'logger': QuietLogger(),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
    except Exception as e:
        log_error(url, f"could not resolve quality: {e}")
        return None
    if not data:
        return None
    fmts = data.get('requested_formats') or [data]
    video = next((f for f in fmts if _has(f.get('vcodec'))), None)
    height = None
    if video:
        w, h = video.get('width'), video.get('height')
        if isinstance(w, int) and isinstance(h, int):
            height = min(w, h)  # YouTube names resolutions by the short side
        elif isinstance(h, int):
            height = h
    return {
        'height': height,
        'has_audio': any(_has(f.get('acodec')) for f in fmts),
        'has_video': video is not None,
    }

def announce_quality(resolved, label, lead=True):
    h = resolved.get('height') if resolved else None
    if h:
        text = f"{h}p quality selected"
    elif label.lower().startswith('best'):
        text = "Best available quality selected"
    else:
        text = f"{label} quality selected"
    print(("\n" if lead else "") + text)
