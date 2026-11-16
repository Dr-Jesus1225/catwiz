"""Create user-requested, sanitized diagnostic bundles."""

import os
import platform
import sys
import zipfile
from datetime import datetime

from .logging_redaction import redact_text
from .logging_service import get_log_paths


def export_diagnostics(kind="full"):
    """Export errors only or a full diagnostic bundle; never uploads anything."""
    if kind not in ("errors", "full"):
        raise ValueError("Export kind must be 'errors' or 'full'.")
    paths = get_log_paths()
    os.makedirs(paths["exports"], exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = os.path.join(paths["exports"], f"catwiz-{kind}-{stamp}.zip")

    if kind == "errors":
        sources = [("errors.log", paths["errors"])]
    else:
        sources = [
            ("activity.log", paths["activity"]),
            ("diagnostics.log", paths["diagnostics"]),
            ("errors.log", paths["errors"]),
        ]

    try:
        archived = sorted(os.listdir(paths["archive"]))
    except OSError:
        archived = []
    if kind == "full":
        sources.extend((f"archive/{name}", os.path.join(paths["archive"], name)) for name in archived if name.endswith(".log"))
    else:
        sources.extend((f"archive/{name}", os.path.join(paths["archive"], name)) for name in archived if name.startswith("errors.log.") and name.endswith(".log"))

    try:
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for archive_name, source in sources:
                if os.path.isfile(source):
                    with open(source, "r", encoding="utf-8", errors="replace") as stream:
                        bundle.writestr(archive_name, redact_text(stream.read()))
            if kind == "full":
                metadata = (
                    "CatWiz diagnostic metadata\n"
                    f"Platform: {sys.platform}\n"
                    f"Architecture: {platform.machine()}\n"
                    f"Python: {platform.python_version()}\n"
                    "Sensitive environment variables and credentials are excluded.\n"
                )
                bundle.writestr("environment.txt", metadata)
    except (OSError, zipfile.BadZipFile):
        try:
            os.remove(destination)
        except OSError:
            pass
        raise
    return destination
