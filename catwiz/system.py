"""Operating system details: platform, paths, package manager helpers, ffmpeg check."""

import os
import re
import shutil
import subprocess
import sys
import json
import itertools

from .ui import RED, RESET


def get_default_download_dir():
    if os.path.isdir('/sdcard/Download'):
        return '/sdcard/Download'
    return os.path.join(os.path.expanduser('~'), 'Downloads')


def get_config_file():
    config_dir = os.path.join(os.path.expanduser('~'), '.catwiz')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'config.json')




def get_download_dir():
    default_root = os.path.join(get_default_download_dir(), 'CatWiz')

    try:
        with open(get_config_file(), 'r', encoding='utf-8') as f:
            config = json.load(f)

        if not isinstance(config, dict):
            config = {}

        custom_path = config.get('download_location')

        if isinstance(custom_path, str) and custom_path.strip():
            custom_path = os.path.abspath(
                os.path.expanduser(
                    os.path.expandvars(custom_path.strip())
                )
            )

            is_naked = (
                os.path.basename(os.path.normpath(custom_path)).lower()
                != 'catwiz'
            )

            if is_naked:
                return os.path.join(custom_path, 'CatWiz')

            return custom_path

    except (OSError, ValueError, TypeError, AttributeError):
        pass

    return default_root

def set_download_dir(path):
    config_file = get_config_file()

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            if not isinstance(config, dict):
                config = {}
    except (OSError, ValueError):
        config = {}

    config['download_location'] = os.path.abspath(
        os.path.expanduser(os.path.expandvars(path))
    )

    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
    try:
        from .logging_service import log_activity
        log_activity('Download folder preference updated', component='settings')
    except Exception:
        pass

def get_category_dir(category):
    """Return the folder for a download category."""
    folders = {
        'audio': 'Audios',
        'video': 'Videos',
        'thumbnail': 'Thumbnails'
    }

    if category not in folders:
        raise ValueError(f"Unknown download category: {category}")

    return os.path.join(get_download_dir(), folders[category])


def check_ffmpeg():
    if shutil.which('ffmpeg') is None:
        print(f"{RED}ffmpeg was not found.{RESET}")
        print("Install it, then reopen this terminal:")
        print("  Windows: winget install Gyan.FFmpeg")
        print("  Termux:  pkg install ffmpeg")
        print("  Debian:  sudo apt install ffmpeg")
        print("  macOS:   brew install ffmpeg")
        sys.exit(1)

IS_WINDOWS = os.name == 'nt'

IS_MAC = sys.platform == 'darwin'

IS_TERMUX = os.path.isdir('/data/data/com.termux') or 'com.termux' in os.environ.get('PREFIX', '')

SIZES_MB = {
    'windows': {'ffmpeg': 300, 'yt-dlp': 20, 'python': 100, 'git': 350},
    'termux':  {'ffmpeg': 150, 'yt-dlp': 20, 'python': 100, 'git': 40},
    'linux':   {'ffmpeg': 250, 'yt-dlp': 20, 'python': 60,  'git': 50},
    'mac':     {'ffmpeg': 400, 'yt-dlp': 20, 'python': 150, 'git': 60},
}

DISPLAY = {'ffmpeg': 'FFmpeg', 'yt-dlp': 'yt-dlp', 'python': 'Python', 'git': 'Git'}

def platform_key():
    if IS_WINDOWS:
        return 'windows'
    if IS_TERMUX:
        return 'termux'
    if IS_MAC:
        return 'mac'
    return 'linux'

def fmt_mb(mb):
    return f"{mb:.1f} MB" if mb < 10 else f"{int(round(mb))} MB"

def folder_size_mb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1048576

def program_dir_is_safe(path):
    """Only allow deleting a folder that really looks like this project."""
    real = os.path.realpath(path)
    home = os.path.realpath(os.path.expanduser('~'))
    if real == home or os.path.dirname(real) == real:
        return False
    if not (os.path.isfile(os.path.join(real, 'main.py')) and os.path.isdir(os.path.join(real, 'catwiz'))):
        return False
    name = os.path.basename(real).lower()
    return name in ('catwiz', 'catwiz-ytdl', 'ytdl-termux') or os.path.isdir(os.path.join(real, '.git'))

def shortcut_path():
    """Return the primary launcher path for the currently configured command."""
    paths = shortcut_paths(*get_shortcut_settings())
    return paths[0] if paths else None

def in_venv():
    return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)

def find_brew():
    found = shutil.which('brew')
    if found:
        return found
    for p in ('/opt/homebrew/bin/brew', '/usr/local/bin/brew'):
        if os.path.exists(p):
            return p
    return None

def brew_formulae():
    brew = find_brew()
    if not brew:
        return set()
    try:
        r = subprocess.run([brew, 'list', '--formula'], capture_output=True, text=True)
        return set(r.stdout.split())
    except Exception:
        return set()

def mac_python_formula():
    for f in sorted(brew_formulae()):
        if f == 'python' or f.startswith('python@'):
            return f
    return 'python'

def windows_python_id():
    """Find the winget id of the installed Python (falls back to 3.12)."""
    try:
        r = subprocess.run(['winget', 'list', 'Python.Python', '--accept-source-agreements'],
                           capture_output=True, text=True)
        m = re.search(r'Python\.Python\.\d+\.\d+', r.stdout or '')
        if m:
            return m.group(0)
    except Exception:
        pass
    return 'Python.Python.3.12'

def run_quiet(cmd):
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        lines = (r.stderr or '').strip().splitlines()
        return r.returncode == 0, (lines[-1] if lines else '')
    except Exception as e:
        return False, str(e)

