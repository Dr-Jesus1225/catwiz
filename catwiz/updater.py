"""Settings > Update."""

import os
import shutil
import subprocess
import sys
import tempfile

from .system import DISPLAY, brew_formulae, find_brew, in_venv, last_line, mac_python_formula, platform_key, run_capture, windows_python_id
from .ui import CYAN, GREEN, RED, RESET, YELLOW, ask_yes_no, print_green
from .utils import PROGRAM_DIR, short_reason

def show_status(status, msg):
    if status in ('changed', 'same'):
        print_green(msg)
    elif status == 'skipped':
        print(f"{YELLOW}{msg}{RESET}")
    else:
        print(f"{RED}failed ({msg}){RESET}")

def ytdlp_version():
    ok, out = run_capture([sys.executable, '-c', 'import yt_dlp.version as v; print(v.__version__)'])
    return last_line(out) if ok else None

def update_program():
    if not os.path.isdir(os.path.join(PROGRAM_DIR, '.git')):
        return 'skipped', 'skipped (not a git copy, run the install command again to enable updates)'
    if not shutil.which('git'):
        return 'failed', 'git not found'
    ok, out = run_capture(['git', '-C', PROGRAM_DIR, 'pull', '--ff-only'])
    if not ok:
        return 'failed', last_line(out)[:140]
    if 'already up to date' in out.lower():
        return 'same', 'already up to date'
    return 'changed', 'updated'

def update_ytdlp():
    before = ytdlp_version()
    cmd = [sys.executable, '-m', 'pip', 'install', '-U', 'yt-dlp']
    ok, out = run_capture(cmd)
    if not ok and 'externally-managed' in out.lower() and not in_venv():
        ok, out = run_capture(cmd + ['--break-system-packages'])
    if not ok:
        return 'failed', last_line(out)[:140]
    after = ytdlp_version()
    if before and after and before != after:
        return 'changed', f"{before} -> {after}"
    return 'same', f"already up to date ({after or before or 'unknown version'})"

def run_step(label, cmd, same_texts=()):
    print(f"Updating {label}... ", end='', flush=True)
    ok, out = run_capture(cmd)
    low = out.lower()
    if any(t in low for t in same_texts):
        print_green("already up to date")
        return 'same'
    if ok:
        print_green("done")
        return 'changed'
    print(f"{RED}failed ({last_line(out)[:120]}){RESET}")
    return 'failed'

