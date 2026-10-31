"""PKHeX-backed FireRed/LeafGreen encounter catalog and legal generation.

The app already ships PKHeX.Core.dll.  This module turns its Gen 3 encounter
tables into a small, UI-friendly catalog and generates PK3 records from a
specific encounter instead of guessing one origin per species.
"""

from __future__ import annotations

import os
import random
import struct
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import paths
from sprite_paths import UNOWN_FORM_LABELS, UNOWN_SPECIES, unown_form_from_pid
from core_data import SUBSTRUCT_ORDER

BASE_DIR = paths.APP_DIR

# Keep standalone imports working while reusing the assembly that the editor
# has already loaded at startup.
_runtime = BASE_DIR / "src" / "PKHeX.runtimeconfig.json"
if _runtime.exists():
    os.environ.setdefault("PYTHONNET_CORECLR_RUNTIME_CONFIG", str(_runtime))
try:
    from pythonnet import load

    try:
        load("coreclr")
    except Exception:
        # The editor normally loads coreclr before importing this module.
        pass
except Exception:
    pass

import clr

clr.AddReference(str(BASE_DIR / "src" / "PKHeX.Core.dll"))
import PKHeX.Core as C
import System


ENCOUNTER_FLAGS = (
    C.EncounterTypeGroup.Egg
    | C.EncounterTypeGroup.Static
    | C.EncounterTypeGroup.Trade
    | C.EncounterTypeGroup.Slot
)

CATEGORY_ORDER = {"wild": 0, "static": 1, "trade": 2, "egg": 3, "mystery": 4}

# Event distributions are only offered for species that have no in-game
# source at all (Celebi and Jirachi in Gen 3), so they never clutter the
# normal catalog.
_MYSTERY_FLAGS = ENCOUNTER_FLAGS | C.EncounterTypeGroup.Mystery
_CACHE: dict[tuple[int, int], list["EncounterOption"]] = {}
_LOCATION_CACHE: dict[int, list[tuple[int, str]]] = {}

# Editor origin-game ids -> PKHeX GameVersion.  The ids match PKHeX's own
# numbering for the Gen 3 games (Sapphire 1, Ruby 2, Emerald 3, FR 4, LG 5).
_GAME_VERSIONS = {
    1: C.GameVersion.S,
    2: C.GameVersion.R,
    3: C.GameVersion.E,
    4: C.GameVersion.FR,
    5: C.GameVersion.LG,
}

# Order used when the selected game has no real source for a species: the
# matching version of the other game first, then the Hoenn games.
_FALLBACK_ORDER = {
    C.GameVersion.FR: (C.GameVersion.LG, C.GameVersion.E, C.GameVersion.R, C.GameVersion.S),
    C.GameVersion.LG: (C.GameVersion.FR, C.GameVersion.E, C.GameVersion.R, C.GameVersion.S),
    C.GameVersion.E: (C.GameVersion.R, C.GameVersion.S, C.GameVersion.FR, C.GameVersion.LG),
    C.GameVersion.R: (C.GameVersion.S, C.GameVersion.E, C.GameVersion.FR, C.GameVersion.LG),
    C.GameVersion.S: (C.GameVersion.R, C.GameVersion.E, C.GameVersion.FR, C.GameVersion.LG),
}

# A legal Unown spread depends on the form, nature, shiny state and trainer
# IDs, and building one is cheap now, but remembering the result keeps repeat
# requests instant when the editor re-renders the same record.
_UNOWN_SPREAD_CACHE: dict[tuple[int, int, int, int, bool], tuple[int, int]] = {}

_LCRNG_MULT = 0x41C64E6D
_LCRNG_ADD = 0x6073
_LCRNG_MASK = 0xFFFFFFFF
# Constructed PIDs are reachable from a real stream about two times in three,
# so a few candidates normally suffice; the cap only guards pathological cases.
_UNOWN_CANDIDATE_LIMIT = 400


@dataclass(frozen=True)
class EncounterOption:
    """One displayable, deduplicated acquisition source."""

    category: str
    label: str
    encounter: Any
    species: int
    target_species: int
    form: int
    location: int
    location_name: str
    level_min: int
    level_max: int
    target_level_min: int
    slot_type: str
    rate: int
    source_name: str
    version: Any
    fixed_note: str = ""
    # Contest Beauty a record must carry to be a legal evolution of the source
    # (Milotic needs 170 from Feebas).  0 means no contest requirement.
    beauty_required: int = 0
    # Number of evolution steps from the encounter's species to this one.
    evolution_steps: int = 0

    def __str__(self) -> str:
        return self.label


def version_for_game_id(game_id: int):
    """Map the editor's origin-game IDs to PKHeX GameVersion values."""
    return _GAME_VERSIONS.get(int(game_id), C.GameVersion.FR)


def game_id_for_version(version) -> int:
    for game_id, value in _GAME_VERSIONS.items():
        if version == value:
            return game_id
    try:
        bits = int(version)
    except Exception:
        return 4
    if bits == 15:  # Colosseum/XD: kept as its own origin, never a Gen 3 GBA game
        return 15
    # Combined flags (e.g. RSE, FRLG) resolve to the newest game in the set.
    for game_id in (3, 5, 4, 2, 1):
        if bits & int(_GAME_VERSIONS[game_id]):
            return game_id
    return 4


# PKHeX names the combined Gen 3 flags tersely ("RS"), which is not useful
# in a picker.  Only the combinations an event can actually carry are here.
_COMBINED_VERSION_NAMES = {
    int(C.GameVersion.RS): "Ruby/Sapphire",
    int(C.GameVersion.RSE): "Ruby/Sapphire/Emerald",
    int(C.GameVersion.FRLG): "FireRed/LeafGreen",
}


def _version_name(version) -> str:
    try:
        combined = _COMBINED_VERSION_NAMES.get(int(version))
        if combined:
            return combined
        name = str(C.GameInfo.GetVersionName(version))
    except Exception:
        name = ""
    return name or str(version)


def gen3_locations(version=None) -> list[tuple[int, str]]:
    """Every Gen 3 met location PKHeX knows, as (id, name) pairs.

    PKHeX keeps one merged table for the whole generation: ids 0-87 are the
    Hoenn maps, 88-252 the Kanto/Sevii maps, and 253-255 the special values.
    Using it keeps the editor from showing "Unknown Location" for real ids.
    """
    version = version or C.GameVersion.FR
    cache_key = int(version)
    cached = _LOCATION_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)
    pairs: list[tuple[int, str]] = []
    try:
        items = C.GameInfo.GetLocationList(version, C.EntityContext.Gen3)
        pairs = [(int(item.Value), str(item.Text)) for item in items]
    except Exception:
        pairs = []
    pairs = [(loc, name) for loc, name in pairs if name and 0 <= loc <= 255]
    _LOCATION_CACHE[cache_key] = pairs
    return list(pairs)


def make_trainer(
    ot: str,
    tid: int,
    sid: int,
    *,
    version=None,
    language: int = 2,
    trainer_gender: int = 0,
):
    """Build the trainer record used by PKHeX's converters."""
    version = version or C.GameVersion.FR
    tr = C.SimpleTrainerInfo(version)
    tr.OT = (ot or "TRAINER")[:7]
    tr.TID16 = int(tid) & 0xFFFF
    tr.SID16 = int(sid) & 0xFFFF
    tr.Gender = int(trainer_gender) & 1
    tr.Language = int(language) or 2
    return tr


