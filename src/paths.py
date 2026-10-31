"""Filesystem layout shared by source runs and the packaged AppImage.

Every run uses the same release layout:

* ``APP_DIR`` / ``ASSETS_DIR`` are read-only program files.
* ``DATA_DIR`` holds PC boxes, trade slots, journal, captures and profiles.
* ``CONFIG_DIR`` holds the small settings files (theme, scale, preferences).

By default these are the per-user XDG directories.  A developer can point a
run at a checkout-local tree with ``FRLG_STUDIO_DATA_DIR`` and
``FRLG_STUDIO_CONFIG_DIR``; the AppImage's AppRun sets both explicitly so
nothing tries to write inside the mounted squashfs.  ``tools/migrate_to_xdg``
imports the old checkout-root layout from before this split.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        return Path(value).expanduser().resolve()
    except OSError:
        return Path(value).expanduser()


def _source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _xdg_dir(env_name: str, fallback: Path) -> Path:
    raw = os.environ.get(env_name, "").strip()
    if raw:
        return Path(raw).expanduser()
    return fallback


IS_FROZEN = bool(getattr(sys, "frozen", False))

# In a PyInstaller onedir build, ``_MEIPASS`` is the ``_internal`` directory
# beside the executable.  AppRun can also point at it explicitly, which makes
# the same code work if the bundle is relocated by an AppImage runtime.
_APP_ENV = _env_path("FRLG_STUDIO_APP_DIR")
if _APP_ENV is not None:
    APP_DIR = _APP_ENV
elif IS_FROZEN:
    APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
else:
    APP_DIR = _source_root()

ASSETS_DIR = APP_DIR / "assets"
SRC_DIR = APP_DIR / "src"
UI_ASSETS_DIR = ASSETS_DIR / "ui"
# The program tree's audio banks.  Cry names are resolved through
# species.json, so both species-name files (abra.wav) and dex-prefixed files
# are accepted.  The original-synthesis SFX kit lives beside them and is the
# base layer; a user pack may override any cue by filename.
BUNDLED_CRIES_DIR = ASSETS_DIR / "sound" / "cries"
BUNDLED_SFX_DIR = ASSETS_DIR / "sound" / "sfx"

# Source runs and the AppImage use the same writable locations.  An explicit
# data directory stays self-contained unless the caller also supplies config.
_DATA_ENV = _env_path("FRLG_STUDIO_DATA_DIR")
if _DATA_ENV is not None:
    DATA_DIR = _DATA_ENV
else:
    DATA_DIR = _xdg_dir(
        "XDG_DATA_HOME", Path.home() / ".local" / "share"
    ) / "frlg-studio"

_CONFIG_ENV = _env_path("FRLG_STUDIO_CONFIG_DIR")
if _CONFIG_ENV is not None:
    CONFIG_DIR = _CONFIG_ENV
elif _DATA_ENV is not None:
    CONFIG_DIR = DATA_DIR / "config"
else:
    CONFIG_DIR = _xdg_dir(
        "XDG_CONFIG_HOME", Path.home() / ".config"
    ) / "frlg-studio"

# User data.  Keep these names in one place so the read-only AppImage root is
# never mistaken for a storage location.
PC_DIR = DATA_DIR / "PCstorage"
SLOT1_DIR = DATA_DIR / "slot1"
SLOT2_DIR = DATA_DIR / "slot2"
RECEIVED_DIR = DATA_DIR / "received"
CREATED_DIR = DATA_DIR / "created"
CAPTURES_DIR = DATA_DIR / "captures"
JOURNAL_DIR = DATA_DIR / "journal"
CUSTOM_CARDS_DIR = DATA_DIR / "custom_cards"
CUSTOM_GIFTS_DIR = DATA_DIR / "custom gifts"
# User-supplied OEM audio pack for SFX, music and optional extra cries.  It is
# deliberately writable user data; the primary cry bank lives under assets.
SOUNDPACK_DIR = DATA_DIR / "soundpack"
BACKUP_ROOT = DATA_DIR / ".backups" / "user"
TRAINER_PROFILE = DATA_DIR / "my_trainer.json"
WONDERCARD_JSON = DATA_DIR / "custom_wondercard.json"
LEGACY_RECEIVED = DATA_DIR / "received.pk3"
STAGING_RECEIVED = RECEIVED_DIR / "_incoming.pk3"
# Live offer preview written the instant the Switch confirms its selection.
STAGING_PREVIEW = RECEIVED_DIR / "_incoming_preview.pk3"
STAGING_POKEGIFT = DATA_DIR / "custom_gift.pokegift"

# Settings live apart from the read-only UI art.
PREFS_PATH = CONFIG_DIR / "prefs.json"
THEME_PATH = CONFIG_DIR / "theme.txt"
SCALE_PATH = CONFIG_DIR / "ui_scale.txt"

_DATA_DIRS = (
    PC_DIR,
    SLOT1_DIR,
    SLOT2_DIR,
    RECEIVED_DIR,
    CREATED_DIR,
    CAPTURES_DIR,
    JOURNAL_DIR,
    CUSTOM_CARDS_DIR,
    CUSTOM_GIFTS_DIR,
    SOUNDPACK_DIR,
    BACKUP_ROOT,
)


def ensure_layout() -> None:
    """Create the writable folders without making import fail on a bad path."""
    for directory in (DATA_DIR, CONFIG_DIR, *_DATA_DIRS):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            # The setup checklist will report the unwritable folder.  Import
            # must still work so the app can explain the problem.
            pass


def config_fallback(name: str) -> Path:
    """Return the bundled default for a settings file, if one exists."""
    return UI_ASSETS_DIR / name
