"""Run the official CatWiz installer from GitHub."""

import subprocess

from .system import platform_key
from .ui import print_green


INSTALL_SH = "https://raw.githubusercontent.com/Dr-Jesus1225/catwiz/main/install.sh"
INSTALL_PS1 = "https://raw.githubusercontent.com/Dr-Jesus1225/catwiz/main/install.ps1"


def run_github_installer():
    key = platform_key()
    print_green("Starting the official CatWiz installer from GitHub...")
    if key == "windows":
        command = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command",
            f"$script = (Invoke-WebRequest -UseBasicParsing '{INSTALL_PS1}').Content; Invoke-Expression $script",
        ]
    else:
        command = ["bash", "-c", f"curl -fsSL '{INSTALL_SH}' | bash"]
    try:
        result = subprocess.run(command, check=False)
    except OSError as error:
        print(f"Could not start the GitHub installer: {error}")
        return
    if result.returncode == 0:
        print_green("GitHub installer finished.")
    else:
        print(f"GitHub installer exited with status {result.returncode}.")
