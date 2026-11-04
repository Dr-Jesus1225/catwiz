"""Settings > Uninstall."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

from .system import DISPLAY, SIZES_MB, brew_formulae, find_brew, fmt_mb, folder_size_mb, in_venv, mac_python_formula, platform_key, program_dir_is_safe, run_quiet, shortcut_path, windows_python_id
from .ui import CYAN, RED, RESET, YELLOW, ask_yes_no, print_green
from .utils import PROGRAM_DIR

def removable_items():
    key = platform_key()
    items = []
    if key == 'mac':
        formulae = brew_formulae()
        has_python = any(f == 'python' or f.startswith('python@') for f in formulae)
        items.append({'id': 'ffmpeg', 'found': 'ffmpeg' in formulae})
        if not in_venv():
            items.append({'id': 'yt-dlp', 'found': importlib.util.find_spec('yt_dlp') is not None})
        items.append({'id': 'python', 'found': has_python})
        items.append({'id': 'git', 'found': 'git' in formulae})
        return items
    items.append({'id': 'ffmpeg', 'found': shutil.which('ffmpeg') is not None})
    if not in_venv():
        items.append({'id': 'yt-dlp', 'found': importlib.util.find_spec('yt_dlp') is not None})
    if key != 'linux':
        # Debian/Ubuntu is skipped on purpose: system tools depend on Python there
        items.append({'id': 'python', 'found': True})
    items.append({'id': 'git', 'found': shutil.which('git') is not None})
    return items

def removal_command(item):
    key = platform_key()
    if item == 'yt-dlp':
        return [sys.executable, '-m', 'pip', 'uninstall', '-y', 'yt-dlp']
    if key == 'termux':
        return ['pkg', 'uninstall', '-y', item]
    if key == 'linux':
        return ['sudo', 'apt-get', 'remove', '-y', item]
    if key == 'mac':
        name = mac_python_formula() if item == 'python' else item
        return [find_brew() or 'brew', 'uninstall', name]
    ids = {'ffmpeg': 'Gyan.FFmpeg', 'python': 'Python.Python.3.12', 'git': 'Git.Git'}
    return ['winget', 'uninstall', '-e', '--id', ids[item], '--silent', '--accept-source-agreements']

def report(ok, reason=''):
    if ok:
        print_green("done")
    else:
        print(f"{RED}failed{RESET}" + (f" ({reason[:120]})" if reason else ""))

def parse_selection(text, count):
    tokens = text.replace(',', ' ').split()
    if not tokens:
        return None
    picked = set()
    for tok in tokens:
        if not tok.isdigit():
            return None
        v = int(tok)
        if v == 0:
            return [] if len(tokens) == 1 else None
        if v == count + 1:
            return list(range(1, count + 1))
        if 1 <= v <= count:
            picked.add(v)
        else:
            return None
    return sorted(picked)

def schedule_windows_cleanup(folder, remove_python, python_id='Python.Python.3.12'):
    """A running program can't delete its own folder on Windows, so a helper does it after we exit."""
    lines = ['@echo off', 'cd /d "%USERPROFILE%"', 'ping 127.0.0.1 -n 4 >nul']
    if remove_python:
        lines.append(f'winget uninstall -e --id {python_id} --silent --accept-source-agreements >nul 2>&1')
    if folder:
        lines += [
            'for /l %%i in (1,1,60) do (',
            f'  rmdir /s /q "{folder}" >nul 2>&1',
            f'  if not exist "{folder}" goto done',
            '  ping 127.0.0.1 -n 3 >nul',
            ')',
            ':done',
        ]
    lines.append('del "%~f0" >nul 2>&1')
    bat = os.path.join(tempfile.gettempdir(), 'catwiz_cleanup.bat')
    with open(bat, 'w') as f:
        f.write('\r\n'.join(lines) + '\r\n')
    flags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
    subprocess.Popen(['cmd', '/c', bat], creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def uninstall_menu():
    key = platform_key()
    sizes = SIZES_MB[key]
    folder_ok = program_dir_is_safe(PROGRAM_DIR)
    folder_mb = folder_size_mb(PROGRAM_DIR) if folder_ok else 0
    shortcut = shortcut_path()
    shortcut_exists = bool(shortcut) and os.path.exists(shortcut)

    print(f"\n{CYAN}--------------------------------------{RESET}")
    print(" Uninstall CatWiz")
    print(f"{CYAN}--------------------------------------{RESET}")
    print("This will remove:")
    if folder_ok:
        print(f"  - Program folder: {PROGRAM_DIR} (~{fmt_mb(folder_mb)})")
    else:
        print(f"  - {YELLOW}Program folder not recognised, so it will NOT be deleted:{RESET}")
        print(f"    {PROGRAM_DIR}")
    if shortcut_exists:
        print(f"  - Shortcut: {shortcut}")
    print("Your downloaded files will NOT be deleted.")

    items = removable_items()
    found = [it for it in items if it['found']]
    selected = []

    print("\nAlso remove these programs? Other apps may use them.")
    n = 0
    for it in items:
        label = DISPLAY[it['id']]
        if it['found']:
            n += 1
            it['num'] = n
            print(f"  {n}. {label:<8} (found, ~{sizes[it['id']]} MB)")
        else:
            print(f"  -  {label:<8} (not found)")
    if found:
        print(f"  {n + 1}. All of the above")
    print("  0. Keep them all")

    if found:
        attempts = 0
        max_attempts = 3
        while True:
            choice = input(f"{YELLOW}Select (e.g. 1,3):{RESET} ")
            picked = parse_selection(choice, len(found))
            if picked is not None:
                selected = [it for it in found if it['num'] in picked]
                break
            attempts += 1
            if attempts >= max_attempts:
                print_green("Too many invalid attempts. Exiting.")
                sys.exit(1)
            print_green("Invalid selection.")

    names = []
    freed = 0
    if folder_ok:
        names.append("Program folder")
        freed += folder_mb
    for it in selected:
        names.append(DISPLAY[it['id']])
        freed += sizes[it['id']]
    if not names and not shortcut_exists:
        print_green("\nNothing to remove.")
        return

    print(f"\nYou chose to remove: {', '.join(names) if names else 'Shortcut only'}")
    print(f"This frees about {fmt_mb(freed)}.")
    if not ask_yes_no("Are you sure? This can't be undone."):
        print_green("Cancelled.")
        return

    print()
    needs_sudo = key == 'linux' and (shortcut_exists or any(it['id'] != 'yt-dlp' for it in selected))
    needs_sudo = needs_sudo or (key == 'mac' and shortcut_exists)
    sudo_ok = True
    if needs_sudo:
        sudo_ok = subprocess.run(['sudo', '-v']).returncode == 0

    if shortcut_exists:
        print("Removing shortcut... ", end='', flush=True)
        if key in ('termux', 'windows'):
            try:
                os.remove(shortcut)
                report(True)
            except OSError as e:
                report(False, str(e))
        elif sudo_ok:
            report(*run_quiet(['sudo', 'rm', '-f', shortcut]))
        else:
            report(False, 'sudo password needed')

    deferred_python = False
    order = ['yt-dlp', 'ffmpeg', 'git', 'python']
    for item_id in order:
        it = next((x for x in selected if x['id'] == item_id), None)
        if not it:
            continue
        label = DISPLAY[item_id]
        if item_id == 'python' and key == 'windows':
            deferred_python = True
            continue
        print(f"Removing {label}... ", end='', flush=True)
        if key == 'linux' and not sudo_ok and item_id != 'yt-dlp':
            report(False, 'sudo password needed')
            continue
        ok, why = run_quiet(removal_command(item_id))
        if not ok and not why and key == 'windows':
            why = 'not installed with winget? remove it in Settings > Apps'
        report(ok, why)

    if folder_ok:
        print("Removing program folder... ", end='', flush=True)
        try:
            os.chdir(os.path.expanduser('~'))
        except OSError:
            pass
        if key == 'windows':
            try:
                schedule_windows_cleanup(PROGRAM_DIR, deferred_python, windows_python_id())
                print_green("scheduled")
            except Exception as e:
                report(False, str(e))
        else:
            try:
                shutil.rmtree(PROGRAM_DIR)
                report(True)
            except Exception as e:
                report(False, str(e))
    elif deferred_python:
        try:
            schedule_windows_cleanup(None, True, windows_python_id())
        except Exception:
            pass

    print_green("\nCatWiz has been uninstalled.")
    if key == 'windows':
        if folder_ok:
            print("The program folder is deleted in the background once this terminal is no longer inside it.")
            print("If it is still there after a minute, run: cd ~")
        if deferred_python:
            print("Python is removed in the background after this window closes (a permission prompt may appear).")
    sys.exit(0)
