"""Sound-pack audio for FRLG Studio.

The program tree supplies the canonical cry bank (``assets/sound/cries``) and
a small PC/UI cue kit rendered from the actual HGSS SDAT sequences
(``assets/sound/sfx``), plus a writable OEM pack for genuine exports.
Species-name cries are mapped through ``species.json``.  The writable
``~/.local/share/frlg-studio/soundpack`` directory (or the matching XDG /
``FRLG_STUDIO_DATA_DIR`` root) supplies music, optional cue/cry overrides and
manifest overrides.  The pack has three independent buses:

* music    — one loop per theme, plus the Gen 3 trade theme
* effects  — menu, PC box and trade cues
* cries    — one clip per National Dex number

A missing bank is a normal state, not an error: every call becomes a no-op and
the rest of the studio works exactly as before.  Missing files, an unsupported
format, a headless Qt platform or a vanished audio device are all contained
here so audio can never block startup, a save or a trade.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QObject, QUrl, pyqtSignal

try:  # pragma: no cover - depends on the Qt deployment
    from PyQt6.QtMultimedia import (
        QAudioOutput,
        QMediaDevices,
        QMediaPlayer,
        QSoundEffect,
    )
except Exception:  # pragma: no cover
    QAudioOutput = None
    QMediaDevices = None
    QMediaPlayer = None
    QSoundEffect = None

import app_prefs
import paths
import theme

AUDIO_EXTENSIONS = {".wav", ".ogg", ".mp3", ".flac", ".opus", ".m4a", ".aac"}

# Every cue the UI can ask for.  Pack authors can supply any subset; aliases
# below let a Gen 4 PC pack answer the shared menu calls and vice versa.
SFX_NAMES = (
    "menu_move",
    "menu_select",
    "a_button_press",
    "ui_back",
    "ui_click",
    "ui_close",
    "ui_confirm",
    "ui_error",
    "ui_open",
    "open_settings",
    "ui_toggle",
    "ui_warning",
    "pc_open",
    "pc_close",
    "pc_pick",
    "pc_move",
    "pc_place",
    "pc_swap",
    "pc_deposit",
    "pc_withdraw",
    "pc_release",
    "pc_import",
    "pc_undo",
    "pc_error",
    "editor_open",
    "editor_save",
    "link_connected",
    "link_incoming",
    "trade_start",
    "trade_cancel",
    "trade_complete",
    "trade_failed",
)

# A pack with only one naming convention still answers the other call sites.
CUE_FALLBACKS = {
    "menu_move": ("menu_move", "a_button_press"),
    "menu_select": ("a_button_press", "menu_select"),
    "a_button_press": ("a_button_press", "menu_select"),
    "ui_click": ("ui_click", "a_button_press"),
    "ui_confirm": ("ui_confirm", "a_button_press"),
    "ui_back": ("ui_back", "menu_select"),
    "ui_open": ("ui_open", "open_settings", "editor_open"),
    "open_settings": ("open_settings", "ui_open"),
    "ui_close": ("ui_close", "a_button_press"),
    "ui_toggle": ("ui_toggle", "a_button_press"),
    "ui_error": ("ui_error", "menu_select"),
    "ui_warning": ("ui_warning", "menu_select"),
    "pc_open": ("pc_open", "ui_open"),
    "pc_close": ("pc_close", "ui_close", "a_button_press"),
    "pc_pick": ("pc_pick", "pc_move", "a_button_press"),
    "pc_move": ("pc_move", "pc_pick", "a_button_press"),
    "pc_place": ("pc_place", "pc_swap", "a_button_press"),
    "pc_swap": ("pc_swap", "pc_place", "a_button_press"),
    "pc_deposit": ("pc_deposit", "menu_select"),
    "pc_withdraw": ("pc_withdraw", "menu_select"),
    "pc_release": ("pc_release", "menu_select"),
    "pc_import": ("pc_import", "menu_select"),
    "pc_undo": ("pc_undo", "menu_select"),
    "pc_error": ("pc_error", "menu_select"),
    "editor_open": ("editor_open", "ui_open"),
    "editor_save": ("editor_save", "menu_select"),
    "link_connected": ("link_connected", "open_settings"),
    "link_incoming": ("link_incoming", "open_settings"),
    "trade_start": ("trade_start", "menu_select"),
    "trade_cancel": ("trade_cancel", "a_button_press"),
    "trade_complete": ("trade_complete", "menu_select"),
    "trade_failed": ("trade_failed", "menu_select"),
}

# Theme id -> canonical music key.  Light and dark are UI treatments, not
# main-series regions, so they borrow the closest Centre theme.
THEME_MUSIC_KEYS = {
    "frlg": "frlg",
    "hoenn": "hoenn",
    "hgss": "hgss",
    "sinnoh": "sinnoh",
    "unova": "unova",
    "light": "frlg",
    "dark": "hgss",
}

MUSIC_KEYS = ("frlg", "hoenn", "hgss", "sinnoh", "unova", "default")

_TRADE_MUSIC_STEMS = {
    "trade",
    "trade_gen3",
    "gen3_trade",
    "trade_theme",
    "link_trade",
    "trade_music",
}

_HEADLESS_PLATFORMS = {"offscreen", "minimal"}
_MAX_EFFECT_VOICES = 12
_MAX_MEDIA_VOICES = 5
_GLOBAL_COOLDOWN = 0.015

# Long cues get a little more room so a double-click cannot stack them.
CUE_COOLDOWNS = {
    "link_incoming": 1.55,
    "editor_save": 1.10,
    "trade_complete": 0.35,
    "trade_failed": 0.25,
    "ui_error": 0.16,
    "ui_warning": 0.16,
    "pc_error": 0.16,
}


def _clamp_volume(value, default: float = 0.55) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _norm_stem(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")


def _species_dex_by_name() -> dict[str, int]:
    """Map normalized species names to dex numbers for the assets cry bank."""
    try:
        raw = json.loads(
            (paths.ASSETS_DIR / "data" / "species.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    mapping: dict[str, int] = {}
    if not isinstance(raw, dict):
        return mapping
    for key, value in raw.items():
        try:
            dex = int(key)
        except (TypeError, ValueError):
            continue
        if not 1 <= dex <= 1025:
            continue
        name = _norm_stem(Path(str(value)))
        if name:
            mapping.setdefault(name, dex)
    return mapping


def _audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


@dataclass
class SoundPack:
    """The assets audio banks plus the user's writable soundpack."""

    root: Path
    name: str = ""
    cries: dict[int, Path] = field(default_factory=dict)
    sfx: dict[str, Path] = field(default_factory=dict)
    music: dict[str, Path] = field(default_factory=dict)
    trade_music: Path | None = None
    gains: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    from_manifest: bool = False

    @classmethod
    def load(
        cls,
        root: Path,
        *,
        bundled_cries: Path | None = None,
        bundled_sfx: Path | None = None,
    ) -> "SoundPack":
        pack = cls(root=Path(root), name=Path(root).name or "soundpack")
        # The program-tree banks are the canonical source.  Cries are scanned
        # first so a stale copy in soundpack/cries cannot shadow the files
        # beside the app; the user pack still fills missing dex numbers.  SFX
        # have the opposite precedence: bundled cues are a complete base and
        # the user pack overrides individual filenames.  A manifest entry can
        # override either bank below.
        if bundled_cries is not None:
            pack._scan_cries_dir(Path(bundled_cries), names=True)
        if bundled_sfx is not None:
            pack._scan_sfx_dir(Path(bundled_sfx))
        if pack.cries or pack.sfx:
            pack.name = "FRLG Studio"
        if not pack.root.is_dir():
            return pack
        raw: dict = {}
        manifest = pack.root / "manifest.json"
        if manifest.is_file():
            try:
                loaded = json.loads(manifest.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    raw = loaded
                    pack.from_manifest = True
                else:
                    pack.errors.append("manifest.json is not a JSON object")
            except (OSError, json.JSONDecodeError) as exc:
                pack.errors.append(f"manifest.json: {exc}")
        pack._scan()
        if raw:
            pack._apply_manifest(raw)
        return pack

    # -- discovery ---------------------------------------------------------
    def _scan_cries_dir(self, cries_dir: Path, *, names: bool = False) -> None:
        """Index ``<dex>`` or, with ``names``, species-name cry files."""
        if not cries_dir.is_dir():
            return
        by_name = _species_dex_by_name() if names else {}
        for path in sorted(
            cries_dir.rglob("*"), key=lambda item: item.as_posix().lower()
        ):
            if not _audio_file(path):
                continue
            match = re.match(r"^(\d{1,4})(?:\D|$)", path.stem)
            if match:
                dex = int(match.group(1))
            elif names:
                dex = by_name.get(_norm_stem(path), 0)
            else:
                dex = 0
            if 1 <= dex <= 1025:
                self.cries.setdefault(dex, path)

    def _scan_sfx_dir(self, sfx_dir: Path, *, override: bool = False) -> None:
        """Index canonical cue filenames, optionally replacing earlier ones."""
        if not sfx_dir.is_dir():
            return
        wanted = set(SFX_NAMES)
        for path in sorted(sfx_dir.rglob("*"), key=lambda item: item.as_posix().lower()):
            if not _audio_file(path):
                continue
            stem = _norm_stem(path)
            if stem not in wanted:
                continue
            if override:
                self.sfx[stem] = path
            else:
                self.sfx.setdefault(stem, path)

    def _scan(self) -> None:
        self._scan_cries_dir(self.root / "cries")
        self._scan_sfx_dir(self.root / "sfx", override=True)

        music_dir = self.root / "music"
        if not music_dir.is_dir():
            return
        for path in sorted(music_dir.rglob("*"), key=lambda item: item.as_posix().lower()):
            if not _audio_file(path):
                continue
            stem = _norm_stem(path)
            if stem in _TRADE_MUSIC_STEMS:
                if self.trade_music is None:
                    self.trade_music = path
                continue
            for key in MUSIC_KEYS:
                aliases = {
                    key,
                    f"pokemon_center_{key}",
                    f"pc_{key}",
                    f"theme_{key}",
                }
                if key in ("default",):
                    aliases |= {"pokemon_center", "theme"}
                if stem in aliases:
                    self.music.setdefault(key, path)
                    break

    def _safe_path(self, value) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            return None
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError:
            self.errors.append(f"{value}: outside the soundpack directory")
            return None
        if not _audio_file(candidate):
            self.errors.append(f"{value}: missing or unsupported audio")
            return None
        return candidate

    def _apply_manifest(self, raw: dict) -> None:
        if raw.get("name"):
            self.name = str(raw["name"])[:80]
        cries = raw.get("cries")
        if isinstance(cries, dict):
            for key, value in cries.items():
                try:
                    dex = int(key)
                except (TypeError, ValueError):
                    continue
                path = self._safe_path(value)
                if path is not None and 1 <= dex <= 1025:
                    self.cries[dex] = path
        sfx = raw.get("sfx")
        if isinstance(sfx, dict):
            for key, value in sfx.items():
                cue = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
                path = self._safe_path(value)
                if path is not None and cue:
                    self.sfx[cue] = path
        music = raw.get("music")
        if isinstance(music, str):
            self.trade_music = self._safe_path(music) or self.trade_music
        elif isinstance(music, dict):
            themes = music.get("themes")
            if isinstance(themes, dict):
                for key, value in themes.items():
                    song = self._safe_path(value)
                    if song is not None:
                        self.music[str(key).lower()] = song
            for key, value in music.items():
                if key == "themes":
                    continue
                song = self._safe_path(value)
                if song is None:
                    continue
                low = str(key).lower()
                if low in ("trade", "trade_gen3", "link"):
                    self.trade_music = song
                elif low in THEME_MUSIC_KEYS.values() or low == "default":
                    self.music[low] = song
        gains = raw.get("gains")
        if isinstance(gains, dict):
            for key, value in gains.items():
                try:
                    self.gains[str(key)] = _clamp_volume(value, 1.0)
                except (TypeError, ValueError):
                    continue

    # -- lookup ------------------------------------------------------------
    def cue_path(self, cue: str) -> tuple[str, Path] | None:
        for candidate in CUE_FALLBACKS.get(cue, (cue,)):
            path = self.sfx.get(candidate)
            if path is not None:
                return candidate, path
        return None

    def theme_music(self, theme_id: str) -> Path | None:
        key = THEME_MUSIC_KEYS.get(str(theme_id), str(theme_id))
        return self.music.get(key) or self.music.get("default")

    @property
    def empty(self) -> bool:
        return not (self.cries or self.sfx or self.music or self.trade_music)

    def summary(self) -> str:
        if self.empty:
            return "NO OEM SOUND PACK"
        return (
            f"{self.name}: {len(self.cries)} CRIES · {len(self.sfx)} SFX"
            f" · {len(self.music)} THEMES"
        )


class SoundManager(QObject):
    """Three-bus audio manager with a hard no-op fallback."""

    pack_changed = pyqtSignal()
    music_changed = pyqtSignal(str)
    mute_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        prefs = app_prefs.load()
        self.master_muted = bool(prefs.get("sound_muted", False))
        self.sfx_enabled = bool(
            prefs.get("sound_effects", prefs.get("sound_enabled", True))
        )
        self.sfx_volume = _clamp_volume(
            prefs.get("sound_effects_volume", prefs.get("sound_volume", 0.55))
        )
        self.cries_enabled = bool(prefs.get("cries_enabled", True))
        self.cries_volume = _clamp_volume(prefs.get("cries_volume", 0.80))
        self.music_enabled = bool(
            prefs.get("music_enabled", prefs.get("sound_music", True))
        )
        self.music_volume = _clamp_volume(
            prefs.get("sound_music_volume", 0.30)
        )

        self.pack = SoundPack.load(
            paths.SOUNDPACK_DIR,
            bundled_cries=paths.BUNDLED_CRIES_DIR,
            bundled_sfx=paths.BUNDLED_SFX_DIR,
        )
        self._write_pack_readme()
        self.available = QSoundEffect is not None and not self._headless()
        self.music_available = QMediaPlayer is not None and not self._headless()

        self._cues_loaded = False
        self._shut_down = False
        self._effects: list = []
        self._media_voices: list[dict] = []
        self._effect_started: dict[int, float] = {}
        self._media_started: dict[int, float] = {}
        self._media_sources: dict[int, str] = {}
        self._last_played: dict[str, float] = {}
        self._last_global = 0.0

        self._music_player = None
        self._music_output = None
        self._music_path: Path | None = None
        self._music_context = "menu"
        self._theme_id = theme.THEME_ID
        self._music_label = ""

    # -- setup -------------------------------------------------------------
    @staticmethod
    def _headless() -> bool:
        app = QCoreApplication.instance()
        platform = (app.platformName() if app is not None else "") or os.environ.get(
            "QT_QPA_PLATFORM", ""
        )
        return platform.split(":", 1)[0].lower() in _HEADLESS_PLATFORMS

    def _write_pack_readme(self) -> None:
        """Leave an explicit layout beside the empty folder, once."""
        readme = paths.SOUNDPACK_DIR / "README.txt"
        if readme.exists():
            return
        try:
            paths.SOUNDPACK_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        sfx = "\n".join(f"  {name}" for name in SFX_NAMES)
        music = "\n".join(
            f"  pokemon_center_{key}.ogg" for key in MUSIC_KEYS if key != "default"
        )
        text = (
            "FRLG Studio sound pack\n"
            "=======================\n\n"
            "The program tree supplies the cry bank and PC/UI cues rendered\n"
            "from the actual HGSS sequences.  This folder supplies music,\n"
            "optional overrides and extra cries.\n\n"
            "Layout\n"
            "------\n"
            "  assets/sound/cries/abra.wav  built-in bank; species name or dex\n"
            "  assets/sound/sfx/pc_pick.wav built-in HGSS-rendered cue kit\n"
            "  soundpack/\n"
            "    manifest.json          optional; see below\n"
            "    cries/001.ogg           National Dex number, 001..1025\n"
            "    cries/025 - Pikachu.ogg also accepted\n"
            "    sfx/pc_pick.wav         overrides the built-in cue\n"
            "    music/pokemon_center_frlg.ogg\n"
            "    music/pokemon_center_hoenn.ogg\n"
            "    music/pokemon_center_hgss.ogg\n"
            "    music/pokemon_center_sinnoh.ogg\n"
            "    music/pokemon_center_unova.ogg\n"
            "    music/trade_gen3.ogg\n\n"
            "WAV is the low-latency format for short SFX and cries. OGG, MP3,\n"
            "FLAC, OPUS, M4A and AAC also load through Qt Multimedia.\n\n"
            "SFX names\n"
            "---------\n"
            f"{sfx}\n\n"
            "Music names\n"
            "-----------\n"
            f"{music}\n"
            "  music/trade_gen3.ogg\n\n"
            "A manifest can rename files without moving them:\n\n"
            "{\n"
            '  "name": "My OEM pack",\n'
            '  "cries": {"1": "cries/bulbasaur.ogg"},\n'
            '  "sfx": {"ui_click": "sfx/gba_click.wav"},\n'
            '  "music": {\n'
            '    "themes": {"frlg": "music/kanto_centre.ogg"},\n'
            '    "trade": "music/gen3_trade.ogg"\n'
            "  },\n"
            '  "gains": {"cries": 0.9, "music": 0.8, "trade_complete": 0.7}\n'
            "}\n\n"
            "A pack with only some files is valid. A missing cue falls back to the\n"
            "built-in kit; the Sound Settings dialog shows how many each bus found.\n"
            "The built-in cues are rendered from the actual HGSS sound archive,\n"
            "not synthesized approximations.  The bank is 12 WAV files for 32\n"
            "logical names; every file is used and no audio is stored twice.\n\n"
            "Built-in HGSS cues\n"
            "------------------\n"
            "These are the sequence IDs behind the bundled files:\n\n"
            "  SEQ_SE_DP_PC_LOGIN     (1548) -> pc_open.wav\n"
            "  SEQ_SE_DP_PC_LOGOFF    (1549) -> pc_close.wav\n"
            "  SEQ_SE_DP_BOX02        (1515) -> pc_pick.wav (pc_move alias)\n"
            "  SEQ_SE_DP_BOX01        (1514) -> pc_place.wav (pc_swap alias)\n"
            "  SEQ_SE_DP_SELECT       (1500) -> a_button_press.wav\n"
            "      aliases: menu_move, ui_click, ui_confirm, ui_close, trade_cancel\n"
            "  SEQ_SE_DP_DECIDE       (1501) -> menu_select.wav\n"
            "      aliases: ui_back, ui_error, ui_warning, pc_deposit, pc_withdraw,\n"
            "               pc_release, pc_import, pc_undo, pc_error, trade_start,\n"
            "               trade_failed\n"
            "  SEQ_SE_DP_SELECT78     (1504) -> open_settings.wav\n"
            "      alias: link_connected\n"
            "  SEQ_SE_DP_BUTTON3      (1509) -> ui_toggle.wav\n"
            "  SEQ_SE_DP_OPEN2        (1518) -> ui_open.wav (editor_open alias)\n"
            "  SEQ_SE_DP_PINPON       (1521) -> link_incoming.wav\n"
            "  SEQ_SE_DP_KATI         (1526) -> trade_complete.wav\n"
            "  SEQ_SE_DP_SAVE         (1562) -> editor_save.wav\n\n"
            "BOX01 and BOX02 are reserved for the storage hand: a lift uses BOX02,\n"
            "and an empty-slot drop, a same-slot drop, or a swap each use one\n"
            "BOX01 set-down.  The swap cue is a single hit, never two.  Tabs,\n"
            "box changes and menu_select calls prefer a_button_press.wav\n"
            "(SEQ_SE_DP_SELECT); menu_select.wav (DECIDE) is the fallback when\n"
            "a pack lacks it.  Settings opens with open_settings.wav; other\n"
            "dialogs open with OPEN2 and close with the soft SELECT click.  No\n"
            "non-hand cue borrows the box samples.\n\n"
            "The user pack is read first, so a matching file replaces only that\n"
            "cue; menu_select still prefers a_button_press.wav.  Use SOUND\n"
            "SETTINGS -> RELOAD PACK after copying the WAVs.\n"
        )
        try:
            readme.write_text(text, encoding="utf-8")
        except OSError:
            pass

    @property
    def enabled(self) -> bool:
        """Compatibility alias used by the old Settings popup call sites."""
        return self.sfx_enabled

    def retry_audio(self) -> None:
        """Re-check a backend that had no device at startup."""
        if self._shut_down:
            return
        if self._headless():
            return
        self.available = QSoundEffect is not None
        self.music_available = QMediaPlayer is not None
        self.preload()
        self.refresh_music()

    def preload(self) -> None:
        """Create the low-latency voice pool after the first frame."""
        if self._cues_loaded or self._shut_down or not self.available:
            return
        if QMediaDevices is not None:
            try:
                if not QMediaDevices.audioOutputs():
                    self.available = False
                    self.music_available = False
                    return
            except Exception:
                self.available = False
                self.music_available = False
                return
        try:
            for _ in range(_MAX_EFFECT_VOICES):
                voice = QSoundEffect(self)
                voice.setLoopCount(1)
                self._effects.append(voice)
            if QMediaPlayer is not None and QAudioOutput is not None:
                for _ in range(_MAX_MEDIA_VOICES):
                    player = QMediaPlayer(self)
                    output = QAudioOutput(self)
                    player.setAudioOutput(output)
                    self._media_voices.append(
                        {"player": player, "output": output}
                    )
        except Exception:
            self.available = False
            self.music_available = False
            self._effects.clear()
            self._media_voices.clear()
            return
        self._cues_loaded = True

    def _ensure_music(self) -> bool:
        if self._music_player is not None:
            return True
        if (
            not self.music_available
            or QMediaPlayer is None
            or QAudioOutput is None
        ):
            return False
        try:
            player = QMediaPlayer(self)
            output = QAudioOutput(self)
            player.setAudioOutput(output)
            player.setLoops(QMediaPlayer.Loops.Infinite)
            self._music_player = player
            self._music_output = output
        except Exception:
            self.music_available = False
            return False
        return True

    # -- low-level playback ------------------------------------------------
    def _pick_effect(self, now: float):
        if not self._effects:
            return None
        for voice in self._effects:
            try:
                if not voice.isPlaying():
                    return voice
            except RuntimeError:
                continue
        oldest = min(
            self._effects,
            key=lambda voice: self._effect_started.get(id(voice), 0.0),
        )
        try:
            oldest.stop()
        except RuntimeError:
            pass
        return oldest

    def _pick_media(self, now: float) -> dict | None:
        if not self._media_voices:
            return None
        for voice in self._media_voices:
            try:
                if voice["player"].playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                    return voice
            except RuntimeError:
                continue
        oldest = min(
            self._media_voices,
            key=lambda voice: self._media_started.get(id(voice["player"]), 0.0),
        )
        try:
            oldest["player"].stop()
        except RuntimeError:
            pass
        return oldest

    def _play_path(
        self,
        path: Path,
        gain: float,
        bus_volume: float,
        *,
        key: str,
        force: bool = False,
    ) -> None:
        if self._shut_down or self.master_muted:
            return
        self.preload()
        now = time.monotonic()
        if not force:
            if now - self._last_global < _GLOBAL_COOLDOWN:
                return
            cooldown = CUE_COOLDOWNS.get(key, 0.03)
            if now - self._last_played.get(key, 0.0) < cooldown:
                return
        volume = _clamp_volume(bus_volume * gain * self.pack.gains.get(key, 1.0))
        try:
            if path.suffix.lower() == ".wav" and self._effects:
                voice = self._pick_effect(now)
                if voice is None:
                    return
                voice.setSource(QUrl.fromLocalFile(str(path)))
                voice.setVolume(volume)
                voice.play()
                self._effect_started[id(voice)] = now
            elif self._media_voices:
                voice = self._pick_media(now)
                if voice is None:
                    return
                player = voice["player"]
                source = str(path)
                if self._media_sources.get(id(player)) != source:
                    player.setSource(QUrl.fromLocalFile(source))
                    self._media_sources[id(player)] = source
                else:
                    player.setPosition(0)
                voice["output"].setVolume(volume)
                player.play()
                self._media_started[id(player)] = now
            else:
                return
        except Exception:
            # One bad file or a device that vanished mid-session stays silent.
            return
        self._last_played[key] = now
        self._last_global = now

    # -- SFX ---------------------------------------------------------------
    def play(self, cue: str, *, force: bool = False) -> None:
        if (
            self._shut_down
            or self.master_muted
            or not self.sfx_enabled
            or not self.available
        ):
            return
        resolved = self.pack.cue_path(str(cue))
        if resolved is None:
            return
        name, path = resolved
        self._play_path(
            path,
            1.0,
            self.sfx_volume,
            key=name,
            force=force,
        )

    def play_cry(self, dex: int) -> None:
        if (
            self._shut_down
            or self.master_muted
            or not self.cries_enabled
            or not self.available
        ):
            return
        try:
            species = int(dex)
        except (TypeError, ValueError):
            return
        path = self.pack.cries.get(species)
        if path is None:
            return
        # A cry is a direct response to clicking that Pokémon.  It must not be
        # swallowed by the short global cooldown that follows a UI click.
        self._play_path(
            path,
            self.pack.gains.get("cries", 1.0),
            self.cries_volume,
            key=f"cry:{species}",
            force=True,
        )

    def preview_cry(self) -> None:
        """Play a representative cry for the Sound Settings test button."""
        for species in (25, 133, 6, 150, 1):
            if species in self.pack.cries:
                self.play_cry(species)
                return
        if self.pack.cries:
            self.play_cry(min(self.pack.cries))

    # -- music -------------------------------------------------------------
    def _music_for_context(self) -> Path | None:
        if self._music_context == "trade" and self.pack.trade_music is not None:
            return self.pack.trade_music
        return self.pack.theme_music(self._theme_id)

    def _apply_music(self, *, force: bool = False) -> None:
        if self._shut_down:
            return
        if not self.music_enabled or self.master_muted:
            self._stop_music(clear_label=True)
            return
        if not self._ensure_music():
            return
        path = self._music_for_context()
        if path is None:
            self._stop_music(clear_label=True)
            return
        player = self._music_player
        output = self._music_output
        assert player is not None and output is not None
        playing = (
            player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        )
        if path == self._music_path and playing and not force:
            output.setVolume(
                _clamp_volume(
                    self.music_volume * self.pack.gains.get("music", 1.0)
                )
            )
            return
        try:
            if path != self._music_path or force:
                player.setSource(QUrl.fromLocalFile(str(path)))
                self._music_path = path
            output.setVolume(
                _clamp_volume(
                    self.music_volume * self.pack.gains.get("music", 1.0)
                )
            )
            player.play()
            self._music_label = path.stem.replace("_", " ").upper()
            self.music_changed.emit(self._music_label)
        except Exception:
            return

    def _stop_music(self, *, clear_label: bool = False) -> None:
        if self._music_player is not None:
            try:
                self._music_player.stop()
            except RuntimeError:
                pass
        if clear_label and self._music_label:
            self._music_label = ""
            self.music_changed.emit("")

    def _stop_effects(self) -> None:
        for voice in self._effects:
            try:
                voice.stop()
            except RuntimeError:
                pass
        for voice in self._media_voices:
            try:
                voice["player"].stop()
            except RuntimeError:
                pass

    def stop_all(self) -> None:
        self._stop_effects()
        self._stop_music()

    def set_theme(self, theme_id: str) -> None:
        self._theme_id = str(theme_id)
        if self._music_context == "menu":
            self._apply_music()

    def set_music_context(self, context: str) -> None:
        context = "trade" if context == "trade" else "menu"
        if context == self._music_context:
            return
        self._music_context = context
        self._apply_music(force=True)

    def refresh_music(self, *, force: bool = False) -> None:
        self._apply_music(force=force)

    def preview_music(self) -> None:
        self._apply_music(force=True)

    def reload_pack(self) -> None:
        self.pack = SoundPack.load(
            paths.SOUNDPACK_DIR,
            bundled_cries=paths.BUNDLED_CRIES_DIR,
            bundled_sfx=paths.BUNDLED_SFX_DIR,
        )
        self._write_pack_readme()
        self._stop_effects()
        self._music_path = None
        self._apply_music(force=True)
        self.pack_changed.emit()

    # -- preferences -------------------------------------------------------
    def set_master_muted(self, muted: bool) -> None:
        self.master_muted = bool(muted)
        app_prefs.update(sound_muted=self.master_muted)
        if self.master_muted:
            self.stop_all()
        else:
            self._apply_music(force=True)
        self.mute_changed.emit(self.master_muted)

    def set_sfx_enabled(self, enabled: bool) -> None:
        self.sfx_enabled = bool(enabled)
        app_prefs.update(sound_effects=self.sfx_enabled, sound_enabled=self.sfx_enabled)
        if not self.sfx_enabled:
            self._stop_effects()

    def set_sfx_volume(self, volume: float) -> None:
        self.sfx_volume = _clamp_volume(volume)
        app_prefs.update(
            sound_effects_volume=self.sfx_volume, sound_volume=self.sfx_volume
        )

    def set_cries_enabled(self, enabled: bool) -> None:
        self.cries_enabled = bool(enabled)
        app_prefs.update(cries_enabled=self.cries_enabled)

    def set_cries_volume(self, volume: float) -> None:
        self.cries_volume = _clamp_volume(volume)
        app_prefs.update(cries_volume=self.cries_volume)

    def set_music_enabled(self, enabled: bool) -> None:
        self.music_enabled = bool(enabled)
        app_prefs.update(music_enabled=self.music_enabled, sound_music=self.music_enabled)
        if self.music_enabled:
            self._apply_music(force=True)
        else:
            self._stop_music(clear_label=True)

    def set_music_volume(self, volume: float) -> None:
        self.music_volume = _clamp_volume(volume)
        app_prefs.update(sound_music_volume=self.music_volume)
        if self._music_output is not None:
            try:
                self._music_output.setVolume(
                    _clamp_volume(
                        self.music_volume * self.pack.gains.get("music", 1.0)
                    )
                )
            except RuntimeError:
                pass

    # -- status ------------------------------------------------------------
    def summary(self) -> str:
        return self.pack.summary()

    def status(self) -> dict:
        return {
            "available": self.available,
            "music_available": self.music_available,
            "muted": self.master_muted,
            "pack": self.pack.summary(),
            "pack_name": self.pack.name,
            "cries": len(self.pack.cries),
            "sfx": len(self.pack.sfx),
            "music": len(self.pack.music),
            "trade_music": self.pack.trade_music is not None,
            "music_label": self._music_label,
            "errors": list(self.pack.errors),
        }

    def shutdown(self) -> None:
        self._shut_down = True
        self.stop_all()
        if self._music_player is not None:
            try:
                self._music_player.setSource(QUrl())
            except RuntimeError:
                pass


# ---------------------------------------------------------------------------
# Process-wide accessor.  Before ``init`` every helper is a no-op.
# ---------------------------------------------------------------------------
_MANAGER: SoundManager | None = None


def init(parent=None) -> SoundManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = SoundManager(parent)
    return _MANAGER


def manager() -> SoundManager | None:
    return _MANAGER


def play(cue: str, *, force: bool = False) -> None:
    if _MANAGER is not None:
        _MANAGER.play(cue, force=force)


def play_cry(dex: int) -> None:
    if _MANAGER is not None:
        _MANAGER.play_cry(dex)


def set_theme(theme_id: str) -> None:
    if _MANAGER is not None:
        _MANAGER.set_theme(theme_id)


def set_music_context(context: str) -> None:
    if _MANAGER is not None:
        _MANAGER.set_music_context(context)


def refresh_music(*, force: bool = False) -> None:
    if _MANAGER is not None:
        _MANAGER.refresh_music(force=force)


def reload_pack() -> None:
    if _MANAGER is not None:
        _MANAGER.reload_pack()


def stop_all() -> None:
    if _MANAGER is not None:
        _MANAGER.stop_all()


def shutdown() -> None:
    if _MANAGER is not None:
        _MANAGER.shutdown()
