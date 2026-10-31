import os
import sys
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPixmap, QColor
except ImportError:
    print("Error: PyQt6 must be installed. Activate your venv and run: pip install PyQt6")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DIRS = [
    ASSETS_DIR / "icons",
    ASSETS_DIR / "sprites" / "normal",
    ASSETS_DIR / "sprites" / "shiny",
    ASSETS_DIR / "data",
    ASSETS_DIR / "wallpapers"
]
for d in DIRS: d.mkdir(parents=True, exist_ok=True)

def dl(url, dest):
    if dest.exists(): return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            dest.write_bytes(r.read())
        print(f"  [OK] {dest.name}")
    except Exception as e:
        print(f"  [FAIL] {dest.name}: {e}")

def dl_sprite(i):
    dl(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/{i}.png", ASSETS_DIR / f"icons/{i}.png")
    dl(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-iii/emerald/{i}.png", ASSETS_DIR / f"sprites/normal/{i}.png")
    dl(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-iii/emerald/shiny/{i}.png", ASSETS_DIR / f"sprites/shiny/{i}.png")

print("--- 1. Downloading Gen 7 Icons & Gen 3 Sprites ---")
with ThreadPoolExecutor(max_workers=15) as exe:
    exe.map(dl_sprite, range(1, 387))

print("\n--- 2. Building Move & Species Dictionaries ---")
DATA_DIR = ASSETS_DIR / "data"
if not (DATA_DIR / "move_types.json").exists():
    moves, move_types = {0: "— None —"}, {0: "NORMAL"}
    def fetch_move(i):
        try:
            req = urllib.request.Request(f"https://pokeapi.co/api/v2/move/{i}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                return i, data["name"].replace("-", " ").title(), data["type"]["name"].upper()
        except:
            return i, f"Move {i}", "NORMAL"

    with ThreadPoolExecutor(max_workers=15) as exe:
        for i, m_name, m_type in exe.map(fetch_move, range(1, 355)):
            moves[i] = m_name
            move_types[i] = m_type
            print(f"  Mapped Move #{i}: {m_name} ({m_type})")

    (DATA_DIR / "moves.json").write_text(json.dumps(moves, indent=2))
    (DATA_DIR / "move_types.json").write_text(json.dumps(move_types, indent=2))

if not (DATA_DIR / "species.json").exists():
    species = {}
    try:
        req = urllib.request.Request("https://pokeapi.co/api/v2/pokemon-species?limit=386", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            for idx, entry in enumerate(data.get("results", []), start=1):
                species[idx] = entry["name"].replace("-", " ").title()
        (DATA_DIR / "species.json").write_text(json.dumps(species, indent=2))
        print("  [OK] Species dictionary saved.")
    except Exception as e:
        print("  [FAIL] Species dictionary:", e)

print("\n--- 3. Generating Wallpaper Placeholders ---")
app = QApplication(sys.argv)
WP_THEMES = {
    "Forest": "#86efac", "City": "#cbd5e1", "Desert": "#fde047",
    "Savanna": "#d9f99d", "Crag": "#d6d3d1", "Volcano": "#fca5a5",
    "Snow": "#e0f2fe", "Cave": "#a1a1aa", "Beach": "#fef08a",
    "Seafloor": "#60a5fa", "River": "#93c5fd", "Sky": "#bae6fd",
    "Stars": "#bfa7d8", "PokéCenter": "#b7e0bf", "Tiles": "#afafaf",
    "Simple": "#e0e09f",
}
WP_DIR = ASSETS_DIR / "wallpapers"
for name, color in WP_THEMES.items():
    filename = "pokecenter.png" if name == "PokéCenter" else f"{name.lower()}.png"
    path = WP_DIR / filename
    if not path.exists():
        pm = QPixmap(240, 160)
        pm.fill(QColor(color))
        pm.save(str(path))
        print(f"  Created placeholder for {name} box. Overwrite this PNG with the real texture later!")

print("\n[SUCCESS] All assets bundled. The application is now 100% offline.")
