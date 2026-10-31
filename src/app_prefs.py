"""Small, dependency-free store for desktop preferences.

Theme and UI scale are kept beside this file too, so a packaged AppImage can
write them to the per-user config directory instead of the read-only bundle.
This module holds the session-level choices: window geometry, the last tab,
recent .pk3 files, the rehearsal capture, and first-run bookkeeping.

The file is deliberately plain JSON.  It is not a save file and can be
deleted at any time without touching a Pokémon.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import paths

BASE_DIR = paths.APP_DIR
PREFS_DIR = paths.CONFIG_DIR
PREFS_PATH = paths.PREFS_PATH

_DEFAULTS: dict[str, Any] = {
    "window_geometry": "",
    "last_tab": 0,
    "recent_files": [],
    "last_dir": str(paths.DATA_DIR),
    "first_run_done": False,
    "readiness_seen": False,
    "rehearsal_capture": "",
    "rehearsal_mode": "live",
    "record_capture": False,
    "journal_export_dir": str(paths.DATA_DIR),
    "update_checked_at": "",
    # Audio.  The app ships no Nintendo/Game Freak recordings; these levels
    # apply to the OEM pack the user places in their data directory.
    "sound_muted": False,
    "sound_enabled": True,          # legacy alias for sound_effects
    "sound_effects": True,
    "sound_effects_volume": 0.55,
    "sound_volume": 0.55,           # legacy alias for sound_effects_volume
    "sound_music": True,            # legacy alias for music_enabled
    "music_enabled": True,
    "sound_music_volume": 0.30,
    "cries_enabled": True,
    "cries_volume": 0.80,
    "sound_scan_pulse": False,
}

_cache: dict[str, Any] | None = None


def _read() -> dict[str, Any]:
    try:
        raw = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def load() -> dict[str, Any]:
    """Return the merged preference map, loading it once."""
    global _cache
    if _cache is None:
        merged = dict(_DEFAULTS)
        merged.update(_read())
        _cache = merged
    return _cache


def get(key: str, default: Any = None) -> Any:
    prefs = load()
    if key in prefs:
        return prefs[key]
    return _DEFAULTS.get(key, default)


def set_value(key: str, value: Any) -> None:
    load()[key] = value
    save()


def update(**values: Any) -> None:
    load().update(values)
    save()


def save() -> None:
    """Write atomically so a crash cannot leave a half-written prefs file."""
    prefs = load()
    try:
        PREFS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    temp_name = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=".prefs-", suffix=".json", dir=str(PREFS_DIR)
        )
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(prefs, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_name, PREFS_PATH)
    except OSError:
        # A read-only checkout should not stop the app from closing.
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------
def geometry_text(geometry) -> str:
    """Encode a QByteArray from QWidget.saveGeometry() for JSON storage."""
    if geometry is None:
        return ""
    try:
        return base64.b64encode(bytes(geometry)).decode("ascii")
    except (TypeError, ValueError):
        return ""


def geometry_bytes(text: str) -> bytes | None:
    if not text:
        return None
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Recent files
# ---------------------------------------------------------------------------
def add_recent(path: str | Path, limit: int = 8) -> None:
    """Put a .pk3 at the front of the recent list, newest first."""
    try:
        resolved = str(Path(path).expanduser().resolve())
    except OSError:
        resolved = str(path)
    recent = [item for item in get("recent_files", []) if item != resolved]
    recent.insert(0, resolved)
    update(recent_files=recent[:limit])


def recent_files(limit: int = 8) -> list[str]:
    values = get("recent_files", [])
    if not isinstance(values, list):
        return []
    return [str(item) for item in values[:limit] if Path(str(item)).exists()]


def remember_dir(path: str | Path) -> None:
    try:
        update(last_dir=str(Path(path).expanduser().resolve().parent))
    except OSError:
        pass
