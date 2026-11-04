"""The optional lyrics (.lrc) and subtitles (.srt) step: check, ask, download."""

from .captions import cues_to_lrc, cues_to_srt, download_caption_cues, find_subtitles, valid_lrc, valid_srt
from .lyrics import ProviderError, find_lyrics
from .ui import RESET, YELLOW, ask_yn
from .utils import log_error, short_reason

def materialize(found, kind, url, safe_title):
    """Produce the final LRC/SRT text for a found source. Returns None if nothing valid came out."""
    if found['source'] == 'lrclib':
        return found['text'] if valid_lrc(found['text']) else None
    cues = download_caption_cues(url, found['lang'], found['auto'], safe_title)
    text = cues_to_lrc(cues) if kind == 'lyrics' else cues_to_srt(cues)
    check = valid_lrc if kind == 'lyrics' else valid_srt
    return text if check(text) else None

def run_sidecar_step(kind, url, info, safe_title, ask):
    """Check for lyrics ('lyrics') or subtitles ('subtitles'), optionally ask, and fetch.
    Returns the converted text, or None. Never raises for provider or conversion problems."""
    noun = 'lyrics' if kind == 'lyrics' else 'subtitles'
    print(f"Checking for {noun}...")
    provider_down = False
    try:
        found = find_lyrics(url, info) if kind == 'lyrics' else find_subtitles(info)
    except ProviderError:
        found, provider_down = None, True
    if not found:
        if kind == 'lyrics':
            print("Lyrics not found" + (" (lyrics provider unavailable)" if provider_down else ""))
        else:
            print("Subtitles not found")
            print("Continuing without subtitles...")
        return None
    print("Lyrics found" if kind == 'lyrics' else "Subtitles found")
    if ask and not ask_yn(f"Do you want to download {noun}?"):
        return None
    print("Downloading Lyrics" if kind == 'lyrics' else "Downloading Subtitles")
    try:
        text = materialize(found, kind, url, safe_title)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        log_error(url, f"{noun} download failed: {e}")
        print(f"{YELLOW}{noun.capitalize()} download failed ({short_reason(e)}){RESET}")
        return None
    if not text:
        log_error(url, f"{noun}: no valid data")
        print(f"{YELLOW}{noun.capitalize()} download failed (no valid data){RESET}")
        return None
    print("Lyrics Downloaded" if kind == 'lyrics' else "Subtitles downloaded")
    return text
