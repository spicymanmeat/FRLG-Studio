"""Form-aware asset paths used by the editor, PC, and trade widgets.

Generation 3 Unown forms are derived from the PID; there is no separate form
byte in a PK3.  The animated sprites and the 40x30 box icons use the same
suffix convention:

    form 0      -> 201.gif / 201.png
    forms 1-25  -> 201_B.gif ... 201_Z.gif
    form 26     -> 201_exclamation.gif
    form 27     -> 201_question.gif
"""

from __future__ import annotations

from pathlib import Path

import paths

BASE_DIR = paths.APP_DIR
ASSETS_DIR = paths.ASSETS_DIR

UNOWN_SPECIES = 201
UNOWN_FORM_LABELS = [chr(ord("A") + i) for i in range(26)] + ["!", "?"]


def unown_form_from_pid(pid: int) -> int:
    """Return the Generation 3 Unown form encoded in a PID (0-27)."""
    pid = int(pid) & 0xFFFFFFFF
    value = (
        ((pid & 0x03000000) >> 18)
        | ((pid & 0x00030000) >> 12)
        | ((pid & 0x00000300) >> 6)
        | (pid & 0x00000003)
    )
    return value % 28


def unown_asset_stem(form: int) -> str:
    """Return the shared filename stem for an Unown form."""
    try:
        form = int(form)
    except (TypeError, ValueError):
        form = 0
    if form == 0:
        return "201"
    if 1 <= form <= 25:
        return f"201_{chr(ord('A') + form)}"
    if form == 26:
        return "201_exclamation"
    if form == 27:
        return "201_question"
    return "201"


def animated_sprite_path(species: int, form: int = 0, shiny: bool = False) -> Path:
    """Path to the animated sprite, falling back to the base species sprite."""
    folder = "sprites_animated_shiny" if shiny else "sprites_animated"
    stem = unown_asset_stem(form) if int(species) == UNOWN_SPECIES else str(int(species))
    path = ASSETS_DIR / folder / f"{stem}.gif"
    if path.exists():
        return path

    # Unown's base sprite is the safest fallback if a form asset is missing.
    fallback_stem = "201" if int(species) == UNOWN_SPECIES else str(int(species))
    return ASSETS_DIR / folder / f"{fallback_stem}.gif"


def icon_path(species: int, form: int = 0) -> Path:
    """Path to the 40x30 box icon, including all 28 Unown form icons."""
    stem = unown_asset_stem(form) if int(species) == UNOWN_SPECIES else str(int(species))
    path = ASSETS_DIR / "icons" / f"{stem}.png"
    if path.exists():
        return path

    fallback_stem = "201" if int(species) == UNOWN_SPECIES else str(int(species))
    return ASSETS_DIR / "icons" / f"{fallback_stem}.png"
