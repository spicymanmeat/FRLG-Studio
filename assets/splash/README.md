# Title-screen splash sprites

These files are used only by the region title scenes in `src/trade_gui.py`.
The animated strips are drawn with nearest-neighbour filtering at whole
device-pixel scales, so the sprites stay crisp from 100% through 200% UI size.

## Active title-scene animation strips

Each `anim_*.png` is one horizontal row of equally sized cells. The game
cycles one cell at a time; the frame counts live in `_SPLASH_ANIM` in
`src/trade_gui.py`, and the native delay for every cell lives in
`anim_timing.json`. The renderer schedules paints on the next real frame
boundary (with a 30 fps decorative-motion cap), so a 60 ms Black/White cycle
is not sampled on a 100 ms grid and the variable holds in Zekrom's cycle are
preserved.

The usual source cadences are 100 ms for FRLG/HGSS, 60 ms for Platinum and
Black/White (with occasional 120 ms holds), and 134 ms for the Ruby bicycle
(eight GBA frames per cell at 59.7275 Hz).

| File | Source |
| --- | --- |
| `anim_charizard.png`, `anim_venusaur.png` | [PokeAPI/sprites](https://github.com/PokeAPI/sprites), FireRed/LeafGreen animated sprites (every source frame) |
| `anim_hooh.png`, `anim_lugia.png` | PokeAPI/sprites, HeartGold/SoulSilver animated sprites (every source frame) |
| `anim_uxie.png`, `anim_mesprit.png`, `anim_azelf.png` | PokeAPI/sprites, Platinum animated sprites (every source frame) |
| `anim_reshiram.png`, `anim_zekrom.png` | PokeAPI/sprites, Black/White animated sprites (every source frame) |
| `latios_full.png`, `latias_full.png` | [pret/pokeruby](https://github.com/pret/pokeruby), `graphics/intro/intro2_latios.png` and `intro2_latias.png`. The GBA source stores each 128x64 creature as two 64x64 halves; both halves are reassembled here. |
| `anim_brendan_ride.png` | [pret/pokeruby](https://github.com/pret/pokeruby) `graphics/intro/intro2_brendan.png` rider frames composited over its `graphics/intro/intro2_bicycle.png` bicycle frames. Four 64x64 cells keep the full rider and bike in one sprite. In the intro, the rider (64x64) is at the sprite origin and the bicycle (64x32) is centred eight pixels lower, so the bicycle's top-left is 24 px below the rider's. Both sprites are drawn in that order; there is only one bicycle. |

The intro sprites' palette index 0 was made transparent, preserving the
original colours and the black shading inside the sprites.

## Retired static art

The older static GBA/DS front sprites and the official `art_*.png` pieces were
removed in the 2026-10-29 unused-file cleanup. No title scene draws them. A
copy remains in `.backups/frlg-studio-cleanup-20261029-122402.tar.gz` if an
earlier title design ever needs them again.

## Rebuilding the strips

The PokeAPI strips are generated from the source GIFs by:

```bash
venv/bin/python .backups/build_animated_sprites.py
```

The script expects the source GIFs in `/tmp/splashrefresh`, keeps every
source frame, and writes the native-resolution strips into this folder. It
also reads each GIF's per-frame delay and writes `anim_timing.json`; the
frame counts in `_SPLASH_ANIM` (`src/trade_gui.py`) must match both. Keeping
the cells at their native resolution is deliberate: the title renderer
performs the integer scaling.

Pokémon and Pokémon character names are trademarks of Nintendo, Creatures Inc.
and GAME FREAK inc. These assets are used by this non-commercial fan project
and are not part of the LDN/trade engine.
