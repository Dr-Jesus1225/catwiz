"""Caption/subtitle parsing, LRC and SRT conversion, and writing the lyrics/subtitle files."""

import glob
import html as _html
import os
import re
import yt_dlp

from .utils import QuietLogger, safe_remove, short_reason

TIME_RE = re.compile(r'((?:\d+:)?\d+:\d+[.,]\d+)\s*-->\s*((?:\d+:)?\d+:\d+[.,]\d+)')

TAG_RE = re.compile(r'<[^>]+>')

def _to_seconds(t):
    secs = 0.0
    for part in t.replace(',', '.').split(':'):
        secs = secs * 60 + float(part)
    return secs

def _clean_cue_line(line):
    line = _html.unescape(TAG_RE.sub('', line)).replace('\u00a0', ' ')
    return re.sub(r'\s+', ' ', line).strip()

def parse_caption_text(text):
    """Parse WebVTT or SRT into [(start, end, [lines])]."""
    cues = []
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    for block in re.split(r'\n{2,}', text):
        lines = block.strip('\n').split('\n')
        for i, line in enumerate(lines):
            m = TIME_RE.search(line)
            if m:
                body = [_clean_cue_line(l) for l in lines[i + 1:]]
                cues.append((_to_seconds(m.group(1)), _to_seconds(m.group(2)), [b for b in body if b]))
                break
    return cues

def dedupe_rolling(cues):
    """Automatic captions repeat the previous line in every cue. Keep only the new text."""
    out = []
    prev = []
    for start, end, lines in cues:
        new = [l for l in lines if l not in prev]
        prev = lines
        if new:
            out.append((start, end, new))
    return out

def _lrc_stamp(sec):
    cs = int(round(sec * 100))
    m, rem = divmod(cs, 6000)
    s, c = divmod(rem, 100)
    return f"[{m:02d}:{s:02d}.{c:02d}]"

def cues_to_lrc(cues, header=None):
    rows = []
    for start, _end, lines in sorted(cues, key=lambda c: c[0]):
        text = ' '.join(lines).strip()
        if text:
            rows.append(f"{_lrc_stamp(start)}{text}")
    if not rows:
        return None
    return '\n'.join((header or []) + rows) + '\n'

def _srt_stamp(sec):
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def cues_to_srt(cues):
    blocks = []
    n = 0
    for start, end, lines in sorted(cues, key=lambda c: c[0]):
        if not lines:
            continue
        if end <= start:
            end = start + 1.0
        n += 1
        blocks.append(f"{n}\n{_srt_stamp(start)} --> {_srt_stamp(end)}\n" + '\n'.join(lines))
    if not blocks:
        return None
    return '\n\n'.join(blocks) + '\n'

def valid_lrc(text):
    return bool(text) and len(re.findall(r'^\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]\s*\S', text, re.M)) >= 1

def valid_srt(text):
    return bool(text) and len(re.findall(r'^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n\S', text, re.M)) >= 1

def pick_caption_track(info):
    """Return (language key, is_automatic) or None. Manual subtitles win over automatic captions."""
    def usable(d):
        return {k: v for k, v in (d or {}).items() if v and k != 'live_chat'}
    manual = usable(info.get('subtitles'))
    auto = usable(info.get('automatic_captions'))
    lang = (info.get('language') or '').split('-')[0].lower()
    if manual:
        if lang:
            for k in manual:
                if k.split('-')[0].lower() == lang:
                    return k, False
        for k in manual:
            if k.split('-')[0].lower() == 'en':
                return k, False
        return next(iter(manual)), False
    if auto:
        for k in auto:
            if k.endswith('-orig'):
                return k, True
        for cand in (lang, 'en'):
            if cand and cand in auto:
                return cand, True
    return None

def download_caption_cues(url, lang, is_auto, safe_title):
    """Download one caption track with yt-dlp and return cleaned cues."""
    base = f"cap_{safe_title}"
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [lang],
        'subtitlesformat': 'vtt',
        'noplaylist': True,
        'outtmpl': base.replace('%', '%%'),
        'logger': QuietLogger(),
    }
    files = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = sorted(glob.glob(glob.escape(base) + '.*'))
        files = [f for f in files if f.lower().endswith(('.vtt', '.srt'))]
        if not files:
            return []
        with open(files[0], 'r', encoding='utf-8', errors='replace') as f:
            cues = parse_caption_text(f.read())
    finally:
        for f in glob.glob(glob.escape(base) + '.*'):
            safe_remove(f)
    return dedupe_rolling(cues) if is_auto else cues

def find_subtitles(info):
    track = pick_caption_track(info)
    return {'source': 'captions', 'lang': track[0], 'auto': track[1]} if track else None

def write_sidecar(path, text, kind):
    """Write the file only if it is valid, using a temp file so a partial file is never left behind."""
    check = valid_lrc if kind == 'lyrics' else valid_srt
    if not check(text):
        return False, 'invalid content'
    tmp = path + '.part'
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
        return True, ''
    except OSError as e:
        safe_remove(tmp)
        return False, short_reason(e)
