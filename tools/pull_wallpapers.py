import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = Path(__file__).resolve().parent.parent
WP_DIR = BASE_DIR / "assets" / "wallpapers"
WP_DIR.mkdir(parents=True, exist_ok=True)

# The exact authentic FRLG/RS filenames on the Bulbagarden Archives.
# Values are (archive filename, local filename); the four Etcetera entries
# are the FireRed/LeafGreen set, not Ruby/Sapphire's different four.
THEMES = {
    "Forest": ("Box_Forest_RS.png", "forest.png"),
    "City": ("Box_City_RS.png", "city.png"),
    "Desert": ("Box_Desert_RS.png", "desert.png"),
    "Savanna": ("Box_Savanna_RS.png", "savanna.png"),
    "Crag": ("Box_Crag_RS.png", "crag.png"),
    "Volcano": ("Box_Volcano_RS.png", "volcano.png"),
    "Snow": ("Box_Snow_RS.png", "snow.png"),
    "Cave": ("Box_Cave_RS.png", "cave.png"),
    "Beach": ("Box_Beach_RS.png", "beach.png"),
    "Seafloor": ("Box_Seafloor_RS.png", "seafloor.png"),
    "River": ("Box_River_RS.png", "river.png"),
    "Sky": ("Box_Sky_RS.png", "sky.png"),
    "Stars": ("Box_Stars_FRLG.png", "stars.png"),
    "PokéCenter": ("Box_PokéCenter_FRLG.png", "pokecenter.png"),
    "Tiles": ("Box_Tiles_FRLG.png", "tiles.png"),
    "Simple": ("Box_Simple_FRLG.png", "simple.png"),
}

API_URL = "https://archives.bulbagarden.net/w/api.php?action=query&titles=File:{}&prop=imageinfo&iiprop=url&format=json"

def download_wallpaper(theme_tuple):
    theme_name, (file_name, local_name) = theme_tuple
    dest = WP_DIR / local_name

    url = API_URL.format(urllib.parse.quote(file_name))

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            pages = data.get("query", {}).get("pages", {})
            page = list(pages.values())[0]

            if "imageinfo" in page:
                image_url = page["imageinfo"][0]["url"]
                img_req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(img_req, timeout=10) as img_response:
                    dest.write_bytes(img_response.read())
                    print(f"  [OK] Successfully downloaded: {theme_name.lower()}.png")
            else:
                print(f"  [FAIL] Could not find image URL for {file_name}")
    except Exception as e:
        print(f"  [FAIL] Error downloading {theme_name.lower()}.png: {e}")

print("--- Downloading Authentic PC Wallpapers from Bulbagarden Archives ---")

with ThreadPoolExecutor(max_workers=12) as executor:
    executor.map(download_wallpaper, THEMES.items())

print("\n[SUCCESS] Wallpapers pulled and placed in assets/wallpapers/.")
