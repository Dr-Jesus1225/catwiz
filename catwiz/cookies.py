"""Optional browser authentication for yt-dlp; no cookie files are stored by CatWiz."""

import json
import os

from .system import get_config_file
from .ui import print_green
from .session_log import write_diagnostic

BROWSERS = ('chrome', 'firefox', 'edge', 'brave', 'chromium', 'opera', 'vivaldi', 'safari')


def selected_browser():
    try:
        with open(get_config_file(), encoding='utf-8') as stream:
            data = json.load(stream)
        browser = data.get('cookies_browser') if isinstance(data, dict) else None
        return browser if browser in BROWSERS else None
    except (OSError, ValueError, TypeError):
        return None


def apply_browser_cookies(options):
    """Use browser cookies and a locally installed CA bundle when available."""
    # Prefer certifi's maintained Mozilla root bundle without disabling TLS checks.
    try:
        import certifi
        options.setdefault('compat_opts', set()).add('no-certifi')
        options.setdefault('ca_certs', certifi.where())
    except ImportError:
        # yt-dlp retains its own secure certificate defaults.
        pass
    except OSError as error:
        write_diagnostic(f"Could not locate certificate bundle: {error}")

    browser = selected_browser()
    if browser:
        options['cookiesfrombrowser'] = (browser,)
    return options


def browser_cookies_menu():
    current = selected_browser()
    print()
    print('YouTube browser cookies (optional)')
    print('CatWiz reads your browser cookies when downloading; it does not save copies.')
    print('Browser login may help with YouTube sign-in checks, but cannot bypass all blocks.')
    print('Current: ' + (current.title() if current else 'Off'))
    print('  0. Disable browser cookies')
    for number, browser in enumerate(BROWSERS, 1):
        print(f'  {number}. {browser.title()}')
    print('  B. Back')
    choice = input('Choose browser [0-8/B]: ').strip().lower()
    if choice == 'b':
        return
    if choice != '0' and (not choice.isdigit() or not 1 <= int(choice) <= len(BROWSERS)):
        print('Invalid selection.')
        return
    browser = None if choice == '0' else BROWSERS[int(choice) - 1]
    try:
        path = get_config_file()
        try:
            with open(path, encoding='utf-8') as stream:
                config = json.load(stream)
            if not isinstance(config, dict):
                config = {}
        except (OSError, ValueError, TypeError):
            config = {}
        if browser:
            config['cookies_browser'] = browser
        else:
            config.pop('cookies_browser', None)
        temporary = path + '.cookies.tmp'
        try:
            with open(temporary, 'w', encoding='utf-8') as stream:
                json.dump(config, stream, indent=4)
                stream.write(chr(10))
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        print_green('Browser cookies: ' + (browser.title() if browser else 'Off'))
    except OSError as error:
        print('Could not save cookie preference: ' + str(error))