def schedule_windows_python_upgrade(python_id):
    """Python can't be upgraded while this program is running it, so a helper does it after we exit."""
    lines = [
        '@echo off',
        'cd /d "%USERPROFILE%"',
        'ping 127.0.0.1 -n 4 >nul',
        f'winget upgrade -e --id {python_id} --silent --accept-package-agreements --accept-source-agreements >nul 2>&1',
        'del "%~f0" >nul 2>&1',
    ]
    bat = os.path.join(tempfile.gettempdir(), 'catwiz_update.bat')
    with open(bat, 'w') as f:
        f.write('\r\n'.join(lines) + '\r\n')
    flags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
    subprocess.Popen(['cmd', '/c', bat], creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def update_system_packages():
    """Upgrade FFmpeg, Python and Git with the system package manager. Returns a list of statuses."""
    key = platform_key()
    results = []
    if key == 'termux':
        results.append(run_step('package lists', ['pkg', 'update', '-y']))
        names = ['python'] + [n for n in ('ffmpeg', 'git') if shutil.which(n)]
        for n in names:
            results.append(run_step(DISPLAY.get(n, n), ['pkg', 'install', '-y', n],
                                    ('already the newest version',)))
    elif key == 'linux':
        results.append(run_step('package lists', ['sudo', 'apt-get', 'update', '-y']))
        for n, pkg in (('ffmpeg', 'ffmpeg'), ('git', 'git'), ('python', 'python3')):
            if n == 'python' or shutil.which(n):
                results.append(run_step(DISPLAY[n], ['sudo', 'apt-get', 'install', '-y', '--only-upgrade', pkg],
                                        ('already the newest version',)))
    elif key == 'mac':
        brew = find_brew()
        if not brew:
            print(f"{YELLOW}Homebrew not found, skipping FFmpeg, Python and Git.{RESET}")
            return results
        results.append(run_step('Homebrew', [brew, 'update']))
        formulae = brew_formulae()
        todo = [('FFmpeg', 'ffmpeg' if 'ffmpeg' in formulae else None),
                ('Python', mac_python_formula() if any(f == 'python' or f.startswith('python@') for f in formulae) else None),
                ('Git', 'git' if 'git' in formulae else None)]
        for label, name in todo:
            if not name:
                print(f"Updating {label}... {YELLOW}skipped (not installed with Homebrew){RESET}")
                continue
            _, before = run_capture([brew, 'list', '--versions', name])
            st = run_step(label, [brew, 'upgrade', name], ('already installed',))
            if st == 'changed':
                _, after = run_capture([brew, 'list', '--versions', name])
                if before == after:
                    st = 'same'
                    print(f"  ({label} was already up to date)")
            results.append(st)
    else:
        if not shutil.which('winget'):
            print(f"{YELLOW}winget not found, skipping FFmpeg, Python and Git.{RESET}")
            return results
        same = ('no available upgrade found', 'no newer package versions')
        base = ['winget', 'upgrade', '-e', '--silent',
                '--accept-package-agreements', '--accept-source-agreements', '--id']
        if shutil.which('ffmpeg'):
            results.append(run_step('FFmpeg', base + ['Gyan.FFmpeg'], same))
        if shutil.which('git'):
            results.append(run_step('Git', base + ['Git.Git'], same))
        try:
            schedule_windows_python_upgrade(windows_python_id())
            print(f"Updating Python... {GREEN}scheduled{RESET} (runs in the background after this program closes)")
            results.append('changed')
        except Exception as e:
            print(f"Updating Python... {RED}failed ({short_reason(e)}){RESET}")
            results.append('failed')
    return results

def update_necessary():
    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Updating what's necessary")
    print(f"{CYAN}--------------------------------------{RESET}")
    statuses = []
    print("Updating CATWIZ-ytdl... ", end='', flush=True)
    st, msg = update_program()
    show_status(st, msg)
    statuses.append(st)
    print("Updating yt-dlp... ", end='', flush=True)
    st, msg = update_ytdlp()
    show_status(st, msg)
    statuses.append(st)
    return statuses

def update_everything():
    key = platform_key()
    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Update everything")
    print(f"{CYAN}--------------------------------------{RESET}")
    tools = {'termux': 'pkg', 'linux': 'apt', 'mac': 'Homebrew', 'windows': 'winget'}[key]
    print("This will check for updates to:")
    print("  - CATWIZ-ytdl (the program)")
    print("  - yt-dlp")
    print(f"  - FFmpeg, Python and Git (using {tools})")
    if key == 'windows':
        print("  A Windows permission prompt may appear.")
    elif key in ('linux', 'mac'):
        print("  You may be asked for your password.")
    print("This can take a few minutes.")
    if not ask_yes_no("Proceed?"):
        print_green("Cancelled.")
        return None
    if key == 'linux' and subprocess.run(['sudo', '-v']).returncode != 0:
        print(f"{RED}Could not get permission (sudo). Nothing was updated.{RESET}")
        return []
    print()
    statuses = []
    print("Updating CATWIZ-ytdl... ", end='', flush=True)
    st, msg = update_program()
    show_status(st, msg)
    statuses.append(st)
    statuses += update_system_packages()
    # yt-dlp last, because a Python upgrade can remove packages installed outside a virtual environment
    print("Updating yt-dlp... ", end='', flush=True)
    st, msg = update_ytdlp()
    show_status(st, msg)
    statuses.append(st)
    return statuses

def update_menu():
    max_attempts = 3
    print(f"\n{CYAN}======================================{RESET}")
    print(" Update")
    print("  1. Update what's necessary (CATWIZ-ytdl and yt-dlp)")
    print("  2. Update everything (also FFmpeg, Python and Git)")
    print("  0. Back")
    print(f"{CYAN}--------------------------------------{RESET}")
    attempts = 0
    choice = None
    while attempts < max_attempts:
        choice = input(f"{YELLOW}Select option [1/2/0]:{RESET} ").strip()
        if choice in ('0', '1', '2'):
            break
        attempts += 1
        if attempts < max_attempts:
            print_green("Invalid option selected.")
        else:
            print_green("Too many invalid attempts. Exiting.")
            sys.exit(1)
    if choice == '0':
        return
    statuses = update_necessary() if choice == '1' else update_everything()
    if statuses is None:
        return
    print()
    if 'failed' in statuses:
        print(f"{YELLOW}Some updates failed. Running the install command again usually repairs everything.{RESET}")
    if 'changed' in statuses:
        print_green("Updates installed. Restart CATWIZ-ytdl to use them.")
        sys.exit(0)
    if 'failed' not in statuses:
        print_green("Everything is up to date.")
