# FRLG Studio fonts

This folder contains the two pixel fonts used by the HD-remaster skin.

| File | In-game counterpart | Used for |
| --- | --- | --- |
| `PokePixelGBA.ttf` | Pokémon FireRed / LeafGreen (GBA) in-game text | Trade plates, PC box banner, menu labels, Wonder Card text, dialogue logs |
| `PokemonDS.ttf` | Pokémon Diamond / Pearl / Platinum / HGSS (DS) in-game text | Menus, forms, tables, buttons and dense data readouts |

`PokemonDS.ttf` is *Pokémon DS Font* by
[sergalbutt](https://fontstruct.com/fontstructors/show/936595/sergalbutt) on
FontStruct, released under CC0: https://fontstruct.com/fontstructions/show/1182741
`PokePixelGBA.ttf` is *PokePixel GBA* from
[PokéPrint](https://pokeprint.kimbachu.com/downloads/), a recreation of the FRLG
in-game text; its site terms allow personal, non-commercial use.

Both are fan recreations provided for personal, non-commercial use. They are
**not** covered by this project's AGPL licence and are not redistributable under
it. If this repository is published or shared, remove these two files or replace
them with fonts you have redistribution rights for. The UI falls back to the
system font cleanly when either file is missing.

The UI loads whichever of these files are present at startup; no network access
is required.
