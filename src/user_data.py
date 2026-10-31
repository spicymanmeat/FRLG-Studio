"""Rotating snapshots of the app's user data, plus one-step undo.

The PC, trade slots and editor all write .pk3 files directly.  That is fine
until a drag, a legalize pass or a mis-click replaces something the player
cared about.  Before each mutation the app copies the small user-data tree
into ``.backups/user/<timestamp>-<reason>/``; "Undo last change" restores the
newest snapshot and first saves the current state, so the undo is reversible.

Only user data is copied.  Source, assets, the venv and prod.keys are not.
A PC box holds 30 x 100-byte records, so a snapshot is cheap.
"""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

import paths

BASE_DIR = paths.DATA_DIR
BACKUP_ROOT = paths.BACKUP_ROOT
MAX_SNAPSHOTS = 30

MANAGED_DIRS = (
    "PCstorage",
    "slot1",
    "slot2",
    "created",
    "received",
    "custom_cards",
    "custom gifts",
)
# Journal entries and capture files are historical records, not Pokémon data.
# They can be many megabytes, and undoing a PC move must not erase the proof
# that a trade happened, so they stay out of both snapshots and restores.
MANAGED_FILES = (
    "my_trainer.json",
    "custom_wondercard.json",
)


def _timestamp() -> str:
    # Microseconds keep two actions in the same second in the right order.
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _slug(reason: str) -> str:
    cleaned = "".join(
        char.lower() if char.isalnum() else "-" for char in str(reason)
    ).strip("-")
    return (cleaned or "change")[:40]


def _manifest(snapshot_dir: Path) -> dict:
    try:
        return json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def snapshot(reason: str) -> Path | None:
    """Copy the current user data and return the snapshot directory."""
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_ROOT / f"{_timestamp()}-{_slug(reason)}"
    included_dirs: list[str] = []
    included_files: list[str] = []
    try:
        dest.mkdir(parents=True, exist_ok=False)
        for name in MANAGED_DIRS:
            source = BASE_DIR / name
            if not source.is_dir():
                continue
            shutil.copytree(source, dest / name, dirs_exist_ok=True)
            included_dirs.append(name)
        for name in MANAGED_FILES:
            source = BASE_DIR / name
            if source.is_file():
                shutil.copy2(source, dest / name)
                included_files.append(name)
        (dest / "manifest.json").write_text(
            json.dumps(
                {
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "reason": str(reason),
                    "dirs": included_dirs,
                    "files": included_files,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        shutil.rmtree(dest, ignore_errors=True)
        return None

    _prune()
    return dest


def _prune() -> None:
    try:
        snapshots = sorted(
            (item for item in BACKUP_ROOT.iterdir() if item.is_dir()),
            key=lambda item: item.name,
        )
    except OSError:
        return
    for old in snapshots[:-MAX_SNAPSHOTS]:
        shutil.rmtree(old, ignore_errors=True)


def snapshots() -> list[Path]:
    try:
        return sorted(
            (item for item in BACKUP_ROOT.iterdir() if item.is_dir()),
            key=lambda item: item.name,
        )
    except OSError:
        return []


def latest_snapshot() -> Path | None:
    items = snapshots()
    return items[-1] if items else None


def describe_latest() -> str:
    latest = latest_snapshot()
    if latest is None:
        return "No changes have been recorded yet."
    manifest = _manifest(latest)
    return f"{manifest.get('reason', 'Change')} · {manifest.get('created', latest.name)}"


def restore_latest() -> tuple[bool, str]:
    """Restore the newest snapshot, saving the current state first.

    Returns ``(ok, message)``.  The caller is responsible for refreshing any
    open tab; files are restored on disk immediately.
    """
    latest = latest_snapshot()
    if latest is None:
        return False, "There is no saved change to undo yet."

    manifest = _manifest(latest)
    if not manifest:
        return False, "The newest snapshot is incomplete and was not restored."

    safety = snapshot("Before undo")
    if safety is None:
        return False, "Could not save the current state, so nothing was restored."

    restored = 0
    try:
        for name in MANAGED_DIRS:
            target = BASE_DIR / name
            source = latest / name
            if name in manifest.get("dirs", []) and source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target, dirs_exist_ok=False)
                restored += 1
        for name in MANAGED_FILES:
            target = BASE_DIR / name
            source = latest / name
            if name in manifest.get("files", []) and source.is_file():
                shutil.copy2(source, target)
                restored += 1
    except OSError as exc:
        return False, f"Restore stopped early: {exc}"

    reason = manifest.get("reason", "change")
    return (
        True,
        f"Restored the data from before “{reason}”. "
        f"The state you just left is saved as {safety.name}.",
    )
