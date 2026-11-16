"""Automatic setup for yt-dlp's YouTube JavaScript and PO-token support."""

import importlib.metadata
import os
import shutil
import subprocess
import sys

from .logging_service import component_logger, log_activity

PROVIDER_REPO = "https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git"
PROVIDER_HOME = os.path.join(os.path.expanduser("~"), "bgutil-ytdlp-pot-provider")


def _run(command, cwd=None, timeout=900):
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True,
        errors="replace", timeout=timeout
    )


def ensure_youtube_support():
    """Install and prepare EJS plus BgUtils PO-token support for yt-dlp."""
    logger = component_logger("youtube-setup")
    python = sys.executable

    try:
        # Keep yt-dlp, its matching EJS package, and the PO-token plugin in
        # the exact interpreter used by CatWiz.
        result = _run([
            python, "-m", "pip", "install", "--upgrade",
            "yt-dlp[default]", "certifi", "bgutil-ytdlp-pot-provider"
        ])
        if result.returncode:
            logger.error("YouTube support package setup failed: %s",
                         (result.stderr or result.stdout).strip()[-600:])
            return False

        importlib.invalidate_caches()
        try:
            importlib.metadata.version("yt-dlp-ejs")
            importlib.metadata.version("bgutil-ytdlp-pot-provider")
        except importlib.metadata.PackageNotFoundError:
            logger.error("YouTube EJS or PO-token provider package is not installed")
            return False

        if not shutil.which("deno"):
            logger.error("Deno is unavailable; YouTube challenge solving may be incomplete")
            return False

        # BgUtils' script provider is the simplest no-daemon setup. Its
        # documented default location is ~/bgutil-ytdlp-pot-provider/server.
        if os.path.isdir(os.path.join(PROVIDER_HOME, ".git")):
            update = _run(["git", "-C", PROVIDER_HOME, "pull", "--ff-only"])
            if update.returncode:
                logger.warning("Could not update BgUtils provider source: %s",
                               (update.stderr or update.stdout).strip()[-400:])
        elif not os.path.exists(PROVIDER_HOME):
            clone = _run([
                "git", "clone", "--depth", "1", PROVIDER_REPO, PROVIDER_HOME
            ])
            if clone.returncode:
                logger.error("Could not download BgUtils provider source: %s",
                             (clone.stderr or clone.stdout).strip()[-500:])
                return False
        else:
            logger.error("BgUtils provider path exists but is not a Git checkout: %s",
                         PROVIDER_HOME)
            return False

        server_dir = os.path.join(PROVIDER_HOME, "server")
        if not os.path.isdir(server_dir):
            logger.error("BgUtils provider source has no server directory")
            return False

        install = _run([
            shutil.which("deno"), "install",
            "--allow-scripts=npm:canvas", "--frozen"
        ], cwd=server_dir, timeout=1200)
        if install.returncode:
            logger.error("BgUtils Deno dependencies could not be installed: %s",
                         (install.stderr or install.stdout).strip()[-700:])
            return False

        log_activity(
            "YouTube challenge solver and PO-token provider are ready",
            component="youtube-setup"
        )
        return True
    except Exception:
        logger.exception("Automatic YouTube support setup failed")
        return False
