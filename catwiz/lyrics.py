"""Synchronized lyrics from LRCLIB (with a fall back to captions)."""

import json as _json
import re

from .captions import pick_caption_track, valid_lrc
from .utils import log_error, short_reason

USER_AGENT = 'CatWiz (https://github.com/Dr-Jesus1225/catwiz)'
LRCLIB_API = 'https://lrclib.net/api'

class ProviderError(Exception):
    """A lyrics provider could not be reached or returned something unusable."""

def _http_get_json(path, params, timeout=10):
    import urllib.request, urllib.parse, urllib.error
    req = urllib.request.Request(f"{LRCLIB_API}/{path}?{urllib.parse.urlencode(params)}",
                                 headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return _json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise ProviderError(f"LRCLIB returned HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ProviderError(f"LRCLIB unreachable ({short_reason(e)})")

def _norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()

def music_metadata(info, url):
    """Return (track, artist, album, duration) when this looks like a song, else None."""
    track = info.get('track')
    artist = (info.get('artist') or '').split(',')[0].strip()
    is_music_url = 'music.youtube.com' in (url or '')
    if not (track and artist) and not is_music_url:
        return None
    if not track:
        track = info.get('title') or ''
        track = re.sub(r'\s*[\(\[][^)\]]*(official|video|audio|lyric|visuali[sz]er|hd|4k)[^)\]]*[\)\]]', '', track, flags=re.I).strip()
    if not artist:
        artist = re.sub(r'\s*-\s*Topic$', '', info.get('uploader') or info.get('channel') or '').strip()
    if not track or not artist:
        return None
    return track, artist, info.get('album') or '', info.get('duration')

def lrclib_lookup(info, url):
    """Return LRC text (synchronized lyrics only) or None. Raises ProviderError on network problems."""
    meta = music_metadata(info, url)
    if not meta:
        return None
    track, artist, album, duration = meta
    found = None
    if album and duration:
        found = _http_get_json('get', {'track_name': track, 'artist_name': artist,
                                       'album_name': album, 'duration': int(duration)})
    if not (found and found.get('syncedLyrics')):
        results = _http_get_json('search', {'track_name': track, 'artist_name': artist}) or []
        best, best_diff = None, None
        for r in results:
            if not r.get('syncedLyrics'):
                continue
            diff = abs((r.get('duration') or 0) - duration) if duration else 0
            if duration and diff > 4:
                continue
            if _norm(artist) not in _norm(r.get('artistName')) and _norm(r.get('artistName')) not in _norm(artist):
                continue
            if best is None or diff < best_diff:
                best, best_diff = r, diff
        found = best
    if not found or not found.get('syncedLyrics'):
        return None
    header = [f"[ti:{found.get('trackName') or track}]", f"[ar:{found.get('artistName') or artist}]"]
    if found.get('albumName'):
        header.append(f"[al:{found['albumName']}]")
    return '\n'.join(header) + '\n' + found['syncedLyrics'].strip() + '\n'

def find_lyrics(url, info):
    """Return a descriptor of where lyrics can come from, or None."""
    err = None
    try:
        text = lrclib_lookup(info, url)
        if valid_lrc(text):
            return {'source': 'lrclib', 'text': text}
    except ProviderError as e:
        err = e
        log_error(url, f"lyrics provider problem: {e}")
    track = pick_caption_track(info)
    if track:
        return {'source': 'captions', 'lang': track[0], 'auto': track[1]}
    if err:
        raise err
    return None

