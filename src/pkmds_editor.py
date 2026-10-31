import json
import struct
import os
import sys
import random
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QEvent, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QMovie, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QComboBox, QCheckBox,
    QPushButton, QFileDialog, QMessageBox, QCompleter, QFrame,
    QSizePolicy, QApplication, QScrollArea, QLayout, QMenu
)

import paths

# Read-only bundle paths and the writable user-data root are separate in a
# packaged AppImage.  "BASE_DIR" remains the program root for DLLs/assets.
BASE_DIR = paths.APP_DIR
DATA_DIR = paths.DATA_DIR

import app_prefs
import sound
import theme
import user_data

# --- Fix: Force modern .NET Core instead of legacy Mono ---
runtime_config = BASE_DIR / "src" / "PKHeX.runtimeconfig.json"
if not runtime_config.exists():
    try:
        runtime_config.write_text(json.dumps({
            "runtimeOptions": {
                "tfm": "net10.0",
                "rollForward": "LatestMajor",
                "framework": {
                    "name": "Microsoft.NETCore.App",
                    "version": "10.0.0"
                }
            }
        }))
    except OSError:
        # A packaged AppImage is read-only; the file is shipped in the bundle.
        pass

os.environ["PYTHONNET_CORECLR_RUNTIME_CONFIG"] = str(runtime_config)

from pythonnet import load
load("coreclr")
import clr  # pythonnet
import System

# Load the official PKHeX Engine into Python
DLL_PATH = BASE_DIR / "src" / "PKHeX.Core.dll"
clr.AddReference(str(DLL_PATH))
from PKHeX.Core import PK3

from pkhex_encounters import (
    EncounterOption,
    allowed_balls,
    complete_level_up_moves,
    convert_egg_state,
    game_id_for_version,
    gen3_locations,
    generate_pk3,
    legalize_pk3,
    legality_from_bytes,
    list_encounters,
    make_trainer,
    method_name_for_pk,
    pk3_from_bytes,
    raw_bytes_from_pk,
    required_ball,
    version_for_game_id,
)
from sprite_paths import UNOWN_FORM_LABELS, animated_sprite_path, unown_form_from_pid
from pixel_sprite import CrispSpriteLabel, sprite_plate_extent
from summary_sprites import SummaryIconSlot
from trainer_profile import load_profile, save_profile

DB_PATH = BASE_DIR / "gen3_offline_db.json"
ENC_PATH = BASE_DIR / "assets" / "data" / "legal_encounters.json"

GEN3_DB = {int(k): v for k, v in json.loads(DB_PATH.read_text()).items()} if DB_PATH.exists() else {}

# Load the decoupled, rigorously audited legal encounters table
if ENC_PATH.exists():
    try:
        ENC_DB = json.loads(ENC_PATH.read_text())
        ENC_DB = {int(k): v for k, v in ENC_DB.items()}
    except Exception as e:
        print(f"Failed to load legal_encounters.json: {e}")
        ENC_DB = {}
else:
    ENC_DB = {}

# The strictly mapped 76 abilities that existed in Generation 3.
GEN3_ABILITIES = {
    1: "Stench", 2: "Drizzle", 3: "Speed Boost", 4: "Battle Armor", 5: "Sturdy",
    6: "Damp", 7: "Limber", 8: "Sand Veil", 9: "Static", 10: "Volt Absorb",
    11: "Water Absorb", 12: "Oblivious", 13: "Cloud Nine", 14: "Compound Eyes",
    15: "Insomnia", 16: "Color Change", 17: "Immunity", 18: "Flash Fire",
    19: "Shield Dust", 20: "Own Tempo", 21: "Suction Cups", 22: "Intimidate",
    23: "Shadow Tag", 24: "Rough Skin", 25: "Wonder Guard", 26: "Levitate",
    27: "Effect Spore", 28: "Synchronize", 29: "Clear Body", 30: "Natural Cure",
    31: "Lightning Rod", 32: "Serene Grace", 33: "Swift Swim", 34: "Chlorophyll",
    35: "Illuminate", 36: "Trace", 37: "Huge Power", 38: "Poison Point",
    39: "Inner Focus", 40: "Magma Armor", 41: "Water Veil", 42: "Magnet Pull",
    43: "Soundproof", 44: "Rain Dish", 45: "Sand Stream", 46: "Pressure",
    47: "Thick Fat", 48: "Early Bird", 49: "Flame Body", 50: "Run Away",
    51: "Keen Eye", 52: "Hyper Cutter", 53: "Pickup", 54: "Truant",
    55: "Hustle", 56: "Cute Charm", 57: "Plus", 58: "Minus", 59: "Forecast",
    60: "Sticky Hold", 61: "Shed Skin", 62: "Guts", 63: "Marvel Scale",
    64: "Liquid Ooze", 65: "Overgrow", 66: "Blaze", 67: "Torrent", 68: "Swarm",
    69: "Rock Head", 70: "Drought", 71: "Arena Trap", 72: "Vital Spirit",
    73: "White Smoke", 74: "Pure Power", 75: "Shell Armor", 76: "Air Lock"
}

FRLG_LOCS = {
    88: "Pallet Town", 89: "Viridian City", 90: "Pewter City", 91: "Cerulean City", 92: "Lavender Town",
    93: "Vermilion City", 94: "Celadon City", 95: "Fuchsia City", 96: "Cinnabar Island", 97: "Indigo Plateau",
    98: "Saffron City", 99: "Route 4 (Pokémon Center)", 100: "Route 10 (Pokémon Center)",
    101: "Route 1", 102: "Route 2", 103: "Route 3", 104: "Route 4", 105: "Route 5", 106: "Route 6",
    107: "Route 7", 108: "Route 8", 109: "Route 9", 110: "Route 10", 111: "Route 11", 112: "Route 12",
    113: "Route 13", 114: "Route 14", 115: "Route 15", 116: "Route 16", 117: "Route 17", 118: "Route 18",
    119: "Route 19", 120: "Route 20", 121: "Route 21", 122: "Route 22", 123: "Route 23", 124: "Route 24",
    125: "Route 25", 126: "Viridian Forest", 127: "Mt. Moon", 128: "S.S. Anne", 129: "Underground Path (5-6)",
    130: "Underground Path (7-8)", 131: "Diglett's Cave", 132: "Victory Road", 133: "Rocket Hideout",
    134: "Silph Co.", 135: "Pokémon Mansion", 136: "Safari Zone", 137: "Pokémon League", 138: "Rock Tunnel",
    139: "Seafoam Islands", 140: "Pokémon Tower", 141: "Cerulean Cave", 142: "Power Plant", 143: "One Island",
    144: "Two Island", 145: "Three Island", 146: "Four Island / Day Care", 147: "Five Island", 148: "Seven Island",
    149: "Six Island", 150: "Kindle Road", 151: "Treasure Beach", 152: "Cape Brink", 153: "Bond Bridge",
    154: "Three Isle Port", 159: "Resort Gorgeous", 160: "Water Labyrinth", 161: "Five Isle Meadow",
    162: "Memorial Pillar", 163: "Outcast Island", 164: "Green Path", 165: "Water Path", 166: "Ruin Valley",
    167: "Trainer Tower (Exterior)", 168: "Canyon Entrance", 169: "Sevault Canyon", 170: "Tanoby Ruins",
    174: "Navel Rock", 175: "Mt. Ember", 176: "Berry Forest", 177: "Icefall Cave", 178: "Rocket Warehouse",
    179: "Trainer Tower", 180: "Dotted Hole", 181: "Lost Cave", 182: "Pattern Bush", 183: "Altering Cave",
    184: "Tanoby Chambers", 185: "Three Isle Path", 186: "Tanoby Key", 187: "Birth Island",
    253: "In-Game Trade", 254: "Met in a Distant Land", 255: "Fateful Encounter (Event)"
}

# Hoenn locations are not curated here: the Gen 3 id space is shared with
# Kanto/Sevii, so the full table (with the correct RSE names) comes from
# PKHeX through pkhex_encounters.gen3_locations().
DAY_CARE_LOCS = {1: 32, 2: 32, 3: 32, 4: 146, 5: 146}  # RSE Route 117 / FRLG Four Island

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed",
    "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest",
    "Mild", "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"
]

STAT_MOD_NAMES = ["Atk", "Def", "Spe", "SpA", "SpD"]

# --- TYPE COLORS FOR AUTHENTIC UI ---
TYPE_COLORS = {
    "NORMAL": "#A8A878", "FIRE": "#F08030", "WATER": "#6890F0", "ELECTRIC": "#F8D030",
    "GRASS": "#78C850", "ICE": "#98D8D8", "FIGHTING": "#C03028", "POISON": "#A040A0",
    "GROUND": "#E0C068", "FLYING": "#A890F0", "PSYCHIC": "#F85888", "BUG": "#A8B820",
    "ROCK": "#B8A038", "GHOST": "#705898", "DRAGON": "#7038F8", "DARK": "#705848",
    "STEEL": "#B8B8D0", "NONE": "#888888"
}


def _readable_type_ink(color: str) -> str:
    """Choose dark text on pale type badges, white on saturated ones."""
    c = QColor(color)
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return "#1f2328" if lum > 145 else "#ffffff"

# Gen 3 Move Types Array (100% Accurate for all 354 moves without JSON dependency)
_MOVE_TYPES_LIST = [
    "NONE", # 0
    "NORMAL", "FIGHTING", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "FIRE", "ICE", "ELECTRIC", "NORMAL", # 1-10
    "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "FLYING", "FLYING", "NORMAL", "FLYING", "NORMAL", # 11-20
    "NORMAL", "GRASS", "NORMAL", "FIGHTING", "NORMAL", "FIGHTING", "FIGHTING", "GROUND", "NORMAL", "NORMAL", # 21-30
    "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "POISON", # 31-40
    "BUG", "BUG", "NORMAL", "DARK", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", # 41-50
    "POISON", "FIRE", "FIRE", "ICE", "WATER", "WATER", "WATER", "ICE", "ICE", "PSYCHIC", # 51-60
    "WATER", "ICE", "NORMAL", "FLYING", "FLYING", "FIGHTING", "FIGHTING", "FIGHTING", "FIGHTING", "NORMAL", # 61-70
    "GRASS", "GRASS", "GRASS", "NORMAL", "GRASS", "GRASS", "POISON", "GRASS", "GRASS", "GRASS", # 71-80
    "BUG", "DRAGON", "FIRE", "ELECTRIC", "ELECTRIC", "ELECTRIC", "ELECTRIC", "ROCK", "GROUND", "GROUND", # 81-90
    "GROUND", "POISON", "PSYCHIC", "PSYCHIC", "PSYCHIC", "PSYCHIC", "PSYCHIC", "NORMAL", "NORMAL", "PSYCHIC", # 91-100
    "GHOST", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "GHOST", "WATER", # 101-110
    "NORMAL", "PSYCHIC", "PSYCHIC", "ICE", "PSYCHIC", "NORMAL", "NORMAL", "NORMAL", "FLYING", "NORMAL", # 111-120
    "NORMAL", "GHOST", "POISON", "POISON", "GROUND", "FIRE", "WATER", "WATER", "NORMAL", "NORMAL", # 121-130
    "NORMAL", "NORMAL", "PSYCHIC", "PSYCHIC", "NORMAL", "FIGHTING", "NORMAL", "PSYCHIC", "POISON", "NORMAL", # 131-140
    "BUG", "NORMAL", "FLYING", "NORMAL", "WATER", "NORMAL", "GRASS", "NORMAL", "PSYCHIC", "NORMAL", # 141-150
    "POISON", "WATER", "NORMAL", "NORMAL", "GROUND", "PSYCHIC", "ROCK", "NORMAL", "NORMAL", "NORMAL", # 151-160
    "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "FIGHTING", "DARK", "BUG", "NORMAL", # 161-170
    "GHOST", "FIRE", "NORMAL", "NONE", "NORMAL", "NORMAL", "FLYING", "GRASS", "FIGHTING", "GHOST", # 171-180
    "ICE", "NORMAL", "FIGHTING", "NORMAL", "DARK", "NORMAL", "NORMAL", "POISON", "GROUND", "WATER", # 181-190
    "GROUND", "ELECTRIC", "NORMAL", "GHOST", "NORMAL", "ICE", "FIGHTING", "GROUND", "NORMAL", "DRAGON", # 191-200
    "ROCK", "GRASS", "NORMAL", "NORMAL", "ROCK", "NORMAL", "NORMAL", "NORMAL", "ELECTRIC", "BUG", # 201-210
    "STEEL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", # 211-220
    "FIRE", "GROUND", "FIGHTING", "BUG", "DRAGON", "NORMAL", "NORMAL", "DARK", "NORMAL", "NORMAL", # 221-230
    "STEEL", "STEEL", "FIGHTING", "NORMAL", "GRASS", "NORMAL", "NORMAL", "FIGHTING", "DRAGON", "WATER", # 231-240
    "FIRE", "DARK", "PSYCHIC", "NORMAL", "NORMAL", "ROCK", "GHOST", "PSYCHIC", "FIGHTING", "WATER", # 241-250
    "DARK", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "FIRE", "ICE", "DARK", "DARK", # 251-260
    "FIRE", "DARK", "NORMAL", "FIGHTING", "NORMAL", "NORMAL", "NORMAL", "ELECTRIC", "DARK", "NORMAL", # 261-270
    "PSYCHIC", "PSYCHIC", "NORMAL", "NORMAL", "GRASS", "FIGHTING", "PSYCHIC", "NORMAL", "FIGHTING", "FIGHTING", # 271-280
    "NORMAL", "DARK", "NORMAL", "FIRE", "PSYCHIC", "PSYCHIC", "NORMAL", "GHOST", "DARK", "NORMAL", # 281-290
    "WATER", "FIGHTING", "NORMAL", "BUG", "PSYCHIC", "PSYCHIC", "FLYING", "NORMAL", "FIRE", "GROUND", # 291-300
    "ICE", "GRASS", "NORMAL", "NORMAL", "POISON", "NORMAL", "FIRE", "WATER", "STEEL", "GHOST", # 301-310
    "NORMAL", "GRASS", "DARK", "FLYING", "FIRE", "NORMAL", "ROCK", "BUG", "STEEL", "GRASS", # 311-320
    "NORMAL", "PSYCHIC", "WATER", "BUG", "GHOST", "PSYCHIC", "FIGHTING", "GROUND", "ICE", "WATER", # 321-330
    "GRASS", "FLYING", "ICE", "STEEL", "NORMAL", "NORMAL", "DRAGON", "GRASS", "FIGHTING", "FLYING", # 331-340
    "GROUND", "POISON", "NORMAL", "ELECTRIC", "GRASS", "WATER", "PSYCHIC", "GRASS", "DRAGON", "ROCK", # 341-350
    "ELECTRIC", "WATER", "STEEL", "PSYCHIC" # 351-354
]

def nature_display_label(nat_idx: int) -> str:
    name = NATURES[nat_idx]
    inc = nat_idx // 5
    dec = nat_idx % 5
    if inc == dec:
        return f"{name} (Neutral)"
    return f"{name} (+{STAT_MOD_NAMES[inc]}, -{STAT_MOD_NAMES[dec]})"

GEN3_MOVE_BASE_PP = (
    0,
    35, 25, 10, 15, 20, 20, 15, 15, 15, 35, 30, 5, 10, 30, 30, 35, 35, 20, 15, 20,
    20, 10, 20, 30, 5, 25, 15, 15, 15, 25, 20, 5, 35, 15, 20, 20, 20, 15, 30, 35,
    20, 20, 30, 25, 40, 20, 15, 20, 20, 20, 30, 25, 15, 30, 25, 5, 15, 10, 5, 20,
    20, 20, 5, 35, 20, 25, 20, 20, 20, 15, 20, 10, 10, 40, 25, 10, 35, 30, 15, 20,
    40, 10, 15, 30, 15, 20, 10, 15, 10, 5, 10, 10, 25, 10, 20, 40, 30, 30, 20, 20,
    15, 10, 40, 15, 20, 30, 20, 20, 10, 40, 40, 30, 30, 30, 20, 30, 10, 10, 20, 5,
    10, 30, 20, 20, 20, 5, 15, 10, 20, 15, 15, 35, 20, 15, 10, 20, 30, 15, 40, 20,
    15, 10, 5, 10, 30, 10, 15, 20, 15, 40, 40, 10, 5, 15, 10, 10, 10, 15, 30, 30,
    10, 10, 20, 10, 1, 1, 10, 10, 10, 5, 15, 25, 15, 10, 15, 30, 5, 40, 15, 10,
    25, 10, 30, 10, 20, 10, 10, 10, 10, 10, 20, 5, 40, 5, 5, 15, 5, 10, 5, 15,
    10, 5, 10, 20, 20, 40, 15, 10, 20, 20, 25, 5, 15, 10, 5, 20, 15, 20, 25, 20,
    5, 30, 5, 10, 20, 40, 5, 20, 40, 20, 15, 35, 10, 5, 5, 5, 15, 5, 20, 5,
    5, 15, 20, 10, 5, 5, 15, 15, 15, 15, 10, 10, 10, 10, 10, 10, 10, 10, 15, 15,
    15, 10, 20, 20, 10, 20, 20, 20, 20, 20, 10, 10, 10, 20, 20, 5, 15, 10, 10, 15,
    10, 20, 5, 5, 10, 10, 20, 5, 10, 20, 10, 20, 20, 20, 5, 5, 15, 20, 10, 15,
    20, 15, 10, 10, 15, 10, 5, 5, 10, 15, 10, 5, 20, 25, 5, 40, 10, 5, 40, 15,
    20, 20, 5, 15, 20, 30, 15, 15, 5, 10, 30, 20, 30, 15, 5, 40, 15, 5, 20, 5,
    15, 25, 40, 15, 20, 15, 20, 15, 20, 10, 20, 20, 5, 5
)

def calc_max_pp(move_id: int, pp_ups: int) -> int:
    if move_id <= 0 or move_id >= len(GEN3_MOVE_BASE_PP):
        return 0
    base = GEN3_MOVE_BASE_PP[move_id]
    if base == 1:
        return 1
    return base + (base * max(0, min(3, pp_ups))) // 5

# PKHeX's Gen 3 ability check wants the stored ability flag to equal PID bit 0
# for every species with two different abilities, and to stay clear for
# single-ability species.  Granbull, Vibrava and Flygon are the exception it
# carves out: their two slots hold the same ability, but the games still store
# the flag from the PID, so PKHeX follows the PID for them too.
PID_SOURCED_ABILITY_SPECIES = (210, 329, 330)

SUBSTRUCT_ORDER = [
    (0,1,2,3), (0,1,3,2), (0,2,1,3), (0,3,1,2), (0,2,3,1), (0,3,2,1),
    (1,0,2,3), (1,0,3,2), (2,0,1,3), (3,0,1,2), (2,0,3,1), (3,0,2,1),
    (1,2,0,3), (1,3,0,2), (2,1,0,3), (3,1,0,2), (2,3,0,1), (3,2,0,1),
    (1,2,3,0), (1,3,2,0), (2,1,3,0), (3,1,2,0), (2,3,1,0), (3,2,1,0)
]

HOENN_INTERNAL_TO_NAT = {
    277:252, 278:253, 279:254, 280:255, 281:256, 282:257, 283:258, 284:259, 285:260,
    286:261, 287:262, 288:263, 289:264, 290:265, 291:266, 292:267, 293:268, 294:269,
    295:270, 296:271, 297:272, 298:273, 299:274, 300:275, 301:290, 302:291, 303:292,
    304:276, 305:277, 306:285, 307:286, 308:327, 309:278, 310:279, 311:283, 312:284,
    313:320, 314:321, 315:300, 316:301, 317:352, 318:343, 319:344, 320:299, 321:324,
    322:302, 323:339, 324:340, 325:370, 326:341, 327:342, 328:349, 329:350, 330:318,
    331:319, 332:328, 333:329, 334:330, 335:296, 336:297, 337:309, 338:310, 339:322,
    340:323, 341:363, 342:364, 343:365, 344:331, 345:332, 346:361, 347:362, 348:337,
    349:338, 350:298, 351:325, 352:326, 353:311, 354:312, 355:303, 356:307, 357:308,
    358:333, 359:334, 360:360, 361:355, 362:356, 363:315, 364:287, 365:288, 366:289,
    367:316, 368:317, 369:357, 370:293, 371:294, 372:295, 373:366, 374:367, 375:368,
    376:359, 377:353, 378:354, 379:336, 380:335, 381:369, 382:304, 383:305, 384:306,
    385:351, 386:313, 387:314, 388:345, 389:346, 390:347, 391:348, 392:280, 393:281,
    394:282, 395:371, 396:372, 397:373, 398:374, 399:375, 400:376, 401:377, 402:378,
    403:379, 404:382, 405:383, 406:384, 407:380, 408:381, 409:385, 410:386, 411:358
}
NAT_TO_HOENN_INTERNAL = {v: k for k, v in HOENN_INTERNAL_TO_NAT.items()}

def nat_to_internal(nat_dex: int) -> int:
    return nat_dex if 1 <= nat_dex <= 251 else NAT_TO_HOENN_INTERNAL.get(nat_dex, nat_dex)

