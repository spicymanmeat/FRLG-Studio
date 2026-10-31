# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the FRLG Studio onedir bundle.

Build with:
    FRLG_STUDIO_ROOT="$PWD" venv/bin/pyinstaller --noconfirm --clean \
        --distpath build/pyinstaller/dist \
        --workpath build/pyinstaller/work \
        tools/frlg_studio.spec

The AppImage builder wraps the resulting ``build/pyinstaller/dist/frlg-studio``
directory.  User data (PCstorage, saves, prefs, prod.keys) is deliberately not
part of this bundle; it lives in the XDG data directory at runtime.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

ROOT = Path(
    os.environ.get("FRLG_STUDIO_ROOT", Path(SPECPATH).resolve().parent)
).resolve()
for _entry in (str(ROOT), str(ROOT / "src")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

datas = []
# Copy the read-only UI art, data tables, fonts and sprites.  Settings are
# excluded: each user gets fresh defaults in their own config directory.
for source in (ROOT / "assets").rglob("*"):
    if not source.is_file():
        continue
    rel = source.relative_to(ROOT)
    if rel.as_posix() in {
        "assets/ui/prefs.json",
        "assets/ui/theme.txt",
        "assets/ui/ui_scale.txt",
    }:
        continue
    datas.append((str(source), str(rel.parent)))

datas.extend(
    [
        (str(ROOT / "gen3_offline_db.json"), "."),
        (str(ROOT / "src" / "PKHeX.Core.dll"), "src"),
        (str(ROOT / "src" / "PKHeX.runtimeconfig.json"), "src"),
        (str(ROOT / "src" / "config" / "host.toml"), "config"),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "README.md"), "."),
    ]
)

# pokeldn ships a few JSON tables used by the Wonder Card host.
datas += collect_data_files("pokeldn")
datas += collect_data_files("pythonnet")

hiddenimports = (
    collect_submodules("frlgsim")
    + collect_submodules("pokeldn")
    + [
        "frlgtrade",
        "frlg_mg_host",
        "clr",
        "pythonnet",
        "pythonnet.runtime",
        "zstandard",
        "ldn",
        "trio",
        "PyQt6.QtMultimedia",
    ]
)

a = Analysis(
    [str(ROOT / "src" / "frlg_entry.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL.ImageTk"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="frlg-studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "branding" / "frlg_studio_icon.png"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="frlg-studio",
)
