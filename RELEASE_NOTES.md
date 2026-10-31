# FRLG Studio 0.10.0 — portable Linux release

FRLG Studio is a desktop companion for Pokémon FireRed and LeafGreen: wireless
trading through a Switch, Bill's PC storage, a PK3 editor, a Wonder Card
builder, and an offline rehearsal mode.

This release packages the current interface and the sound pass into one
x86_64 AppImage.

## Download and run

Download `FRLG_Studio-x86_64.AppImage`, then:

```bash
chmod +x FRLG_Studio-x86_64.AppImage
./FRLG_Studio-x86_64.AppImage
```

If FUSE is unavailable on your system:

```bash
./FRLG_Studio-x86_64.AppImage --appimage-extract-and-run
```

The build includes Python, Qt, the LDN/trade engine, PKHeX, the .NET 10
runtime, the UI assets, cries, and the PC/UI sound bank. It is built on a
glibc 2.31 baseline (Debian 11 / Ubuntu 20.04 or newer).

## What is in 0.10.0

- Seven desktop themes with animated title scenes: FRLG, Hoenn, HGSS,
  Sinnoh, Unova, Light and Dark.
- Bill's PC with box wallpapers, animated sprite scaling, drag and drop,
  cross-box moves, and multi-select block moves with the green storage glove.
- A three-bus sound system: independent music, sound effects and cries, plus
  per-theme Pokémon Center loops, Gen 3 trade cues, and click-to-cry summary
  portraits.
- A PK3 editor with encounter-aware generation, legal level-up movesets,
  PKHeX legalize, ball and held-item badges, and always-new saves to Bill's PC.
- Wonder Card creation, trade rehearsal and capture playback, a persistent
  trade journal, user-data snapshots, and offline box auditing.
- A console-timed trade stage that shows the Switch's selection before the
  trade commits.

## Where your data lives

The AppImage is read-only. On first launch it creates:

```text
~/.local/share/frlg-studio/     # PC boxes, slots, journal, captures, trainer,
                                # Wonder Card data, prod.keys and undo snapshots
~/.config/frlg-studio/          # prefs.json, theme.txt, ui_scale.txt
```

Set `XDG_DATA_HOME` or `XDG_CONFIG_HOME` to move those roots, or set
`FRLG_STUDIO_DATA_DIR` and `FRLG_STUDIO_CONFIG_DIR` for a one-off test.
Updating the AppImage does not touch either directory.

`prod.keys` is never packaged. The app checks the data folder and then
`~/.switch/prod.keys`. The AppImage also does not contain PC boxes, `.pk3`
files, the trade journal, trainer profiles, custom cards, or preferences.

## Updating and verifying

Keep the file at a stable path such as
`~/Applications/FRLG_Studio-x86_64.AppImage`. Quit the app, replace that file,
and launch it again; all data and settings stay in place. The AppImage embeds
an AppImageUpdate zsync URL, but there is no automatic updater inside the app
yet.

```bash
sha256sum -c SHA256SUMS
```

`SHA256SUMS` and the AppImage can be signed by setting `FRLG_SIGN_KEY` when
building. Use a stable release key for public builds.

## Limits

- Live LDN needs a supported wireless adapter, the host's wireless tools and
  administrator access for the radio. A portable AppImage cannot package a
  kernel driver or sudo.
- This packaging pass was verified with the CLI entry points and an offscreen
  GUI launch. It did not include a physical Switch trade.
- Only x86_64 Linux is built here.

## Asset notice

The application code is licensed under the GNU Affero General Public License
v3. Pokémon names, sprites, cries, music and other game-derived artwork and
audio remain the property of their respective rights holders.
