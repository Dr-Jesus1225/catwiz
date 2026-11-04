#!/usr/bin/env python3
"""
Rename this project from CATWIZ-ytdl/ytdl to CatWiz/catwiz.

Run from the repository root:
    python rename_to_catwiz.py

The script makes timestamped backups of every changed file before editing.
It deliberately preserves yt-dlp-related identifiers and the .ytdl extension.
"""

from datetime import datetime
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
BACKUP_DIR = ROOT / f".catwiz-rename-backup-{datetime.now():%Y%m%d-%H%M%S}"

REPLACEMENTS = {
    "README.md": [
        ("# CATWIZ-ytdl", "# CatWiz"),
        ("type `ytdl` to start", "type `catwiz` to start"),
        ("there is no `ytdl` shortcut. Run:", "use the `catwiz` command. Alternatively, run:"),
        ('$HOME\\CATWIZ-ytdl\\main_cli.py', '$HOME\\CatWiz\\main.py'),
        ("Uninstall CATWIZ-ytdl", "Uninstall CatWiz"),
        ("the `ytdl` shortcut", "the `catwiz` shortcut"),
    ],
    "install.sh": [
        ("CATWIZ-ytdl", "CatWiz"),
        ('DIR="$HOME/CATWIZ-ytdl"', 'DIR="$HOME/CatWiz"'),
        ("ytdl shortcut", "catwiz shortcut"),
        ('"$PREFIX/bin/ytdl"', '"$PREFIX/bin/catwiz"'),
        ('"/usr/local/bin/ytdl"', '"/usr/local/bin/catwiz"'),
        ("type ytdl next time", "type catwiz next time"),
    ],
    "install.ps1": [
        ("CATWIZ-ytdl", "CatWiz"),
        ("Install-CatwizYtdl", "Install-CatWiz"),
        ("ytdl shortcut", "catwiz shortcut"),
        ("\\CATWIZ-ytdl\\main.py", "\\CatWiz\\main.py"),
        ("'CATWIZ-ytdl'", "'CatWiz'"),
        ("'ytdl.cmd'", "'catwiz.cmd'"),
        ("the ytdl shortcut", "the catwiz shortcut"),
        ("type ytdl next time", "type catwiz next time"),
    ],
    "main.py": [
        ("CATWIZ-ytdl entry point", "CatWiz entry point"),
    ],
    "catwiz/__init__.py": [
        ("CATWIZ-ytdl:", "CatWiz:"),
    ],
    "catwiz/lyrics.py": [
        ("CATWIZ-ytdl (https://github.com/Dr-Jesus1225/ytdl-termux)",
         "CatWiz (https://github.com/Dr-Jesus1225/catwiz)"),
    ],
    "catwiz/settings.py": [
        ("Uninstall CATWIZ-ytdl", "Uninstall CatWiz"),
    ],
    "catwiz/uninstaller.py": [
        ("Uninstall CATWIZ-ytdl", "Uninstall CatWiz"),
        ("CATWIZ-ytdl has been uninstalled.", "CatWiz has been uninstalled."),
    ],
    "catwiz/updater.py": [
        ("CATWIZ-ytdl", "CatWiz"),
    ],
    "catwiz/system.py": [
        ("return name in ('catwiz-ytdl', 'ytdl-termux') or os.path.isdir(os.path.join(real, '.git'))",
         "return name in ('catwiz', 'catwiz-ytdl', 'ytdl-termux') or os.path.isdir(os.path.join(real, '.git'))"),
        ("os.path.join(prefix, 'bin', 'ytdl')", "os.path.join(prefix, 'bin', 'catwiz')"),
        ("'/usr/local/bin/ytdl'", "'/usr/local/bin/catwiz'"),
        ("'Microsoft', 'WindowsApps', 'ytdl.cmd'", "'Microsoft', 'WindowsApps', 'catwiz.cmd'"),
    ],
}

def main():
    if not (ROOT / "main.py").is_file() or not (ROOT / "catwiz").is_dir():
        print("ERROR: Run this script from the CatWiz repository root (next to main.py and catwiz/).")
        return 1

    changes = []
    missing = []

    for relative, pairs in REPLACEMENTS.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue

        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in pairs:
            updated = updated.replace(old, new)

        if updated != original:
            changes.append((path, original, updated))

    if not changes:
        print("No changes needed. The project may already be renamed.")
        if missing:
            print("Files not found (skipped): " + ", ".join(missing))
        return 0

    BACKUP_DIR.mkdir()
    for path, original, updated in changes:
        backup = BACKUP_DIR / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        path.write_text(updated, encoding="utf-8", newline="")

    print(f"Updated {len(changes)} file(s):")
    for path, _, _ in changes:
        print(f"  - {path.relative_to(ROOT)}")
    print(f"\nOriginal files backed up to: {BACKUP_DIR.relative_to(ROOT)}")
    if missing:
        print("Files not found (skipped): " + ", ".join(missing))

    print("\nNext steps:")
    print("  1. Review the changes with: git diff")
    print("  2. Test the installer and uninstaller on each platform you support.")
    print("  3. Commit and push the changes when everything works.")
    print("\nNote: This edits project files only. It does not rename your GitHub repository,")
    print("move an existing installed folder, or uninstall an old 'ytdl' shortcut.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
