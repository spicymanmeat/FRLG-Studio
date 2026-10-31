"""Persistent "My Trainer" identity for the whole tool.

A Gen 3 record's OT name, TID and SID can only be trusted when they come
from a Pokémon the player actually caught: the tool receives one through
the Switch trade, and that .pk3 carries the real values.  Once learned the
profile is locked on disk and used only for *new* records.  Loading someone
else's Pokémon never rewrites it, so edit-and-return workflows keep the
original trainer's own OT/TID/SID.

The store is a small JSON file at the project root and has no GUI or PKHeX
dependencies, so both the editor and the trade window can import it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

PROFILE_FILENAME = "my_trainer.json"


def profile_path(base_dir) -> Path:
    """Location of the profile file for a project root."""
    return Path(base_dir) / PROFILE_FILENAME


def _as_u16(value) -> int | None:
    """Return the value as an unsigned 16-bit int, or None if it is not one."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= number <= 0xFFFF:
        return number
    return None


def load_profile(base_dir) -> dict | None:
    """Return the locked trainer profile, or None when none is valid yet."""
    try:
        raw = json.loads(profile_path(base_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None

    ot = str(raw.get("ot") or "").strip()[:7]
    tid = _as_u16(raw.get("tid"))
    sid = _as_u16(raw.get("sid"))
    if not ot or tid is None or sid is None:
        return None

    return {
        "ot": ot,
        "tid": tid,
        "sid": sid,
        "source": str(raw.get("source") or ""),
        "saved_at": str(raw.get("saved_at") or ""),
    }


def save_profile(base_dir, ot: str, tid, sid, source: str = "") -> dict | None:
    """Write the profile atomically; returns the stored copy or None if invalid."""
    ot = str(ot or "").strip()[:7]
    tid = _as_u16(tid)
    sid = _as_u16(sid)
    if not ot or tid is None or sid is None:
        return None

    profile = {
        "ot": ot,
        "tid": tid,
        "sid": sid,
        "source": str(source or ""),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = profile_path(base_dir)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
    return profile


def clear_profile(base_dir) -> None:
    """Remove the locked profile (the tool falls back to the editor fields)."""
    profile_path(base_dir).unlink(missing_ok=True)