def internal_to_nat(internal_id: int) -> int:
    return internal_id if 1 <= internal_id <= 251 else HOENN_INTERNAL_TO_NAT.get(internal_id, 1)

BALLS = {
    1: "Master Ball", 2: "Ultra Ball", 3: "Great Ball", 4: "Poké Ball",
    5: "Safari Ball", 6: "Net Ball", 7: "Dive Ball", 8: "Nest Ball",
    9: "Repeat Ball", 10: "Timer Ball", 11: "Luxury Ball", 12: "Premier Ball"
}

GAMES = {
    1: "Sapphire", 2: "Ruby", 3: "Emerald",
    4: "FireRed", 5: "LeafGreen", 15: "Colosseum/XD"
}

GROWTH_RATES = [
    "Medium Fast",           # 0
    "Erratic",               # 1
    "Fluctuating",           # 2
    "Medium Slow (Starters)",# 3
    "Fast",                  # 4
    "Slow"                   # 5
]

# Translation mapping to correctly align PKHeX true internal curve ID to the GUI Dropdown Index above
PK_TO_UI_GROWTH = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

def calc_exp_for_level(level: int, rate_idx: int) -> int:
    n = max(1, min(100, level))
    if n == 1: return 0
    if rate_idx == 0:   # Medium Fast
        return n ** 3
    elif rate_idx == 1: # Erratic
        if n <= 50: return ((n ** 3) * (100 - n)) // 50
        elif n <= 68: return ((n ** 3) * (150 - n)) // 100
        elif n <= 98: return ((n ** 3) * ((1911 - 10 * n) // 3)) // 500
        else: return ((n ** 3) * (160 - n)) // 100
    elif rate_idx == 2: # Fluctuating
        if n <= 15: return (n ** 3) * (((n + 1) // 3) + 24) // 50
        elif n <= 36: return (n ** 3) * (n + 14) // 50
        else: return (n ** 3) * ((n // 2) + 32) // 50
    elif rate_idx == 3: # Medium Slow
        return max(0, int((6 * (n ** 3)) // 5 - 15 * (n ** 2) + 100 * n - 140))
    elif rate_idx == 4: # Fast
        return (4 * (n ** 3)) // 5
    elif rate_idx == 5: # Slow
        return (5 * (n ** 3)) // 4
    return 0

def infer_level_and_rate(exp: int) -> tuple[int, int]:
    if exp <= 0: return 1, 3
    for r_idx in range(len(GROWTH_RATES)):
        for lvl in range(1, 101):
            if calc_exp_for_level(lvl, r_idx) == exp:
                return lvl, r_idx
    best_lvl = 1
    for lvl in range(1, 101):
        if calc_exp_for_level(lvl, 3) <= exp:
            best_lvl = lvl
    return best_lvl, 3

def load_gen3_species() -> dict[int, str]:
    path = BASE_DIR / "assets" / "data" / "species.json"
    if path.exists():
        try: return {int(k): v for k, v in json.loads(path.read_text()).items()}
        except Exception: pass
    return {i: f"Pokemon #{i}" for i in range(1, 387)}

def load_gen3_moves() -> dict[int, str]:
    path = BASE_DIR / "assets" / "data" / "moves.json"
    if path.exists():
        try:
            full_data = json.loads(path.read_text())
            # Handle if the json values are dicts (e.g. {"name": "Pound", "type": "Normal"}) or just strings
            res = {0: "— None —"}
            for k, v in full_data.items():
                if isinstance(v, dict) and "name" in v:
                    res[int(k)] = v["name"]
                elif isinstance(v, str):
                    res[int(k)] = v
            return res
        except Exception: pass
    moves = {0: "— None —"}
    for idx in range(1, 355): moves[idx] = f"Move #{idx}"
    return moves

def calc_gen3_party_stats(nat_dex: int, level: int, pid: int, ivs: dict, evs: dict) -> tuple[int, int, int, int, int, int]:
    temp_pk = PK3()
    temp_pk.Species = nat_dex
    pi = temp_pk.PersonalInfo

    if nat_dex == 292: max_hp = 1
    else: max_hp = ((2 * pi.HP + ivs["HP"] + (evs["HP"] // 4)) * level) // 100 + level + 10

    nat_idx = pid % 25
    inc_stat = nat_idx // 5
    dec_stat = nat_idx % 5

    stat_order = [("Atk", pi.ATK, 0), ("Def", pi.DEF, 1), ("Spe", pi.SPE, 2), ("SpA", pi.SPA, 3), ("SpD", pi.SPD, 4)]
    out_stats = []
    for key, base_val, n_pos in stat_order:
        val = ((2 * base_val + ivs[key] + (evs[key] // 4)) * level) // 100 + 5
        if inc_stat != dec_stat:
            if n_pos == inc_stat: val = (val * 110) // 100
            elif n_pos == dec_stat: val = (val * 90) // 100
        out_stats.append(max(1, val))
    return (max_hp, out_stats[0], out_stats[1], out_stats[2], out_stats[3], out_stats[4])

def load_gen3_items() -> dict[int, str]:
    base = {
        0: "None", 1: "Master Ball", 2: "Ultra Ball", 3: "Great Ball", 4: "Poké Ball",
        5: "Safari Ball", 6: "Net Ball", 7: "Dive Ball", 8: "Nest Ball",
        9: "Repeat Ball", 10: "Timer Ball", 11: "Luxury Ball", 12: "Premier Ball",
        19: "Full Restore", 20: "Max Potion", 25: "Max Revive", 37: "Max Elixir",
        44: "Berry Juice", 45: "Sacred Ash", 63: "HP Up", 64: "Protein", 65: "Iron",
        66: "Carbos", 67: "Calcium", 68: "Rare Candy", 69: "PP Up", 70: "Zinc", 71: "PP Max",
        93: "Sun Stone", 94: "Moon Stone", 95: "Fire Stone", 96: "Thunderstone",
        97: "Water Stone", 98: "Leaf Stone", 110: "Nugget", 111: "Heart Scale",
        133: "Cheri Berry", 134: "Chesto Berry", 135: "Pecha Berry", 136: "Rawst Berry",
        138: "Leppa Berry", 139: "Oran Berry", 141: "Lum Berry", 142: "Sitrus Berry",
        168: "Liechi Berry", 169: "Ganlon Berry", 170: "Salac Berry", 171: "Petaya Berry",
        179: "BrightPowder", 180: "White Herb", 181: "Macho Brace", 182: "Exp. Share",
        183: "Quick Claw", 184: "Soothe Bell", 185: "Mental Herb", 186: "Choice Band",
        187: "King's Rock", 188: "SilverPowder", 189: "Amulet Coin", 191: "Soul Dew",
        192: "DeepSeaTooth", 193: "DeepSeaScale", 194: "Smoke Ball", 195: "Everstone",
        196: "Focus Band", 197: "Lucky Egg", 198: "Scope Lens", 199: "Metal Coat",
        200: "Leftovers", 201: "Dragon Scale", 202: "Light Ball", 203: "Soft Sand",
        204: "Hard Stone", 205: "Miracle Seed", 206: "BlackGlasses", 207: "Black Belt",
        208: "Magnet", 209: "Mystic Water", 210: "Sharp Beak", 211: "Poison Barb",
        212: "NeverMeltIce", 213: "Spell Tag", 214: "TwistedSpoon", 215: "Charcoal",
        216: "Dragon Fang", 217: "Silk Scarf", 218: "Up-Grade", 219: "Shell Bell",
        224: "Thick Club", 225: "Stick"
    }
    for i in range(1, 51): base[288 + i] = f"TM{i:02d}"
    return base

# Western (English/French/German/Italian/Spanish) Gen 3 text table.
# Keep this in sync with PKHeX's StringConverter3.G3_EN; the apostrophe at
# 0xB4 matters for fixed in-game-trade nicknames like CH'DING.
_GEN3_EN_SPECIAL = {
    0x00: " ", 0x01: "À", 0x02: "Á", 0x03: "Â", 0x04: "Ç", 0x05: "È",
    0x06: "É", 0x07: "Ê", 0x08: "Ë", 0x09: "Ì", 0x0B: "Î", 0x0C: "Ï",
    0x0D: "Ò", 0x0E: "Ó", 0x0F: "Ô", 0x10: "Œ", 0x11: "Ù", 0x12: "Ú",
    0x13: "Û", 0x14: "Ñ", 0x15: "ß", 0x16: "à", 0x17: "á", 0x19: "ç",
    0x1A: "è", 0x1B: "é", 0x1C: "ê", 0x1D: "ë", 0x1E: "ì", 0x20: "î",
    0x21: "ï", 0x22: "ò", 0x23: "ó", 0x24: "ô", 0x25: "œ", 0x26: "ù",
    0x27: "ú", 0x28: "û", 0x29: "ñ", 0x2A: "º", 0x2B: "ª", 0x2D: "&",
    0x2E: "+", 0x35: "=", 0x36: ";", 0x51: "¿", 0x52: "¡", 0x5A: "Í",
    0x5B: "%", 0x5C: "(", 0x5D: ")", 0x68: "â", 0x6F: "í", 0x79: "↑",
    0x7A: "↓", 0x7B: "←", 0x7C: "＋", 0xAF: "·", 0xB1: "“", 0xB2: "”",
    0xB3: "‘", 0xB4: "'", 0xB5: "♂", 0xB6: "♀", 0xB7: "$", 0xB8: ",",
    0xBA: "/", 0xEF: "►", 0xF0: ":", 0xF1: "Ä", 0xF2: "Ö", 0xF3: "Ü",
    0xF4: "ä", 0xF5: "ö", 0xF6: "ü",
}
GEN3_EN_TABLE: list[str | None] = [None] * 256
for _code, _char in _GEN3_EN_SPECIAL.items():
    GEN3_EN_TABLE[_code] = _char
for _i in range(10):
    GEN3_EN_TABLE[0xA1 + _i] = chr(ord('0') + _i)
for _i in range(26):
    GEN3_EN_TABLE[0xBB + _i] = chr(ord('A') + _i)
for _i in range(26):
    GEN3_EN_TABLE[0xD5 + _i] = chr(ord('a') + _i)
GEN3_EN_REVERSE = {ch: code for code, ch in enumerate(GEN3_EN_TABLE) if ch is not None}


def decode_gen3_str(raw: bytes) -> str:
    out = []
    for b in raw:
        if b == 0xFF:
            break
        ch = GEN3_EN_TABLE[b] if 0 <= b < 256 else None
        if ch is not None:
            out.append(ch)
    return "".join(out).strip() or "PKMN"


def encode_gen3_str(text: str, max_len: int) -> bytes:
    res = bytearray(b"\xFF" * max_len)
    for i, ch in enumerate(text[:max_len]):
        # Accept the typographic apostrophe as well as ASCII; both map to 0xB4.
        if ch == "’":
            ch = "'"
        res[i] = GEN3_EN_REVERSE.get(ch, 0x00)
    return bytes(res)


def encode_or_preserve_gen3_str(text: str, max_len: int, generated_text: str,
                                generated_bytes: bytes | None) -> bytes:
    """Encode field text, or reuse the record's own bytes when it is untouched.

    Fixed encounters can carry text the Western table cannot express - the
    Japanese OT of a Gen 3 event distribution, for example.  Re-encoding that
    to blanks makes PKHeX reject the record, so an unedited field keeps the
    bytes the generated record already had.
    """
    if generated_bytes is not None and generated_text and text == generated_text:
        return bytes(generated_bytes)[:max_len]
    return encode_gen3_str(text, max_len)


class ElidedLabel(QLabel):
    """A one-line label that shortens its text instead of widening its parent.

    The summary title is the longest fixed label in the editor.  A long
    nickname plus the shiny star used to paint past the summary card and
    nudge the window wider, so the star is now a separate fixed width label
    and this one elides its share of the row.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__("", parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(False)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self._refresh_elide()

    def full_text(self) -> str:
        return self._full_text

    def _refresh_elide(self) -> None:
        width = max(0, self.contentsRect().width())
        shown = (
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, width)
            if width and self._full_text else self._full_text
        )
        if shown != super().text():
            super().setText(shown)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_elide()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._refresh_elide()


class PKMDSEditorTab(QWidget):
    send_to_slot2 = pyqtSignal(str)
    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir

        self.last_dir = str(app_prefs.get("last_dir", self.base_dir))

        self.species_map = load_gen3_species()
        self.moves_map = load_gen3_moves()
        self.items_map = load_gen3_items()

        self.current_path = None
        self.raw_data = None
        self.was_encrypted = True
        self.was_shuffled = True
        self._syncing = False
        self._bounce_step = False
        self._last_generated_method = ""
        self._last_generated_label = ""
        self.encounter_options: list[EncounterOption] = []

        self._build_ui()

        # Locked "My Trainer" profile, learned from a Pokémon received by
        # trade and stored next to the app.  It is the identity new records
        # are generated with; loading someone else's Pokémon never touches it.
        self._my_trainer = load_profile(self.base_dir)
        if self._my_trainer:
            self._apply_profile_to_fields(self._my_trainer)

        # The trainer of the document currently open in the editor.  Event
        # distributions and in-game trades carry their own fixed OT/ID; those
        # fill the fields temporarily but never replace this identity.
        self._trainer_identity = self._current_trainer_identity()
        self._identity_from_fixed_source = False
        self._refresh_my_trainer_row()

        self._legality_timer = QTimer(self)
        self._legality_timer.setSingleShot(True)
        self._legality_timer.timeout.connect(self._refresh_legality_status)

        self._refresh_species_abilities(1)

        # Build the encounter picker straight away: it comes from PKHeX, so it
        # must be usable before a species change or a file load happens.
        self._refresh_encounter_catalog(select_first=False)

        # Force initial render of move colors
        for i in range(4):
            self._on_move_or_ppup_changed(i)

        self.refresh_live_preview()

    def _init_blank_buffer_if_needed(self):
        pass

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._editor_scroll = QScrollArea()
        scroll = self._editor_scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        body = QWidget()
        self._editor_body = body
        body.setObjectName("EditorBody")
        # 1440p and 4K windows should use their width.  The body is centred
        # once it reaches a sane 3200 px working measure so ultra-wide setups
        # do not turn every field into a full-screen strip.
        body.setMaximumWidth(3200)
        main = QVBoxLayout(body)
        self._editor_main = main
        main.setContentsMargins(10, 0, 10, 0)
        main.setSpacing(1)
        main.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)

        top = QHBoxLayout()
        loaded_lbl = QLabel("Loaded .pk3:")
        loaded_lbl.setMinimumWidth(92)
        top.addWidget(loaded_lbl)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Open an existing .pk3 OR pick a Species below to generate from scratch...")
        top.addWidget(self.path_edit)
        self.btn_open = QPushButton("OPEN .PK3")
        self.btn_open.setStyleSheet("padding: 1px 7px; min-height: 18px;")
        self.btn_open.clicked.connect(self.browse_pk3)
        top.addWidget(self.btn_open)
        self.btn_recent = QPushButton("RECENT")
        self.btn_recent.setStyleSheet("padding: 1px 7px; min-height: 18px;")
        self.btn_recent.setToolTip("Open a recently used .pk3")
        self.btn_recent.clicked.connect(self.show_recent_menu)
        top.addWidget(self.btn_recent)
        main.addLayout(top)

        # ==========================================
        # AUTHENTIC SUMMARY SCREEN - compact side panel
        # ==========================================
        self.preview_frame = QFrame()
        self.preview_frame.setMinimumWidth(248)
        self.preview_frame.setMaximumWidth(360)
        self.preview_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.preview_frame.setObjectName("EditorSummary")
        prev_layout = QVBoxLayout(self.preview_frame)
        prev_layout.setContentsMargins(9, 8, 9, 9)
        prev_layout.setSpacing(5)

        self.summary_plate = QLabel("POKéMON SUMMARY")
        self.summary_plate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_plate.setFixedHeight(30)
        prev_layout.addWidget(self.summary_plate)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(2)
        self.summary_title_lbl = ElidedLabel("Lv. 5   BULBASAUR")
        self.summary_title_lbl.setMinimumHeight(32)
        self.summary_title_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        title_row.addWidget(self.summary_title_lbl, 1)

        self.summary_gender_lbl = QLabel("")
        self.summary_gender_lbl.setFixedWidth(16)
        self.summary_gender_lbl.setMinimumHeight(32)
        self.summary_gender_lbl.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.summary_gender_lbl.setVisible(False)
        title_row.addWidget(self.summary_gender_lbl, 0)

        self.summary_star_lbl = QLabel("")
        self.summary_star_lbl.setFixedWidth(16)
        self.summary_star_lbl.setMinimumHeight(32)
        self.summary_star_lbl.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.summary_star_lbl.setToolTip("Shiny")
        self.summary_star_lbl.setVisible(False)
        title_row.addWidget(self.summary_star_lbl, 0)
        prev_layout.addLayout(title_row)

        self.summary_rule = QFrame()
        self.summary_rule.setFixedHeight(3)
        prev_layout.addWidget(self.summary_rule)

        self.sprite_lbl = CrispSpriteLabel("Sprite")
        sprite_extent = sprite_plate_extent(104)
        self.sprite_lbl.set_plate_base(sprite_extent)
        self.sprite_lbl.setFixedSize(sprite_extent, sprite_extent)
        self.sprite_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_lbl.set_clickable(True)
        self.sprite_lbl.setToolTip("Click to hear this Pokémon's cry")
        self.sprite_lbl.clicked.connect(self._play_current_cry)
        self._cry_nat_dex = 0
        self.summary_ball_badge = SummaryIconSlot(self)
        self.summary_item_badge = SummaryIconSlot(self, base=22, reserve=True)

        # The ball and the smaller held-item badge share the portrait row.
        # They therefore cannot add a row or push the memo and stats down.
        sprite_row = QHBoxLayout()
        sprite_row.setSpacing(3)
        sprite_row.addStretch()
        sprite_row.addWidget(self.sprite_lbl)
        sprite_row.addWidget(
            self.summary_ball_badge, 0, Qt.AlignmentFlag.AlignBottom
        )
        sprite_row.addWidget(
            self.summary_item_badge, 0, Qt.AlignmentFlag.AlignBottom
        )
        sprite_row.addStretch()
        prev_layout.addLayout(sprite_row)

        self.memo_frame = QFrame()
        self.memo_frame.setObjectName("EditorTrainerMemo")
        memo_layout = QHBoxLayout(self.memo_frame)
        memo_layout.setContentsMargins(0, 0, 0, 0)
        memo_layout.setSpacing(6)
        self.trainer_memo_lbl = QLabel("Naughty nature.\nMet in Route 1 at Lv 5.\nHates to lose.")
        self.trainer_memo_lbl.setMinimumHeight(76)
        self.trainer_memo_lbl.setWordWrap(True)
        self.trainer_memo_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        memo_layout.addWidget(self.trainer_memo_lbl, 1)
        prev_layout.addWidget(self.memo_frame)

        # Classic stats box, sized to the narrow summary column.
        self.stats_box = QFrame()
        stats_grid = QGridLayout(self.stats_box)
        stats_grid.setContentsMargins(6, 5, 6, 5)
        stats_grid.setHorizontalSpacing(7)
        stats_grid.setVerticalSpacing(2)
        stats_grid.setColumnStretch(0, 1)

        self.stat_readout_lbls = {}
        self.stat_name_lbls = []
        row = 0
        for st_key in ["HP", "ATTACK", "DEFENSE", "SP. ATK", "SP. DEF", "SPEED"]:
            name_lbl = QLabel(st_key)
            name_lbl.setMinimumWidth(82)
            name_lbl.setMinimumHeight(24)
            name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.stat_name_lbls.append(name_lbl)
            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setMinimumWidth(52)

            stats_grid.addWidget(name_lbl, row, 0)
            stats_grid.addWidget(val_lbl, row, 1)
            internal_k = "SpA" if st_key == "SP. ATK" else "SpD" if st_key == "SP. DEF" else "Spe" if st_key == "SPEED" else "Atk" if st_key == "ATTACK" else "Def" if st_key == "DEFENSE" else "HP"
            self.stat_readout_lbls[internal_k] = val_lbl
            row += 1
        prev_layout.addWidget(self.stats_box)

        self.exp_box = QFrame()
        exp_grid = QGridLayout(self.exp_box)
        exp_grid.setContentsMargins(7, 3, 7, 3)
        exp_grid.setVerticalSpacing(2)

        self.exp_lbl = QLabel("EXP. POINTS")
        self.exp_val_lbl = QLabel("135")
        self.exp_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.next_lbl = QLabel("NEXT LV.")
        self.next_val_lbl = QLabel("0")
        self.next_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        exp_grid.addWidget(self.exp_lbl, 0, 0)
        exp_grid.addWidget(self.exp_val_lbl, 0, 1)
        exp_grid.addWidget(self.next_lbl, 1, 0)
        exp_grid.addWidget(self.next_val_lbl, 1, 1)
        prev_layout.addWidget(self.exp_box)
        prev_layout.addStretch()

        self.bounce_timer = QTimer(self)
        self.bounce_timer.timeout.connect(self._tick_bounce)
        self.bounce_timer.start(240)

        # ==========================================
        # EDITING CONTROLS
        # ==========================================
        right_column = QVBoxLayout()
        right_column.setSpacing(0)
        right_column.setContentsMargins(0, 0, 0, 0)

        r1 = QHBoxLayout()
        r1.setSpacing(0)
        id_box = QGroupBox("Species, Nature, Ability && Level")
        id_grid = QGridLayout(id_box)

        id_grid.addWidget(QLabel("Species:"), 0, 0)
        self.species_combo = theme.AppComboBox()
        self.species_combo.setEditable(True)
        self.species_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.species_combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.species_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        for ndex, sname in sorted(self.species_map.items()):
            self.species_combo.addItem(f"#{ndex:03d} {sname}", ndex)
        self.species_combo.activated.connect(self._on_species_changed)
        species_row = QHBoxLayout()
        species_row.addWidget(self.species_combo, 1)

        self.form_label = QLabel("Form:")
        self.form_label.setToolTip("Unown form. In Gen 3 the form is derived from the PID.")
        self.form_label.setVisible(False)
        species_row.addWidget(self.form_label)

        self.form_combo = theme.AppComboBox()
        for form_idx, form_label in enumerate(UNOWN_FORM_LABELS):
            self.form_combo.addItem(form_label, form_idx)
        self.form_combo.setFixedWidth(96)
        self.form_combo.setToolTip(
            "Unown form (A-Z, !, ?). In Gen 3 the form is derived from the PID, "
            "so choosing one regenerates from that Tanoby Chamber's slot."
        )
        self.form_combo.setVisible(False)
        self.form_combo.currentIndexChanged.connect(self._on_unown_form_changed)
        species_row.addWidget(self.form_combo)
        id_grid.addLayout(species_row, 0, 1)

        id_grid.addWidget(QLabel("Encounter:"), 1, 0)
        preset_row = QHBoxLayout()
        self.preset_combo = theme.AppComboBox()
        self.preset_combo.setMinimumWidth(180)
        self.preset_combo.setToolTip(
            "Choose the actual Gen 3 acquisition source. Wild slots, static gifts, "
            "in-game trades, and eggs are all listed; sources from another Gen 3 "
            "game are shown with their game name and switch the origin on generate. "
            "Custom / Manual keeps your field values; Generate then picks the "
            "closest real encounter so the record is still legal."
        )
        self.preset_combo.currentIndexChanged.connect(self._on_encounter_changed)
        preset_row.addWidget(self.preset_combo, 1)

        btn_generate = QPushButton("GENERATE")
        btn_generate.setProperty("role", "primary")
        btn_generate.setToolTip(
            "Create a fresh record from this encounter. Rerolls the PID/IV "
            "spread and fills the encounter's legal moves, met data and ball."
        )
        btn_generate.setMinimumWidth(88)
        btn_generate.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_generate.setStyleSheet("padding: 0px 8px; min-height: 0px;")
        # The Generate button belongs to the encounter bar: match its height
        # instead of standing a few pixels proud of it at every UI scale.
        btn_generate.setFixedHeight(self.preset_combo.sizeHint().height())
        btn_generate.clicked.connect(lambda: self.generate_from_selected_encounter())
        preset_row.addWidget(btn_generate)
        id_grid.addLayout(preset_row, 1, 1)

        id_grid.addWidget(QLabel("Nickname:"), 2, 0)
        self.nick_edit = QLineEdit("")
        self.nick_edit.setPlaceholderText("Leave blank for default species name")
        self.nick_edit.setMaxLength(10)
        self.nick_edit.textChanged.connect(self.refresh_live_preview)
        id_grid.addWidget(self.nick_edit, 2, 1)

        id_grid.addWidget(QLabel("Nature / PID:"), 3, 0)
        nat_pid_row = QHBoxLayout()
        self.nature_combo = theme.AppComboBox()
        for idx in range(25):
            self.nature_combo.addItem(nature_display_label(idx), idx)
        self.nature_combo.currentIndexChanged.connect(self._on_nature_or_ability_dropdown_changed)
        nat_pid_row.addWidget(self.nature_combo, stretch=1)

        self.pid_edit = QLineEdit("00000000")
        self.pid_edit.setFixedWidth(92)
        self.pid_edit.setStyleSheet(
            "font-family: '%s'; font-weight: bold; color: %s;" % (theme.FONT_DS, theme.NAVY_DARK)
        )
        self.pid_edit.textEdited.connect(self._on_pid_manually_edited)
        nat_pid_row.addWidget(self.pid_edit)

        self.shiny_chk = QCheckBox("★ Shiny")
        self.shiny_chk.setStyleSheet("color: #8a6412; font-weight: bold;")
        self.shiny_chk.toggled.connect(lambda _checked: self._on_nature_or_ability_dropdown_changed())
        nat_pid_row.addWidget(self.shiny_chk)
        id_grid.addLayout(nat_pid_row, 3, 1)

        id_grid.addWidget(QLabel("Gender:"), 4, 0)
        self.gender_combo = theme.AppComboBox()
        self.gender_combo.addItems(["Any", "Male", "Female"])
        self.gender_combo.currentIndexChanged.connect(self._on_nature_or_ability_dropdown_changed)
        id_grid.addWidget(self.gender_combo, 4, 1)

        id_grid.addWidget(QLabel("Ability:"), 5, 0)
        self.ability_combo = theme.AppComboBox()
        self.ability_combo.currentIndexChanged.connect(self._on_nature_or_ability_dropdown_changed)
        id_grid.addWidget(self.ability_combo, 5, 1)

        id_grid.addWidget(QLabel("Held Item:"), 6, 0)
        self.item_combo = theme.AppComboBox()
        for item_id, name in sorted(self.items_map.items(), key=lambda x: (x[0] != 0, x[1])):
            self.item_combo.addItem(f"{name} (#{item_id})", item_id)
        self.item_combo.currentIndexChanged.connect(self.refresh_live_preview)
        id_grid.addWidget(self.item_combo, 6, 1)

        id_grid.addWidget(QLabel("Level (1–100):"), 7, 0)
        lvl_row = QHBoxLayout()
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 100)
        self.level_spin.setValue(5)
        self.level_spin.setStyleSheet("font-weight: bold; color: #2f7d4f;")
        self.level_spin.valueChanged.connect(self._on_level_changed)
        lvl_row.addWidget(self.level_spin)

        self.growth_combo = theme.AppComboBox()
        self.growth_combo.addItems(GROWTH_RATES)
        self.growth_combo.currentIndexChanged.connect(self._on_level_changed)
        self.growth_combo.setVisible(False)
        id_grid.addLayout(lvl_row, 7, 1)

        id_grid.addWidget(QLabel("EXP:"), 8, 0)
        exp_fr_row = QHBoxLayout()
        self.exp_spin = QSpinBox()
        self.exp_spin.setRange(0, 1640000)
        self.exp_spin.setValue(135)
        self.exp_spin.valueChanged.connect(self._on_exp_changed)
        exp_fr_row.addWidget(self.exp_spin)
        exp_fr_row.addWidget(QLabel("Friendship:"))
        self.friend_spin = QSpinBox()
        self.friend_spin.setRange(0, 255)
        self.friend_spin.setValue(70)
        exp_fr_row.addWidget(self.friend_spin)
        id_grid.addLayout(exp_fr_row, 8, 1)
        r1.addWidget(id_box)

        ot_box = QGroupBox("Original Trainer && Met Data")
        ot_grid = QGridLayout(ot_box)

        ot_grid.addWidget(QLabel("OT Name:"), 0, 0)
        self.ot_edit = QLineEdit("RYAN")
        self.ot_edit.setMaxLength(7)
        self.ot_edit.textEdited.connect(self._remember_trainer_identity)
        ot_grid.addWidget(self.ot_edit, 0, 1)

        ot_grid.addWidget(QLabel("TID:"), 1, 0)
        self.tid_spin = QSpinBox()
        self.tid_spin.setRange(0, 65535)
        self.tid_spin.setValue(34162)
        self.tid_spin.valueChanged.connect(self.refresh_live_preview)
        self.tid_spin.valueChanged.connect(self._remember_trainer_identity)
        ot_grid.addWidget(self.tid_spin, 1, 1)

        ot_grid.addWidget(QLabel("SID:"), 2, 0)
        self.sid_spin = QSpinBox()
        self.sid_spin.setRange(0, 65535)
        self.sid_spin.setValue(26296)
        self.sid_spin.valueChanged.connect(self.refresh_live_preview)
        self.sid_spin.valueChanged.connect(self._remember_trainer_identity)
        ot_grid.addWidget(self.sid_spin, 2, 1)

        ot_grid.addWidget(QLabel("Origin Game:"), 3, 0)
        self.game_combo = theme.AppComboBox()
        for gid, gname in GAMES.items():
            self.game_combo.addItem(gname, gid)
        self.game_combo.setCurrentIndex(self.game_combo.findData(4))
        self.game_combo.currentIndexChanged.connect(self._on_game_changed)
        ot_grid.addWidget(self.game_combo, 3, 1)

        ot_grid.addWidget(QLabel("Poké Ball:"), 4, 0)
        self.ball_combo = theme.AppComboBox()
        for bid, bname in BALLS.items():
            self.ball_combo.addItem(bname, bid)
        self.ball_combo.setCurrentIndex(self.ball_combo.findData(4))
        # The player's own ball choice, kept apart from the fixed balls that
        # Safari slots and gifts mandate.
        self._preferred_ball = 4
        self.ball_combo.currentIndexChanged.connect(self._remember_ball_choice)
        self.ball_combo.currentIndexChanged.connect(self.refresh_live_preview)
        ot_grid.addWidget(self.ball_combo, 4, 1)

        ot_grid.addWidget(QLabel("Met Location:"), 5, 0)
        self.met_loc_combo = theme.AppComboBox()
        self._populate_locations(4)
        self.met_loc_combo.setCurrentIndex(self.met_loc_combo.findData(88))
        self.met_loc_combo.currentIndexChanged.connect(self.refresh_live_preview)
        ot_grid.addWidget(self.met_loc_combo, 5, 1)

        ot_grid.addWidget(QLabel("Met Level:"), 6, 0)
        self.met_lvl_spin = QSpinBox()
        self.met_lvl_spin.setRange(0, 100)
        self.met_lvl_spin.setValue(5)
        self.met_lvl_spin.valueChanged.connect(self.refresh_live_preview)
        ot_grid.addWidget(self.met_lvl_spin, 6, 1)

        flag_row = QHBoxLayout()
        self.egg_origin_chk = QCheckBox("Originated from Egg")
        self.egg_origin_chk.setStyleSheet("font-weight: bold; color: %s;" % theme.INK)

        self.hatched_chk = QCheckBox("Is Hatched")
        self.hatched_chk.setStyleSheet("font-weight: bold; color: %s;" % theme.INK)
        self.hatched_chk.setEnabled(False)

        self.hatch_btn = QPushButton("1-Step Hatch")
        self.hatch_btn.setStyleSheet(
            "background-color: %s; color: #fffdf6; font-weight: bold; border: 2px solid #924414;"
            " border-radius: 5px; padding: 1px 6px; font-family: '%s'; font-size: 12px;"
            % (theme.ORANGE, theme.FONT_DS)
        )

        sp_policy = self.hatch_btn.sizePolicy()
        sp_policy.setRetainSizeWhenHidden(True)
        self.hatch_btn.setSizePolicy(sp_policy)
        self.hatch_btn.setEnabled(False)
        self.hatch_btn.setStyleSheet(self.hatch_btn.styleSheet() + " color: transparent; background-color: transparent;")

        self.egg_origin_chk.toggled.connect(self._on_egg_origin_toggled)
        self.hatched_chk.toggled.connect(self._on_hatched_toggled)
        self.hatch_btn.clicked.connect(self._set_ready_to_hatch)

        self.fateful_chk = QCheckBox("Fateful Encounter")
        self.fateful_chk.setStyleSheet("font-weight: bold; color: %s;" % theme.INK)

        flag_row.addWidget(self.egg_origin_chk)
        flag_row.addWidget(self.hatched_chk)
        flag_row.addWidget(self.hatch_btn)
        flag_row.addWidget(self.fateful_chk)
        ot_grid.addLayout(flag_row, 7, 0, 1, 2)

        # Locked identity used for new records.  Learned from a Pokémon
        # received by trade; loading files never changes it.
        self.my_trainer_row = QHBoxLayout()
        self.my_trainer_lbl = QLabel("")
        self.my_trainer_lbl.setStyleSheet("color: #2f5fa8; font-size: 14px;")
        self.my_trainer_lbl.setWordWrap(True)
        # Two wrapped lines at 14 px plus the note's padding; 40 px keeps the
        # whole editor inside the 820 px minimum window without a scrollbar.
        self.my_trainer_lbl.setMinimumHeight(40)
        self.my_trainer_row.addWidget(self.my_trainer_lbl, 1)
        self.btn_set_my_trainer = QPushButton("Set as My Trainer")
        self.btn_set_my_trainer.setToolTip(
            "Lock the OT/TID/SID currently shown as My Trainer. New Pokémon use "
            "it; Pokémon loaded from files keep their own trainer."
        )
        self.btn_set_my_trainer.clicked.connect(self._on_set_my_trainer_clicked)
        self.my_trainer_row.addWidget(self.btn_set_my_trainer, 0)
        ot_grid.addLayout(self.my_trainer_row, 8, 0, 1, 2)

        # Shown while an event/trade record or another trainer's Pokémon is on
        # screen, explaining which identity new records will use.
        self.identity_note = QLabel("")
        self.identity_note.setStyleSheet("color: #8a6412; font-size: 12px; padding-top: 2px;")
        self.identity_note.setWordWrap(True)
        self.identity_note.setVisible(False)
        ot_grid.addWidget(self.identity_note, 9, 0, 1, 2)

        r1.addWidget(ot_box)

        # Tight, predictable field geometry.  The old 180 px fixed label
        # column plus 360 px minimum group height is what forced scrolling at
        # every window size; a 126 px column and content-sized rows fit both
        # the 1180 px minimum and a maximised 4K window.
        for box, label_column in ((id_box, 112), (ot_box, 104)):
            grid = box.layout()
            if grid is not None:
                grid.setContentsMargins(8, 5, 8, 5)
                grid.setHorizontalSpacing(8)
                grid.setVerticalSpacing(0)
                grid.setColumnMinimumWidth(0, label_column)
                for idx in range(grid.count()):
                    item = grid.itemAt(idx)
                    widget = item.widget() if item is not None else None
                    if isinstance(widget, QLabel):
                        widget.setMinimumHeight(22)

        right_column.addLayout(r1, 1)

        r2 = QHBoxLayout()
        r2.setSpacing(0)

        stat_box = QGroupBox("IVs (0–31) && EVs (0–255)")
        stat_grid = QGridLayout(stat_box)
        stat_names = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
        self.iv_spins = {}
        self.ev_spins = {}

        stat_grid.setContentsMargins(8, 6, 8, 6)
        stat_grid.setHorizontalSpacing(8)
        stat_grid.setVerticalSpacing(0)
        stat_grid.setColumnStretch(1, 1)
        stat_grid.setColumnStretch(2, 1)
        stat_grid.addWidget(QLabel("Stat"), 0, 0)
        stat_grid.addWidget(QLabel("IV (0-31)"), 0, 1)
        stat_grid.addWidget(QLabel("EV (0-255)"), 0, 2)

        for row_idx, sname in enumerate(stat_names, start=1):
            stat_grid.addWidget(QLabel(f"{sname}:"), row_idx, 0)
            iv_s = QSpinBox()
            iv_s.setRange(0, 31)
            iv_s.valueChanged.connect(self.refresh_live_preview)
            self.iv_spins[sname] = iv_s
            stat_grid.addWidget(iv_s, row_idx, 1)

            ev_s = QSpinBox()
            ev_s.setRange(0, 255)
            ev_s.valueChanged.connect(lambda val, k=sname: self._on_ev_changed(k, val))
            self.ev_spins[sname] = ev_s
            stat_grid.addWidget(ev_s, row_idx, 2)

        self.ev_total_lbl = QLabel("EV Total:   0 / 510 (510 Remaining)")
        self.ev_total_lbl.setStyleSheet(
            "color: %s; font-weight: bold; font-family: '%s'; font-size: 12px;"
            % (theme.GREEN_DARK, theme.FONT_DS)
        )
        stat_grid.addWidget(self.ev_total_lbl, 7, 0, 1, 3)

        btn_max_ivs = QPushButton("MAX ALL IVS")
        btn_max_ivs.clicked.connect(lambda: [s.setValue(31) for s in self.iv_spins.values()])
        stat_grid.addWidget(btn_max_ivs, 8, 0, 1, 2)

        btn_zero_evs = QPushButton("ZERO ALL EVS")
        btn_zero_evs.clicked.connect(lambda: [s.setValue(0) for s in self.ev_spins.values()])
        stat_grid.addWidget(btn_zero_evs, 8, 2, 1, 1)
        stat_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        r2.addWidget(stat_box, 2)

        # ==========================================
        # AUTHENTIC TYPE-COLORED MOVES COMBO BOXES
        # ==========================================
        move_box = QGroupBox("Moves, PP Ups / PP Max && Encounter RNG")
        move_grid = QGridLayout(move_box)
        move_grid.setContentsMargins(8, 6, 8, 7)
        move_grid.setHorizontalSpacing(5)
        move_grid.setVerticalSpacing(0)
        move_grid.setColumnStretch(2, 1)
        move_grid.setColumnStretch(4, 1)
        self.move_combos = []
        self.pp_up_combos = []
        self.pp_spins = []
        self.max_pp_lbls = []

        for i in range(4):
            move_grid.addWidget(QLabel(f"Move {i+1}:"), i, 0)

            # The type badge ONLY (no layout wrapping)
            type_lbl = QLabel("NONE")
            type_lbl.setFixedSize(62, 22)
            type_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            type_lbl.setStyleSheet(
                f"background-color: {TYPE_COLORS['NONE']}; color: {_readable_type_ink(TYPE_COLORS['NONE'])}; font-size: 12px;"
                f" border-radius: 4px; font-family: '{theme.FONT_DS}'; border: 1px solid rgba(0,0,0,0.25);"
            )
            move_grid.addWidget(type_lbl, i, 1)

            # Combobox stays fully independent
            m_cb = theme.AppComboBox()
            m_cb.setEditable(True)
            m_cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            m_cb.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            m_cb.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            for mid, mname in self.moves_map.items():
                m_cb.addItem(mname, mid)

            m_cb.type_label = type_lbl # link it to update color on change

            m_cb.currentIndexChanged.connect(lambda _idx, slot=i: self._on_move_or_ppup_changed(slot))
            self.move_combos.append(m_cb)
            move_grid.addWidget(m_cb, i, 2)

            pp_up_cb = theme.AppComboBox()
            pp_up_cb.addItems(["0 PP Up", "+1 PP Up", "+2 PP Up", "PP Max (3)"])
            pp_up_cb.currentIndexChanged.connect(lambda _idx, slot=i: self._on_move_or_ppup_changed(slot))
            self.pp_up_combos.append(pp_up_cb)
            move_grid.addWidget(pp_up_cb, i, 3)

            p_s = QSpinBox()
            p_s.setRange(0, 64)
            self.pp_spins.append(p_s)
            move_grid.addWidget(p_s, i, 4)

            max_lbl = QLabel("/  0 PP")
            max_lbl.setStyleSheet(
                "font-family: '%s'; font-size: 12px; color: %s;" % (theme.FONT_DS, theme.INK_SOFT)
            )
            self.max_pp_lbls.append(max_lbl)
            move_grid.addWidget(max_lbl, i, 5)

        btn_all_pp_max = QPushButton("PP MAX — ALL MOVES")
        btn_all_pp_max.setToolTip("Apply PP Max (+3 PP Ups) to all four moves")
        btn_all_pp_max.clicked.connect(lambda: [cb.setCurrentIndex(3) for cb in self.pp_up_combos])
        move_grid.addWidget(btn_all_pp_max, 4, 1, 1, 3)

        btn_reset_pp = QPushButton("RESET PP")
        btn_reset_pp.setToolTip("Reset all moves to default base PP (0 PP Up)")
        btn_reset_pp.clicked.connect(lambda: [cb.setCurrentIndex(0) for cb in self.pp_up_combos])
        move_grid.addWidget(btn_reset_pp, 4, 4, 1, 2)

        # These three actions are intentionally compact: the two Generate
        # buttons are each about half of the PP Max button's width, and
        # Legalize sits beside them instead of taking over another full row.
        roll_row = QHBoxLayout()
        roll_row.setSpacing(6)
        roll_row.addStretch(1)

        btn_roll_shiny = QPushButton("★ LEGAL SHINY")
        btn_roll_shiny.setProperty("role", "accent")
        btn_roll_shiny.setToolTip(
            "Create a fresh legal shiny record from the selected encounter. "
            "Rerolls the PID/IV spread and adopts the encounter's moves, ball "
            "and met data, so moves and EVs you set here can be replaced."
        )
        btn_roll_shiny.setFixedWidth(190)
        btn_roll_shiny.setFixedHeight(28)
        btn_roll_shiny.setStyleSheet("padding: 2px 8px; min-height: 20px;")
        btn_roll_shiny.clicked.connect(lambda: self.roll_legal_pid_ivs(shiny=True))
        roll_row.addWidget(btn_roll_shiny)

        btn_roll_normal = QPushButton("LEGAL NON-SHINY")
        btn_roll_normal.setToolTip(
            "Create a fresh legal non-shiny record from the selected encounter. "
            "Rerolls the PID/IV spread and adopts the encounter's moves, ball "
            "and met data, so moves and EVs you set here can be replaced."
        )
        btn_roll_normal.setFixedWidth(190)
        btn_roll_normal.setFixedHeight(28)
        btn_roll_normal.setStyleSheet("padding: 2px 8px; min-height: 20px;")
        btn_roll_normal.clicked.connect(lambda: self.roll_legal_pid_ivs(shiny=False))
        roll_row.addWidget(btn_roll_normal)

        btn_legalize = QPushButton("LEGALIZE")
        btn_legalize.setProperty("role", "blue")
        btn_legalize.setToolTip(
            "Repair the record currently in the editor. If PKHeX already "
            "accepts it, nothing changes. Otherwise it keeps your PID/IVs, "
            "moves, nature and level whenever a real source can explain them, "
            "and only corrects what PKHeX rejects."
        )
        btn_legalize.setFixedWidth(150)
        btn_legalize.setFixedHeight(28)
        btn_legalize.setStyleSheet("padding: 2px 8px; min-height: 20px;")
        btn_legalize.clicked.connect(self.legalize_current_record)
        roll_row.addWidget(btn_legalize)

        roll_row.addStretch(1)
        move_grid.addLayout(roll_row, 5, 1, 1, 5)

        self.rng_method_lbl = QLabel("RNG Generation Method: Waiting for encounter...")
        self.rng_method_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding-top: 2px; font-size: 13px;" % theme.NAVY
        )
        self.rng_method_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        move_grid.addWidget(self.rng_method_lbl, 6, 1, 1, 5)

        self.legality_lbl = QLabel("Legality: —")
        self.legality_lbl.setWordWrap(True)
        self.legality_lbl.setMinimumHeight(44)
        self.legality_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding: 3px; font-size: 14px;" % theme.INK_SOFT
        )
        self.legality_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        move_grid.addWidget(self.legality_lbl, 7, 1, 1, 5)
        move_grid.setContentsMargins(8, 6, 8, 7)

        move_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        r2.addWidget(move_box, 3)
        right_column.addLayout(r2, 1)

        content_row = QHBoxLayout()
        content_row.setSpacing(6)
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.addWidget(self.preview_frame, 0)
        content_row.addLayout(right_column, 1)
        main.addLayout(content_row, 1)

        btn_bar = QHBoxLayout()
        btn_save = QPushButton("OVERWRITE CURRENT .PK3")
        btn_save.setProperty("role", "primary")
        btn_save.clicked.connect(lambda: self.save_pk3(overwrite=True))

        btn_save_as = QPushButton("EXPORT .PK3...")
        btn_save_as.clicked.connect(lambda: self.save_pk3(overwrite=False))

        btn_to_slot2 = QPushButton("SEND TO TRADE SLOT 2")
        btn_to_slot2.setToolTip("Save the Pokémon and load it directly into Trade Slot 2")
        btn_to_slot2.setProperty("role", "blue")
        btn_to_slot2.clicked.connect(self.save_and_send_slot2)

        btn_to_pc = QPushButton("SAVE TO BILL'S PC")
        btn_to_pc.setToolTip(
            "Save this Pokémon as a new copy in Bill's PC; it never overwrites "
            "a stored Pokémon"
        )
        btn_to_pc.setProperty("role", "primary")
        btn_to_pc.clicked.connect(self.save_and_send_pc)

        for bar_btn in (btn_save, btn_save_as, btn_to_slot2, btn_to_pc):
            bar_btn.setStyleSheet("padding: 1px 7px; min-height: 18px;")
        btn_bar.addWidget(btn_save)
        btn_bar.addWidget(btn_save_as)
        btn_bar.addWidget(btn_to_slot2)
        btn_bar.addWidget(btn_to_pc)
        main.addLayout(btn_bar)

        scroll.setWidget(body)
        outer.addWidget(scroll)
        self.apply_theme()

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------
    def apply_theme(self):
        """Refresh the summary screen and the editor-only inline styles."""
        if not hasattr(self, "preview_frame"):
            return
        self._editor_body.setStyleSheet(
            "#EditorBody { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 %s, stop:1 %s); }" % (theme.APP_BG_TOP, theme.APP_BG_BOTTOM)
        )

        self.preview_frame.setStyleSheet(
            "QFrame#EditorSummary {"
            " background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 %s, stop:0.55 %s, stop:1 %s);"
            " border: 3px solid %s; border-radius: %spx; }"
            % (theme.SUMMARY_BG_1, theme.SUMMARY_BG_2, theme.SUMMARY_BG_3,
               theme.SUMMARY_BORDER, theme.PANEL_RADIUS)
        )
        self.summary_plate.setStyleSheet(
            "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 %s, stop:0.55 %s, stop:1 %s); color: %s;"
            " border: 2px solid %s; border-radius: %spx; font-family: '%s';"
            " font-size: 14px; padding: 2px;"
            % (theme.HEADER_LIGHT, theme.HEADER, theme.HEADER_DARK,
               theme.ON_HEADER, theme.GOLD, theme.CONTROL_RADIUS, theme.FONT_GBA)
        )
        self.summary_title_lbl.setStyleSheet(
            "font-family: '%s'; font-size: 16px; color: %s;"
            " border: none; background: transparent; padding: 1px 0 2px 0;"
            % (theme.FONT_GBA, theme.SUMMARY_TITLE)
        )
        self.summary_gender_lbl.setStyleSheet(
            "font-family: '%s'; font-size: 16px; color: %s;"
            " border: none; background: transparent; padding: 1px 0 2px 0;"
            % (theme.FONT_GBA, theme.RED_DARK)
        )
        self.summary_star_lbl.setStyleSheet(
            "font-family: '%s'; font-size: 16px; color: %s;"
            " border: none; background: transparent; padding: 1px 0 2px 0;"
            % (theme.FONT_GBA, theme.GOLD)
        )
        self.summary_rule.setStyleSheet(
            "background-color: %s; border: none; border-radius: 1px;" % theme.SUMMARY_RULE
        )
        self.sprite_lbl.setStyleSheet(
            "background-color: %s; border: 3px solid %s; border-radius: 7px;"
            " color: %s; font-family: '%s'; font-size: 12px;"
            % (theme.SUMMARY_CARD, theme.SUMMARY_BORDER, theme.INK_MUTED, theme.FONT_GBA)
        )
        self.memo_frame.setStyleSheet(
            "QFrame#EditorTrainerMemo { background-color: %s;"
            " border: 2px solid %s; border-radius: %spx; }"
            "QFrame#EditorTrainerMemo QLabel { background: transparent;"
            " border: none; padding: 7px 8px; font-size: 15px; color: %s;"
            " font-family: '%s'; }"
            % (theme.SUMMARY_MEMO_BG, theme.SUMMARY_MEMO_BORDER,
               theme.CONTROL_RADIUS, theme.INK, theme.FONT_DS)
        )
        self.stats_box.setStyleSheet(
            "QFrame { background-color: %s; border: 2px solid %s;"
            " border-radius: %spx; }"
            % (theme.SUMMARY_CARD, theme.SUMMARY_RULE, theme.CONTROL_RADIUS)
        )
        for name_lbl in self.stat_name_lbls:
            name_lbl.setStyleSheet(
                "background-color: %s; color: %s; border-radius: 3px;"
                " padding-left: 7px; font-family: '%s'; font-size: 15px;"
                % (theme.SUMMARY_STAT_BG, theme.SUMMARY_STAT_TEXT, theme.FONT_DS)
            )
        for val_lbl in self.stat_readout_lbls.values():
            val_lbl.setStyleSheet(
                "font-size: 17px; color: %s; border: none; background: transparent;"
                " font-family: '%s';" % (theme.INK, theme.FONT_DS)
            )
        self.exp_box.setStyleSheet(
            "QFrame { background-color: %s; border: 2px solid %s;"
            " border-radius: %spx; }"
            % (theme.SUMMARY_CARD, theme.SUMMARY_RULE, theme.CONTROL_RADIUS)
        )
        for lbl in (self.exp_lbl, self.next_lbl):
            lbl.setStyleSheet(
                "color: %s; font-family: '%s'; font-size: 14px;"
                " border: none; background: transparent;" % (theme.INK_SOFT, theme.FONT_DS)
            )
        for lbl in (self.exp_val_lbl, self.next_val_lbl):
            lbl.setStyleSheet(
                "font-size: 17px; color: %s; border: none; background: transparent;"
                " font-family: '%s';" % (theme.INK, theme.FONT_DS)
            )

        # Inline editor accents
        self.pid_edit.setStyleSheet(
            "font-family: '%s'; font-weight: bold; color: %s;"
            % (theme.FONT_DS, theme.NAVY_DARK)
        )
        self.shiny_chk.setStyleSheet("color: %s; font-weight: bold;" % theme.ORANGE_DARK)
        self.level_spin.setStyleSheet("font-weight: bold; color: %s;" % theme.GREEN_DARK)
        for chk in (self.egg_origin_chk, self.hatched_chk, self.fateful_chk):
            chk.setStyleSheet("font-weight: bold; color: %s;" % theme.INK)
        self.my_trainer_lbl.setStyleSheet(
            "color: %s; font-size: 14px; padding-bottom: 2px;" % theme.BLUE
        )
        self.identity_note.setStyleSheet(
            "color: %s; font-size: 13px; padding-top: 2px;" % theme.ORANGE_DARK
        )
        self.ev_total_lbl.setStyleSheet(
            "color: %s; font-weight: bold; font-family: '%s'; font-size: 12px;"
            % (theme.GREEN_DARK, theme.FONT_DS)
        )
        self.rng_method_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding-top: 2px; font-size: 13px;"
            % theme.NAVY
        )
        self.legality_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding: 3px; font-size: 14px;"
            % theme.INK_SOFT
        )
        for lbl in self.max_pp_lbls:
            lbl.setStyleSheet(
                "font-family: '%s'; font-size: 12px; color: %s;"
                % (theme.FONT_DS, theme.INK_SOFT)
            )
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep QScrollArea's centred body geometry in sync after a resize.
        if hasattr(self, "_editor_body"):
            self._editor_body.layout().activate()

    # ------------------------------------------------------------------
    # PKHeX encounter integration
    # ------------------------------------------------------------------
    def _current_game_version(self):
        return version_for_game_id(int(self.game_combo.currentData() or 4))

    def _set_form_control_visible(self, visible: bool):
        """Show/hide the Unown form label together with its combo."""
        self.form_combo.setVisible(visible)
        if hasattr(self, "form_label"):
            self.form_label.setVisible(visible)

    def _selected_encounter(self):
        if not hasattr(self, "preset_combo"):
            return None
        data = self.preset_combo.currentData()
        return data if isinstance(data, EncounterOption) else None

    @staticmethod
    def _encounter_key(option: EncounterOption):
        return (
            option.category,
            option.location,
            option.form,
            option.level_min,
            option.level_max,
            option.species,
            option.slot_type if option.category == "wild" else "",
            option.fixed_note if option.category in ("trade", "mystery") else "",
        )

    def _refresh_encounter_catalog(self, select_first: bool = False, preserve: bool = True,
                                   apply_metadata: bool = True) -> bool:
        """Rebuild the encounter picker for the current species/game."""
        if not hasattr(self, "preset_combo"):
            return False

        species = int(self.species_combo.currentData() or 1)
        previous = self._selected_encounter()
        options = list_encounters(species, self._current_game_version())

        if species == 201:
            current_form = self.form_combo.currentData()
            form = int(current_form) if current_form is not None else 0
            matching = [option for option in options if option.form == form]
            if matching:
                options = matching
            self._set_form_control_visible(True)
        else:
            self._set_form_control_visible(False)

        self.encounter_options = options
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("Custom / Manual (Generate picks the closest encounter)", None)
        for option in options:
            self.preset_combo.addItem(option.label, option)

        selected_index = 0
        if select_first and options:
            selected_index = 1
        elif preserve and previous is not None:
            previous_key = self._encounter_key(previous)
            for index, option in enumerate(options, start=1):
                if self._encounter_key(option) == previous_key:
                    selected_index = index
                    break

        self.preset_combo.setCurrentIndex(selected_index)
        self.preset_combo.blockSignals(False)
        self.preset_combo.setToolTip(self.preset_combo.currentText())

        selected_option = self.preset_combo.itemData(selected_index)
        if selected_index > 0 and apply_metadata:
            self._apply_encounter_metadata(selected_option)
        else:
            self._update_ball_tooltip(
                selected_option if isinstance(selected_option, EncounterOption) else None
            )
            self.refresh_live_preview()
        return bool(options)

    def _remember_ball_choice(self):
        """Remember the player's own ball choice for free-choice encounters.

        Safari slots and gifts override the combo; without remembering the
        player's own pick, switching from a Safari slot to a normal wild slot
        would leave the Safari Ball selected and make the record illegal.
        """
        if self._syncing:
            return
        option = self._selected_encounter()
        if option is not None and required_ball(option) is not None:
            return
        self._preferred_ball = int(self.ball_combo.currentData() or 4)

    def _update_ball_tooltip(self, option: EncounterOption | None = None):
        """Explain which balls PKHeX accepts for the selected encounter."""
        if not hasattr(self, "ball_combo"):
            return
        if option is None:
            self.ball_combo.setToolTip("")
            return
        mandated = required_ball(option)
        if mandated is not None:
            ball_name = BALLS.get(mandated, f"Ball #{mandated}")
            self.ball_combo.setToolTip(
                f"{option.label}\nPKHeX requires the {ball_name} for this encounter."
            )
            return
        allowed = ", ".join(BALLS.get(b, f"Ball #{b}") for b in allowed_balls(option))
        self.ball_combo.setToolTip(
            f"{option.label}\nThis encounter accepts: {allowed}."
        )

    def _encounter_match_score(self, option: EncounterOption) -> int:
        """How well an encounter explains the values currently in the editor."""
        met_loc = int(self.met_loc_combo.currentData() or 0)
        met_lvl = self.met_lvl_spin.value()
        egg = self.egg_origin_chk.isChecked()
        fateful = self.fateful_chk.isChecked()

        score = 0
        if met_loc and option.location == met_loc:
            score += 4
        if option.category == "egg":
            if egg:
                score += 3
        elif egg:
            score -= 2
        if fateful and bool(getattr(option.encounter, "FatefulEncounter", False)):
            score += 2
        if option.category == "egg":
            if met_lvl == 0:
                score += 2
        elif option.level_min <= met_lvl <= max(option.level_min, option.level_max):
            score += 2
        return score

    def _select_matching_encounter(self) -> EncounterOption | None:
        """Highlight the encounter that best matches the current field values.

        Used when the picker sits on Custom / Manual (including right after a
        save file is opened): the fields already hold whatever the player set
        or loaded, so choose the closest real source instead of leaving the
        generator with nothing to work from.  The editor fields are not
        touched here - the caller generates from the returned option.
        """
        if not hasattr(self, "preset_combo"):
            return None
        if self.preset_combo.count() <= 1:
            self._refresh_encounter_catalog(select_first=False, preserve=False)
            if self.preset_combo.count() <= 1:
                return None

        best_index = 0
        best_score = -1
        for index in range(1, self.preset_combo.count()):
            option = self.preset_combo.itemData(index)
            if not isinstance(option, EncounterOption):
                continue
            score = self._encounter_match_score(option)
            if score > best_score:
                best_index, best_score = index, score
        if best_index == 0:
            return None

        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(best_index)
        self.preset_combo.blockSignals(False)
        chosen = self.preset_combo.itemData(best_index)
        return chosen if isinstance(chosen, EncounterOption) else None

    def _apply_encounter_metadata(self, option: EncounterOption | None):
        """Apply the fixed parts of an encounter to the editor widgets."""
        if option is None:
            return

        old_sync = self._syncing
        self._syncing = True
        try:
            game_id = game_id_for_version(option.version)
            game_index = self.game_combo.findData(game_id)
            if game_index >= 0:
                self.game_combo.setCurrentIndex(game_index)
            self._populate_locations(game_id)

            location_index = self.met_loc_combo.findData(int(option.location))
            if location_index < 0:
                self.met_loc_combo.addItem(f"Unknown Location (ID {option.location})", int(option.location))
                location_index = self.met_loc_combo.count() - 1
            self.met_loc_combo.setCurrentIndex(location_index)

            # Selecting a source only sets the form up: this whole method runs
            # with _syncing set, so picking a Day Care egg in the list cannot
            # rewrite the record on its own.  Generate, or an explicit click on
            # the egg boxes, is what converts it.
            is_egg = option.category == "egg"
            self.egg_origin_chk.setChecked(is_egg)
            self.hatched_chk.setChecked(is_egg)
            self.hatched_chk.setEnabled(is_egg)

            met_level = 0 if is_egg else int(option.level_min)
            self.met_lvl_spin.setValue(met_level)

            # Only sources whose ball PKHeX fixes may change the player's
            # ball choice: Safari slots (Safari Ball), Day Care eggs, in-game
            # trades and the FRLG gift statics (Poké Ball).  Wild and plain
            # static encounters keep whatever ball is already selected, and
            # the combo tooltip lists what the chosen source accepts.
            mandated_ball = required_ball(option)
            if mandated_ball is not None:
                ball_index = self.ball_combo.findData(mandated_ball)
                if ball_index < 0:
                    self.ball_combo.addItem(f"Ball #{mandated_ball}", mandated_ball)
                    ball_index = self.ball_combo.count() - 1
                self.ball_combo.setCurrentIndex(ball_index)
            else:
                # Leaving a Safari slot (or a gift) must not carry its fixed
                # ball onto an encounter that does not accept it.
                allowed = allowed_balls(option)
                if int(self.ball_combo.currentData() or 4) not in allowed:
                    preferred = int(getattr(self, "_preferred_ball", 4))
                    if preferred not in allowed:
                        preferred = 4 if 4 in allowed else int(allowed[0])
                    ball_index = self.ball_combo.findData(preferred)
                    if ball_index < 0:
                        self.ball_combo.addItem(f"Ball #{preferred}", preferred)
                        ball_index = self.ball_combo.count() - 1
                    self.ball_combo.setCurrentIndex(ball_index)
            self._update_ball_tooltip(option)

            self.fateful_chk.setChecked(bool(getattr(option.encounter, "FatefulEncounter", False)))

            if option.category == "egg":
                target_level = max(self.level_spin.value(), option.level_min + 1)
            else:
                target_level = max(self.level_spin.value(), option.level_min, option.target_level_min)
            if target_level != self.level_spin.value():
                self.level_spin.setValue(target_level)

            if int(self.species_combo.currentData() or 1) == 201:
                self.form_combo.blockSignals(True)
                self.form_combo.setCurrentIndex(max(0, min(27, int(option.form))))
                self.form_combo.blockSignals(False)
                self._set_form_control_visible(True)
        finally:
            self._syncing = old_sync

        self._update_egg_ui()

    def _on_encounter_changed(self):
        if self._syncing:
            return
        # Narrow windows elide long encounter labels; keep the full source
        # available on hover.
        self.preset_combo.setToolTip(self.preset_combo.currentText())
        option = self._selected_encounter()
        if option is None:
            self._update_ball_tooltip(None)
            self.refresh_live_preview()
            return
        previous_game = int(self.game_combo.currentData() or 4)
        self._apply_encounter_metadata(option)
        if int(self.game_combo.currentData() or 4) != previous_game:
            # A cross-game source switched the origin game; rebuild the list
            # for that game without re-applying metadata over the new values.
            self._refresh_encounter_catalog(select_first=False, preserve=True,
                                            apply_metadata=False)

    def _on_unown_form_changed(self, _index=None):
        if self._syncing:
            return
        if int(self.species_combo.currentData() or 1) != 201:
            return
        if not self._refresh_encounter_catalog(select_first=True):
            return
        self.generate_from_selected_encounter()

    def _sync_form_combo_from_pid(self, pid: int):
        if not hasattr(self, "form_combo"):
            return
        old_sync = self._syncing
        self._syncing = True
        try:
            self.form_combo.blockSignals(True)
            if int(self.species_combo.currentData() or 1) == 201:
                self.form_combo.setCurrentIndex(unown_form_from_pid(pid))
                self._set_form_control_visible(True)
            else:
                self._set_form_control_visible(False)
            self.form_combo.blockSignals(False)
        finally:
            self._syncing = old_sync

    def _ensure_game_for_option(self, option: EncounterOption) -> None:
        """Switch the origin game when the chosen source belongs to another game.

        A cross-game entry (e.g. an Emerald starter while FireRed is selected)
        has to generate its record with the matching game version, or the met
        location and origin would contradict each other and fail legality.
        """
        game_id = game_id_for_version(option.version)
        if int(self.game_combo.currentData() or 4) == game_id:
            return
        index = self.game_combo.findData(game_id)
        if index < 0:
            return
        old_sync = self._syncing
        self._syncing = True
        try:
            self.game_combo.setCurrentIndex(index)
            self._populate_locations(game_id)
        finally:
            self._syncing = old_sync

    def _current_trainer_identity(self) -> tuple[str, int, int]:
        return (
            self.ot_edit.text().strip() or "TRAINER",
            self.tid_spin.value(),
            self.sid_spin.value(),
        )

    def _generation_trainer_identity(self) -> tuple[str, int, int]:
        """Identity new records are generated with: My Trainer, or the fields."""
        profile = getattr(self, "_my_trainer", None)
        if profile:
            return (profile["ot"], profile["tid"], profile["sid"])
        return self._trainer_identity

    def _apply_profile_to_fields(self, profile: dict):
        """Show a profile's OT/TID/SID in the fields without firing edits."""
        old_sync = self._syncing
        self._syncing = True
        widgets = [self.ot_edit, self.tid_spin, self.sid_spin]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.ot_edit.setText(profile["ot"])
            self.tid_spin.setValue(int(profile["tid"]))
            self.sid_spin.setValue(int(profile["sid"]))
        finally:
            for widget in widgets:
                widget.blockSignals(False)
            self._syncing = old_sync

    def _refresh_my_trainer_row(self):
        """Refresh the locked-profile label, button and explanatory note."""
        if not hasattr(self, "my_trainer_lbl"):
            return
        profile = getattr(self, "_my_trainer", None)
        if profile:
            self.my_trainer_lbl.setText(
                f"My Trainer: {profile['ot']} (TID {profile['tid']} / SID {profile['sid']}) — used for new records"
            )
            self.my_trainer_lbl.setToolTip(
                "Locked on disk after being learned from a received Pokémon. "
                "Pokémon loaded from files keep their own OT/TID/SID."
            )
            self.btn_set_my_trainer.setText("Replace My Trainer")
        else:
            self.my_trainer_lbl.setText(
                "My Trainer: not set — new records use the OT/TID/SID above"
            )
            self.my_trainer_lbl.setToolTip(
                "Trade a Pokémon you caught into the tool; it will offer to lock "
                "your real OT/TID/SID in. You can also click the button to use "
                "the values currently shown."
            )
            self.btn_set_my_trainer.setText("Set as My Trainer")
        self._update_identity_note()

    def reload_trainer_profile(self):
        """Re-read the locked profile from disk (used after a trade learns it)."""
        self._my_trainer = load_profile(self.base_dir)
        self._refresh_my_trainer_row()

    def _on_set_my_trainer_clicked(self):
        ot, tid, sid = self._current_trainer_identity()
        if not ot:
            QMessageBox.warning(self, "No OT Name", "Enter the trainer's OT name first.")
            return
        profile = getattr(self, "_my_trainer", None)
        if profile:
            question = (
                f"My Trainer is currently {profile['ot']} "
                f"(TID {profile['tid']} / SID {profile['sid']}).\n\n"
                f"Replace it with {ot} (TID {tid} / SID {sid})?"
            )
        else:
            question = (
                f"Lock My Trainer as {ot} (TID {tid} / SID {sid})?\n\n"
                "New Pokémon you generate will use this OT/TID/SID. Pokémon "
                "loaded from files keep their own trainer."
            )
        reply = QMessageBox.question(
            self,
            "Set My Trainer",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        source = self.current_path.name if self.current_path else "editor fields"
        saved = save_profile(self.base_dir, ot, tid, sid, source=source)
        if not saved:
            QMessageBox.warning(
                self, "Could Not Save", "My Trainer could not be saved to disk."
            )
            return
        self._my_trainer = saved
        self._refresh_my_trainer_row()
        self.rng_method_lbl.setText(
            f"My Trainer locked: {saved['ot']} (TID {saved['tid']} / SID {saved['sid']})"
        )

    def _remember_trainer_identity(self, *_args):
        """Follow manual OT/TID/SID edits as the open document's identity."""
        if not hasattr(self, "_trainer_identity") or self._syncing:
            return
        self._trainer_identity = self._current_trainer_identity()
        self._identity_from_fixed_source = False
        self._update_identity_note()

    def _restore_trainer_identity(self):
        """Put the open document's own OT/TID/SID back into the fields."""
        ot, tid, sid = self._trainer_identity
        old_sync = self._syncing
        self._syncing = True
        try:
            self.ot_edit.setText(ot)
            self.tid_spin.setValue(tid)
            self.sid_spin.setValue(sid)
        finally:
            self._syncing = old_sync
        self._identity_from_fixed_source = False
        self._update_identity_note()

    def _update_identity_note(self):
        """Explain a fixed event/trade trainer without hiding the profile."""
        if not hasattr(self, "identity_note"):
            return
        profile = getattr(self, "_my_trainer", None)
        current_ot, current_tid, current_sid = self._current_trainer_identity()

        if self._identity_from_fixed_source:
            if profile:
                target = f"My Trainer {profile['ot']} ({profile['tid']}/{profile['sid']})"
            else:
                target = "the OT/TID/SID fields above"
            self.identity_note.setText(
                f"Fixed OT: {current_ot} ({current_tid}) — new records use {target}."
            )
            self.identity_note.setToolTip(
                "This event/trade must keep its own OT, TID and SID. Your "
                "trainer is unchanged; generating any other Pokémon restores it."
            )
            self.identity_note.setStyleSheet("color: #8a6412; font-size: 12px; padding-top: 2px;")
            self.identity_note.setVisible(True)
            return

        if profile and (current_ot, current_tid, current_sid) != (
            profile["ot"], profile["tid"], profile["sid"]
        ):
            self.identity_note.setText(
                f"Editing {current_ot} ({current_tid}/{current_sid}) — saves keep this "
                f"trainer; new records use My Trainer {profile['ot']} "
                f"({profile['tid']}/{profile['sid']})."
            )
            self.identity_note.setToolTip(
                "This Pokémon belongs to another trainer. Editing and saving it "
                "does not change its OT/TID/SID, and does not change My Trainer."
            )
            self.identity_note.setStyleSheet("color: #2f5fa8; font-size: 12px; padding-top: 2px;")
            self.identity_note.setVisible(True)
            return

        self.identity_note.setVisible(False)

    def generate_from_selected_encounter(self, shiny: bool | None = None):
        option = self._selected_encounter()
        if option is None:
            # Custom / Manual: generate from the closest real source for the
            # values already in the editor instead of refusing to run.
            option = self._select_matching_encounter()
        if option is None:
            QMessageBox.information(
                self,
                "No Encounter Available",
                "PKHeX lists no legal Gen 3 encounter for this species "
                "(event-only distributions are excluded), so there is nothing to generate from.",
            )
            return

        if shiny is None:
            shiny = self.shiny_chk.isChecked()

        target_species = int(self.species_combo.currentData() or option.target_species)
        target_level = max(self.level_spin.value(), option.level_min, option.target_level_min)
        nature = int(self.nature_combo.currentData() or 0)
        ability_slot = int(self.ability_combo.currentData() or 0)
        gender_text = self.gender_combo.currentText()
        gender = 0 if gender_text == "Male" else 1 if gender_text == "Female" else None

        # An event or trade leaves its fixed trainer in the fields.  New
        # records must not inherit it: go back to the session's trainer
        # profile first, so the next ordinary Pokémon belongs to the player.
        if self._identity_from_fixed_source:
            self._restore_trainer_identity()

        trainer_ot, trainer_tid, trainer_sid = self._generation_trainer_identity()
        trainer_ot = (trainer_ot or "TRAINER")[:7]

        previous_game = int(self.game_combo.currentData() or 4)
        self._ensure_game_for_option(option)
        trainer = make_trainer(
            trainer_ot,
            trainer_tid,
            trainer_sid,
            version=version_for_game_id(int(self.game_combo.currentData() or 4)),
            language=2,
        )

        if shiny and int(self.species_combo.currentData() or 1) == 201:
            self.rng_method_lbl.setText("Building a legal shiny Unown spread...")
        else:
            self.rng_method_lbl.setText("Asking PKHeX for a legal spread...")
        self.legality_lbl.setText("Legality: checking generated record...")
        self.legality_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding: 3px; font-size: 13px;" % theme.INK_SOFT
        )
        QApplication.processEvents()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            pk, error = generate_pk3(
                option,
                trainer,
                target_species=target_species,
                target_level=target_level,
                nature=nature,
                shiny=bool(shiny),
                ability_slot=ability_slot,
                gender=gender,
            )
        except Exception as exc:
            pk, error = None, f"Unexpected generator error: {exc}"
        finally:
            QApplication.restoreOverrideCursor()

        if error or pk is None:
            self.rng_method_lbl.setText("Could not generate from this encounter")
            self.legality_lbl.setText(f"No record generated: {error}")
            self.legality_lbl.setStyleSheet(
                "font-weight: bold; color: %s; padding: 3px; font-size: 13px;" % theme.RED_DARK
            )
            self.legality_lbl.setToolTip(str(error))
            QMessageBox.warning(self, "Generation Failed", str(error))
            return

        self._apply_pk3_to_ui(pk, option)
        self._refresh_move_type_badges()

        applied_ot = str(pk.OriginalTrainerName).rstrip()
        applied_tid = int(pk.TID16)
        applied_sid = int(pk.SID16)
        # PKHeX overrides the trainer for events and in-game trades.  Treat
        # that as a temporary display state, not as the player's profile.
        self._identity_from_fixed_source = (
            applied_ot != trainer_ot
            or applied_tid != int(trainer_tid)
            or applied_sid != int(trainer_sid)
        )
        if not self._identity_from_fixed_source:
            self._trainer_identity = (applied_ot, applied_tid, applied_sid)
        self._update_identity_note()

        if int(self.game_combo.currentData() or 4) != previous_game:
            self._refresh_encounter_catalog(select_first=False, preserve=True,
                                            apply_metadata=False)

    def _apply_pk3_to_ui(self, pk, option: EncounterOption):
        """Copy a generated PK3 into the editor fields without re-rolling it."""
        old_sync = self._syncing
        self._syncing = True
        try:
            dex = int(pk.Species)
            version_id = game_id_for_version(pk.Version)
            game_index = self.game_combo.findData(version_id)
            if game_index >= 0:
                self.game_combo.setCurrentIndex(game_index)
            self._populate_locations(version_id)

            species_index = self.species_combo.findData(dex)
            if species_index >= 0:
                self.species_combo.setCurrentIndex(species_index)

            self.form_combo.blockSignals(True)
            if dex == 201:
                self.form_combo.setCurrentIndex(unown_form_from_pid(int(pk.PID)))
                self._set_form_control_visible(True)
            else:
                self._set_form_control_visible(False)
            self.form_combo.blockSignals(False)

            temp_pk = PK3()
            temp_pk.Species = dex
            pi = temp_pk.PersonalInfo
            growth_index = PK_TO_UI_GROWTH.get(pi.EXPGrowth, 0)
            self.growth_combo.setCurrentIndex(growth_index)

            ability_slot = 1 if int(pk.AbilityNumber) == 2 else 0
            self._refresh_species_abilities(dex, preferred_slot=ability_slot)

            gender_ratio = pi.Gender
            if gender_ratio not in (0, 254, 255):
                self.gender_combo.setEnabled(True)
                self.gender_combo.setCurrentIndex(2 if int(pk.Gender) == 1 else 1)
            else:
                self.gender_combo.setCurrentIndex(0)
                self.gender_combo.setEnabled(False)

            # A record's default nickname is just its species name.  Show
            # those as an empty field (the placeholder explains it), while
            # fixed names such as an in-game trade's CH'DING stay visible.
            generated_nick = str(pk.Nickname).rstrip()
            default_nick = str(self.species_map.get(dex, "")).strip()
            if default_nick and generated_nick.upper() == default_nick.upper():
                generated_nick = ""
            self.nick_edit.setText(generated_nick)
            self.ot_edit.setText(str(pk.OriginalTrainerName).rstrip())
            self.tid_spin.setValue(int(pk.TID16))
            self.sid_spin.setValue(int(pk.SID16))
            self.pid_edit.setText(f"{int(pk.PID):08X}")
            nature_index = self.nature_combo.findData(int(pk.Nature))
            if nature_index >= 0:
                self.nature_combo.setCurrentIndex(nature_index)

            item_id = int(pk.HeldItem)
            item_index = self.item_combo.findData(item_id)
            if item_index < 0:
                self.item_combo.addItem(f"Item #{item_id}", item_id)
                item_index = self.item_combo.count() - 1
            self.item_combo.setCurrentIndex(item_index)

            self.level_spin.setValue(int(pk.CurrentLevel))
            self.exp_spin.setValue(int(pk.EXP))
            self.friend_spin.setValue(int(pk.OriginalTrainerFriendship))

            location_index = self.met_loc_combo.findData(int(pk.MetLocation))
            if location_index < 0:
                self.met_loc_combo.addItem(f"Unknown Location (ID {pk.MetLocation})", int(pk.MetLocation))
                location_index = self.met_loc_combo.count() - 1
            self.met_loc_combo.setCurrentIndex(location_index)

            is_egg_source = option.category == "egg"
            self.egg_origin_chk.setChecked(is_egg_source)
            self.hatched_chk.setChecked(is_egg_source and not bool(pk.IsEgg))
            self.hatched_chk.setEnabled(is_egg_source)
            self._record_is_egg = bool(pk.IsEgg)
            self.met_lvl_spin.setValue(int(pk.MetLevel))
            self.fateful_chk.setChecked(bool(pk.FatefulEncounter))

            # Keep the player's ball choice unless PKHeX fixes it for this
            # source.  The generated record carries the encounter's default
            # ball, but saving writes the combo's value, so a free-choice
            # source must not silently rewrite the selection.
            mandated_ball = required_ball(option)
            if mandated_ball is not None:
                ball_index = self.ball_combo.findData(mandated_ball)
                if ball_index < 0:
                    self.ball_combo.addItem(f"Ball #{mandated_ball}", mandated_ball)
                    ball_index = self.ball_combo.count() - 1
                self.ball_combo.setCurrentIndex(ball_index)
            else:
                # Leaving a Safari slot (or a gift) must not carry its fixed
                # ball onto an encounter that does not accept it.
                allowed = allowed_balls(option)
                if int(self.ball_combo.currentData() or 4) not in allowed:
                    preferred = int(getattr(self, "_preferred_ball", 4))
                    if preferred not in allowed:
                        preferred = 4 if 4 in allowed else int(allowed[0])
                    ball_index = self.ball_combo.findData(preferred)
                    if ball_index < 0:
                        self.ball_combo.addItem(f"Ball #{preferred}", preferred)
                        ball_index = self.ball_combo.count() - 1
                    self.ball_combo.setCurrentIndex(ball_index)
            self._update_ball_tooltip(option)

            for key, value in (
                ("HP", pk.IV_HP), ("Atk", pk.IV_ATK), ("Def", pk.IV_DEF),
                ("SpA", pk.IV_SPA), ("SpD", pk.IV_SPD), ("Spe", pk.IV_SPE),
            ):
                self.iv_spins[key].setValue(int(value))
            for key, value in (
                ("HP", pk.EV_HP), ("Atk", pk.EV_ATK), ("Def", pk.EV_DEF),
                ("SpA", pk.EV_SPA), ("SpD", pk.EV_SPD), ("Spe", pk.EV_SPE),
            ):
                self.ev_spins[key].setValue(int(value))

            for slot in range(4):
                move_id = int(getattr(pk, f"Move{slot + 1}"))
                move_index = self.move_combos[slot].findData(move_id)
                if move_index < 0:
                    self.move_combos[slot].addItem(f"Move #{move_id}", move_id)
                    move_index = self.move_combos[slot].count() - 1
                self.move_combos[slot].setCurrentIndex(move_index)
                pp_ups = int(getattr(pk, f"Move{slot + 1}_PPUps"))
                self.pp_up_combos[slot].setCurrentIndex(max(0, min(3, pp_ups)))
                max_pp = calc_max_pp(move_id, pp_ups)
                self.pp_spins[slot].setMaximum(max(64, max_pp))
                self.pp_spins[slot].setValue(int(getattr(pk, f"Move{slot + 1}_PP")) or max_pp)
                self.max_pp_lbls[slot].setText(f"/ {max_pp:2d} PP")

            # Preserve PKHeX's own record bytes.  Fixed encounters (in-game
            # trades especially) carry data the editor widgets do not expose:
            # contest stats, ribbons, Pokérus, and trash bytes.  Blanking them
            # makes PKHeX reject the record even though the visible fields
            # look correct.
            generated_raw = raw_bytes_from_pk(pk)
            if len(generated_raw) >= 0x50:
                # Remember the record's own name bytes: fixed encounters can
                # carry text the Western charset cannot encode.
                self._generated_nick_text = str(pk.Nickname).rstrip()
                self._generated_nick_raw = bytes(generated_raw[0x08:0x12])
                self._generated_ot_text = str(pk.OriginalTrainerName).rstrip()
                self._generated_ot_raw = bytes(generated_raw[0x14:0x1B])
                self.raw_data = bytearray(generated_raw)
                self.block_g = bytearray(generated_raw[0x20:0x2C])
                self.block_a = bytearray(generated_raw[0x2C:0x38])
                self.block_e = bytearray(generated_raw[0x38:0x44])
                self.block_m = bytearray(generated_raw[0x44:0x50])
            else:
                self._generated_nick_text = ""
                self._generated_nick_raw = None
                self._generated_ot_text = ""
                self._generated_ot_raw = None
                self.raw_data = bytearray(100)
                self.raw_data[0x12] = int(pk.Language) if int(pk.Language) else 2
                self.raw_data[0x13] = 0x02
                self.block_g = bytearray(12)
                self.block_a = bytearray(12)
                self.block_e = bytearray(12)
                self.block_m = bytearray(12)

            self._last_generated_method = method_name_for_pk(pk)
            self._last_generated_label = option.label
        finally:
            self._syncing = old_sync

        self._update_egg_ui()
        self.rng_method_lbl.setText(
            f"PKHeX: {self._last_generated_method} · {option.category.title()} encounter"
        )
        self.rng_method_lbl.setToolTip(option.label)
        self.refresh_live_preview()

    def _select_encounter_option(self, option: EncounterOption | None) -> None:
        """Highlight an encounter without letting it rewrite the editor fields."""
        if option is None or not hasattr(self, "preset_combo"):
            return
        wanted = self._encounter_key(option)
        for index in range(1, self.preset_combo.count()):
            candidate = self.preset_combo.itemData(index)
            if isinstance(candidate, EncounterOption) and self._encounter_key(candidate) == wanted:
                self.preset_combo.blockSignals(True)
                self.preset_combo.setCurrentIndex(index)
                self.preset_combo.blockSignals(False)
                self.preset_combo.setToolTip(candidate.label)
                return

    def legalize_current_record(self):
        """Ask PKHeX to repair the assembled record with minimal changes.

        A legal record is left alone.  An illegal one keeps its PID/IV spread,
        moves, nature and level whenever a real encounter can explain them;
        only the source metadata is corrected.  If the spread itself is
        impossible, a fresh legal spread is generated and the player's choices
        are reapplied, with only the pieces PKHeX rejects changed.
        """
        built = self.build_pk3_bytes(silent=True)
        if not built:
            QMessageBox.information(
                self, "Legalize",
                "There is no complete record to check yet. Fill in the species and level first.",
            )
            return

        pk, already_valid, _messages = legality_from_bytes(built)
        if pk is None:
            QMessageBox.warning(self, "Legalize", "PKHeX could not read this record as a PK3.")
            return

        species = int(self.species_combo.currentData() or 1)
        options = list_encounters(species, self._current_game_version())
        selected = self._selected_encounter()
        if already_valid:
            # A record can be legal and still carry only its met-level moves,
            # e.g. a Lv 20 Rattata generated from a Lv 2 slot.  Complete empty
            # slots from the current-level learnset without replacing a move
            # the player already chose.
            if selected is None:
                selected = self._select_matching_encounter()
            option = selected or (options[0] if options else None)
            completed = complete_level_up_moves(pk, option)
            if completed is not None:
                filled_pk, added = completed
                self._apply_pk3_to_ui(filled_pk, option)
                self._refresh_move_type_badges()
                self._refresh_legality_status()
                names = ", ".join(
                    str(self.moves_map.get(int(move), f"Move #{int(move)}"))
                    for move in added
                )
                QMessageBox.information(
                    self, "Legalize — PKHeX",
                    f"Added {names} from the Lv {int(filled_pk.CurrentLevel)} level-up "
                    "learnset. Existing moves were kept.",
                )
                return
            self._refresh_legality_status()
            QMessageBox.information(
                self, "Legalize — PKHeX",
                "PKHeX already reports this Pokémon as legal. No changes were made.",
            )
            return

        if selected is None:
            selected = self._select_matching_encounter()
        if selected is not None:
            selected_key = self._encounter_key(selected)
            options = [selected] + [
                option for option in options
                if self._encounter_key(option) != selected_key
            ]
        if not options:
            QMessageBox.warning(
                self, "Legalize",
                "PKHeX lists no legal Gen 3 encounter for this species, so there is nothing to repair against.",
            )
            return

        trainer = make_trainer(
            self.ot_edit.text().strip() or "TRAINER",
            self.tid_spin.value(), self.sid_spin.value(),
            version=self._current_game_version(), language=2,
        )
        moves = tuple(int(combo.currentData() or 0) for combo in self.move_combos)
        pp_ups = tuple(combo.currentIndex() for combo in self.pp_up_combos)
        pp_values = tuple(spin.value() for spin in self.pp_spins)
        evs = {
            "EV_HP": self.ev_spins["HP"].value(),
            "EV_ATK": self.ev_spins["Atk"].value(),
            "EV_DEF": self.ev_spins["Def"].value(),
            "EV_SPA": self.ev_spins["SpA"].value(),
            "EV_SPD": self.ev_spins["SpD"].value(),
            "EV_SPE": self.ev_spins["Spe"].value(),
        }

        self.legality_lbl.setText("Legality: legalizing with PKHeX...")
        self.legality_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding: 3px; font-size: 13px;" % theme.INK_SOFT
        )
        QApplication.processEvents()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        error = "Could not make this record legal."
        try:
            result = legalize_pk3(
                pk, options, trainer,
                moves=moves,
                pp_ups=pp_ups,
                pp_values=pp_values,
                evs=evs,
                held_item=int(self.item_combo.currentData() or 0),
                friendship=self.friend_spin.value(),
                nickname=self.nick_edit.text().strip(),
                move_names=self.moves_map,
            )
        except Exception as exc:
            result = None
            error = f"Unexpected legalize error: {exc}"
        finally:
            QApplication.restoreOverrideCursor()

        if result is None or result.pk is None:
            if result is not None:
                error = result.error
            self._refresh_legality_status()
            QMessageBox.warning(self, "Legalize — PKHeX", str(error or "Could not make this record legal."))
            return

        option = result.option or selected or options[0]
        result_changes = list(result.changes)
        # Repairs that had to change the PID/IV spread can still leave the
        # met-level moves in place.  Fill empty slots from the current-level
        # learnset after the record is legal; this never replaces a move.
        completion = complete_level_up_moves(result.pk, option)
        if completion is not None:
            result.pk, added = completion
            names = ", ".join(
                str(self.moves_map.get(int(move), f"Move #{int(move)}"))
                for move in added
            )
            result_changes.append(f"Level-up moves added: {names}")
        self._apply_pk3_to_ui(result.pk, option)
        self._refresh_move_type_badges()
        # The chosen source can belong to another Gen 3 game, so rebuild the
        # picker for the game the record now says it came from, then highlight
        # the source without applying its metadata a second time.
        self._refresh_encounter_catalog(select_first=False, preserve=False, apply_metadata=False)
        self._select_encounter_option(option)
        self._refresh_legality_status()

        changes = "\n".join(f"• {line}" for line in result_changes)
        QMessageBox.information(
            self, "Legalize — PKHeX",
            changes or "The record is now legal according to PKHeX.",
        )

    def _schedule_legality(self):
        if getattr(self, "_syncing", False):
            return
        timer = getattr(self, "_legality_timer", None)
        if timer is not None:
            timer.start(220)

    def _refresh_legality_status(self):
        if self._syncing or not hasattr(self, "legality_lbl"):
            return
        built = self.build_pk3_bytes(silent=True)
        if not built:
            self.legality_lbl.setText("Legality: no complete record")
            self.legality_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding: 3px; font-size: 13px;" % theme.INK_SOFT
        )
            self.legality_lbl.setToolTip("Fill in the editor fields to run a PKHeX legality analysis.")
            return

        _pk, valid, messages = legality_from_bytes(built)
        if valid:
            self.legality_lbl.setText("✓ PKHeX legal")
            self.legality_lbl.setStyleSheet(
                "font-weight: bold; color: %s; padding: 3px; font-size: 13px;" % theme.GREEN_DARK
            )
            self.legality_lbl.setToolTip("PKHeX's Gen 3 legality analysis reports no problems.")
        else:
            detail = "; ".join(messages[:2]) if messages else "PKHeX reported an invalid record."
            self.legality_lbl.setText(f"✗ PKHeX illegal — {detail}")
            self.legality_lbl.setStyleSheet(
                "font-weight: bold; color: %s; padding: 3px; font-size: 13px;" % theme.RED_DARK
            )
            self.legality_lbl.setToolTip("\n".join(messages))

    def _on_game_changed(self):
        if self._syncing: return
        old_sync = self._syncing
        self._syncing = True
        game_id = int(self.game_combo.currentData() or 4)
        self._populate_locations(game_id)
        self._syncing = old_sync

        # The selected game owns the source list, but never let the rebuild
        # drag the origin game back: a species without a source in the newly
        # chosen game keeps that game selected and lists the other games' real
        # encounters, labelled with their game name.
        self._refresh_encounter_catalog(select_first=False, preserve=False)

    def _populate_locations(self, game_id):
        self.met_loc_combo.blockSignals(True)
        current_loc = self.met_loc_combo.currentData()
        self.met_loc_combo.clear()

        game_id = int(game_id or 4)
        is_hoenn = game_id in (1, 2, 3)
        pkhex_names = gen3_locations(version_for_game_id(game_id))

        if is_hoenn:
            # Hoenn uses ids 0-87; 88+ are Kanto/Sevii ids that no RSE record
            # can carry.  PKHeX's own names are authoritative here.
            entries = sorted(
                (loc, name) for loc, name in pkhex_names
                if loc <= 87 or loc >= 253
            )
        else:
            # Keep the curated, story-ordered Kanto/Sevii names and fill in
            # every remaining id PKHeX can name, so no real met location
            # shows up as "Unknown Location".
            names = dict(FRLG_LOCS)
            for loc, name in pkhex_names:
                if loc in names or 1 <= loc <= 87:
                    continue
                names[loc] = name
            curated = [(loc, name) for loc, name in FRLG_LOCS.items()]
            extras = [(loc, names[loc]) for loc in sorted(set(names) - set(FRLG_LOCS))]
            entries = curated + extras

        for k, v in entries:
            self.met_loc_combo.addItem(f"{v} (ID {k})", k)

        idx = self.met_loc_combo.findData(current_loc)
        if idx >= 0:
            self.met_loc_combo.setCurrentIndex(idx)
        else:
            if current_loc is not None:
                self.met_loc_combo.addItem(f"Unknown Location (ID {current_loc})", current_loc)
                self.met_loc_combo.setCurrentIndex(self.met_loc_combo.count() - 1)
        self.met_loc_combo.blockSignals(False)

    def _on_level_changed(self):
        if self._syncing: return
        old_sync = self._syncing
        self._syncing = True
        lvl = self.level_spin.value()
        rate_idx = self.growth_combo.currentIndex()
        self.exp_spin.setValue(calc_exp_for_level(lvl, rate_idx))
        self._syncing = old_sync
        self.refresh_live_preview()

    def _on_exp_changed(self, exp_val: int):
        if self._syncing: return
        old_sync = self._syncing
        self._syncing = True
        rate_idx = self.growth_combo.currentIndex()
        best_lvl = 1
        for lvl in range(1, 101):
            if calc_exp_for_level(lvl, rate_idx) <= exp_val:
                best_lvl = lvl
        self.level_spin.setValue(best_lvl)
        self._syncing = old_sync
        self.refresh_live_preview()

    def _on_ev_changed(self, stat_key: str, val: int):
        if self._syncing: return
        old_sync = self._syncing
        other_sum = sum(s.value() for k, s in self.ev_spins.items() if k != stat_key)
        max_allowed = max(0, min(255, 510 - other_sum))
        if val > max_allowed:
            spin = self.ev_spins[stat_key]
            self._syncing = True
            spin.setValue(max_allowed)
            if spin.lineEdit(): spin.lineEdit().setText(str(max_allowed))
            self._syncing = old_sync
            QTimer.singleShot(0, lambda s=spin, m=max_allowed: s.setValue(m))
        self.refresh_live_preview()

    def _tick_bounce(self):
        self._bounce_step = not self._bounce_step

    def _refresh_species_abilities(self, nat_dex: int, preferred_slot: int = 0):
        old_sync = getattr(self, "_syncing", False)
        self._syncing = True
        self.ability_combo.clear()

        temp_pk = PK3()
        temp_pk.Species = nat_dex
        pi = temp_pk.PersonalInfo

        a1 = pi.Ability1
        a2 = pi.Ability2

        ab1_name = GEN3_ABILITIES.get(a1, f"Unknown ({a1})") if a1 > 0 else "None"
        self.ability_combo.addItem(f"{ab1_name} (Slot 1)", 0)

        if a2 != a1 and a2 > 0:
            ab2_name = GEN3_ABILITIES.get(a2, f"Unknown ({a2})")
            self.ability_combo.addItem(f"{ab2_name} (Slot 2)", 1)
            self.ability_combo.setEnabled(True)
            self.ability_combo.setCurrentIndex(1 if preferred_slot == 1 else 0)
        else:
            self.ability_combo.setEnabled(False)

        gender_ratio = pi.Gender
        if gender_ratio in (0, 254, 255):
            self.gender_combo.setCurrentIndex(0)
            self.gender_combo.setEnabled(False)
        else:
            self.gender_combo.setEnabled(True)

        self._syncing = old_sync

    def _on_species_changed(self):
        if self._syncing: return
        old_sync = self._syncing
        self._syncing = True
        self.nick_edit.setText("")
        self._syncing = old_sync

        if not hasattr(self, "_sp_debounce"):
            self._sp_debounce = QTimer(self)
            self._sp_debounce.setSingleShot(True)
            self._sp_debounce.timeout.connect(self._execute_species_change)
        self._sp_debounce.start(20)

    def _execute_species_change(self):
        if getattr(self, "_species_updating", False): return
        self._species_updating = True
        self.setUpdatesEnabled(False)
        old_sync = getattr(self, "_syncing", False)
        self._syncing = True

        try:
            # Leaving an event/trade record behind: the new species belongs to
            # the player again, so put their trainer back before generating.
            if getattr(self, "_identity_from_fixed_source", False):
                self._restore_trainer_identity()

            if hasattr(self, "sprite_lbl") and self.sprite_lbl.movie():
                self.sprite_lbl.movie().stop()
                self.sprite_lbl.setMovie(None)
            nat_dex = int(self.species_combo.currentData() or 1)
            self._refresh_species_abilities(nat_dex, preferred_slot=0)

            temp_pk = PK3()
            temp_pk.Species = nat_dex
            pi = temp_pk.PersonalInfo

            ui_growth_idx = PK_TO_UI_GROWTH.get(pi.EXPGrowth, 0)
            self.growth_combo.setCurrentIndex(ui_growth_idx)
            self.exp_spin.setValue(calc_exp_for_level(self.level_spin.value(), ui_growth_idx))

            self.shiny_chk.setChecked(False)
            if hasattr(self, "form_combo"):
                self.form_combo.blockSignals(True)
                self.form_combo.setCurrentIndex(0)
                self.form_combo.blockSignals(False)
                self._set_form_control_visible(nat_dex == 201)
            self.item_combo.setCurrentIndex(0)
            for k in self.ev_spins: self.ev_spins[k].setValue(0)
            for i in range(4):
                self.move_combos[i].setCurrentIndex(0)
                self.pp_up_combos[i].setCurrentIndex(0)
                self.pp_spins[i].setValue(0)
                self.max_pp_lbls[i].setText("/  0 PP")
        finally:
            self._syncing = old_sync
            self.auto_legalize_current_species() # Call new decoupled legalize method here
            self.setUpdatesEnabled(True)
            self._species_updating = False
            self.refresh_live_preview()

    def _on_move_or_ppup_changed(self, slot: int):
        if self._syncing: return
        mid = int(self.move_combos[slot].currentData() or 0)
        pp_ups = self.pp_up_combos[slot].currentIndex()
        max_pp = calc_max_pp(mid, pp_ups)
        self.pp_spins[slot].setMaximum(max(64, max_pp))
        self.pp_spins[slot].setValue(max_pp)
        self.max_pp_lbls[slot].setText(f"/ {max_pp:2d} PP")

        # --- Update the Authentic FRLG Type Badge Color ---
        self._refresh_move_type_badges(slot)

    def _refresh_move_type_badges(self, slot: int | None = None):
        """Repaint the FRLG type badges for one move slot, or all four.

        Generation copies a whole record into the widgets while signals are
        blocked, so the per-slot handler never runs; refresh explicitly after
        any bulk update (generated record, species change, file load).
        """
        slots = range(len(self.move_combos)) if slot is None else (slot,)
        for index in slots:
            if not (0 <= index < len(self.move_combos)):
                continue
            cb = self.move_combos[index]
            mid = int(cb.currentData() or 0)
            mtype = _MOVE_TYPES_LIST[mid] if 0 <= mid < len(_MOVE_TYPES_LIST) else "NONE"
            hex_color = TYPE_COLORS.get(mtype, TYPE_COLORS["NONE"])
            if hasattr(cb, "type_label"):
                cb.type_label.setStyleSheet(
                    f"background-color: {hex_color}; color: {_readable_type_ink(hex_color)}; font-size: 12px;"
                    f" border-radius: 4px; font-family: '{theme.FONT_DS}'; border: 1px solid rgba(0,0,0,0.25);"
                )
                cb.type_label.setText(mtype)

    def _on_nature_or_ability_dropdown_changed(self):
        if self._syncing: return
        cur_shiny = self.shiny_chk.isChecked() if hasattr(self, "shiny_chk") else False
        self.roll_legal_pid_ivs(shiny=cur_shiny)

    def _on_pid_manually_edited(self):
        if self._syncing: return
        try: pid = int(self.pid_edit.text().strip(), 16)
        except ValueError: return
        old_sync = self._syncing
        self._syncing = True
        self.nature_combo.setCurrentIndex(pid % 25)
        if self.ability_combo.count() > 1:
            self.ability_combo.setCurrentIndex(pid & 1)
        else:
            self.ability_combo.setCurrentIndex(0)

        nat_dex = int(self.species_combo.currentData() or 1)
        temp_pk = PK3()
        temp_pk.Species = nat_dex
        gender_ratio = temp_pk.PersonalInfo.Gender
        if gender_ratio not in (0, 254, 255):
            self.gender_combo.setCurrentIndex(2 if (pid & 0xFF) < gender_ratio else 1)
        else:
            self.gender_combo.setCurrentIndex(0)

        self._sync_form_combo_from_pid(pid)
        self._syncing = old_sync
        self.refresh_live_preview()

    def _on_egg_origin_toggled(self, checked, *args):
        if getattr(self, "_syncing", False): return
        self.hatched_chk.setEnabled(checked)
        if not checked:
            old_sync = self._syncing
            self._syncing = True
            self.hatched_chk.setChecked(False)
            self._syncing = old_sync
        self._apply_egg_toggle()

    def _on_hatched_toggled(self, checked, *args):
        if getattr(self, "_syncing", False): return
        self._apply_egg_toggle()

    def _apply_egg_toggle(self):
        """Keep the record itself in step with the egg checkboxes."""
        unhatched = self.egg_origin_chk.isChecked() and not self.hatched_chk.isChecked()
        if self.egg_origin_chk.isChecked() or getattr(self, "_record_is_egg", False):
            self._apply_egg_state(unhatched)
        else:
            self._update_egg_ui()

    def _hatch_cycle_limit(self) -> int:
        """Hatch cycles the selected species may have; 255 when unknown."""
        dex = int(self.species_combo.currentData() or 1)
        try:
            probe = PK3()
            probe.Species = dex
            cycles = int(probe.PersonalInfo.HatchCycles)
            return cycles if cycles > 0 else 255
        except Exception:
            return 255

    def _egg_source_for_species(self) -> EncounterOption | None:
        """The legal egg source for the species in the editor, if it has one."""
        option = self._selected_encounter()
        if option is not None and option.category == "egg":
            return option
        dex = int(self.species_combo.currentData() or 0)
        if dex <= 0:
            return None
        for candidate in list_encounters(dex, self._current_game_version()):
            if candidate.category == "egg":
                return candidate
        return None

    def _generate_egg_record(self, option: EncounterOption):
        """Build a legal hatched-egg record for this species and its traits."""
        trainer_ot, trainer_tid, trainer_sid = self._generation_trainer_identity()
        trainer = make_trainer(
            (trainer_ot or "TRAINER")[:7],
            trainer_tid,
            trainer_sid,
            version=version_for_game_id(int(self.game_combo.currentData() or 4)),
            language=2,
        )
        gender_text = self.gender_combo.currentText()
        gender = 0 if gender_text == "Male" else 1 if gender_text == "Female" else None
        pk, error = generate_pk3(
            option,
            trainer,
            target_species=int(self.species_combo.currentData() or option.target_species),
            target_level=max(1, int(option.level_min)),
            nature=int(self.nature_combo.currentData() or 0),
            shiny=self.shiny_chk.isChecked(),
            ability_slot=int(self.ability_combo.currentData() or 0),
            gender=gender,
        )
        return None if (error or pk is None) else pk

    def _convert_record_to_egg(self, option: EncounterOption, unhatched: bool):
        """Rewrite the current record as an egg record, rebuilding the spread
        when the one in the editor cannot be reached by breeding."""

        def convert():
            built = self.build_pk3_bytes(silent=True)
            if not built:
                return None, False, ("Fill in the editor fields to build a record.",)
            pp_values = tuple(
                calc_max_pp(int(combo.currentData() or 0), 0) for combo in self.move_combos
            )
            return convert_egg_state(
                built,
                unhatched,
                level=int(option.level_min),
                location=int(option.location),
                ball=required_ball(option) or 4,
                pp_values=pp_values if unhatched else None,
            )

        pk, valid, messages = convert()
        if valid:
            return pk, valid, messages, False

        # A wild or static spread has a different relation to the RNG than a
        # bred egg, and PKHeX reports that as a PID/IV mismatch.  Build a real
        # egg record with the same species, nature, shiny state and gender
        # rather than saving a record PKHeX rejects.
        rebuilt = self._generate_egg_record(option)
        if rebuilt is None:
            return pk, valid, messages, False
        self._apply_pk3_to_ui(rebuilt, option)
        pk2, valid2, messages2 = convert()
        if pk2 is not None and valid2:
            return pk2, valid2, messages2, True
        return pk, valid, messages, False

    def _apply_egg_state(self, unhatched: bool) -> None:
        """Make the record a legal Gen 3 egg (or a hatched one) for real."""
        option = self._egg_source_for_species()
        if option is None:
            # No legal egg exists for this species, so leave the raw flags
            # alone and let the legality check say so.
            self._update_egg_ui()
            return

        dex = int(self.species_combo.currentData() or 0)
        if unhatched and int(option.species) != dex:
            # An egg only ever holds the species it hatches into, so an evolved
            # record cannot exist unhatched.  Say why instead of leaving an
            # illegal record behind.
            species_name = self.species_map.get(dex, f"#{dex}")
            egg_name = self.species_map.get(int(option.species), f"#{int(option.species)}")
            QMessageBox.information(
                self,
                "Cannot Hatch This Egg",
                f"A {species_name} cannot be an unhatched egg: the egg itself is a "
                f"{egg_name}.  Keeping this record hatched is the only legal "
                f"option, so \"Is Hatched\" has been ticked again.",
            )
            old_sync = self._syncing
            self._syncing = True
            self.hatched_chk.setChecked(True)
            self._syncing = old_sync
            self._update_egg_ui()
            return

        pk, valid, messages, rebuilt = self._convert_record_to_egg(option, unhatched)
        if pk is None:
            self._update_egg_ui()
            return

        self._apply_pk3_to_ui(pk, option)
        self._refresh_move_type_badges()
        self._refresh_legality_status()
        notes = [] if valid else list(messages)
        if rebuilt:
            notes.append(
                "This record's own PID/IV spread cannot be reached by breeding, "
                "so a fresh legal egg record was generated for the same species, "
                "nature, shiny state and gender."
            )
            QMessageBox.information(
                self,
                "Egg Spread Rebuilt",
                notes[-1],
            )
        if notes:
            self.legality_lbl.setToolTip("\n".join(notes))

    def _update_egg_ui(self):
        if not hasattr(self, "hatch_btn"): return

        egg_widget = getattr(self, "egg_origin_chk", None)
        hatch_widget = getattr(self, "hatched_chk", None)

        is_unhatched = egg_widget and hatch_widget and egg_widget.isChecked() and not hatch_widget.isChecked()
        is_hatched = egg_widget and hatch_widget and egg_widget.isChecked() and hatch_widget.isChecked()
        is_egg = is_unhatched or is_hatched

        if is_egg:
            self.met_lvl_spin.blockSignals(True)
            self.met_lvl_spin.setValue(0)
            self.met_lvl_spin.setEnabled(False)
            self.met_lvl_spin.blockSignals(False)
        else:
            self.met_lvl_spin.setEnabled(True)

        # While unhatched the friendship field is the hatch counter, and PKHeX
        # only accepts values inside the species' own hatch cycle range.  The
        # spin box enforces it so the record cannot be made illegal by hand.
        if hasattr(self, "friend_spin"):
            self.friend_spin.setMaximum(self._hatch_cycle_limit() if is_unhatched else 255)

        self.hatch_btn.setEnabled(bool(is_unhatched))
        if is_unhatched:
            self.hatch_btn.setText("1-Step Hatch")
            self.hatch_btn.setStyleSheet(
            "background-color: %s; color: #fffdf6; font-weight: bold; border: 2px solid #924414;"
            " border-radius: 5px; padding: 1px 6px; font-family: '%s'; font-size: 12px;"
            % (theme.ORANGE, theme.FONT_DS)
        )
        else:
            self.hatch_btn.setText("1-Step Hatch")
            self.hatch_btn.setStyleSheet(
                "background-color: transparent; color: transparent; border: 2px solid transparent;"
                " border-radius: 5px; padding: 1px 6px; font-family: '%s'; font-size: 12px;"
                % theme.FONT_DS
            )

        for lbl in self.findChildren(QLabel):
            if lbl.text() in ("Friendship:", "Egg Cycles:"):
                lbl.setText("Egg Cycles:" if is_unhatched else "Friendship:")
                break
        self.refresh_live_preview()

    def _set_ready_to_hatch(self):
        """Drop the hatch counter to 1 so the egg hatches in one step."""
        spin = getattr(self, "friend_spin", None)
        if spin is not None:
            spin.setValue(min(1, spin.maximum()))
            return
        for attr_name, attr_val in self.__dict__.items():
            if isinstance(attr_val, QSpinBox) and attr_val.maximum() == 255 and attr_name not in ["met_loc_spin", "met_lvl_spin"]:
                if "friend" in attr_name.lower() or "happy" in attr_name.lower():
                    attr_val.setValue(1)
                    return
        for child in self.findChildren(QSpinBox):
            if child.maximum() == 255 and child.value() > 0:
                child.setValue(1)

    def auto_legalize_current_species(self):
        """Select a real PKHeX encounter for the species and generate from it."""
        if not hasattr(self, "preset_combo"):
            return
        if self._refresh_encounter_catalog(select_first=True):
            self.generate_from_selected_encounter(shiny=self.shiny_chk.isChecked())
        else:
            # Drop the previous record's method text first: refresh_live_preview
            # rebuilds the label from it, which would otherwise describe the
            # species that was selected before this one.
            self._last_generated_method = ""
            self._last_generated_label = ""
            self._fill_default_moves()

    def _fill_default_moves(self):
        nat_dex = int(self.species_combo.currentData() or 1)
        lvl = self.level_spin.value()

        # Override to ensure legal starting moves for iconic low-level static/gift encounters
        best_moves = []
        if lvl <= 5:
            if nat_dex in (1, 2, 3): best_moves = [33, 45] # Bulbasaur: Tackle, Growl
            elif nat_dex in (4, 5, 6): best_moves = [10, 45] # Charmander: Scratch, Growl
            elif nat_dex in (7, 8, 9): best_moves = [33, 39] # Squirtle: Tackle, Tail Whip
            elif nat_dex in (25, 26): best_moves = [84, 45] # Pikachu: Thunder Shock, Growl
            elif nat_dex in (133, 134, 135, 136, 196, 197): best_moves = [33, 39] # Eevee: Tackle, Tail Whip
            elif nat_dex == 147: best_moves = [35, 43] # Dratini: Wrap, Leer

        if not best_moves:
            learnset = GEN3_DB.get(nat_dex, {}).get("learnset", [])
            # Enforce Gen 3 strictly bounded move IDs (moves inside 1-354 only), excluding Follow Me (266)
            available_moves = [m[1] for m in learnset if m[0] <= lvl and m[1] <= 354 and m[1] != 266]
            best_moves = available_moves[-4:] if available_moves else []

        for m_id in best_moves:
            already_known = any(self.move_combos[i].currentData() == m_id for i in range(4))
            if already_known: continue

            for i in range(4):
                if self.move_combos[i].currentData() in (0, None):
                    idx = self.move_combos[i].findData(m_id)
                    if idx >= 0:
                        self.move_combos[i].setCurrentIndex(idx)
                        break
        self._refresh_move_type_badges()
        self.refresh_live_preview()

    def _original_auto_legalize(self):
        # 1. Grab selected IDs from UI
        dex_id = int(self.species_combo.currentData() or 1)
        current_game_text = self.game_combo.currentText()
        if current_game_text not in ("FireRed", "LeafGreen"):
            current_game_text = "FireRed"

        preset_idx = self.preset_combo.currentIndex()

        # 2. Base defaults (fallback if JSON is missing or incomplete)
        loc = 101 # Route 1
        met_lv = 5
        origin = current_game_text
        is_egg = False
        is_fateful = False

        # 3. Pull from Decoupled JSON Database
        enc_data = ENC_DB.get(dex_id)

        if enc_data:
            # Check for version specific data first based on currently selected game
            v_data = enc_data.get(current_game_text)
            if not v_data:
                # Fallback to the other version if the selected one isn't valid for this mon,
                # or use the "Any" table if it's identical across versions.
                v_data = enc_data.get("Any")
                if not v_data:
                    fallback_game = "LeafGreen" if current_game_text == "FireRed" else "FireRed"
                    v_data = enc_data.get(fallback_game)
                    if v_data:
                        origin = fallback_game # Force origin to the only legal game

            if v_data:
                loc = v_data.get("location_id", loc)
                met_lv = v_data.get("min_level", met_lv)

                # Check fateful encounter flag
                if v_data.get("type") == "fateful":
                    is_fateful = True

        # 4. Handle UI Preset Overrides (Eggs)
        if preset_idx in (1, 2):
            loc = 146
            met_lv = 5
            is_egg = True
        elif preset_idx == 0:
            pass # Standard auto-detect from JSON handled above

        # MIN_EVO_LVLS strictly retained to ensure Current Level logic applies
        # independently of the inherited Met Level.
        MIN_EVO_LVLS = {
            2:16, 3:32, 5:16, 6:36, 8:16, 9:36, 11:7, 12:10, 14:7, 15:10, 17:18, 18:36,
            20:20, 22:20, 24:22, 26:1, 28:22, 30:16, 31:16, 33:16, 34:16, 36:1, 38:1,
            40:1, 42:22, 44:21, 45:21, 47:24, 49:31, 51:26, 53:28, 55:33, 57:28, 59:1,
            61:25, 62:1, 64:16, 65:16, 67:28, 68:28, 70:21, 71:21, 73:30, 75:25, 76:25,
            78:40, 80:37, 82:30, 85:31, 87:34, 89:38, 91:1, 93:25, 94:25, 97:26, 99:28,
            101:30, 103:1, 105:28, 110:35, 112:42, 117:32, 119:33, 121:1, 130:20, 134:1,
            135:1, 136:1, 139:40, 141:40, 148:30, 149:55
        }

        cur_lv = max(met_lv, MIN_EVO_LVLS.get(dex_id, met_lv))

        # 5. Apply Values to UI
        self.game_combo.setCurrentIndex(max(0, self.game_combo.findText(origin)))
        self._populate_locations(int(self.game_combo.currentData() or 4))

        loc_idx = self.met_loc_combo.findData(loc)
        if loc_idx < 0:
            self.met_loc_combo.addItem(f"Unknown (ID {loc})", loc)
            loc_idx = self.met_loc_combo.count() - 1
        self.met_loc_combo.setCurrentIndex(loc_idx)

        self.met_lvl_spin.setValue(met_lv)
        if self.level_spin.value() < cur_lv:
            self.level_spin.setValue(cur_lv)

        old_sync = getattr(self, "_syncing", False)
        self._syncing = True
        self.egg_origin_chk.setChecked(is_egg)
        self.hatched_chk.setChecked(is_egg)
        self.hatched_chk.setEnabled(is_egg)
        self._syncing = old_sync
        self._update_egg_ui()

        if hasattr(self, "fateful_chk"):
            self.fateful_chk.setChecked(is_fateful)

        target_ball = 5 if loc == 136 else 4
        if loc == 253:
            target_ball = 4

        ball_idx = self.ball_combo.findData(target_ball)
        if ball_idx >= 0:
            self.ball_combo.setCurrentIndex(ball_idx)

        temp_pk = PK3()
        temp_pk.Species = dex_id
        pi = temp_pk.PersonalInfo
        ui_growth_idx = PK_TO_UI_GROWTH.get(pi.EXPGrowth, 0)
        self.growth_combo.setCurrentIndex(ui_growth_idx)
        self.exp_spin.setValue(calc_exp_for_level(self.level_spin.value(), ui_growth_idx))

        # Roll PID/IVs automatically based on newly applied data
        cur_shiny = self.shiny_chk.isChecked() if hasattr(self, "shiny_chk") else False
        self.roll_legal_pid_ivs(shiny=cur_shiny)

    def browse_pk3(self):
        start = str(app_prefs.get("last_dir", self.last_dir))
        if not Path(start).is_dir():
            start = self.last_dir
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Gen 3 Pokémon", start, "Gen 3 Pokemon (*.pk3 *.ek3)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if path:
            self.last_dir = str(Path(path).parent)
            self.load_file(path)

    def show_recent_menu(self):
        menu = QMenu(self)
        recent = app_prefs.recent_files(8)
        if not recent:
            action = menu.addAction("No recent .pk3 files")
            action.setEnabled(False)
        for path in recent:
            action = menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, target=path: self.load_file(target)
            )
        menu.exec(self.btn_recent.mapToGlobal(QPoint(0, self.btn_recent.height())))

    def load_file(self, filepath: str):
        p = Path(filepath)
        if not p.exists() or p.stat().st_size < 80:
            QMessageBox.warning(self, "Invalid File", "Selected file is missing or smaller than 80 bytes.")
            return

        self.current_path = p
        self.path_edit.setText(str(p))
        sound.play("editor_open")
        self.last_dir = str(p.parent)
        app_prefs.add_recent(p)
        app_prefs.update(last_dir=self.last_dir)
        self.raw_data = bytearray(p.read_bytes())
        if len(self.raw_data) < 100:
            self.raw_data.extend(b"\x00" * (100 - len(self.raw_data)))

        pid, otid = struct.unpack("<II", self.raw_data[0:8])
        tid = otid & 0xFFFF
        sid = (otid >> 16) & 0xFFFF

        chk = struct.unpack("<H", self.raw_data[0x1C:0x1E])[0]
        sub_raw = self.raw_data[0x20:0x50]
        raw_sum = sum(struct.unpack("<24H", sub_raw)) & 0xFFFF
        order = SUBSTRUCT_ORDER[pid % 24]

        if raw_sum == chk:
            self.was_encrypted = False
            dec = sub_raw
            sp0, it0, _ = struct.unpack("<HHI", dec[0:8])
            orig3 = struct.unpack("<H", dec[36 + 2 : 36 + 4])[0]
            unshuf_ok = (1 <= sp0 <= 411) and (it0 <= 376) and (1 <= ((orig3 >> 11) & 0xF) <= 12)
            self.was_shuffled = not unshuf_ok
        else:
            self.was_encrypted = True
            key = pid ^ otid
            words = struct.unpack("<12I", sub_raw)
            dec = b"".join(struct.pack("<I", w ^ key) for w in words)
            sp_test = struct.unpack("<H", dec[order[0]*12 : order[0]*12 + 2])[0]
            self.was_shuffled = (1 <= sp_test <= 411)

        g_i, a_i, e_i, m_i = order if self.was_shuffled else (0, 1, 2, 3)
        self.block_g = bytearray(dec[g_i*12 : (g_i+1)*12])
        self.block_a = bytearray(dec[a_i*12 : (a_i+1)*12])
        self.block_e = bytearray(dec[e_i*12 : (e_i+1)*12])
        self.block_m = bytearray(dec[m_i*12 : (m_i+1)*12])

        internal_sp, item_id, exp, pp_bonuses, friend = struct.unpack("<HHIBB", self.block_g[0:10])
        nat_dex = internal_to_nat(internal_sp)
        self._cry_nat_dex = int(nat_dex)
        _, met_loc, origins, iv_word = struct.unpack("<BBHI", self.block_m[0:8])
        file_abil_bit = (iv_word >> 31) & 1

        old_sync = getattr(self, "_syncing", False)
        self._syncing = True

        idx_sp = self.species_combo.findData(nat_dex)
        if idx_sp != -1:
            self.species_combo.setCurrentIndex(idx_sp)

        temp_pk = PK3()
        temp_pk.Species = nat_dex
        pi = temp_pk.PersonalInfo
        gender_ratio = pi.Gender

        if gender_ratio not in (0, 254, 255):
            self.gender_combo.setEnabled(True)
            self.gender_combo.setCurrentIndex(2 if (pid & 0xFF) < gender_ratio else 1)
        else:
            self.gender_combo.setCurrentIndex(0)
            self.gender_combo.setEnabled(False)

        self._refresh_species_abilities(nat_dex, preferred_slot=file_abil_bit)

        # Gen 3 eggs store a Japanese タマゴ the Western table cannot encode, so
        # ask PKHeX for the text, then remember the file's own name bytes: an
        # untouched field saves back exactly what the file had.
        name_pk = pk3_from_bytes(bytes(self.raw_data))
        if name_pk is not None:
            decoded_nick = str(name_pk.Nickname).rstrip()
            self.nick_edit.setText(decoded_nick or decode_gen3_str(self.raw_data[0x08:0x12]))
        else:
            self.nick_edit.setText(decode_gen3_str(self.raw_data[0x08:0x12]))
        self.ot_edit.setText(decode_gen3_str(self.raw_data[0x14:0x1B]))
        self._generated_nick_text = self.nick_edit.text().strip()
        self._generated_nick_raw = bytes(self.raw_data[0x08:0x12])
        self._generated_ot_text = self.ot_edit.text().strip()
        self._generated_ot_raw = bytes(self.raw_data[0x14:0x1B])
        self.tid_spin.setValue(tid)
        self.sid_spin.setValue(sid)
        # The open document now belongs to whichever trainer the file has.
        # This never touches the locked My Trainer profile, so a friend's
        # Pokémon keeps her OT/TID/SID when edited and saved back.
        self._trainer_identity = (
            self.ot_edit.text().strip() or "TRAINER", int(tid), int(sid)
        )
        self._identity_from_fixed_source = False
        self._refresh_my_trainer_row()
        self.pid_edit.setText(f"{pid:08X}")
        self.nature_combo.setCurrentIndex(pid % 25)

        idx_item = self.item_combo.findData(item_id)
        if idx_item == -1:
            self.item_combo.addItem(f"Item #{item_id}", item_id)
            idx_item = self.item_combo.count() - 1
        self.item_combo.setCurrentIndex(idx_item)

        inferred_lvl, inferred_rate = infer_level_and_rate(exp)
        if len(self.raw_data) >= 85 and 1 <= self.raw_data[0x54] <= 100:
            inferred_lvl = self.raw_data[0x54]

        ui_growth_idx = PK_TO_UI_GROWTH.get(pi.EXPGrowth, 0)
        self.growth_combo.setCurrentIndex(ui_growth_idx)

        self.level_spin.setValue(inferred_lvl)
        self.exp_spin.setValue(exp)
        self.friend_spin.setValue(friend)

        m1, m2, m3, m4, pp1, pp2, pp3, pp4 = struct.unpack("<HHHHBBBB", self.block_a)
        for i, (mid, cur_pp) in enumerate(zip((m1, m2, m3, m4), (pp1, pp2, pp3, pp4))):
            idx_m = self.move_combos[i].findData(mid)
            if idx_m != -1:
                self.move_combos[i].setCurrentIndex(idx_m)
            up_count = (pp_bonuses >> (i * 2)) & 3
            self.pp_up_combos[i].setCurrentIndex(up_count)
            max_pp = calc_max_pp(mid, up_count)
            self.pp_spins[i].setMaximum(max(64, max_pp))
            self.pp_spins[i].setValue(cur_pp if 0 < cur_pp <= max_pp else max_pp)
            self.max_pp_lbls[i].setText(f"/ {max_pp:2d} PP")

        ev_hp, ev_atk, ev_def, ev_spe, ev_spa, ev_spd = struct.unpack("<6B", self.block_e[0:6])
        self.ev_spins["HP"].setValue(ev_hp)
        self.ev_spins["Atk"].setValue(ev_atk)
        self.ev_spins["Def"].setValue(ev_def)
        self.ev_spins["SpA"].setValue(ev_spa)
        self.ev_spins["SpD"].setValue(ev_spd)
        self.ev_spins["Spe"].setValue(ev_spe)

        game_id = (origins >> 7) & 0xF
        g_idx = self.game_combo.findData(game_id)
        if g_idx != -1:
            self.game_combo.setCurrentIndex(g_idx)

        self._populate_locations(game_id)

        idx_loc = self.met_loc_combo.findData(int(met_loc))
        if idx_loc != -1:
            self.met_loc_combo.setCurrentIndex(idx_loc)
        else:
            self.met_loc_combo.addItem(f"Unknown Location (ID {met_loc})", int(met_loc))
            self.met_loc_combo.setCurrentIndex(self.met_loc_combo.count() - 1)

        old_iv_word = struct.unpack("<I", self.block_m[4:8])[0]

        is_unhatched = bool(old_iv_word & (1 << 30))
        met_lvl_raw = origins & 0x7F
        day_care_loc = DAY_CARE_LOCS.get(game_id, 146)
        is_hatched = (met_lvl_raw == 0) and (int(met_loc) == day_care_loc) and not is_unhatched
        self._record_is_egg = is_unhatched

        self.egg_origin_chk.blockSignals(True)
        self.hatched_chk.blockSignals(True)

        if is_unhatched:
            self.egg_origin_chk.setChecked(True)
            self.hatched_chk.setChecked(False)
        elif is_hatched:
            self.egg_origin_chk.setChecked(True)
            self.hatched_chk.setChecked(True)
        else:
            self.egg_origin_chk.setChecked(False)
            self.hatched_chk.setChecked(False)

        self.hatched_chk.setEnabled(self.egg_origin_chk.isChecked())
        self.egg_origin_chk.blockSignals(False)
        self.hatched_chk.blockSignals(False)

        self.met_lvl_spin.setValue(met_lvl_raw)
        self._update_egg_ui()

        old_ribbons = struct.unpack("<I", self.block_m[8:12])[0]
        self.fateful_chk.setChecked(bool(old_ribbons & (1 << 31)))
        ball_id = (origins >> 11) & 0xF

        b_idx = self.ball_combo.findData(ball_id)
        if b_idx != -1:
            self.ball_combo.setCurrentIndex(b_idx)

        self.iv_spins["HP"].setValue(iv_word & 31)
        self.iv_spins["Atk"].setValue((iv_word >> 5) & 31)
        self.iv_spins["Def"].setValue((iv_word >> 10) & 31)
        self.iv_spins["Spe"].setValue((iv_word >> 15) & 31)
        self.iv_spins["SpA"].setValue((iv_word >> 20) & 31)
        self.iv_spins["SpD"].setValue((iv_word >> 25) & 31)

        self._syncing = old_sync

        self._last_generated_method = ""
        self._last_generated_label = ""
        self._sync_form_combo_from_pid(pid)
        self._refresh_encounter_catalog(select_first=False, preserve=False)
        # Show the source this record came from without rewriting the loaded
        # fields; the picker then has a real encounter selected if one matches.
        self._select_matching_encounter()

        for i in range(4):
            self._on_move_or_ppup_changed(i)

        self.refresh_live_preview()

    def apply_external_spread(self, pid: int, ivs: tuple):
        old_sync = getattr(self, "_syncing", False)
        self._syncing = True
        self.pid_edit.setText(f"{pid:08X}")
        self.nature_combo.setCurrentIndex(pid % 25)
        if self.ability_combo.count() > 1:
            self.ability_combo.setCurrentIndex(pid & 1)
        else:
            self.ability_combo.setCurrentIndex(0)
        for name, val in zip(["HP", "Atk", "Def", "SpA", "SpD", "Spe"], ivs):
            self.iv_spins[name].setValue(val)
        self._syncing = old_sync
        self.refresh_live_preview()

    def roll_legal_pid_ivs(self, shiny: bool = True):
        """Generate from the chosen PKHeX encounter, or fall back to the legacy RNG."""
        if self._selected_encounter() is None:
            self._select_matching_encounter()
        if self._selected_encounter() is not None:
            self.generate_from_selected_encounter(shiny=shiny)
            return
        self._roll_legacy_pid_ivs(shiny=shiny)

    def _roll_legacy_pid_ivs(self, shiny: bool = True):
        tid = self.tid_spin.value()
        sid = self.sid_spin.value()
        target_nat_idx = int(self.nature_combo.currentData() or 0)
        has_two_abils = self.ability_combo.count() > 1
        target_abil_slot = int(self.ability_combo.currentData() or 0)

        target_gender = self.gender_combo.currentText()
        target_dex_id = int(self.species_combo.currentData() or 1)

        temp_pk = PK3()
        temp_pk.Species = target_dex_id
        gender_ratio = temp_pk.PersonalInfo.Gender

        loc_val = self.met_loc_combo.currentData()
        loc = int(loc_val) if loc_val is not None else 0

        is_unhatched = self.egg_origin_chk.isChecked() and not self.hatched_chk.isChecked()
        is_hatched = self.egg_origin_chk.isChecked() and self.hatched_chk.isChecked()
        is_egg = is_unhatched or is_hatched

        if is_egg:
            ivs = (
                random.randint(10, 31), random.randint(10, 31), random.randint(10, 31),
                random.randint(10, 31), random.randint(10, 31), random.randint(10, 31)
            )

            while True:
                pid = random.randint(0, 0xFFFFFFFF)
                if pid % 25 == target_nat_idx:
                    if not has_two_abils or (pid & 1) == target_abil_slot:
                        if target_gender != "Any" and gender_ratio not in (0, 254, 255):
                            gender_byte = pid & 0xFF
                            is_female = gender_byte < gender_ratio
                            if target_gender == "Male" and is_female:
                                continue
                            if target_gender == "Female" and not is_female:
                                continue

                        is_sh = ((tid ^ sid ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8)
                        if is_sh == shiny:
                            self.apply_external_spread(pid, ivs)
                            return

        s = random.randint(0, 0xFFFFFFFF)
        limit = 15_000_000 if shiny else 350_000

        for _ in range(limit):
            s1 = (s * 0x41C64E6D + 0x6073) & 0xFFFFFFFF
            s2 = (s1 * 0x41C64E6D + 0x6073) & 0xFFFFFFFF

            # Method 1 generation sequence
            pid_lower = s1 >> 16
            pid_upper = s2 >> 16
            pid = (pid_upper << 16) | pid_lower

            is_sh = ((tid ^ sid ^ pid_upper ^ pid_lower) < 8)

            if is_sh == shiny:
                if (pid % 25) == target_nat_idx:
                    if not has_two_abils or (pid & 1) == target_abil_slot:
                        if target_gender != "Any" and gender_ratio not in (0, 254, 255):
                            gender_byte = pid & 0xFF
                            is_female = gender_byte < gender_ratio
                            if target_gender == "Male" and is_female:
                                s = s1
                                continue
                            if target_gender == "Female" and not is_female:
                                s = s1
                                continue

                        s3 = (s2 * 0x41C64E6D + 0x6073) & 0xFFFFFFFF
                        s4 = (s3 * 0x41C64E6D + 0x6073) & 0xFFFFFFFF

                        iv1, iv2 = s3 >> 16, s4 >> 16

                        ivs = (
                            iv1 & 31, (iv1 >> 5) & 31, (iv1 >> 10) & 31,
                            (iv2 >> 5) & 31, (iv2 >> 10) & 31, iv2 & 31
                        )

                        if shiny:
                            self.apply_external_spread(pid, ivs)
                            return
                        else:
                            if sum(ivs) >= 80:
                                self.apply_external_spread(pid, ivs)
                                return
            s = s1

    def build_pk3_bytes(self, silent: bool = False) -> bytes | None:
        try:
            pid = int(self.pid_edit.text().strip(), 16) & 0xFFFFFFFF
        except ValueError:
            if not silent:
                QMessageBox.warning(self, "Bad PID", "PID must be a valid 8-digit hex number.")
            return None

        tid = self.tid_spin.value() & 0xFFFF
        sid = self.sid_spin.value() & 0xFFFF

        if hasattr(self, 'raw_data') and self.raw_data and len(self.raw_data) >= 80:
            raw = bytearray(self.raw_data)
        else:
            raw = bytearray(100)
            raw[0x12] = 0x02

        struct.pack_into("<I", raw, 0x00, pid)
        struct.pack_into("<I", raw, 0x04, (sid << 16) | tid)

        nick = self.nick_edit.text().strip() or self.species_map.get(int(self.species_combo.currentData() or 1), "PKMN").upper()
        nick_fallback = self.species_map.get(int(self.species_combo.currentData() or 1), "PKMN").upper()
        raw[0x08:0x12] = encode_or_preserve_gen3_str(
            nick, 10, getattr(self, "_generated_nick_text", "") or nick_fallback,
            getattr(self, "_generated_nick_raw", None),
        )

        is_unhatched = self.egg_origin_chk.isChecked() and not self.hatched_chk.isChecked()
        is_hatched = self.egg_origin_chk.isChecked() and self.hatched_chk.isChecked()
        stored_flags = self.raw_data[0x13] if self.raw_data else 0x02
        # Bit 0 marks a bad egg; bit 1 is "has species" and bit 2 "is egg".
        # Own the last two so hatching a record cannot leave a stale egg flag
        # behind in the saved file.
        raw[0x13] = (stored_flags & ~0x06) | (0x06 if is_unhatched else 0x02)

        ot = self.ot_edit.text().strip()
        raw[0x14:0x1B] = encode_or_preserve_gen3_str(
            ot, 7, getattr(self, "_generated_ot_text", ""),
            getattr(self, "_generated_ot_raw", None),
        )

        block_g = bytearray(self.block_g) if hasattr(self, 'block_g') else bytearray(12)
        block_a = bytearray(self.block_a) if hasattr(self, 'block_a') else bytearray(12)
        block_e = bytearray(self.block_e) if hasattr(self, 'block_e') else bytearray(12)
        block_m = bytearray(self.block_m) if hasattr(self, 'block_m') else bytearray(12)

        species_id = int(self.species_combo.currentData() or 1)
        internal_sp = nat_to_internal(species_id)
        struct.pack_into("<H", block_g, 0, internal_sp)
        struct.pack_into("<H", block_g, 2, int(self.item_combo.currentData() or 0))
        struct.pack_into("<I", block_g, 4, self.exp_spin.value())

        pp_ups = (self.pp_up_combos[0].currentIndex()) | \
                 (self.pp_up_combos[1].currentIndex() << 2) | \
                 (self.pp_up_combos[2].currentIndex() << 4) | \
                 (self.pp_up_combos[3].currentIndex() << 6)
        block_g[8] = pp_ups
        block_g[9] = self.friend_spin.value()

        struct.pack_into("<H", block_a, 0, int(self.move_combos[0].currentData() or 0))
        struct.pack_into("<H", block_a, 2, int(self.move_combos[1].currentData() or 0))
        struct.pack_into("<H", block_a, 4, int(self.move_combos[2].currentData() or 0))
        struct.pack_into("<H", block_a, 6, int(self.move_combos[3].currentData() or 0))
        block_a[8] = self.pp_spins[0].value()
        block_a[9] = self.pp_spins[1].value()
        block_a[10] = self.pp_spins[2].value()
        block_a[11] = self.pp_spins[3].value()

        block_e[0] = self.ev_spins["HP"].value()
        block_e[1] = self.ev_spins["Atk"].value()
        block_e[2] = self.ev_spins["Def"].value()
        block_e[3] = self.ev_spins["Spe"].value()
        block_e[4] = self.ev_spins["SpA"].value()
        block_e[5] = self.ev_spins["SpD"].value()

        loc_val = self.met_loc_combo.currentData()
        block_m[1] = int(loc_val) if loc_val is not None else 0

        met_lvl = 0 if (is_hatched or is_unhatched) else self.met_lvl_spin.value()

        if hasattr(self, 'block_m') and self.block_m:
            old_origins = struct.unpack("<H", self.block_m[2:4])[0]
            ot_gender_bit = old_origins & 0x8000
        else:
            ot_gender_bit = 0

        origins = (met_lvl & 0x7F) | (int(self.game_combo.currentData() or 4) << 7) | (int(self.ball_combo.currentData() or 4) << 11) | ot_gender_bit
        struct.pack_into("<H", block_m, 2, origins)

        base_ivs = self.iv_spins["HP"].value() | \
                   (self.iv_spins["Atk"].value() << 5) | \
                   (self.iv_spins["Def"].value() << 10) | \
                   (self.iv_spins["Spe"].value() << 15) | \
                   (self.iv_spins["SpA"].value() << 20) | \
                   (self.iv_spins["SpD"].value() << 25)

        iv_word = base_ivs
        if is_unhatched:
            iv_word |= (1 << 30)

        from PKHeX.Core import PK3
        temp_pk_ab = PK3()
        temp_pk_ab.Species = species_id
        pi_ab = temp_pk_ab.PersonalInfo
        has_two_gen3_abils = (pi_ab.Ability1 != pi_ab.Ability2) and (pi_ab.Ability2 > 0)

        # Ability is stored as bit 31 of the IV word, not inferred from the
        # PID.  Fixed encounters (notably in-game trades) can legitimately
        # have an ability slot that contradicts PID bit 0, and PKHeX accepts
        # the encounter's own ability value.  Encode the user's slot so the
        # UI, generated record, and legality check agree.
        ability_slot = int(self.ability_combo.currentData() or 0) if has_two_gen3_abils else 0
        if not has_two_gen3_abils and species_id in PID_SOURCED_ABILITY_SPECIES:
            # PKHeX still follows the PID for these three: their two slots hold
            # the same ability, but the games store the flag from PID bit 0.
            ability_slot = pid & 1
        if ability_slot:
            iv_word |= (1 << 31)
        else:
            iv_word &= ~(1 << 31)

        struct.pack_into("<I", block_m, 4, iv_word)

        if hasattr(self, 'block_m') and self.block_m:
            old_ribbons = struct.unpack("<I", self.block_m[8:12])[0]
        else:
            old_ribbons = 0

        if self.fateful_chk.isChecked():
            old_ribbons |= (1 << 31)
        else:
            old_ribbons &= ~(1 << 31)

        struct.pack_into("<I", block_m, 8, old_ribbons)

        order = SUBSTRUCT_ORDER[pid % 24]
        ordered_blocks = [None] * 4
        ordered_blocks[order[0]] = block_g
        ordered_blocks[order[1]] = block_a
        ordered_blocks[order[2]] = block_e
        ordered_blocks[order[3]] = block_m

        sub_raw = bytearray()
        for b in ordered_blocks:
            sub_raw.extend(b)

        chk = sum(struct.unpack("<24H", sub_raw)) & 0xFFFF
        struct.pack_into("<H", raw, 0x1C, chk)

        key = pid ^ ((sid << 16) | tid)
        words = struct.unpack("<12I", sub_raw)
        enc_words = [w ^ key for w in words]
        enc_sub = struct.pack("<12I", *enc_words)

        raw[0x20:0x50] = enc_sub

        lvl = self.level_spin.value()
        iv_dict = {k: s.value() for k, s in self.iv_spins.items()}
        ev_dict = {k: s.value() for k, s in self.ev_spins.items()}
        max_hp, atk, dfn, spe, spa, spd = calc_gen3_party_stats(
            species_id, lvl, pid, iv_dict, ev_dict
        )
        struct.pack_into(
            "<IBBHHHHHHH", raw, 0x50,
            0, lvl, 0xFF, max_hp, max_hp, atk, dfn, spe, spa, spd
        )

        return bytes(raw)

    def save_pk3(self, overwrite: bool = True) -> str | None:
        built = self.build_pk3_bytes()
        if not built:
            return None

        nat_dex = int(self.species_combo.currentData() or 1)
        sp_clean = self.nick_edit.text().strip() or "PKMN"
        default_name = f"{nat_dex:03d}_{sp_clean}.pk3"

        if overwrite and self.current_path:
            dest = self.current_path
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save .pk3 File", str(Path(self.last_dir) / default_name), "Gen 3 Pokemon (*.pk3)",
                options=QFileDialog.Option.DontUseNativeDialog
            )
            if not path:
                return None

            if not path.lower().endswith(('.pk3', '.ek3')):
                path += ".pk3"

            dest = Path(path)
            self.last_dir = str(dest.parent)

        user_data.snapshot(f"Save {dest.name} from the editor")
        dest.write_bytes(built)
        sound.play("editor_save")
        app_prefs.add_recent(dest)
        app_prefs.update(last_dir=self.last_dir)
        self.current_path = dest
        self.path_edit.setText(str(dest))
        return str(dest)

    def save_and_send_slot2(self):
        slot2_dir = paths.SLOT2_DIR
        slot2_dir.mkdir(exist_ok=True)

        existing = list(slot2_dir.glob("*.pk3"))
        if existing:
            try:
                name = existing[0].stem.split('_')[1]
            except:
                name = "A Pokémon"
            QMessageBox.warning(self, "Trade Slot Occupied", f"{name} is still being offered for Trade.\n\nPlease send it to Bill's PC from the Trade Center before trying to trade another Pokémon.")
            return

        built = self.build_pk3_bytes()
        if not built: return

        nat_dex = int(self.species_combo.currentData() or 1)
        sp_clean = self.nick_edit.text().strip() or "PKMN"
        try:
            pid = int(self.pid_edit.text().strip(), 16)
        except:
            pid = 0

        pid_hex = f"{pid:08X}"
        dest = slot2_dir / f"{nat_dex:03d}_{sp_clean}_{pid_hex}.pk3"

        user_data.snapshot(f"Send {dest.name} to Trade Slot 2")
        dest.write_bytes(built)
        sound.play("editor_save")
        self.send_to_slot2.emit(str(dest))
        QMessageBox.information(self, "Loaded into Trade Center", f"Saved and sent to Trade Slot:\n{dest.name}")

    def save_and_send_pc(self):
        built = self.build_pk3_bytes()
        if not built: return

        nat_dex = int(self.species_combo.currentData() or 1)
        species_name = self.species_map.get(nat_dex, "PKMN").upper().replace(" ", "_")

        try:
            pid = int(self.pid_edit.text().strip(), 16)
        except ValueError:
            pid = 0

        tid = self.tid_spin.value()
        sid = self.sid_spin.value()
        is_shiny = ((tid ^ sid ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8)

        nature_name = NATURES[pid % 25].upper()
        shiny_suffix = "_s" if is_shiny else ""
        pid_hex = f"{pid:08X}"

        # Format: SKARMORY_IMPISH_s_2153C299.pk3
        filename = f"{species_name}_{nature_name}{shiny_suffix}_{pid_hex}.pk3"

        # This button is deliberately a COPY operation.  A user can generate a
        # mon, deposit it, change its nature/level/species and deposit again;
        # matching the filename or PID to an existing PC file used to overwrite
        # that earlier Pokémon.  Bill's PC now receives every click as a new
        # slot entry, with tab_pc adding _1/_2 if the filename already exists.
        user_data.snapshot(f"Deposit {filename} from the editor")
        temp_path = DATA_DIR / filename
        temp_path.write_bytes(built)

        win = self.window()
        if hasattr(win, "pc_tab"):
            win.pc_tab.store_pokemon(str(temp_path), move_file=True)
            # Leave current_path alone: this click made a new stored copy, so
            # "Save Over Current" still refers to the file the editor loaded.
            QMessageBox.information(
                self, "Sent to PC",
                f"Deposited {species_name} as a new Pokémon in Bill's PC.",
            )
        else:
            QMessageBox.warning(self, "Error", "Could not locate Bill's PC storage interface.")

    def _play_current_cry(self):
        if self._cry_nat_dex:
            sound.play_cry(self._cry_nat_dex)

    def refresh_live_preview(self):
        nat_dex = int(self.species_combo.currentData() or 1)
        self._cry_nat_dex = int(nat_dex)
        lvl = self.level_spin.value()
        nick = self.nick_edit.text().strip() or self.species_map.get(nat_dex, "PKMN").upper()
        try:
            pid = int(self.pid_edit.text().strip(), 16)
        except ValueError:
            pid = 0

        tid = self.tid_spin.value()
        sid = self.sid_spin.value()
        shiny = ((tid ^ sid ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8)
        nat_idx = pid % 25
        abil_text = self.ability_combo.currentText()

        if hasattr(self, "shiny_chk") and self.shiny_chk.isChecked() != shiny:
            self.shiny_chk.blockSignals(True)
            self.shiny_chk.setChecked(shiny)
            self.shiny_chk.blockSignals(False)

        temp_pk = PK3()
        temp_pk.Species = nat_dex
        gender_ratio = temp_pk.PersonalInfo.Gender
        if gender_ratio not in (0, 254, 255):
            is_female = (pid & 0xFF) < gender_ratio
            gender_sym = "♀" if is_female else "♂"
            self.summary_gender_lbl.setText(gender_sym)
            self.summary_gender_lbl.setStyleSheet(
                "font-family: '%s'; font-size: 16px; color: %s;"
                " border: none; background: transparent; padding: 1px 0 2px 0;"
                % (theme.FONT_GBA, theme.RED_DARK if is_female else theme.BLUE)
            )
            self.summary_gender_lbl.setToolTip("Female" if is_female else "Male")
            self.summary_gender_lbl.setVisible(True)
        else:
            self.summary_gender_lbl.clear()
            self.summary_gender_lbl.setVisible(False)

        self.summary_star_lbl.setText("★" if shiny else "")
        self.summary_star_lbl.setVisible(bool(shiny))
        self.summary_title_lbl.setText(f"Lv. {lvl} {nick}")
        self.summary_ball_badge.set_ball(int(self.ball_combo.currentData() or 4))
        self.summary_item_badge.set_item(int(self.item_combo.currentData() or 0))

        # Construct Authentic Trainer Memo
        nature_name = NATURES[nat_idx]
        met_lv = self.met_lvl_spin.value()
        met_loc = self.met_loc_combo.currentText()
        if "(ID" in met_loc:
            met_loc = met_loc.split(" (ID")[0]

        is_unhatched = self.egg_origin_chk.isChecked() and not self.hatched_chk.isChecked()
        is_hatched = self.egg_origin_chk.isChecked() and self.hatched_chk.isChecked()

        if is_unhatched:
            memo_text = f"An Odd Pokémon Egg.\n\n"
        elif is_hatched:
            memo_text = f"<span style='color:{theme.RED_DARK};'>{nature_name}</span> nature.<br>Hatched at Lv {met_lv}."
        else:
            memo_text = f"<span style='color:{theme.RED_DARK};'>{nature_name}</span> nature.<br>Met in <span style='color:{theme.RED_DARK};'>{met_loc}</span> at Lv {met_lv}."

        self.trainer_memo_lbl.setText(memo_text)

        iv_dict = {k: s.value() for k, s in self.iv_spins.items()}
        ev_dict = {k: s.value() for k, s in self.ev_spins.items()}
        total_evs = sum(ev_dict.values())
        rem_evs = max(0, 510 - total_evs)
        if hasattr(self, "ev_total_lbl"):
            self.ev_total_lbl.setText(f"EV Total: {total_evs:3d} / 510 ({rem_evs:3d} Remaining)")
            ev_col = theme.ORANGE_DARK if total_evs == 510 else theme.GREEN_DARK
            self.ev_total_lbl.setStyleSheet(
                f"color: {ev_col}; font-weight: bold; font-family: '{theme.FONT_DS}'; font-size: 12px;"
            )

        max_hp, atk, dfn, spe, spa, spd = calc_gen3_party_stats(
            nat_dex, lvl, pid, iv_dict, ev_dict
        )
        vals = {"HP": f"{max_hp}/{max_hp}", "Atk": str(atk), "Def": str(dfn), "SpA": str(spa), "SpD": str(spd), "Spe": str(spe)}
        inc_idx = nat_idx // 5
        dec_idx = nat_idx % 5
        pos_map = {"Atk": 0, "Def": 1, "Spe": 2, "SpA": 3, "SpD": 4}

        # Update Classic Stat Block
        for k, text_val in vals.items():
            color = theme.INK
            if k in pos_map and inc_idx != dec_idx:
                if pos_map[k] == inc_idx:
                    color = theme.RED_DARK  # Stat increased by nature
                elif pos_map[k] == dec_idx:
                    color = theme.BLUE  # Stat decreased by nature

            # Use the internal key mapped to the UI labels
            self.stat_readout_lbls[k].setText(text_val)
            self.stat_readout_lbls[k].setStyleSheet(
                f"font-size: 15px; color: {color}; border: none; background: transparent; font-family: '{theme.FONT_DS}';"
            )

        # Update EXP Block
        exp_val = self.exp_spin.value()
        self.exp_val_lbl.setText(str(exp_val))

        ui_growth_idx = self.growth_combo.currentIndex()
        next_lvl_exp = calc_exp_for_level(lvl + 1, ui_growth_idx)
        if lvl >= 100:
            self.next_val_lbl.setText("0")
        else:
            self.next_val_lbl.setText(str(max(0, next_lvl_exp - exp_val)))

        option = self._selected_encounter()
        if hasattr(self, "rng_method_lbl"):
            if self._last_generated_method:
                detail = f"PKHeX: {self._last_generated_method}"
                if option is not None:
                    detail += f" · {option.category.title()}"
                self.rng_method_lbl.setText(detail)
            elif option is not None:
                self.rng_method_lbl.setText(
                    f"Selected: {option.category.title()} — click Generate to roll a legal spread"
                )
            else:
                has_encounters = hasattr(self, "preset_combo") and any(
                    isinstance(self.preset_combo.itemData(i), EncounterOption)
                    for i in range(self.preset_combo.count())
                )
                self.rng_method_lbl.setText(
                    "Select a PKHeX encounter to generate" if has_encounters
                    else "No Gen 3 encounter for this species"
                )
            self.rng_method_lbl.setStyleSheet(
            "font-weight: bold; color: %s; padding-top: 2px; font-size: 12px;" % theme.NAVY
        )
            self.rng_method_lbl.setToolTip(self._last_generated_label or "")

        # Instantly load completely offline sprites (form-aware for Unown).
        if self.sprite_lbl.movie(): self.sprite_lbl.movie().stop(); self.sprite_lbl.setMovie(None)

        form = int(self.form_combo.currentData() or 0) if nat_dex == 201 else 0
        gif_path = animated_sprite_path(nat_dex, form, shiny)

        if gif_path.exists():
            self._current_movie = QMovie(str(gif_path))
            self.sprite_lbl.setMovie(self._current_movie)
            self._current_movie.start()
        else:
            self.sprite_lbl.setPixmap(QPixmap())

        self._schedule_legality()