def _attr(obj, name: str, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _int_attr(obj, name: str, default: int = 0) -> int:
    value = _attr(obj, name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _category(enc) -> str:
    name = enc.GetType().Name
    if "Egg" in name:
        return "egg"
    if "Gift" in name or "Mystery" in name:
        return "mystery"
    if "Trade" in name:
        return "trade"
    if "Slot" in name:
        return "wild"
    if "Static" in name:
        return "static"
    return "other"


def _species_name(species: int) -> str:
    try:
        return C.SpeciesName.GetSpeciesNameGeneration(int(species), 2, 3).title()
    except Exception:
        return f"Species {species}"


def _location_name(location: int, version) -> str:
    if not location:
        return ""
    if int(location) == 146:
        return "Four Island Day Care"
    if int(location) == 254:
        return "In-game Trade"
    try:
        return C.GameInfo.GetLocationName(False, int(location), 3, 3, version)
    except Exception:
        return f"Location {location}"


def _event_details(option: "EncounterOption") -> tuple[bool, bool]:
    """Return (usable GBA record, name text is plain ASCII) for an event.

    PKHeX also holds the GameCube distributions (the Japanese Agate Celebi,
    for example).  Those convert to a 312-byte CK3 rather than a .pk3, so the
    editor cannot round-trip them and they are left out.

    Gift eggs are left out as well: the editor's mystery path treats the
    record as a hatched gift, so saving it would drop the egg flag and make
    an invalid file.  The normal Day Care egg source still covers breeding.

    Japanese distributions are left out because the editor's Gen 3 text
    decoder only knows the Western table: reloading one would show "PKMN"
    and a later save would overwrite the OT.  PKHeX still validates the
    records that are offered.
    """
    try:
        sample = option.encounter.ConvertToPKM(
            make_trainer("TRAINER", 0, 0, version=option.version),
            C.EncounterCriteria.Unrestricted,
        )
    except Exception:
        return False, False
    if sample.GetType().Name != "PK3" or bool(sample.IsEgg):
        return False, False
    text = str(sample.OriginalTrainerName).rstrip() + str(sample.Nickname).rstrip()
    return True, all(ord(ch) < 128 for ch in text)


def _trade_details(enc, version) -> str:
    """Read the fixed trade name/OT for a readable catalog label.

    The PCNY distributions draw a random trainer ID from 1-2999 on every
    conversion, so printing one would make the label (and the dedupe key)
    change on each rebuild.  Their OT name is the stable part.
    """
    try:
        dummy = make_trainer("TRAINER", 0, 0, version=version)
        sample = enc.ConvertToPKM(dummy, C.EncounterCriteria.Unrestricted)
        nick = str(sample.Nickname or "").strip()
        ot = str(sample.OriginalTrainerName or "").strip()
        tid = int(sample.TID16)
        random_id = enc.GetType().Name == "EncounterGift3NY"
        pieces = []
        if nick:
            pieces.append(nick)
        if ot:
            pieces.append(f"OT {ot}" if random_id else f"OT {ot} ({tid})")
        return " · ".join(pieces)
    except Exception:
        return "fixed OT/ID"


def _build_option(enc, target_species: int, target_level_min: int, version,
                  evolution_steps: int = 0) -> EncounterOption | None:
    category = _category(enc)
    if category == "other":
        return None

    source_species = _int_attr(enc, "Species")
    if not source_species:
        return None

    form = _int_attr(enc, "Form") if target_species == UNOWN_SPECIES else 0
    location = _int_attr(enc, "Location")
    location_name = _location_name(location, version)
    level_min = _int_attr(enc, "LevelMin", 1)
    level_max = _int_attr(enc, "LevelMax", level_min)
    slot_type = str(_attr(enc, "Type", "") or "")
    rate = _int_attr(enc, "AreaRate")
    source_name = _species_name(source_species)
    target_name = _species_name(target_species)

    fixed_note = ""
    if category in ("trade", "mystery"):
        fixed_note = _trade_details(enc, version)
    elif category == "static" and bool(_attr(enc, "FatefulEncounter", False)):
        fixed_note = "Fateful"
    elif category == "egg":
        fixed_note = ""

    if category == "egg" and source_species != target_species:
        # A hatched egg must gain a level before a friendship/level evolution,
        # so it cannot already be the evolved species at hatch level.
        target_level_min = max(target_level_min, level_min + 1)

    if category == "wild":
        level_text = f"Lv {level_min}" if level_min == level_max else f"Lv {level_min}-{level_max}"
        label = f"Wild — {location_name} · {level_text}"
        if slot_type:
            label += f" · {slot_type}"
        if rate:
            label += f" ({rate}%)"
    elif category == "static":
        label = f"Static/Gift — {location_name} · Lv {level_min}"
    elif category == "trade":
        label = "In-game Trade"
        if location_name and location_name != "In-game Trade":
            label += f" — {location_name}"
    elif category == "mystery":
        label = f"Mystery Gift — Lv {level_min}"
    else:
        label = f"Egg — {location_name} · Hatch Lv {level_min}"

    if source_species != target_species:
        label = f"{label} · {source_name} → {target_name}"

    if target_species == UNOWN_SPECIES:
        label += f" · Form {UNOWN_FORM_LABELS[form] if 0 <= form < 28 else form}"

    if fixed_note:
        label += f" · {fixed_note}"

    return EncounterOption(
        category=category,
        label=label,
        encounter=enc,
        species=source_species,
        target_species=int(target_species),
        form=form,
        location=location,
        location_name=location_name,
        level_min=level_min,
        level_max=level_max,
        target_level_min=max(1, int(target_level_min)),
        slot_type=slot_type,
        rate=rate,
        source_name=source_name,
        version=version,
        fixed_note=fixed_note,
        evolution_steps=evolution_steps if source_species != target_species else 0,
    )


# Species whose Gen 3 acquisition is an evolution the origin-chain walker
# cannot express, mapped to (pre-evolution species, contest Beauty needed).
# PKHeX's chain for Milotic stops at Milotic itself because the Feebas step is
# a contest-stat evolution, so the source slots have to be borrowed by hand.
_PRE_EVOLUTION_FALLBACKS: dict[int, tuple[int, int]] = {
    350: (349, 170),  # Milotic <- Feebas with max Beauty
}


def _retarget_evolution(options: list[EncounterOption], species: int,
                        beauty_required: int = 0) -> list[EncounterOption]:
    """Re-point pre-evolution sources at the evolved species."""
    source_name = _species_name(species)
    retargeted = []
    for option in options:
        retargeted.append(
            replace(
                option,
                target_species=species,
                target_level_min=max(1, option.target_level_min),
                beauty_required=beauty_required,
                evolution_steps=1,
                label=f"{option.label} · {option.source_name} → {source_name}",
            )
        )
    return retargeted


def _sources_for(species: int, version, *, include_mystery: bool = False) -> list[EncounterOption]:
    """Encounters for a species in one game, following pre-evolution sources."""
    options = _collect_encounters(species, version, include_mystery=include_mystery)
    if options:
        return options
    pre = _PRE_EVOLUTION_FALLBACKS.get(species)
    if pre is None:
        return []
    source_species, beauty = pre
    return _retarget_evolution(
        _collect_encounters(source_species, version, include_mystery=include_mystery),
        species,
        beauty,
    )


def _catalog_sort_key(option: "EncounterOption") -> tuple:
    return (
        CATEGORY_ORDER.get(option.category, 9),
        option.level_min,
        option.location_name,
        option.form,
        option.species,
        option.label,
    )


def _option_key(option: EncounterOption) -> tuple:
    return (
        option.category,
        option.location,
        option.form,
        option.level_min,
        option.level_max,
        option.species,
        option.slot_type if option.category == "wild" else "",
        # Events and in-game trades can share a level and location while being
        # different records (Jirachi's WISHMKR and CHANNEL are both Lv 5 at
        # 255), so their fixed OT/ID text has to be part of the identity.
        option.fixed_note if option.category in ("trade", "mystery") else "",
    )


def _collect_encounters(species: int, version, *, include_mystery: bool = False) -> list[EncounterOption]:
    """Deduplicated acquisition sources for one species in one game."""
    probe = C.PK3()
    probe.Species = species
    probe.Version = version
    probe.CurrentLevel = 100
    probe.MetLevel = 1

    try:
        chain = C.EncounterOrigin.GetOriginChain(probe, 3, C.EntityContext.Gen3)
        if len(chain) == 0:
            return []
        raw = C.EncounterPossible3(chain, _MYSTERY_FLAGS if include_mystery else ENCOUNTER_FLAGS, version)
        # The enumerator is lazy and validates the version while iterating, so
        # collect it here where a bad version can still be handled.
        candidates = list(raw)
    except Exception:
        return []

    target_level_min = 1
    evolution_steps = 0
    for evo in chain:
        method = _attr(evo, "Method", None)
        if method is not None and str(method) != "None":
            evolution_steps += 1
        if int(_attr(evo, "Species", 0)) == species:
            target_level_min = max(target_level_min, _int_attr(evo, "LevelMin", 1))

    seen: dict[tuple, EncounterOption] = {}
    for enc in candidates:
        option = _build_option(enc, species, target_level_min, version, evolution_steps)
        if option is None:
            continue
        key = _option_key(option)
        if key not in seen:
            seen[key] = option

    return sorted(seen.values(), key=_catalog_sort_key)


def list_encounters(species: int, version=None) -> list[EncounterOption]:
    """Deduplicated Gen 3 acquisition sources for a species.

    Sources come from the selected game first.  When that game has no wild,
    static or trade source for the species - only the generic Day Care egg, or
    nothing at all - the other Gen 3 games are searched so every species that
    actually exists in the generation still has a legal table to generate
    from.  Those entries are labelled with their game, and generating from one
    switches the editor's origin game to match.  Event-only species fall back
    to PKHeX's mystery gift records as a final step.
    """
    species = int(species)
    version = version or C.GameVersion.FR
    cache_key = (species, int(version))
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return list(cached)

    options = _sources_for(species, version)
    if not any(option.category != "egg" for option in options):
        seen_keys = {_option_key(option) for option in options}
        for fallback in _FALLBACK_ORDER.get(version, ()):
            for option in _sources_for(species, fallback):
                if option.category == "egg":
                    continue
                key = _option_key(option)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                options.append(
                    replace(option, label=f"{_version_name(fallback)} · {option.label}")
                )
            if any(option.category != "egg" for option in options):
                break
        # Real sources first: a cross-game wild/static entry is a more honest
        # default than the generic Day Care egg the requested game lists for
        # every breedable species.
        options = sorted(options, key=_catalog_sort_key)

    if not any(option.category != "egg" for option in options):
        # Last resort: PKHeX also carries the Gen 3 event distributions, which
        # is how Celebi and Jirachi get a legal source at all.  Keeping them
        # here means they never appear for species that are obtainable
        # normally.
        # Every game is scanned, not just the first with a hit: Jirachi's
        # WISHMKR is listed under Ruby while CHANNEL only appears when
        # Sapphire's table is scanned, so stopping at the first game hid one.
        gathered: list[tuple[Any, EncounterOption]] = []
        seen_events: set[tuple[int, int, str]] = set()
        for source_version in (version, *_FALLBACK_ORDER.get(version, ())):
            for option in _sources_for(species, source_version, include_mystery=True):
                if option.category != "mystery":
                    continue
                usable, ascii_text = _event_details(option)
                if not usable or not ascii_text:
                    continue
                signature = (option.level_min, option.level_max, option.fixed_note)
                if signature in seen_events:
                    continue
                seen_events.add(signature)
                gathered.append((source_version, option))
        seen_keys = {_option_key(option) for option in options}
        for source_version, option in gathered:
            key = _option_key(option)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            label = option.label
            if source_version != version:
                # Prefer the distribution's own version over the game whose
                # table happened to list it: CHANNEL is an RS event even
                # though Ruby's table is where it is first found.
                event_version = _attr(option.encounter, "Version", source_version)
                label = f"{_version_name(event_version)} · {label}"
            options.append(replace(option, label=label))
        options = sorted(options, key=_catalog_sort_key)

    _CACHE[cache_key] = options
    return list(options)


def clear_cache() -> None:
    _CACHE.clear()
    _UNOWN_SPREAD_CACHE.clear()


# Ball ids a plain Gen 3 wild catch may use.  Pulled from PKHeX's own
# BallUseLegality table when reachable; the literal fallback is its
# WildPokeBalls3 set (Master, Ultra, Great, Poké + the seven R/S/E balls).
# Safari Ball is deliberately absent: it is Safari-only.
_WILD_BALL_TABLE: tuple[int, ...] | None = None


def _wild_ball_ids() -> tuple[int, ...]:
    global _WILD_BALL_TABLE
    if _WILD_BALL_TABLE is None:
        ids: tuple[int, ...] | None = None
        try:
            from System.Reflection import BindingFlags

            flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static
            kind = System.Type.GetType("PKHeX.Core.BallUseLegality, PKHeX.Core")
            method = kind.GetMethod("GetWildBalls", flags)
            mask = int(method.Invoke(None, [System.Byte(3), C.GameVersion.FR]))
            ids = tuple(i for i in range(1, 13) if (mask >> i) & 1)
        except Exception:
            ids = None
        _WILD_BALL_TABLE = ids or (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12)
    return _WILD_BALL_TABLE


def required_ball(option: "EncounterOption") -> int | None:
    """The ball PKHeX mandates for this encounter, or None for a free choice.

    PKHeX fixes the ball for Safari slots (Safari Ball), Day Care eggs,
    in-game trades, event gifts, and the FRLG gift statics - the starters,
    fossils, Hitmonlee/Hitmonchan, Eevee, Lapras, the Magikarp salesman and
    the Togepi egg all carry ``FixedBall = Poké Ball``.  Ordinary statics
    (legendaries, Snorlax) and plain wild slots keep the Gen 3 ball set.
    """
    try:
        value = int(option.encounter.FixedBall)
    except Exception:
        return None
    return value or None


def allowed_balls(option: "EncounterOption") -> tuple[int, ...]:
    """Ball ids PKHeX accepts for this encounter."""
    fixed = required_ball(option)
    if fixed is not None:
        return (fixed,)
    return _wild_ball_ids()

def unown_form_for_pk(pk) -> int:
    return unown_form_from_pid(int(pk.PID))


def method_name_for_pk(pk) -> str:
    try:
        name = str(C.MethodFinder.Analyze(pk).Type)
        return name.replace("Method_", "Method ")
    except Exception:
        return "Unknown"


def _move_errors(analysis) -> list[str]:
    """PKHeX keeps move legality outside its check results.

    ``LegalityAnalysis.Valid`` also requires every move result to be valid, so
    a record can be flagged with nothing but green check lines: the offending
    move only shows up here (an unreachable move on an event or static record,
    for example).
    """
    messages = []
    try:
        for index, move in enumerate(analysis.Info.Moves):
            if bool(move.Valid):
                continue
            expect = int(move.Expect)
            detail = f"Move {index + 1}: {move.Info.Method}"
            if expect:
                detail += f" (expected move #{expect})"
            messages.append(detail)
    except Exception:
        pass
    return messages


def _legality(pk) -> tuple[bool, tuple[str, ...]]:
    try:
        analysis = C.LegalityAnalysis(pk)
        messages = []
        if not analysis.Valid:
            for result in analysis.Results:
                if not result.Valid:
                    messages.append(f"{result.Identifier}: {result.Result}")
            messages.extend(_move_errors(analysis))
        return bool(analysis.Valid), tuple(messages)
    except Exception as exc:
        return False, (f"Legality analysis failed: {exc}",)


# PKHeX reports these as warnings (severity "fishy"), not errors: the PID/IV
# pair is reachable by the RNG, but the first seed its reversal finds does not
# satisfy the wild slot's frame conditions.  The converter draws a new spread
# every call, so a frame-clean candidate can be preferred instead.
_FRAME_WARNING_CODES = ("EncConditionBadRNGFrame", "EncConditionBadPIDIV")


def _legality_report(pk) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """One analysis, split into (valid, errors, frame warnings)."""
    try:
        analysis = C.LegalityAnalysis(pk)
    except Exception as exc:
        return False, (f"Legality analysis failed: {exc}",), ()

    errors = []
    warnings = []
    for result in analysis.Results:
        try:
            if str(result.Judgement) == "Valid":
                continue
            code = str(result.Result)
            if result.Valid:
                if code in _FRAME_WARNING_CODES:
                    warnings.append(code)
            else:
                errors.append(f"{result.Identifier}: {result.Result}")
        except Exception:
            continue
    if not analysis.Valid:
        errors.extend(_move_errors(analysis))
    return bool(analysis.Valid), tuple(errors), tuple(warnings)


def raw_bytes_from_pk(pk) -> bytes:
    """Return a PK3's in-memory (decrypted, unshuffled) bytes.

    pythonnet cannot marshal PKHeX's ``Span<byte>`` accessors, so read the
    protected ``Raw`` memory field through reflection instead.  The returned
    buffer is the canonical 100-byte party layout: block G at 0x20, A at
    0x2C, E at 0x38, and M at 0x44.
    """
    flags = (
        System.Reflection.BindingFlags.Public
        | System.Reflection.BindingFlags.NonPublic
        | System.Reflection.BindingFlags.Instance
    )
    try:
        current = pk.GetType()
        while current is not None:
            field = current.GetField("Raw", flags)
            if field is not None:
                memory = field.GetValue(pk)
                return bytes(memory.ToArray())
            current = current.BaseType
    except Exception:
        pass
    return b""


def pk3_from_bytes(raw: bytes) -> Any | None:
    """Construct a PK3 from serialized (file format) bytes, without analyzing.

    PKHeX keeps the entity's 100-byte party layout, so the canonical bytes
    other helpers return cannot be fed back in here; this expects the buffer
    the editor serializes (encrypted and shuffled, checksum included).
    """
    try:
        data = System.Array[System.Byte](bytearray(raw))
        return C.PK3(System.Memory[System.Byte](data))
    except Exception:
        return None


def serialize_pk3(pk) -> bytes:
    """Write a PK3 object back in the 100-byte .pk3 file layout.

    PKHeX exposes the record through Span<byte> accessors that pythonnet
    cannot marshal, so ``WriteEncryptedDataStored`` is not callable here.
    ``Raw`` does give the canonical, unshuffled G/A/E/M memory image; this
    applies the same shuffle, checksum and XOR pass the editor uses when it
    saves a record.  The result round-trips through :func:`legality_from_bytes`.
    """
    raw = bytearray(raw_bytes_from_pk(pk))
    if len(raw) < 100:
        return b""
    try:
        pid = int(pk.PID) & 0xFFFFFFFF
        otid = ((int(pk.SID16) & 0xFFFF) << 16) | (int(pk.TID16) & 0xFFFF)
        blocks = [raw[0x20 + i * 12:0x20 + (i + 1) * 12] for i in range(4)]
        order = SUBSTRUCT_ORDER[pid % 24]
        ordered: list[bytes | None] = [None] * 4
        for index, block in enumerate(blocks):
            ordered[order[index]] = block
        if any(block is None for block in ordered):
            return b""
        sub_raw = b"".join(block for block in ordered if block is not None)
        checksum = sum(struct.unpack("<24H", sub_raw)) & 0xFFFF
        struct.pack_into("<H", raw, 0x1C, checksum)
        key = pid ^ otid
        words = struct.unpack("<12I", sub_raw)
        raw[0x20:0x50] = struct.pack(
            "<12I", *[(word ^ key) & 0xFFFFFFFF for word in words]
        )
    except Exception:
        return b""
    return bytes(raw)


def legality_from_bytes(raw: bytes) -> tuple[Any | None, bool, tuple[str, ...]]:
    """Construct a PK3 from the editor's serialized bytes and analyze it."""
    pk = pk3_from_bytes(raw)
    if pk is None:
        return None, False, ("Could not read this record as a PK3.",)
    valid, messages = _legality(pk)
    return pk, valid, messages


# Every Gen 3 egg is Japanese in PKHeX's eyes, and the game stores the egg
# name in the Japanese table: タ (0x60) マ (0x6F) ゴ (0x8B).
EGG_NAME_JAPANESE = "タマゴ"
EGG_BALL_POKE = 4

# PK3 ribbon bits an egg cannot carry (PKHeX's ribbon verifier rejects them).
_PK3_RIBBON_FIELDS = (
    "RibbonCountG3Cool", "RibbonCountG3Beauty", "RibbonCountG3Cute",
    "RibbonCountG3Smart", "RibbonCountG3Tough", "RibbonChampionG3",
    "RibbonWinning", "RibbonVictory", "RibbonArtist", "RibbonEffort",
    "RibbonChampionBattle", "RibbonChampionRegional", "RibbonChampionNational",
    "RibbonCountry", "RibbonNational", "RibbonEarth", "RibbonWorld",
)

_PK3_CONTEST_FIELDS = (
    "ContestCool", "ContestBeauty", "ContestCute", "ContestSmart",
    "ContestTough", "ContestSheen",
)


def convert_egg_state(raw: bytes, unhatched: bool, *, level: int | None = None,
                      location: int | None = None, ball: int = EGG_BALL_POKE,
                      hatch_cycles: int | None = None,
                      pp_values: tuple[int, int, int, int] | None = None,
                      trainer_language: int = 2,
                      ) -> tuple[Any | None, bool, tuple[str, ...]]:
    """Rewrite a serialized PK3 as a legal Gen 3 egg, or as a hatched one.

    PKHeX only accepts a record while it still is an egg: Japanese language,
    the "タマゴ" nickname, hatch cycles inside the species' range, the
    encounter's hatch level with exactly matching EXP, met level 0, a Poké
    Ball and no EVs, items, PP Ups, ribbons, contest stats or fateful flag.

    The language has to be written *after* the egg flag: PKHeX's ``IsEgg``
    setter encodes the egg name using whatever language the record still has,
    so switching to Japanese afterwards is the only way to get real タマゴ
    bytes instead of a Western truncation of them.
    """
    pk = pk3_from_bytes(raw)
    if pk is None:
        return None, False, ("Could not read this record as a PK3.",)

    if unhatched:
        limit = int(pk.PersonalInfo.HatchCycles) or 1
        cycles = int(pk.OriginalTrainerFriendship) if hatch_cycles is None else int(hatch_cycles)
        pk.IsEgg = True
        pk.Language = 1
        pk.PrepareNickname()
        pk.Nickname = EGG_NAME_JAPANESE
        pk.OriginalTrainerFriendship = max(0, min(cycles, limit))
        if level:
            # Also snaps EXP to the encounter's exact hatch-level value.
            pk.CurrentLevel = int(level)
        pk.MetLevel = 0
        if location is not None:
            pk.MetLocation = int(location) & 0xFF
        pk.Ball = int(ball) & 0xF
        for field in ("EV_HP", "EV_ATK", "EV_DEF", "EV_SPE", "EV_SPA", "EV_SPD"):
            setattr(pk, field, 0)
        pk.HeldItem = 0
        for slot in range(1, 5):
            setattr(pk, f"Move{slot}_PPUps", 0)
        if pp_values is not None:
            for slot, value in enumerate(tuple(pp_values)[:4], start=1):
                setattr(pk, f"Move{slot}_PP", int(value) & 0xFF)
        pk.FatefulEncounter = False
        for field in _PK3_CONTEST_FIELDS:
            setattr(pk, field, 0)
        for field in _PK3_RIBBON_FIELDS:
            setattr(pk, field, False)
    else:
        pk.IsEgg = False
        pk.Language = int(trainer_language)
        pk.PrepareNickname()
        pk.Nickname = C.SpeciesName.GetSpeciesNameGeneration(
            int(pk.Species), int(trainer_language), 3
        )
        pk.OriginalTrainerFriendship = int(pk.PersonalInfo.BaseFriendship)
        pk.MetLevel = 0
        if location is not None:
            pk.MetLocation = int(location) & 0xFF
        pk.Ball = int(ball) & 0xF

    valid, errors = _legality(pk)
    return pk, valid, errors


def _ivs_from_pk(pk) -> tuple[int, ...]:
    return (
        int(pk.IV_HP),
        int(pk.IV_ATK),
        int(pk.IV_DEF),
        int(pk.IV_SPE),
        int(pk.IV_SPA),
        int(pk.IV_SPD),
    )


_LEVEL_LEARNSETS: dict[str, Any] = {}


def _level_learnset_table(version) -> Any | None:
    """Return PKHeX's level-up table for a Gen 3 game.

    The table is a static ``Learnset[]``; reading it directly avoids the
    ``ReadOnlySpan`` accessors that pythonnet cannot marshal.  Each entry has
    parallel ``Moves`` and ``Levels`` arrays.
    """
    key = str(version)
    if key in _LEVEL_LEARNSETS:
        return _LEVEL_LEARNSETS[key]
    class_name = {
        "FR": "LearnSource3FR",
        "LG": "LearnSource3LG",
        "E": "LearnSource3E",
        "R": "LearnSource3RS",
        "S": "LearnSource3RS",
    }.get(key)
    table = None
    if class_name is not None:
        try:
            from System.Reflection import BindingFlags

            learned_type = System.Type.GetType(
                f"PKHeX.Core.{class_name}, PKHeX.Core"
            )
            field = learned_type.GetField(
                "Learnsets",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static,
            )
            table = field.GetValue(None)
        except Exception:
            table = None
    _LEVEL_LEARNSETS[key] = table
    return table


def _level_up_moves(version, species: int, level: int) -> tuple[int, ...]:
    """The last four level-up moves a species knows at ``level``.

    PKHeX's converter builds an egg at its hatch level; raising only the
    stored level afterward leaves a Lv 20 egg-origin Pokémon with its Lv 5
    moves.  This reads the same Gen 3 learnset the game uses and keeps the
    most recent four moves, which is exactly the in-game move history.
    """
    table = _level_learnset_table(version)
    if table is None or not (0 <= int(species) < len(table)):
        return ()
    try:
        from System.Reflection import BindingFlags

        learnset = table[int(species)]
        flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance
        moves_field = learnset.GetType().GetField("Moves", flags)
        levels_field = learnset.GetType().GetField("Levels", flags)
        moves = list(moves_field.GetValue(learnset))
        levels = list(levels_field.GetValue(learnset))
    except Exception:
        return ()
    # Some Gen 3 learnsets list the same move twice (Raticate has Quick
    # Attack at both Lv 1 and Lv 7).  A Pokémon cannot store duplicate moves,
    # so collapse repeats before taking the latest four.  Keeping the first
    # occurrence preserves the learn order; the last-four window still favours
    # the most recent distinct moves.
    learned = []
    seen = set()
    for move, needed in zip(moves, levels):
        move = int(move)
        if not move or int(needed) > int(level) or move in seen:
            continue
        seen.add(move)
        learned.append(move)
    return tuple(learned[-4:])


def complete_level_up_moves(pk, option: EncounterOption | None):
    """Fill only the empty move slots with level-appropriate learnset moves.

    Legalize must never replace a move the player chose.  Some records do,
    however, arrive with only their met-level/hatch-level moves and empty
    slots; at a higher current level those empty slots can be completed from
    the same Gen 3 level-up learnset the game uses.  This applies to every
    encounter type, not just wild and egg records: a gift, static, trade or
    event record can also be raised above the level it was received at.
    Returns ``(candidate, added_moves)`` when PKHeX still accepts the result,
    otherwise ``None``.
    """
    if option is None:
        return None

    current = [_int_attr(pk, f"Move{slot}") for slot in range(1, 5)]
    if all(current):
        return None
    known = [move for move in current if move]
    original_pp_ups = [
        _int_attr(pk, f"Move{slot}_PPUps")
        for slot, move in zip(range(1, 5), current) if move
    ]
    original_pp = [
        _int_attr(pk, f"Move{slot}_PP")
        for slot, move in zip(range(1, 5), current) if move
    ]
    learned = _level_up_moves(
        option.version, int(_int_attr(pk, "Species")), int(_int_attr(pk, "CurrentLevel"))
    )
    if not learned:
        return None

    fill = [move for move in learned if move not in known]
    if not fill:
        return None
    # When slots are scarce, add the most recent moves first.  A Lv 14 gift
    # Squirtle that still has Tackle/Tail Whip should gain Water Gun and
    # Withdraw, not the older Bubble/Withdraw pair.
    needed = 4 - len(known)
    fill = fill[-needed:] if needed < len(fill) else fill
    completed = known[:]
    completed.extend(fill[:needed])
    if completed == known:
        return None

    candidate = pk.Clone()
    for index, move in enumerate(completed):
        setattr(candidate, f"Move{index + 1}", int(move) & 0xFFFF)
        setattr(
            candidate, f"Move{index + 1}_PPUps",
            original_pp_ups[index] if index < len(known) else 0,
        )
    for index in range(len(completed), 4):
        setattr(candidate, f"Move{index + 1}", 0)
    candidate.HealPP()
    # Only the added moves get fresh PP.  Keep the player's existing PP and
    # PP Ups on moves that were already in the record.
    for index in range(len(known)):
        maximum = _int_attr(candidate, f"Move{index + 1}_PP")
        setattr(candidate, f"Move{index + 1}_PP", min(original_pp[index], maximum))

    valid, _errors, _warnings = _legality_report(candidate)
    if not valid:
        return None
    return candidate, tuple(completed[len(known):])


def _validate_target(option: EncounterOption, target_species: int, target_level: int,
                     gender: int | None, ability_slot: int | None) -> str | None:
    if target_level < 1 or target_level > 100:
        return "Level must be between 1 and 100."
    if target_level < option.level_min:
        return f"{option.label} is met at Lv {option.level_min}; current level cannot be lower."
    if target_level < option.target_level_min:
        return (
            f"This {_species_name(target_species)} must be at least Lv "
            f"{option.target_level_min} when obtained from this encounter."
        )

    probe = C.PK3()
    probe.Species = target_species
    pi = probe.PersonalInfo
    ratio = int(pi.Gender)
    if gender in (0, 1):
        if ratio == 255:
            return "This species is genderless."
        if ratio == 0 and gender == 1:
            return "This species is male-only."
        if ratio == 254 and gender == 0:
            return "This species is female-only."
    ability_count = 2
    try:
        ability_count = int(pi.AbilityCount)
    except Exception:
        pass
    if ability_slot is not None and ability_slot not in (0, 1):
        return "Ability slot must be 0 or 1."
    if ability_slot == 1 and ability_count < 2:
        return "This species has only one Ability in Generation 3."
    return None


def _finalize_pk3(pk, option: EncounterOption, target_species: int, target_level: int,
                  ability_slot: int | None) -> None:
    source_species = int(pk.Species)
    if target_level < int(pk.MetLevel):
        # Wild slots pick a random level inside their range.  When the chosen
        # met level is above the requested current level, pin it to the
        # requested level (still inside the slot range) instead of failing.
        if option.category == "wild" and option.level_min <= target_level <= option.level_max:
            pk.MetLevel = target_level
        else:
            raise ValueError(
                f"The selected encounter is met at Lv {pk.MetLevel}; current level cannot be lower."
            )

    if target_species != source_species:
        # PKHeX fills an unnamed record with the species name it was converted
        # from.  Evolving that record would otherwise keep the pre-evolution
        # name (WEEDLE on a Beedrill); only replace a name that is the source's
        # own default, never a fixed in-game-trade nickname such as CH'DING.
        try:
            source_default = str(C.SpeciesName.GetSpeciesNameGeneration(
                source_species, int(pk.Language), 3
            )).rstrip()
            target_default = str(C.SpeciesName.GetSpeciesNameGeneration(
                target_species, int(pk.Language), 3
            )).rstrip()
            if not str(pk.Nickname).rstrip() or str(pk.Nickname).rstrip() == source_default:
                pk.Nickname = target_default
        except Exception:
            pass
        pk.Species = target_species
        # PKHeX rejects an evolved record whose level is not above the level it
        # was met at, so each evolution step needs a level of its own above the
        # met/hatch level.  The final species, however, only has to clear its
        # own evolution threshold: a Pidgeot is legal at Lv 36 and a Venusaur
        # at Lv 32, not one level later.  Never lower a higher requested level.
        steps = max(1, int(option.evolution_steps))
        base = max(int(pk.MetLevel), option.level_min)
        floor = max(base + steps, option.target_level_min)
        pk.CurrentLevel = max(target_level, floor)
        if option.beauty_required:
            beauty = max(int(pk.ContestBeauty), int(option.beauty_required))
            pk.ContestBeauty = beauty
            # Gen 3 Pokéblock sheen grows with the stats it feeds; PKHeX checks
            # that correlation, so give the record a matching sheen value.
            pk.ContestSheen = max(int(pk.ContestSheen), min(255, beauty // 5))
        pk.RefreshAbility(ability_slot if ability_slot is not None else (int(pk.PID) & 1))
        # Keep the encounter's legal starting moves.  A Gen 3 evolution retains
        # the moves it knew before evolving; the editor can replace them later.
    else:
        if int(pk.CurrentLevel) != target_level:
            pk.CurrentLevel = target_level
        if ability_slot is not None:
            pk.RefreshAbility(ability_slot)
        if target_species == UNOWN_SPECIES:
            # The converter already selected a PID matching the slot's form.
            # Never assign PK3.Form here: its setter mutates the PID and can
            # invalidate the RNG correlation.
            pass

    if int(pk.CurrentLevel) > option.level_min:
        # Every Gen 3 converter builds the source at its met level: wild slots,
        # eggs, gifts/statics, trades and event distributions alike.  Raising
        # only the stored level afterward leaves a Lv 14 gift Squirtle with its
        # Lv 5 moves.  A newly generated record should know the latest four
        # level-up moves for the level it is being generated at, regardless of
        # how it was obtained.  This applies after evolution too, so a Raticate
        # generated from a low-level Rattata source uses Raticate's learnset.
        learned = _level_up_moves(option.version, target_species, int(pk.CurrentLevel))
        if learned:
            for slot in range(1, 5):
                setattr(pk, f"Move{slot}", learned[slot - 1] if slot <= len(learned) else 0)
    pk.ResetPartyStats()
    pk.HealPP()


def _score(pk) -> int:
    return sum(_ivs_from_pk(pk))


@dataclass(frozen=True)
class LegalizeResult:
    """Outcome of repairing an existing record without generating a new one."""

    pk: Any | None
    option: EncounterOption | None
    changes: tuple[str, ...] = ()
    error: str | None = None


def _encounter_signature(enc) -> tuple:
    """Identity used to pair an encounter object with a catalog entry."""
    return (
        str(enc.GetType().Name),
        _int_attr(enc, "Species"),
        _int_attr(enc, "Form"),
        _int_attr(enc, "Location"),
        _int_attr(enc, "LevelMin"),
        _int_attr(enc, "LevelMax"),
        str(_attr(enc, "Version", "")),
    )


def _moveset_signatures(pk, moves: tuple[int, int, int, int]) -> set[tuple]:
    """Encounters PKHeX says can legally know this moveset."""
    try:
        raw = System.Array[System.UInt16]([int(move) & 0xFFFF for move in moves])
        moveset = System.ReadOnlyMemory[System.UInt16](raw)
        versions = System.Array[C.GameVersion]([
            C.GameVersion.FR, C.GameVersion.LG, C.GameVersion.E,
            C.GameVersion.R, C.GameVersion.S,
        ])
        # The generator normalises the probe's Version as it walks the game
        # list (it leaves it on the last game it checked).  Keep that side
        # effect off the record the user is legalizing.
        probe = pk.Clone()
        found = C.EncounterMovesetGenerator.GenerateEncounters(
            probe, moveset, System.ReadOnlyMemory[C.GameVersion](versions)
        )
        return {_encounter_signature(enc) for enc in found}
    except Exception:
        # The generator is only a prioritisation hint.  A record can still be
        # legalized from the selected encounter when it cannot run.
        return set()


def _legalize_options(pk, options: list[EncounterOption],
                      moves: tuple[int, int, int, int]) -> list[EncounterOption]:
    """Put the most likely source first, without dropping any fallback."""
    signatures = _moveset_signatures(pk, moves)
    current_location = _int_attr(pk, "MetLocation")
    # A hatched egg is not an egg record anymore (IsEgg is false), but its
    # MetLevel 0, day-care location still identifies an egg origin.  Keep that
    # source preferred during repair so Legalize does not switch a hatched
    # Pokémon to a wild encounter and replace its legal egg-level moveset.
    egg_locations = {
        option.location for option in options if option.category == "egg"
    }
    current_category = (
        "egg"
        if bool(_attr(pk, "IsEgg", False))
        or (
            _int_attr(pk, "MetLevel") == 0
            and current_location in egg_locations
        )
        else ""
    )

    def score(item):
        index, option = item
        value = 0
        if index == 0:
            value += 1000
        if _encounter_signature(option.encounter) in signatures:
            value += 100
        if option.category == current_category:
            # A met-level-0 record is an egg origin; prefer the egg source over
            # the catalog's default (usually a wild slot), even when the UI did
            # not manage to carry a selected source into this repair.
            value += 1200 if current_category == "egg" else 20
        if current_location and option.location == current_location:
            value += 40
        if option.category != "egg" and option.level_min <= _int_attr(pk, "MetLevel") <= option.level_max:
            value += 10
        return (-value, index)

    return [option for _, option in sorted(enumerate(options), key=score)]


def _candidate_with_metadata(pk, option: EncounterOption):
    """Clone a record and apply only the selected source's fixed metadata.

    This is the least destructive repair: PID, IVs, moves, nature and level
    stay exactly as the user set them.  PKHeX then decides whether that source
    can actually explain the record.
    """
    candidate = pk.Clone()
    candidate.Version = option.version

    if option.category == "egg":
        # A hatched egg is a normal PK3 (IsEgg is false) whose met level is 0.
        # Rejecting it here forced Legalize to abandon the egg origin and try
        # a wild slot, which then rewrote legal egg moves down to that slot's
        # starting set.  Egg metadata can be applied to any record; PKHeX's
        # legality check still decides whether its PID/IV pair came from an
        # egg, so an unrelated wild record fails safely below.
        candidate.MetLocation = int(option.location) & 0xFF
        candidate.MetLevel = 0
        candidate.Ball = EGG_BALL_POKE
        candidate.FatefulEncounter = False
        return candidate

    candidate.MetLocation = int(option.location) & 0xFF
    if option.category == "wild":
        met_level = _int_attr(pk, "MetLevel")
        if not (option.level_min <= met_level <= option.level_max):
            met_level = max(option.level_min, min(option.level_max, _int_attr(pk, "CurrentLevel")))
        candidate.MetLevel = met_level
    else:
        candidate.MetLevel = option.level_min

    if _int_attr(candidate, "CurrentLevel") < _int_attr(candidate, "MetLevel"):
        candidate.CurrentLevel = _int_attr(candidate, "MetLevel")

    fixed_ball = required_ball(option)
    if fixed_ball is not None:
        candidate.Ball = int(fixed_ball)
    elif _int_attr(candidate, "Ball") not in allowed_balls(option):
        candidate.Ball = 4

    try:
        candidate.FatefulEncounter = bool(option.encounter.FatefulEncounter)
    except Exception:
        candidate.FatefulEncounter = False
    return candidate


def _normalise_moves(moves: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Gen 3 requires empty move slots at the end and no duplicate moves."""
    ordered = []
    for move in moves:
        move = int(move) & 0xFFFF
        if move and move not in ordered:
            ordered.append(move)
    ordered.extend([0] * (4 - len(ordered)))
    return tuple(ordered)


def _apply_saved_fields(pk, source, *, moves, pp_ups, pp_values, evs,
                        held_item: int, friendship: int, nickname: str) -> None:
    """Copy the user's choices onto a generated legal candidate."""
    for index, move in enumerate(moves):
        setattr(pk, f"Move{index + 1}", int(move) & 0xFFFF)
        setattr(pk, f"Move{index + 1}_PPUps", max(0, min(3, int(pp_ups[index]))))
    pk.HealPP()

    # HealPP fills every slot to the maximum that the move and PP Ups allow;
    # put the user's current PP back without ever exceeding that maximum.
    for index, value in enumerate(pp_values):
        max_pp = _int_attr(pk, f"Move{index + 1}_PP")
        setattr(pk, f"Move{index + 1}_PP", max(0, min(int(value), max_pp)))

    if not bool(pk.IsEgg):
        pk.HeldItem = int(held_item) & 0xFFFF
        pk.OriginalTrainerFriendship = max(0, min(255, int(friendship)))
        for prop, value in evs.items():
            setattr(pk, prop, max(0, min(255, int(value))))
        if nickname:
            pk.Nickname = nickname[:10]


def _repair_moves(pk, fallback_moves: tuple[int, int, int, int]) -> bool:
    """Replace only the moves PKHeX flags, leaving every legal move alone."""
    for _ in range(5):
        analysis = C.LegalityAnalysis(pk)
        bad = []
        for index, result in enumerate(analysis.Info.Moves):
            if bool(result.Valid):
                continue
            bad.append((index, _int_attr(result, "Expect")))
        if not bad:
            return bool(analysis.Valid)

        used = {_int_attr(pk, f"Move{i}") for i in range(1, 5)}
        changed = False
        for index, expected in bad:
            current = _int_attr(pk, f"Move{index + 1}")
            choices = [expected, fallback_moves[index], 0]
            choices.extend(fallback_moves)
            # Prefer a real legal fallback move over blanking the slot; an
            # expected move of 0 means "not obtainable", not "use nothing".
            choices = [choice for choice in choices if choice] + [0]
            replacement = 0
            for choice in choices:
                choice = int(choice) & 0xFFFF
                if choice == current:
                    replacement = current
                    break
                if choice == 0 or choice not in used or choice == current:
                    replacement = choice
                    break
            if replacement != current:
                setattr(pk, f"Move{index + 1}", replacement)
                setattr(pk, f"Move{index + 1}_PPUps", 0)
                used.discard(current)
                if replacement:
                    used.add(replacement)
                changed = True
        if not changed:
            break
        pk.HealPP()

    valid, _errors, _warnings = _legality_report(pk)
    return valid


def _move_name(move: int, move_names: dict[int, str] | None) -> str:
    if not move:
        return "(empty)"
    if move_names and move in move_names:
        return str(move_names[move])
    return f"Move #{move}"


def _repair_auxiliary_fields(pk, option: EncounterOption, changes: list[str]) -> bool:
    """Correct the few non-move fields PKHeX can reject after generation."""
    for _ in range(4):
        valid, errors, _warnings = _legality_report(pk)
        if valid:
            return True
        changed = False
        text = tuple(str(error) for error in errors)

        if any(error.startswith("EVs:") for error in text) and not bool(pk.IsEgg):
            for stat in ("HP", "ATK", "DEF", "SPE", "SPA", "SPD"):
                setattr(pk, f"EV_{stat}", 0)
            changes.append("EVs cleared: this level and encounter cannot carry them.")
            changed = True

        if any(error.startswith("Nickname") or error.startswith("Name:") for error in text):
            try:
                default_name = str(C.SpeciesName.GetSpeciesNameGeneration(
                    int(pk.Species), int(getattr(pk, "Language", 2) or 2), 3
                ))
            except Exception:
                default_name = ""
            if default_name:
                pk.Nickname = default_name
                changes.append("Nickname reset to the species name.")
                changed = True

        if any(error.startswith("HeldItem") for error in text):
            if _int_attr(pk, "HeldItem"):
                pk.HeldItem = 0
                changes.append("Held item cleared.")
                changed = True

        if any(error.startswith("Ball") for error in text):
            fixed_ball = required_ball(option)
            target_ball = int(fixed_ball) if fixed_ball is not None else 4
            if _int_attr(pk, "Ball") != target_ball:
                pk.Ball = target_ball
                changes.append(f"Poké Ball corrected to {_ball_name(target_ball)}.")
                changed = True

        if not changed:
            return False
    return _legality_report(pk)[0]


def _change_summary(source, final, *, option: EncounterOption,
                    move_names: dict[int, str] | None) -> tuple[str, ...]:
    """Describe what a legalized record kept and what it had to change."""
    changes = []
    if int(source.Version) != int(final.Version):
        changes.append(f"Origin game corrected to {_version_name(final.Version)}.")
    if _int_attr(source, "MetLocation") != _int_attr(final, "MetLocation") or _int_attr(source, "MetLevel") != _int_attr(final, "MetLevel"):
        changes.append(f"Encounter data set to {option.label}.")
    if _int_attr(source, "Ball") != _int_attr(final, "Ball"):
        changes.append(f"Poké Ball corrected to {_ball_name(int(final.Ball))}.")
    if bool(_attr(source, "FatefulEncounter", False)) != bool(_attr(final, "FatefulEncounter", False)):
        changes.append("Fateful-encounter flag corrected.")
    if _int_attr(source, "CurrentLevel") != _int_attr(final, "CurrentLevel"):
        changes.append(
            f"Level corrected from {_int_attr(source, 'CurrentLevel')} to {_int_attr(final, 'CurrentLevel')}."
        )
    if int(source.PID) != int(final.PID):
        changes.append("PID/IV spread re-rolled by PKHeX; the old spread could not belong to a real encounter.")
    if int(source.Nature) != int(final.Nature):
        changes.append(f"Nature corrected to {C.Nature(final.Nature)}.")
    if bool(source.IsShiny) != bool(final.IsShiny):
        changes.append("Shiny state corrected.")
    if int(source.AbilityNumber) != int(final.AbilityNumber):
        changes.append("Ability slot corrected to match the legal PID.")
    if int(source.Gender) != int(final.Gender):
        changes.append("Gender corrected.")

    source_moves = tuple(_int_attr(source, f"Move{i}") for i in range(1, 5))
    final_moves = tuple(_int_attr(final, f"Move{i}") for i in range(1, 5))
    if source_moves != final_moves:
        changes.append(
            "Moves corrected: " + ", ".join(
                f"{_move_name(a, move_names)} → {_move_name(b, move_names)}"
                for a, b in zip(source_moves, final_moves) if a != b
            ) + "."
        )
    if _int_attr(source, "HeldItem") != _int_attr(final, "HeldItem"):
        changes.append("Held item cleared because this source could not carry it.")
    if _int_attr(source, "OriginalTrainerFriendship") != _int_attr(final, "OriginalTrainerFriendship"):
        changes.append("Friendship corrected.")
    same_spread = (
        int(source.PID) == int(final.PID)
        and all(
            _int_attr(source, f"IV_{stat}") == _int_attr(final, f"IV_{stat}")
            for stat in ("HP", "ATK", "DEF", "SPE", "SPA", "SPD")
        )
    )
    if same_spread:
        changes.append("Existing PID/IV spread kept.")
    if not changes:
        changes.append("Record was already legal; nothing was changed.")
    return tuple(changes)


def legalize_pk3(
    pk,
    options: list[EncounterOption],
    trainer,
    *,
    moves: tuple[int, int, int, int],
    pp_ups: tuple[int, int, int, int] = (0, 0, 0, 0),
    pp_values: tuple[int, int, int, int] = (0, 0, 0, 0),
    evs: dict[str, int] | None = None,
    held_item: int = 0,
    friendship: int = 70,
    nickname: str = "",
    move_names: dict[int, str] | None = None,
) -> LegalizeResult:
    """Make an assembled PK3 pass PKHeX's legality check.

    The method is deliberately conservative:

    1. If the record is already legal, it is returned untouched.
    2. Otherwise the selected source, then every catalog source, is tried by
       changing only met data / origin game / ball.  A record whose PID, IVs,
       moves, nature and level already fit a real encounter keeps all of them.
    3. Only when no source can explain the current spread is a fresh legal
       PID/IV record generated, with the user's moves, PP, EVs, item, nature,
       shiny state, ability, gender and level reapplied.
    4. Moves PKHeX still rejects are replaced one at a time, leaving every
       legal move and every other field intact.
    """
    if not options:
        return LegalizeResult(None, None, error="No legal encounter is available for this species.")

    current_valid, current_errors, _current_warnings = _legality_report(pk)
    if current_valid:
        return LegalizeResult(pk, None, ())

    moves = _normalise_moves(tuple(int(move) for move in moves))
    pp_ups = tuple(max(0, min(3, int(value))) for value in tuple(pp_ups)[:4])
    pp_values = tuple(max(0, int(value)) for value in tuple(pp_values)[:4])
    evs = evs or {}
    ordered = _legalize_options(pk, options, moves)

    # Least destructive: keep the existing PID/IV/move spread and correct only
    # the source metadata that PKHeX says it cannot belong to.
    for option in ordered:
        try:
            candidate = _candidate_with_metadata(pk, option)
        except Exception:
            candidate = None
        if candidate is None:
            continue
        valid, _errors, _warnings = _legality_report(candidate)
        if valid:
            summary = _change_summary(pk, candidate, option=option, move_names=move_names)
            return LegalizeResult(candidate, option, summary)

    # A fresh spread is needed (the PID/IV pair is not reachable, or the
    # requested source cannot carry the assembled moves).  Preserve every
    # choice that can still be preserved.
    last_errors: tuple[str, ...] = current_errors
    for option in ordered:
        target_level = max(
            _int_attr(pk, "CurrentLevel"), option.level_min, option.target_level_min
        )
        target_level = max(1, min(100, target_level))
        shiny = bool(pk.IsShiny)
        ability_slot = 1 if _int_attr(pk, "AbilityNumber") == 2 else 0
        gender = _int_attr(pk, "Gender")
        if gender not in (0, 1):
            gender = None

        variants = [
            (shiny, ability_slot, gender),
            (shiny, ability_slot, None),
            (shiny, None, None),
            (not shiny, ability_slot, gender),
            (not shiny, None, None),
        ]
        generated = None
        generation_error = ""
        version_trainer = make_trainer(
            str(trainer.OT).rstrip(), int(trainer.TID16), int(trainer.SID16),
            version=option.version, language=int(getattr(trainer, "Language", 2) or 2),
        )
        for variant_shiny, variant_ability, variant_gender in variants:
            generated, generation_error = generate_pk3(
                option,
                version_trainer,
                target_species=_int_attr(pk, "Species"),
                target_level=target_level,
                nature=int(pk.Nature),
                shiny=bool(variant_shiny),
                ability_slot=variant_ability,
                gender=variant_gender,
            )
            if generated is not None:
                break
        if generated is None:
            if generation_error:
                last_errors = (generation_error,)
            continue

        fallback_moves = tuple(_int_attr(generated, f"Move{i}") for i in range(1, 5))
        fixed_ball = required_ball(option)

        # Before accepting the fresh spread, see whether the existing PID/IV
        # pair fits this source and only its moves were wrong.  The generated
        # record supplies legal fallback moves for that repair, not its stats.
        try:
            salvaged = _candidate_with_metadata(pk, option)
        except Exception:
            salvaged = None
        if salvaged is not None:
            repair_notes: list[str] = []
            _apply_saved_fields(
                salvaged, pk, moves=moves, pp_ups=pp_ups, pp_values=pp_values,
                evs=evs, held_item=held_item, friendship=friendship, nickname=nickname,
            )
            if fixed_ball is None and _int_attr(pk, "Ball") in allowed_balls(option):
                salvaged.Ball = _int_attr(pk, "Ball")
            valid, errors, _warnings = _legality_report(salvaged)
            if not valid:
                last_errors = errors or last_errors
                if _repair_moves(salvaged, fallback_moves):
                    valid = True
            if not valid:
                valid = _repair_auxiliary_fields(salvaged, option, repair_notes)
            if valid:
                summary = list(_change_summary(
                    pk, salvaged, option=option, move_names=move_names
                ))
                summary.extend(repair_notes)
                return LegalizeResult(salvaged, option, tuple(summary))

        repair_notes = []
        _apply_saved_fields(
            generated, pk, moves=moves, pp_ups=pp_ups, pp_values=pp_values,
            evs=evs, held_item=held_item, friendship=friendship, nickname=nickname,
        )
        if fixed_ball is None and _int_attr(pk, "Ball") in allowed_balls(option):
            generated.Ball = _int_attr(pk, "Ball")

        valid, errors, _warnings = _legality_report(generated)
        if not valid:
            last_errors = errors or last_errors
            if _repair_moves(generated, fallback_moves):
                valid = True
        if not valid:
            valid = _repair_auxiliary_fields(generated, option, repair_notes)
        if not valid:
            continue

        summary = list(_change_summary(pk, generated, option=option, move_names=move_names))
        summary.extend(repair_notes)
        return LegalizeResult(generated, option, tuple(summary))

    detail = "; ".join(last_errors[:2]) if last_errors else "PKHeX found no reachable spread"
    return LegalizeResult(
        None, None,
        error=(
            "Could not make this configuration legal. "
            f"PKHeX still reports: {detail}"
        ),
    )


_BALL_LABELS = {
    1: "Master Ball", 2: "Ultra Ball", 3: "Great Ball", 4: "Poké Ball",
    5: "Safari Ball", 6: "Net Ball", 7: "Dive Ball", 8: "Nest Ball",
    9: "Repeat Ball", 10: "Timer Ball", 11: "Luxury Ball", 12: "Premier Ball",
}


def _ball_name(ball: int) -> str:
    return _BALL_LABELS.get(int(ball), f"Ball #{int(ball)}")


def _u16_with_bits(high2: int, low2: int, start: int = 0):
    """Yield the 16-bit values whose bits 8-9 are `high2` and bits 0-1 are `low2`.

    `start` rotates the high bits first, so successive rolls do not all begin
    with the same near-zero personality value.
    """
    for step in range(0x40):
        top = (start + step) & 0x3F
        base = (top << 10) | (high2 << 8) | low2
        for mid in range(0x40):
            yield base | (mid << 2)


def _unown_pid_candidates(form: int, nature: int, tid: int, sid: int, shiny: bool,
                          start: int = 0):
    """Yield PID values carrying the requested form, nature and shiny state.

    Generation 3 builds Unown's letter from four PID bit pairs, so the search
    can be inverted: enumerate only PIDs that already have the right form
    instead of walking the RNG stream and throwing away 27 of every 28 hits.
    """
    trainer_xor = tid ^ sid
    form = int(form) % 28
    nature = int(nature) % 25
    # A form is a value modulo 28, so each of its 8-bit encodings matches.
    for form_bits in range(form, 0x100, 28):
        hi_high = (form_bits >> 6) & 3
        hi_low = (form_bits >> 4) & 3
        lo_high = (form_bits >> 2) & 3
        lo_low = form_bits & 3
        for hi in _u16_with_bits(hi_high, hi_low, start):
            if shiny:
                # Shininess means top ^ bottom ^ (TID ^ SID) < 8, which leaves
                # the low half only eight possibilities for each high half.
                for deviation in range(8):
                    lo = hi ^ trainer_xor ^ deviation
                    if ((lo >> 8) & 3) != lo_high or (lo & 3) != lo_low:
                        continue
                    pid = (hi << 16) | lo
                    if pid % 25 == nature:
                        yield pid
            else:
                for lo in _u16_with_bits(lo_high, lo_low):
                    if (trainer_xor ^ hi ^ lo) < 8:
                        continue
                    pid = (hi << 16) | lo
                    if pid % 25 == nature:
                        yield pid


def _seed_for_pid(hi: int, lo: int) -> tuple[int, int] | None:
    """Return the LCRNG frames that produce this PID, or None if unreachable.

    Method 1 requires the PID and the IVs to come from one stream, so a built
    PID is only usable when a seed actually generates it.  Raising the low half
    by one adds the multiplier to the second frame, which keeps the sweep to one
    add and one shift per candidate.
    """
    second = (((hi << 16) * _LCRNG_MULT) + _LCRNG_ADD) & _LCRNG_MASK
    for low in range(0x10000):
        if (second >> 16) == lo:
            return ((hi << 16) | low), second
        second = (second + _LCRNG_MULT) & _LCRNG_MASK
    return None


def _unown_search(
    option: EncounterOption,
    trainer,
    target_level: int,
    nature: int,
    *,
    shiny: bool,
    max_hits: int | None = None,
) -> tuple[Any | None, str | None]:
    """Find a legal Unown spread, including the shiny case PKHeX ignores.

    PKHeX's Unown converter deliberately ignores the shiny criterion.  Gen 3
    Unown uses the half-swapped Method 1 ordering: PID = first16 << 16 | second16,
    followed by the usual two IV frames.  The PID is built from the form,
    nature and shiny constraints and then matched back to a real seed, so the
    search costs milliseconds instead of scanning millions of seeds.
    """
    try:
        template = option.encounter.ConvertToPKM(trainer, C.EncounterCriteria.Unrestricted)
    except Exception as exc:
        return None, f"Could not create the Unown template: {exc}"

    if target_level < int(template.MetLevel):
        return None, f"Unown is met at Lv {template.MetLevel}; current level cannot be lower."

    template.CurrentLevel = target_level
    template.RefreshAbility(0)
    tid = int(template.TID16)
    sid = int(template.SID16)
    form = int(option.form)
    nature = int(nature) % 25

    if max_hits is None:
        max_hits = 1 if shiny else 3

    cache_key = (form, nature, tid, sid, bool(shiny))
    cached = _UNOWN_SPREAD_CACHE.get(cache_key)
    if cached is not None:
        cached_pid, cached_iv32 = cached
        template.PID = cached_pid
        template.IV32 = cached_iv32
        template.RefreshAbility(0)
        template.ResetPartyStats()
        template.HealPP()
        if _legality(template)[0]:
            return template, None
        _UNOWN_SPREAD_CACHE.pop(cache_key, None)

    best: tuple[int, int, int] | None = None
    fallback: tuple[int, int, int] | None = None
    hits = 0
    tried = 0

    for pid in _unown_pid_candidates(form, nature, tid, sid, shiny, random.randrange(0x40)):
        tried += 1
        if tried > _UNOWN_CANDIDATE_LIMIT:
            break

        seed = _seed_for_pid(pid >> 16, pid & 0xFFFF)
        if seed is None:
            # About a third of all PIDs never appear in an LCRNG stream.
            continue
        _, second = seed
        third = (second * _LCRNG_MULT + _LCRNG_ADD) & _LCRNG_MASK
        fourth = (third * _LCRNG_MULT + _LCRNG_ADD) & _LCRNG_MASK
        iv1 = (third >> 16) & 0x7FFF
        iv2 = (fourth >> 16) & 0x7FFF
        iv32 = (
            iv1
            | ((iv2 & 31) << 15)
            | (((iv2 >> 5) & 31) << 20)
            | (((iv2 >> 10) & 31) << 25)
        )
        template.PID = pid
        template.IV32 = iv32
        template.RefreshAbility(0)
        template.ResetPartyStats()
        template.HealPP()
        valid, _messages, frame_warnings = _legality_report(template)
        if not valid:
            continue

        score = _score(template)
        if frame_warnings:
            # PKHeX can match a different seed than the one found here; keep
            # the best such spread in reserve but prefer a frame-clean one.
            if fallback is None or score > fallback[0]:
                fallback = (score, pid, iv32)
            continue

        if best is None or score > best[0]:
            best = (score, pid, iv32)
        hits += 1
        if hits >= max_hits:
            break

    if best is None:
        best = fallback
    if best is None:
        if shiny:
            return None, (
                "No legal shiny Unown spread found for this form and nature within the "
                "search budget. Try a different nature or untick Shiny."
            )
        return None, (
            "No legal Unown spread found for this form and nature within the search budget. "
            "Try a different nature."
        )

    _, pid, iv32 = best
    _UNOWN_SPREAD_CACHE[cache_key] = (pid, iv32)
    template.PID = pid
    template.IV32 = iv32
    template.RefreshAbility(0)
    template.ResetPartyStats()
    template.HealPP()
    return template, None


def generate_pk3(
    option: EncounterOption,
    trainer,
    *,
    target_species: int | None = None,
    target_level: int | None = None,
    nature: int = 0,
    shiny: bool = False,
    ability_slot: int | None = None,
    gender: int | None = None,
    best_attempts: int | None = None,
) -> tuple[Any | None, str | None]:
    """Generate a legal PK3 from a selected encounter.

    Exact IV values are intentionally not forced here.  The current records
    expose IV fields as an output of generation (and as a manual editing
    surface); forcing arbitrary exact IVs onto a correlated Gen 3 spread can
    loop forever in PKHeX's converter.  The "best spread" behavior picks the
    highest total IVs among legal candidates.
    """
    target_species = int(target_species or option.target_species)
    if int(option.species) == UNOWN_SPECIES:
        target_species = UNOWN_SPECIES
    target_level = int(target_level or option.level_min)

    problem = _validate_target(option, target_species, target_level, gender, ability_slot)
    if problem:
        return None, problem

    nature = int(nature) % 25

    if int(option.species) == UNOWN_SPECIES:
        return _unown_search(option, trainer, target_level, nature, shiny=shiny)

    criteria = C.EncounterCriteria()
    criteria.Nature = C.Nature(nature)
    criteria.Shiny = C.Shiny.Always if shiny else C.Shiny.Never
    if gender in (0, 1):
        criteria.Gender = C.Gender.Male if gender == 0 else C.Gender.Female

    if best_attempts is None:
        if option.category == "trade":
            best_attempts = 1
        elif shiny:
            best_attempts = 8
        elif int(option.target_species) != int(option.species):
            # Evolved targets can hinge on the PID itself (Wurmple's split into
            # Silcoon/Cascoon), so a handful of rolls is not always enough.
            best_attempts = 24
        else:
            best_attempts = 5

    requires_frame_match = option.category == "wild"
    best_pk = None
    best_score = -1
    fallback_pk = None
    fallback_score = -1
    last_messages: tuple[str, ...] = ()
    wanted = max(1, int(best_attempts))
    clean_hits = 0
    # PKHeX's converter draws a random seed each call, and its legality reversal
    # can land on a different seed than the converter used: roughly half of all
    # wild spreads then fail the slot's frame check.  Draw enough candidates to
    # prefer a frame-clean one, with a time budget so an unlucky nature, shiny
    # or ability combination cannot stall the UI.
    max_tries = wanted if not requires_frame_match else max(1200, wanted * 150)
    deadline = time.monotonic() + 8.0
    for _ in range(max_tries):
        if requires_frame_match and clean_hits >= wanted:
            break
        if requires_frame_match and time.monotonic() > deadline and (clean_hits or fallback_pk is not None):
            break

        try:
            pk = option.encounter.ConvertToPKM(trainer, criteria)
        except Exception as exc:
            return None, f"PKHeX could not generate this encounter: {exc}"

        if pk is not None and pk.GetType().Name != "PK3":
            # GameCube distributions convert to a CK3, which this editor
            # cannot write; refuse instead of storing a mismatched buffer.
            return None, (
                f"{option.label} is a {pk.GetType().Name} record (GameCube origin), "
                "and only GBA .pk3 records are supported."
            )

        try:
            _finalize_pk3(pk, option, target_species, target_level, ability_slot)
        except Exception as exc:
            return None, str(exc)

        valid, messages, frame_warnings = _legality_report(pk)
        last_messages = messages
        if not valid:
            continue

        if option.category == "trade":
            if shiny and not bool(pk.IsShiny):
                return None, "This in-game trade has fixed PID/IVs and cannot be shiny."
        elif bool(pk.IsShiny) != shiny:
            # PKHeX's Unown path is handled above; this guards every other
            # converter against silently returning the wrong shiny state.
            continue

        score = _score(pk)
        if requires_frame_match and frame_warnings:
            # Legal, but PKHeX's own analysis cannot line this spread up with
            # the slot's RNG frame.  Keep it only as a last resort.
            if score > fallback_score:
                fallback_score = score
                fallback_pk = pk
            continue

        if requires_frame_match:
            clean_hits += 1
        if score > best_score:
            best_score = score
            best_pk = pk

    if best_pk is None:
        best_pk = fallback_pk
    if best_pk is None:
        detail = "; ".join(last_messages) if last_messages else "no matching spread"
        return None, f"Could not make a legal record for this encounter ({detail})."

    return best_pk, None
