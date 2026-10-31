"""Box-level PKHeX legality auditing and repair.

The editor checks the record currently assembled in its own fields.  Bill's
PC had no equivalent, so an imported box could be full of illegal records
without the player seeing it.  This module runs PKHeX over real .pk3 files,
caches the result by file timestamp, repairs a record with the same
conservative legalize path the editor uses, and writes a small report.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pkhex_encounters as pe
from utils import parse_pk3_file

_CACHE: dict[tuple[str, int, int], tuple[bool, tuple[str, ...]]] = {}


@dataclass
class Finding:
    path: str
    slot: int = -1
    nickname: str = "PKMN"
    species: int = 0
    level: int = 0
    shiny: bool = False
    valid: bool = True
    messages: tuple[str, ...] = ()
    changes: tuple[str, ...] = field(default_factory=tuple)


def _cache_key(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size)


def audit_file(path: str | Path, slot: int = -1) -> Finding:
    p = Path(path)
    info = parse_pk3_file(str(p)) or {}
    try:
        key = _cache_key(p)
        cached = _CACHE.get(key)
        if cached is None:
            _pk, valid, messages = pe.legality_from_bytes(p.read_bytes())
            cached = (bool(valid), tuple(messages))
            _CACHE[key] = cached
        valid, messages = cached
    except OSError:
        valid, messages = False, ("Could not read this file.",)
    return Finding(
        path=str(p),
        slot=slot,
        nickname=str(info.get("nickname") or "PKMN"),
        species=int(info.get("nat_dex") or 0),
        level=int(info.get("level") or 0),
        shiny=bool(info.get("is_shiny")),
        valid=valid,
        messages=messages,
    )


def audit_paths(paths: list[tuple[int, str]]) -> list[Finding]:
    return [audit_file(path, slot) for slot, path in paths]


def invalidate(path: str | Path) -> None:
    target = str(path)
    for key in list(_CACHE):
        if key[0] == target:
            _CACHE.pop(key, None)


def legalize_file(path: str | Path) -> Finding:
    """Repair one file in place, returning its new legality state.

    A legal file is left untouched.  The original is only replaced after the
    repaired bytes pass PKHeX again, so a failed repair cannot corrupt it.
    """
    p = Path(path)
    finding = audit_file(p)
    if finding.valid:
        return finding

    raw = p.read_bytes()
    pk, valid, messages = pe.legality_from_bytes(raw)
    if pk is None or valid:
        return finding

    try:
        version = pk.Version
        species = int(pk.Species)
        options = pe.list_encounters(species, version)
        if not options:
            finding.messages = ("No legal encounter is available for this species.",)
            return finding
        trainer = pe.make_trainer(
            str(pk.OriginalTrainerName).rstrip(),
            int(pk.TID16),
            int(pk.SID16),
            version=version,
            language=int(pk.Language),
            trainer_gender=int(getattr(pk, "OriginalTrainerGender", 0) or 0),
        )
        moves = (int(pk.Move1), int(pk.Move2), int(pk.Move3), int(pk.Move4))
        pp_ups = (
            int(pk.Move1_PPUps), int(pk.Move2_PPUps),
            int(pk.Move3_PPUps), int(pk.Move4_PPUps),
        )
        pp_values = (
            int(pk.Move1_PP), int(pk.Move2_PP),
            int(pk.Move3_PP), int(pk.Move4_PP),
        )
        evs = {
            "EV_HP": int(pk.EV_HP),
            "EV_ATK": int(pk.EV_ATK),
            "EV_DEF": int(pk.EV_DEF),
            "EV_SPA": int(pk.EV_SPA),
            "EV_SPD": int(pk.EV_SPD),
            "EV_SPE": int(pk.EV_SPE),
        }
        result = pe.legalize_pk3(
            pk,
            options,
            trainer,
            moves=moves,
            pp_ups=pp_ups,
            pp_values=pp_values,
            evs=evs,
            held_item=int(pk.HeldItem),
            friendship=int(pk.OriginalTrainerFriendship),
            nickname=str(pk.Nickname),
        )
    except Exception as exc:
        finding.messages = (f"Legalize failed: {exc}",)
        return finding

    if result.pk is None:
        finding.messages = (result.error or "PKHeX could not repair this record.",)
        return finding

    repaired = pe.serialize_pk3(result.pk)
    if not repaired:
        finding.messages = ("Could not serialize the repaired record.",)
        return finding
    _pk2, repaired_valid, repaired_messages = pe.legality_from_bytes(repaired)
    if not repaired_valid:
        finding.messages = tuple(repaired_messages) or ("The repaired record is still illegal.",)
        return finding

    try:
        p.write_bytes(repaired)
    except OSError as exc:
        finding.messages = (f"Could not write the repaired file: {exc}",)
        return finding

    invalidate(p)
    return Finding(
        path=str(p),
        slot=finding.slot,
        nickname=finding.nickname,
        species=finding.species,
        level=finding.level,
        shiny=finding.shiny,
        valid=True,
        messages=(),
        changes=tuple(result.changes),
    )


def report_markdown(box_name: str, findings: list[Finding]) -> str:
    legal = sum(1 for finding in findings if finding.valid)
    illegal = len(findings) - legal
    lines = [
        f"# Legality report — {box_name}",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Records: {len(findings)} · Legal: {legal} · Illegal: {illegal}",
        "",
        "| Slot | Pokémon | Lv. | Shiny | Status | Findings | File |",
        "| ---: | --- | ---: | :---: | --- | --- | --- |",
    ]
    for finding in sorted(findings, key=lambda item: (item.slot < 0, item.slot)):
        slot = "—" if finding.slot < 0 else str(finding.slot + 1)
        status = "Legal" if finding.valid else "ILLEGAL"
        detail = "; ".join(finding.messages).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {slot} | {finding.nickname} | {finding.level} | "
            f"{'Yes' if finding.shiny else 'No'} | {status} | {detail or '—'} | "
            f"`{Path(finding.path).name}` |"
        )
    lines.extend(
        [
            "",
            "PKHeX's Gen 3 legality analysis produced these results. A legal "
            "record is not a guarantee of authenticity; it means PKHeX accepts "
            "the record's origin, moves and data.",
            "",
        ]
    )
    return "\n".join(lines)
