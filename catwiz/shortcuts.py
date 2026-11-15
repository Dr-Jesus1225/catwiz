"""Create and change the command used to launch CatWiz."""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from .system import (
    get_shortcut_settings,
    platform_key,
    shortcut_paths,
    set_shortcut_settings,
)
from .ui import YELLOW, RESET, print_green
from .utils import PROGRAM_DIR


def _launcher_content():
    key = platform_key()
    main_file = os.path.join(PROGRAM_DIR, "main.py")

    if key == "windows":
        main_file = main_file.replace("/", "\\")
        return (
            "@echo off\r\n"
            'pushd "%TEMP%" >nul\r\n'
            f'py -3 "{main_file}" %*\r\n'
            'set "catwiz_exit=%errorlevel%"\r\n'
            "popd >nul\r\n"
            "exit /b %catwiz_exit%\r\n"
        )

    if key == "termux":
        python = shutil.which("python") or "python"
    else:
        venv_python = os.path.join(PROGRAM_DIR, ".venv", "bin", "python")
        python = venv_python if os.path.isfile(venv_python) else (shutil.which("python3") or sys.executable)

    return (
        "#!/usr/bin/env bash\n"
        f"exec {shlex.quote(python)} {shlex.quote(main_file)} \"$@\"\n"
    )


def _path_for_name(name):
    key = platform_key()
    if key == "termux":
        prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        return os.path.join(prefix, "bin", name)
    if key in ("linux", "mac"):
        return os.path.join("/usr/local/bin", name)
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("LOCALAPPDATA is not set")
    return os.path.join(local, "Microsoft", "WindowsApps", name + ".cmd")


def _run_privileged(command):
    return subprocess.run(command, capture_output=True, text=True)


def _write_primary(path, content):
    key = platform_key()
    if key in ("linux", "mac"):
        result = _run_privileged(["sudo", "mkdir", "-p", os.path.dirname(path)])
        if result.returncode != 0:
            raise OSError((result.stderr or result.stdout or "Could not create launcher directory").strip())
        fd, temporary = tempfile.mkstemp(prefix="catwiz-shortcut-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)
            os.chmod(temporary, 0o755)
            result = _run_privileged(["sudo", "install", "-m", "755", temporary, path])
            if result.returncode != 0:
                raise OSError((result.stderr or result.stdout or "Could not install launcher").strip())
        finally:
            try:
                os.remove(temporary)
            except OSError:
                pass
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        if key == "termux":
            os.chmod(path, 0o755)


def _create_shortcut(name, case_sensitive):
    key = platform_key()
    paths = shortcut_paths(name, case_sensitive)
    primary = _path_for_name(name)
    _write_primary(primary, _launcher_content())

    for path in paths:
        if os.path.abspath(path) == os.path.abspath(primary):
            continue
        if os.path.exists(path) and os.path.exists(primary):
            try:
                if os.path.samefile(path, primary):
                    continue
            except OSError:
                pass
        if key in ("linux", "mac"):
            result = _run_privileged(["sudo", "ln", "-sfn", primary, path])
            if result.returncode != 0:
                raise OSError((result.stderr or result.stdout or f"Could not create alias {path}").strip())
        else:
            try:
                if os.path.lexists(path):
                    os.remove(path)
                os.symlink(primary, path)
            except OSError:
                # Termux normally supports symlinks; if not, write another small launcher.
                _write_primary(path, _launcher_content())

    return paths


def _remove_path(path):
    key = platform_key()
    if key in ("linux", "mac"):
        result = _run_privileged(["sudo", "rm", "-f", path])
        if result.returncode != 0:
            raise OSError((result.stderr or result.stdout or f"Could not remove {path}").strip())
    else:
        try:
            if os.path.lexists(path):
                os.remove(path)
        except OSError:
            raise


def install_current_shortcut():
    """Install the configured shortcut (or the default catwiz command)."""
    name, case_sensitive = get_shortcut_settings()
    key = platform_key()
    if key in ("linux", "mac"):
        result = _run_privileged(["sudo", "-v"])
        if result.returncode != 0:
            raise OSError("Administrator permission is required to install the CatWiz command")
    _create_shortcut(name, case_sensitive)
    return name


def _ask_yes_no(prompt):
    for attempt in range(3):
        answer = input(f"{YELLOW}{prompt}{RESET} ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if attempt < 2:
            print_green("Please enter y or n.")
    return None


def change_shortcut():
    current_name, current_case_sensitive = get_shortcut_settings()
    print(f"\nYour current shortcut is ({current_name})")

    proceed = _ask_yes_no("Proceed to change shortcut [y/n]:")
    if proceed is not True:
        print_green("Cancelled.")
        return

    new_name = input(f"{YELLOW}Enter new shortcut:{RESET} ").strip()
    if (
        not new_name
        or len(new_name) > 32
        or new_name.startswith("-")
        or not re.fullmatch(r"[A-Za-z0-9_-]+", new_name)
    ):
        print_green("Invalid shortcut. Use 1–32 letters, numbers, hyphens or underscores; do not start with a hyphen.")
        return

    keep_case_sensitive = _ask_yes_no("Keep it case sensitive? [y/n]:")
    if keep_case_sensitive is None:
        print_green("Cancelled.")
        return
    case_sensitive = keep_case_sensitive

    key = platform_key()
    if not case_sensitive and key in ("linux", "termux"):
        letters = sum(character.isalpha() for character in new_name)
        if letters > 8:
            print_green("On Linux and Termux, case-insensitive shortcuts are limited to 8 letters (to create all capitalization variants).")
            return

    old_paths = shortcut_paths(current_name, current_case_sensitive)
    new_paths = shortcut_paths(new_name, case_sensitive)
    old_normalized = {os.path.normcase(os.path.abspath(path)) for path in old_paths}

    for path in new_paths:
        normalized = os.path.normcase(os.path.abspath(path))
        if os.path.lexists(path) and normalized not in old_normalized:
            belongs_to_old_shortcut = any(
                os.path.lexists(old_path)
                and os.path.exists(path)
                and os.path.exists(old_path)
                and os.path.samefile(path, old_path)
                for old_path in old_paths
            )
            if not belongs_to_old_shortcut:
                print_green(f"That shortcut already exists: {path}")
                return

    if key in ("linux", "mac"):
        result = _run_privileged(["sudo", "-v"])
        if result.returncode != 0:
            print_green("Could not obtain administrator permission. The shortcut was not changed.")
            return

    try:
        _create_shortcut(new_name, case_sensitive)
        new_normalized = {os.path.normcase(os.path.abspath(path)) for path in new_paths}
        for path in old_paths:
            if os.path.normcase(os.path.abspath(path)) in new_normalized:
                continue
            shared_path = any(
                os.path.exists(path)
                and os.path.exists(new_path)
                and os.path.samefile(path, new_path)
                for new_path in new_paths
            )
            if not shared_path:
                _remove_path(path)
        set_shortcut_settings(new_name, case_sensitive)
    except (OSError, subprocess.SubprocessError) as error:
        print_green(f"Could not change shortcut: {error}")
        return

    print_green("Shortcut changed.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        try:
            name = install_current_shortcut()
            print(f"Installed CatWiz command: {name}")
        except OSError as error:
            print(f"Could not install CatWiz command: {error}", file=sys.stderr)
            sys.exit(1)