def run_capture(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        return r.returncode == 0, ((r.stdout or '') + (r.stderr or '')).strip()
    except Exception as e:
        return False, str(e)

def last_line(text):
    lines = [l.strip() for l in (text or '').splitlines() if l.strip()]
    return lines[-1] if lines else ''



def ensure_deno():
    """Ensure a supported Deno runtime is available for yt-dlp's YouTube EJS solver."""
    minimum = (2, 3, 0)

    def version():
        path = shutil.which('deno')
        if not path:
            return None
        ok, output = run_capture([path, '--version'])
        match = re.search(r'^deno\\s+(\\d+)\\.(\\d+)\\.(\\d+)', output, re.MULTILINE) if ok else None
        return tuple(map(int, match.groups())) if match else None

    current = version()
    if current and current >= minimum:
        return True

    key = platform_key()
    if key == 'mac':
        brew = find_brew()
        command = [brew, 'install', 'deno'] if brew else ['bash', '-lc', 'curl -fsSL https://deno.land/install.sh | sh']
    elif key == 'termux':
        command = ['pkg', 'install', '-y', 'deno']
    elif key == 'linux':
        command = ['bash', '-lc', 'curl -fsSL https://deno.land/install.sh | sh']
    else:
        command = ['winget', 'install', '--id', 'DenoLand.Deno', '-e', '--silent',
                   '--accept-package-agreements', '--accept-source-agreements']

    try:
        result = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=600)
        deno_dir = os.path.join(os.path.expanduser('~'), '.deno', 'bin')
        if os.path.isdir(deno_dir) and deno_dir not in os.environ.get('PATH', '').split(os.pathsep):
            os.environ['PATH'] = deno_dir + os.pathsep + os.environ.get('PATH', '')
        current = version()
        if result.returncode == 0 and current and current >= minimum:
            try:
                from .logging_service import log_activity
                log_activity('Deno JavaScript runtime installed or verified', component='setup')
            except Exception:
                pass
            return True
        detail = (result.stderr or result.stdout or '').strip().splitlines()
        reason = detail[-1][:240] if detail else 'installer did not provide a supported Deno runtime'
        try:
            from .logging_service import component_logger
            component_logger('setup').warning('Could not install Deno: %s', reason)
        except Exception:
            pass
        return False
    except Exception:
        try:
            from .logging_service import component_logger
            component_logger('setup').exception('Deno setup failed')
        except Exception:
            pass
        return False


def get_auto_update_check():
    """Return whether startup update checks are enabled (off by default)."""
    try:
        with open(get_config_file(), 'r', encoding='utf-8') as stream:
            config = json.load(stream)
        return bool(config.get('auto_update_check', False)) if isinstance(config, dict) else False
    except (OSError, ValueError, TypeError):
        return False


def set_auto_update_check(enabled):
    """Persist the startup update-check preference without changing other settings."""
    config_file = get_config_file()
    try:
        with open(config_file, 'r', encoding='utf-8') as stream:
            config = json.load(stream)
        if not isinstance(config, dict):
            config = {}
    except (OSError, ValueError, TypeError):
        config = {}
    config['auto_update_check'] = bool(enabled)
    temporary = config_file + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as stream:
        json.dump(config, stream, indent=4)
        stream.write('\n')
    os.replace(temporary, config_file)
    try:
        from .logging_service import log_activity
        log_activity('Startup update-check preference changed', component='settings')
    except Exception:
        pass


def get_shortcut_settings():
    """Return (shortcut, case_sensitive), preserving the default for old configs."""
    try:
        with open(get_config_file(), 'r', encoding='utf-8') as stream:
            config = json.load(stream)
        if not isinstance(config, dict):
            config = {}
        name = config.get('shortcut', 'catwiz')
        case_sensitive = config.get('shortcut_case_sensitive', True)
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', name) or name.startswith('-'):
            name = 'catwiz'
        if not isinstance(case_sensitive, bool):
            case_sensitive = True
        return name, case_sensitive
    except (OSError, ValueError, TypeError):
        return 'catwiz', True


def set_shortcut_settings(name, case_sensitive):
    """Update shortcut keys without discarding other user configuration."""
    config_file = get_config_file()
    try:
        with open(config_file, 'r', encoding='utf-8') as stream:
            config = json.load(stream)
        if not isinstance(config, dict):
            config = {}
    except (OSError, ValueError, TypeError):
        config = {}
    config['shortcut'] = name
    config['shortcut_case_sensitive'] = bool(case_sensitive)
    temporary = config_file + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as stream:
        json.dump(config, stream, indent=4)
        stream.write('\n')
    os.replace(temporary, config_file)


def shortcut_paths(name, case_sensitive):
    """Return all launcher paths needed to support the selected case policy."""
    key = platform_key()
    if key in ('windows', 'mac'):
        # Windows and standard macOS filesystems resolve command names without case sensitivity.
        names = [name]
    elif case_sensitive:
        names = [name]
    else:
        letters = [index for index, char in enumerate(name) if char.isalpha()]
        if len(letters) > 8:
            raise ValueError('Case-insensitive shortcut supports at most 8 letters on Linux/Termux.')
        names = []
        for bits in itertools.product((False, True), repeat=len(letters)):
            chars = list(name)
            for index, upper in zip(letters, bits):
                chars[index] = chars[index].upper() if upper else chars[index].lower()
            candidate = ''.join(chars)
            if candidate not in names:
                names.append(candidate)

    if key == 'termux':
        prefix = os.environ.get('PREFIX', '/data/data/com.termux/files/usr')
        return [os.path.join(prefix, 'bin', item) for item in names]
    if key in ('linux', 'mac'):
        return [os.path.join('/usr/local/bin', item) for item in names]
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        return []
    return [
        os.path.join(local, 'Microsoft', 'WindowsApps', item + '.cmd')
        for item in names
    ]
