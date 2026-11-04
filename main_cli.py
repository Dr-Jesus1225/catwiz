"""Compatibility shim.

Shortcuts created by older installs still point at main_cli.py, so this file just starts the
app through main.py. New installs use main.py directly. It can be deleted once your
`ytdl` shortcut has been recreated by running the install command again.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import run

run()
