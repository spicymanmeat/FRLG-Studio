#!/usr/bin/env python3
"""Import the old checkout-root data into FRLG Studio's release layout.

The 0.9.0 packaging pass moved user data out of the source checkout so the
same paths work in a read-only AppImage.  Existing copies of the app kept
PCstorage, slot1/slot2, received/created, the journal, captures, profiles and
prod.keys in the project root, with settings in assets/ui.

This tool copies those files to the XDG data/config directories, verifies
every copied byte by SHA-256, and rewrites directory preferences so the app
opens in the new locations.  It never deletes the source tree.

Usage:
    venv/bin/python tools/migrate_to_xdg.py --dry-run
    venv/bin/python tools/migrate_to_xdg.py
    venv/bin/python tools/migrate_to_xdg.py --force   # replace differing files

The source root can be overridden with --source.  The destination honours
FRLG_STUDIO_DATA_DIR, FRLG_STUDIO_CONFIG_DIR, XDG_DATA_HOME and
XDG_CONFIG_HOME exactly like the app itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import paths  # noqa: E402


DATA_DIRS = (
    "PCstorage",
    "slot1",
    "slot2",
    "received",
    "created",
    "journal",
    "captures",
    "custom_cards",
    "custom gifts",
    ".backups/user",
)

DATA_FILES = (
    "my_trainer.json",
    "custom_wondercard.json",
    "prod.keys",
    "received.pk3",
    "custom_gift.pokegift",
)

CONFIG_FILES = (
    "prefs.json",
    "theme.txt",
    "ui_scale.txt",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_tree(root: Path):
    for item in sorted(root.rglob("*")):
        if item.is_file():
            yield item


def _relative_files(source: Path, names: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for name in names:
        candidate = source / name
        if candidate.is_file():
            found.append(candidate)
        elif candidate.is_dir():
            found.extend(_iter_tree(candidate))
    return found


def _copy_file(source: Path, target: Path, *, force: bool, dry_run: bool) -> str:
    """Copy one file and return ``copied``, ``same`` or ``skipped``."""
    if target.exists():
        if _sha256(source) == _sha256(target):
            return "same"
        if not force:
            return "skipped"
    if dry_run:
        return "copied"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    try:
        mode = source.stat().st_mode & 0o777
        if source.name == "prod.keys":
            mode = 0o600
        target.chmod(mode)
    except OSError:
        pass
    return "copied"


def _rewrite_prefs(
    source_prefs: Path,
    target_prefs: Path,
    source_data: Path,
    target_data: Path,
    *,
    dry_run: bool,
) -> bool:
    try:
        raw = json.loads(source_prefs.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(raw, dict):
        return False

    def remap(value):
        if not isinstance(value, str) or not value:
            return value
        try:
            path = Path(value).expanduser()
        except (OSError, ValueError):
            return value
        try:
            relative = path.resolve().relative_to(source_data.resolve())
        except (OSError, ValueError):
            return value
        return str(target_data / relative)

    raw["last_dir"] = remap(raw.get("last_dir", str(target_data)))
    raw["journal_export_dir"] = remap(
        raw.get("journal_export_dir", str(target_data))
    )
    raw["rehearsal_capture"] = remap(raw.get("rehearsal_capture", ""))
    recent = raw.get("recent_files", [])
    if isinstance(recent, list):
        raw["recent_files"] = [remap(item) for item in recent if isinstance(item, str)]
    # This is an existing user, not a brand-new install.
    raw["first_run_done"] = True
    raw["readiness_seen"] = True

    if not dry_run:
        target_prefs.parent.mkdir(parents=True, exist_ok=True)
        target_prefs.write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=str(ROOT),
        help="old checkout root (default: the repository containing this tool)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report only")
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace destination files that differ from the source",
    )
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser().resolve()
    target_data = paths.DATA_DIR
    target_config = paths.CONFIG_DIR
    source_data = source
    source_config = source / "assets" / "ui"

    if target_data == source_data:
        print("Source and destination are the same; nothing to migrate.")
        return 0

    print(f"Source data:   {source_data}")
    print(f"Source config: {source_config}")
    print(f"Data target:   {target_data}")
    print(f"Config target: {target_config}")
    if args.dry_run:
        print("Mode:          dry run")

    files = _relative_files(source_data, DATA_DIRS + DATA_FILES)
    config_files = _relative_files(source_config, CONFIG_FILES)
    if not files and not config_files:
        print("No old checkout-root user data was found.")
        return 0

    counts = {"copied": 0, "same": 0, "skipped": 0}
    copied: list[dict[str, object]] = []
    skipped: list[str] = []

    for source_file in files:
        relative = source_file.relative_to(source_data)
        target_file = target_data / relative
        result = _copy_file(
            source_file, target_file, force=args.force, dry_run=args.dry_run
        )
        counts[result] += 1
        if result == "skipped":
            skipped.append(str(relative))
            continue
        copied.append(
            {
                "path": str(Path("data") / relative),
                "bytes": source_file.stat().st_size,
                "sha256": _sha256(source_file),
                "result": result,
            }
        )

    for source_file in config_files:
        relative = source_file.relative_to(source_config)
        target_file = target_config / relative
        if relative.as_posix() == "prefs.json":
            continue  # written below, with remapped paths
        result = _copy_file(
            source_file, target_file, force=args.force, dry_run=args.dry_run
        )
        counts[result] += 1
        if result == "skipped":
            skipped.append(str(Path("config") / relative))
            continue
        copied.append(
            {
                "path": str(Path("config") / relative),
                "bytes": source_file.stat().st_size,
                "sha256": _sha256(source_file),
                "result": result,
            }
        )

    source_prefs = source_config / "prefs.json"
    prefs_written = False
    if source_prefs.is_file():
        prefs_written = _rewrite_prefs(
            source_prefs,
            target_config / "prefs.json",
            source_data,
            target_data,
            dry_run=args.dry_run,
        )
        if prefs_written:
            counts["copied" if not args.dry_run else "same"] += 1
            copied.append(
                {
                    "path": "config/prefs.json",
                    "bytes": None,
                    "sha256": None,
                    "result": "rewritten",
                }
            )

    if not args.dry_run:
        for source_file in files:
            relative = source_file.relative_to(source_data)
            target_file = target_data / relative
            if target_file.is_file() and _sha256(source_file) != _sha256(target_file):
                print(f"Verification failed: {relative}", file=sys.stderr)
                return 1

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "source": str(source),
        "data_target": str(target_data),
        "config_target": str(target_config),
        "dry_run": args.dry_run,
        "counts": counts,
        "prefs_rewritten": prefs_written,
        "files": copied,
        "skipped": skipped,
    }
    if not args.dry_run:
        target_data.mkdir(parents=True, exist_ok=True)
        (target_data / ".migration-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    print()
    print(
        "Copied {copied}, already present {same}, skipped {skipped}.".format(
            **counts
        )
    )
    if skipped:
        print("Skipped files differ at the destination; use --force to replace:")
        for name in skipped[:20]:
            print(f"  {name}")
        if len(skipped) > 20:
            print(f"  ... and {len(skipped) - 20} more")
    if prefs_written:
        print("Preferences were remapped to the release data directory.")
    if args.dry_run:
        print("No files were changed.")
    else:
        print(f"Manifest: {target_data / '.migration-manifest.json'}")
        print("The old checkout-root files were left untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
