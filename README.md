# FRLG Studio

FRLG Studio is a Linux desktop companion for Pokémon FireRed and LeafGreen.
It combines a wireless trade screen, Bill's PC storage, a PKHeX-backed
Pokémon editor and generator, and a Wonder Card / Mystery Gift lab.

The project started from the curiosity that came after stumbling onto
[Tornadus11's frlg-ldn-trade](https://github.com/tornadus/frlg-ldn-trade):
if a computer could already talk to a real Gen 3 game over local wireless,
how much further could the idea go? The first version was a heavily
AI-assisted Qt front end wrapped around the trade client. It has since
snowballed into something much larger than anticipated.

## What is in it

### Trading

- Join a real FireRed or LeafGreen console over LDN and trade `.pk3` files.
- Keep a persistent trade journal with both Pokémon, trainer IDs, copied
  files, the session log and Markdown/JSON export.

### Bill's PC

- Unlimited boxes of 30 slots with drag and drop, cross-box moves, swaps and a
  transactional layout that rolls back if either side fails.
- Multi-select block moves: toggle **MULTI** or press `M`, then drag a
  selected group while preserving its relative layout. The storage glove
  turns green for group mode.
- All sixteen FRLG wallpapers, including **Stars**, **PokéCenter**, **Tiles**
  and **Simple**, with the game's white palette flash on a change.
- Box audit, one-step legalize for illegal records, and user-data snapshots
  with **UNDO LAST CHANGE** (`Alt+Z`).
- **SAVE TO BILL'S PC** always deposits a new copy; it never silently
  replaces a Pokémon already in storage.

### Editor and generator

- PKHeX-backed legality analysis and encounter-aware generation for wild,
  egg, gift, static, in-game trade and Mystery Gift sources.
- Level-up moves are generated for the actual level, including evolved
  species and egg-origin records; Legalize fills gaps without replacing a
  move you chose.
- Ball and held-item badges on the editor and PC summaries, with
  whole-pixel scaling and no layout shift when an item is added.
- IVs, EVs, nature, ability, gender, shininess, moves, PP, friendship, item
  and encounter data in one editor.

### Wonder Card / Mystery Gift lab

- Build and validate FRLG Wonder Cards and `.pokegift` payloads.
- Load the pokeldn event registry alongside community and custom cards.
- Broadcast a card from the desktop Wonder Card host.

### Interface and sound

- Seven themes: **FRLG**, **Hoenn**, **HGSS**, **Sinnoh**, **Unova**,
  **Light** and **Dark**, each with an animated title scene.
- Whole-device-pixel sprite scaling at 90%, 100%, 125%, 150% and 200% UI
  sizes, including portraits, box icons, ball/item badges and title art.
- Three independent audio buses: music, sound effects and cries. The PC and
  UI cue kit is rendered from the HeartGold/SoulSilver sound archive; cries
  and cues load from the bundled asset banks, and `soundpack/` can override
  them. Music is still on development list.
- Editable species/move/item dropdowns with type-to-search, Up/Down
  navigation and Enter to commit.

## Download

Release builds are AppImages for x86_64 Linux. Download
`FRLG_Studio-x86_64.AppImage` from the
[Releases page](https://github.com/spicymanmeat/FRLG-Studio/releases), then:

```bash
chmod +x FRLG_Studio-x86_64.AppImage
./FRLG_Studio-x86_64.AppImage
```

If FUSE is unavailable:

```bash
./FRLG_Studio-x86_64.AppImage --appimage-extract-and-run
```

The AppImage bundles Python, Qt, PKHeX, the .NET 10 runtime and the asset
banks. It is built against glibc 2.31 (Debian 11 / Ubuntu 20.04 or newer).
It contains no `prod.keys`, PC boxes, saves, journal, trainer profile,
custom card data or preferences.

## Run from source

Requirements:

- Linux
- Python 3.12
- .NET 10 runtime for PKHeX
- PyQt6 and pythonnet
- For live trading: a supported wireless adapter, root access for the radio,
  and a Switch or Switch 2 running FRLG with the Direct Corner unlocked
- `prod.keys` at `~/.switch/prod.keys` or in the data directory, for live
  trading only

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt PyQt6 pythonnet
./frlg-studio
```

A first launch opens **SETUP CHECK**. It verifies the key file, wireless
interface and driver, NetworkManager state, admin access, PKHeX, trade slots,
the writable data folder and the rehearsal capture. Settings → SETUP CHECK
reopens it later.

Live LDN needs the wireless card to be available to the host process. The
app can walk through the checks, but it cannot install a kernel driver or
grant itself root.


## Where your data lives

The AppImage is read-only. On first launch it creates:

```text
~/.local/share/frlg-studio/     # PC boxes, slots, journal, captures, trainer,
                                # Wonder Card data, prod.keys and undo snapshots
~/.config/frlg-studio/          # prefs.json, theme.txt, ui_scale.txt
```

Set `XDG_DATA_HOME` or `XDG_CONFIG_HOME` to move those roots, or set
`FRLG_STUDIO_DATA_DIR` and `FRLG_STUDIO_CONFIG_DIR` for a one-off test. The
AppImage's `soundpack/` directory is writable and is where music and optional
cue/cry overrides belong. `prod.keys` is never packaged.

## Build a release

The release build uses Debian 11 (glibc 2.31), bundles the .NET runtime and
writes the AppImage, zsync metadata, release notes and checksums to `release/`:

```bash
./tools/build_release.sh
```

It requires podman or docker and network access. The host build
`./tools/build_appimage.sh` is faster but inherits the host glibc and Python,
so it is for development rather than publication.

## Known limits

- Live LDN is Linux-only in this tree and still depends on a compatible
  wireless adapter, the host's wireless tools and administrator access. The
  AppImage packaging pass did not include a physical Switch trade.
- There is no automatic updater. Replacing the AppImage keeps the XDG data
  and settings intact.
- Windows is not packaged; the current build is x86_64 Linux only.

## Credits and lineage

This project would not exist without
**[Tornadus11's frlg-ldn-trade](https://github.com/tornadus/frlg-ldn-trade)**.
The LDN transport, trade protocol and simulator in this repository are built
on that work. The original project is also the reason this one started.

The Wonder Card and Mystery Gift functionality uses a **heavily stripped-down
copy of [pokeldn](https://github.com/Decryptu/pokeldn)**, kept only for the
FRLG gift registry, gift composition, save parsing and Wonder Card host paths.
It is not the full pokeldn application.

Additional credit:

- [kinnay's LDN library](https://github.com/kinnay/LDN) and the
  [NintendoClients wiki](https://github.com/kinnay/NintendoClients/wiki) for
  the local-wireless foundation.
- [pret/pokefirered](https://github.com/pret/pokefirered) for the FireRed /
  LeafGreen decompilation and Switch port reference.
- [PKHeX](https://github.com/kwsch/PKHeX) for legality and record handling.
- [PokéSprite](https://github.com/msikma/pokesprite) for the ball and held-item
  sprite source artwork.

## License and asset notice

The application code is licensed under the GNU Affero General Public License
v3. Pokémon names, sprites, cries, music and other game-derived assets remain
the property of Nintendo, Creatures, GAME FREAK and their respective rights
holders. 
