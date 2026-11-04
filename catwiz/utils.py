"""Small shared helpers: file names, error log, ffmpeg runner, cleanup of temp files."""

from datetime import datetime
import glob
import os
import re
import subprocess

from .ui import RED, RESET

PROGRAM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the folder that holds main.py
ERROR_LOG = os.path.join(PROGRAM_DIR, 'errors.log')

class QuietLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

def clean_filename(title):
    name = re.sub(r'[\\/*?:"<>|]', "", title).strip(' .')[:150].strip(' .')
    return name or 'media'

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

def log_error(context, detail):
    """Append a line to errors.log so problems can be reported later."""
    try:
        with open(ERROR_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {context}: {detail}\n")
    except OSError:
        pass

def short_reason(err, limit=140):
    text = ANSI_RE.sub('', str(err)).strip()
    text = re.sub(r'^(ERROR:\s*)+', '', text)
    line = text.splitlines()[0] if text else 'unknown error'
    return line[:limit]

def run_ffmpeg(cmd):
    """Run ffmpeg and return (ok, reason). The reason is the last line ffmpeg printed on failure."""
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           text=True, errors='replace')
    except FileNotFoundError:
        return False, 'ffmpeg not found'
    except OSError as e:
        return False, short_reason(e)
    if r.returncode == 0:
        return True, ''
    lines = [l.strip() for l in (r.stderr or '').splitlines() if l.strip()]
    return False, (lines[-1][:140] if lines else f'exit code {r.returncode}')

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        print(f"{RED}Can't write to {path} ({short_reason(e)}){RESET}")
        if os.path.isdir('/data/data/com.termux'):
            print("On Termux, run termux-setup-storage and allow storage access.")
        log_error('save folder', f"{path}: {e}")
        return False

def safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

def cleanup_partials(safe_title, png_path):
    for p in glob.glob(glob.escape(f"temp_{safe_title}") + ".*") + glob.glob(glob.escape(f"cap_{safe_title}") + ".*"):
        safe_remove(p)
    safe_remove(png_path)
    for ext in ('.webp', '.jpg', '.png'):
        safe_remove(f"{safe_title}{ext}")

def item_failed(index, total, why, context):
    print(f"{RED}File #{index}/{total} failed: {why}{RESET}")
    log_error(context, why)
    return False

def format_duration(sec):
    if not sec:
        return "Unknown"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, sc = divmod(rem, 60)
    return f"{h}:{m:02d}:{sc:02d}" if h else f"{m}:{sc:02d}"
