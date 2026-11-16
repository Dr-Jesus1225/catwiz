# CatWiz logging

CatWiz uses one logging service for the terminal application and the PySide6 desktop
application. Log files are stored under `~/.catwiz/logs/` (the user's home directory).

## Files

- `activity.log`: concise user-relevant events such as application sessions, downloader
  operations, settings changes, and updates.
- `diagnostics.log`: detailed component diagnostics, including yt-dlp and FFmpeg output.
- `errors.log`: warnings, errors, and exception tracebacks.
- `archive/`: daily and size-rotated log files.
- `exports/`: diagnostic ZIP files explicitly requested by the user.

The GUI Logs page provides current activity, diagnostics, errors, archived history, search,
severity filtering, and an action to open the log directory.

## Retention and limits

Daily archives are retained for 30 days. Each active log file is rotated when it reaches
5 MiB. Expired archives are cleaned at application startup. Diagnostic exports are user-owned
and are not automatically deleted.

## Privacy

Redaction is applied before records are written and again before an export is packaged.
Cookie and authorization headers, credentials, token-like assignments, URL query values,
URL user-info, and the local home-directory prefix are redacted. Raw user-input lines from
the legacy download-folder `logs.txt` are excluded during one-time sanitized migration.
The original legacy file is left untouched.

CatWiz does not automatically upload logs. Export creation is always user initiated:

- **Errors export** contains the current and retained archived error logs.
- **Full diagnostics export** contains activity, diagnostics, errors, retained archives, and
  non-sensitive runtime metadata.

## Tests

Run the standard-library redaction regression tests from the repository root:

```bash
python -m unittest discover -s tests -v
```
