import math
import os
import sys
import time
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import (
    QByteArray, QEvent, QPointF, QRectF, QSize, Qt, QProcess, QTimer, QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QFontMetrics, QIcon, QKeySequence, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget, QCompleter, QSizePolicy,
    QApplication, QMainWindow, QStackedWidget
)
from PyQt6.QtGui import QDesktopServices

import app_prefs
import core_data
import paths
import sound
import theme
import trade_journal
import user_data
from readiness import collect_checks, open_readiness as show_readiness_dialog, summarize
from utils import (
    BASE_DIR, DATA_DIR, USER_NAME, acquire_admin, detect_wiphy,
    ensure_slot1_dummy, finalize_received_pk3, find_prod_keys,
    network_manager_active, parse_pk3_file,
)
from trainer_profile import load_profile, save_profile
from version import APP_NAME, APP_VERSION
from ui_widgets import (
    MiniDummyLeadBadge, GBATradeCenterPanel, TradeTunnelWidget, SettingsPopup,
)
from sound_settings import SoundSettingsDialog

from pkmds_editor import PKMDSEditorTab
from tab_wondercard import WonderCardTab
from tab_pc import BillsPCTab

# Point to our new unified source directory
SRC_DIR = BASE_DIR / "src"

# ---------------------------------------------------------------------------
# Load Pokemon Names from JSON (matching pkmds_editor logic)
# ---------------------------------------------------------------------------
def load_gen3_species() -> dict[int, str]:
    path = BASE_DIR / "assets" / "data" / "species.json"
    if path.exists():
        try: return {int(k): v for k, v in json.loads(path.read_text()).items()}
        except Exception: pass
    return {i: f"Pokemon #{i}" for i in range(1, 387)}

POKEMON_NAMES = load_gen3_species()

# ---------------------------------------------------------------------------
# 1. Enrich core_data.GEN3_ITEMS with the full FRLG Item Table (IDs 1..374)
# ---------------------------------------------------------------------------
FULL_FRLG_ITEMS = {
    1: "Master Ball", 2: "Ultra Ball", 3: "Great Ball", 4: "Poké Ball",
    5: "Safari Ball", 6: "Net Ball", 7: "Dive Ball", 8: "Nest Ball",
    9: "Repeat Ball", 10: "Timer Ball", 11: "Luxury Ball", 12: "Premier Ball",
    13: "Potion", 14: "Antidote", 15: "Burn Heal", 16: "Ice Heal",
    17: "Awakening", 18: "Parlyz Heal", 19: "Full Restore", 20: "Max Potion",
    21: "Hyper Potion", 22: "Super Potion", 23: "Full Heal", 24: "Revive",
    25: "Max Revive", 26: "Fresh Water", 27: "Soda Pop", 28: "Lemonade",
    29: "Moomoo Milk", 30: "EnergyPowder", 31: "Energy Root", 32: "Heal Powder",
    33: "Revival Herb", 34: "Ether", 35: "Max Ether", 36: "Elixir",
    37: "Max Elixir", 38: "Lava Cookie", 39: "Blue Flute", 40: "Yellow Flute",
    41: "Red Flute", 42: "Black Flute", 43: "White Flute", 44: "Berry Juice",
    45: "Sacred Ash", 46: "Shoal Salt", 47: "Shoal Shell", 48: "Red Shard",
    49: "Blue Shard", 50: "Yellow Shard", 51: "Green Shard",
    63: "HP Up", 64: "Protein", 65: "Iron", 66: "Carbos",
    67: "Calcium", 68: "Rare Candy", 69: "PP Up", 70: "Zinc", 71: "PP Max",
    73: "Guard Spec.", 74: "Dire Hit", 75: "X Attack", 76: "X Defend",
    77: "X Speed", 78: "X Accuracy", 79: "X Special", 80: "Poké Doll",
    81: "Fluffy Tail", 83: "Super Repel", 84: "Max Repel", 85: "Escape Rope",
    86: "Repel", 93: "Sun Stone", 94: "Moon Stone", 95: "Fire Stone",
    96: "Thunderstone", 97: "Water Stone", 98: "Leaf Stone",
    103: "TinyMushroom", 104: "Big Mushroom", 106: "Pearl", 107: "Big Pearl",
    108: "Stardust", 109: "Star Piece", 110: "Nugget", 111: "Heart Scale",
    121: "Orange Mail", 122: "Harbor Mail", 123: "Glitter Mail", 124: "Mech Mail",
    125: "Wood Mail", 126: "Wave Mail", 127: "Bead Mail", 128: "Shadow Mail",
    129: "Tropic Mail", 130: "Dream Mail", 131: "Fab Mail", 132: "Retro Mail",
    133: "Cheri Berry", 134: "Chesto Berry", 135: "Pecha Berry", 136: "Rawst Berry",
    137: "Aspear Berry", 138: "Leppa Berry", 139: "Oran Berry", 140: "Persim Berry",
    141: "Lum Berry", 142: "Sitrus Berry", 143: "Figy Berry", 144: "Wiki Berry",
    145: "Mago Berry", 146: "Aguav Berry", 147: "Iapapa Berry", 148: "Razz Berry",
    149: "Bluk Berry", 150: "Nanab Berry", 151: "Wepear Berry", 152: "Pinap Berry",
    153: "Pomeg Berry", 154: "Kelpsy Berry", 155: "Qualot Berry", 156: "Hondew Berry",
    157: "Grepa Berry", 158: "Tamato Berry", 159: "Cornn Berry", 160: "Magost Berry",
    161: "Rabuta Berry", 162: "Nomel Berry", 163: "Spelon Berry", 164: "Pamtre Berry",
    165: "Watmel Berry", 166: "Durin Berry", 167: "Belue Berry", 168: "Liechi Berry",
    169: "Ganlon Berry", 170: "Salac Berry", 171: "Petaya Berry", 172: "Apicot Berry",
    173: "Lansat Berry", 174: "Starf Berry", 175: "Enigma Berry",
    179: "BrightPowder", 180: "White Herb", 181: "Macho Brace", 182: "Exp. Share",
    183: "Quick Claw", 184: "Soothe Bell", 185: "Mental Herb", 186: "Choice Band",
    187: "King's Rock", 188: "SilverPowder", 189: "Amulet Coin", 190: "Cleanse Tag",
    191: "Soul Dew", 192: "DeepSeaTooth", 193: "DeepSeaScale", 194: "Smoke Ball",
    195: "Everstone", 196: "Focus Band", 197: "Lucky Egg", 198: "Scope Lens",
    199: "Metal Coat", 200: "Leftovers", 201: "Dragon Scale", 202: "Light Ball",
    203: "Soft Sand", 204: "Hard Stone", 205: "Miracle Seed", 206: "BlackGlasses",
    207: "Black Belt", 208: "Magnet", 209: "Mystic Water", 210: "Sharp Beak",
    211: "Poison Barb", 212: "NeverMeltIce", 213: "Spell Tag", 214: "TwistedSpoon",
    215: "Charcoal", 216: "Dragon Fang", 217: "Silk Scarf", 218: "Up-Grade",
    219: "Shell Bell", 220: "Sea Incense", 221: "Lax Incense", 222: "Lucky Punch",
    223: "Metal Powder", 224: "Thick Club", 225: "Stick",
    254: "Red Scarf", 255: "Blue Scarf", 256: "Pink Scarf", 257: "Green Scarf",
    258: "Yellow Scarf", 259: "Mach Bike", 260: "Coin Case", 261: "Itemfinder",
    262: "Old Rod", 263: "Good Rod", 264: "Super Rod", 265: "S.S. Ticket",
    266: "Contest Pass", 268: "Wailmer Pail", 269: "Devon Goods", 270: "Soot Sack",
    271: "Basement Key", 272: "Acro Bike", 273: "Pokéblock Case", 274: "Letter",
    275: "Eon Ticket", 276: "Red Orb", 277: "Blue Orb", 278: "Scanner",
    279: "Go-Goggles", 280: "Meteorite", 281: "Rm. 1 Key", 282: "Rm. 2 Key",
    283: "Rm. 4 Key", 284: "Rm. 6 Key", 285: "Storage Key", 286: "Root Fossil",
    287: "Claw Fossil", 288: "Devon Scope",
    339: "HM01 (Cut)", 340: "HM02 (Fly)", 341: "HM03 (Surf)", 342: "HM04 (Strength)",
    343: "HM05 (Flash)", 344: "HM06 (Rock Smash)", 345: "HM07 (Waterfall)", 346: "HM08 (Dive)",
    349: "Oak's Parcel", 350: "Poké Flute", 351: "Secret Key", 352: "Bike Voucher",
    353: "Gold Teeth", 354: "Old Amber", 355: "Card Key", 356: "Lift Key",
    357: "Helix Fossil", 358: "Dome Fossil", 359: "Silph Scope", 360: "Bicycle",
    361: "Town Map", 362: "Vs. Seeker", 363: "Fame Checker", 364: "TM Case",
    365: "Berry Pouch", 366: "Teachy TV", 367: "Tri-Pass", 368: "Rainbow Pass",
    369: "Tea", 370: "MysticTicket", 371: "AuroraTicket", 372: "Powder Jar",
    373: "Ruby", 374: "Sapphire",
}
for _tm_idx in range(1, 51):
    FULL_FRLG_ITEMS[288 + _tm_idx] = f"TM{_tm_idx:02d}"

for _item_id, _item_name in FULL_FRLG_ITEMS.items():
    if _item_id not in core_data.GEN3_ITEMS:
        _slug = _item_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
        core_data.GEN3_ITEMS[_item_id] = (_item_name, _slug)

# ==============================================================================
# HD-REMASTER MENU PIECES
# ==============================================================================
SPLASH_DIR = BASE_DIR / "assets" / "splash"
_SPLASH_CACHE: dict[tuple[str, int, bool], QPixmap] = {}

# Animated strips built from the games' own battle animations.  Each strip is
# a single row of cells; the title scene blits one cell per frame instead of
# upscaling a bitmap every tick.
_SPLASH_ANIM = {
    "charizard": ("anim_charizard.png", 72),
    "venusaur": ("anim_venusaur.png", 100),
    "hooh": ("anim_hooh.png", 42),
    "lugia": ("anim_lugia.png", 60),
    "latios_full": ("latios_full.png", 1),
    "latias_full": ("latias_full.png", 1),
    "brendan": ("anim_brendan_ride.png", 4),
    "uxie": ("anim_uxie.png", 144),
    "mesprit": ("anim_mesprit.png", 110),
    "azelf": ("anim_azelf.png", 198),
    "reshiram": ("anim_reshiram.png", 143),
    "zekrom": ("anim_zekrom.png", 98),
}
_ANIM_CACHE: dict[str, QPixmap] = {}


# Native frame durations, in milliseconds, for every strip.  The source
# animations are not all 10 fps: FRLG/HGSS play at 100 ms, Platinum and
# Black/White at 60 ms (with occasional longer holds), and the Ruby intro
# bicycle holds each cell for 8 GBA frames (134 ms).  Sampling them all on one
# hard-coded fps was why the Gen 5 and Hoenn scenes ran at the wrong speed.
_SPLASH_TIMING_FILE = SPLASH_DIR / "anim_timing.json"
_SPLASH_TIMING: dict[str, tuple[int, ...]] = {}
try:
    _raw_timing = json.loads(_SPLASH_TIMING_FILE.read_text(encoding="utf-8"))
    for _name, _delays in _raw_timing.items():
        _values = tuple(max(10, int(value)) for value in _delays)
        if _values and sum(_values) > 0:
            _SPLASH_TIMING[str(_name)] = _values
except (OSError, TypeError, ValueError):
    _SPLASH_TIMING = {}


def _anim_strip(name: str) -> QPixmap:
    cached = _ANIM_CACHE.get(name)
    if cached is not None:
        return cached
    entry = _SPLASH_ANIM.get(name)
    pix = QPixmap()
    if entry is not None:
        pix = QPixmap(str(SPLASH_DIR / entry[0]))
    _ANIM_CACHE[name] = pix
    return pix


def _anim_frame(name: str, count: int, t: float, phase: float) -> int:
    """Return the source frame that should be visible at elapsed time *t*.

    Frame selection walks the native GIF delay table rather than multiplying
    by one fps, so variable-duration holds and 60 ms Gen 5 cycles stay in
    sync with the source animation.  *phase* is expressed in source frames.
    """
    delays = _SPLASH_TIMING.get(name)
    if delays is None or len(delays) != count:
        delays = (100,) * count
    total = sum(delays)
    mean = total / count
    position = (t * 1000.0 + phase * mean) % total
    elapsed = 0
    for index, delay in enumerate(delays):
        elapsed += delay
        if position < elapsed:
            return index
    return count - 1


def _splash_pixmap(name: str, size: int, smooth: bool = False) -> QPixmap:
    """Load and cache a splash image at a logical size.

    Game sprites keep hard nearest-neighbour pixels.  The official character
    artwork uses smooth scaling, because it is drawn at two to three times its
    native menu size on a maximized window.
    """
    key = (name, int(size), bool(smooth))
    cached = _SPLASH_CACHE.get(key)
    if cached is not None:
        return cached
    source = QPixmap(str(SPLASH_DIR / name))
    if source.isNull():
        result = QPixmap()
    else:
        mode = (Qt.TransformationMode.SmoothTransformation if smooth
                else Qt.TransformationMode.FastTransformation)
        result = source.scaled(
            int(size), int(size),
            Qt.AspectRatioMode.KeepAspectRatio,
            mode,
        )
    _SPLASH_CACHE[key] = result
    return result


class MenuBackdrop(QWidget):
    """An animated title-screen scene that adopts the active game region.

    The landscape is rendered once into a high-DPI pixmap and cached.  The
    timer runs decorative motion at a steady 30 fps, but also wakes on the
    exact boundary of the next native sprite frame.  Source frames therefore
    hold for their real duration without forcing a 60-100 fps repaint of the
    whole 1440p/4K canvas.
    """

    # Decorative motion (sparkles, bob, flight paths) is capped at 30 fps;
    # sprite cells are scheduled separately from their native timing table.
    FRAME_MS = 33
    MIN_FRAME_MS = 1

    # Animated strips drawn by each scene, with the frame phase passed to
    # _animated().  Static scenes have no entries.
    _SCENE_ANIMATIONS = {
        "gba": (("charizard", 0.0), ("venusaur", 0.0)),
        "hoenn": (("brendan", 0.0),),
        "hgss": (("hooh", 0.0), ("lugia", 0.0)),
        "platinum": (("uxie", 0.0), ("mesprit", 2.7), ("azelf", 5.4)),
        "city": (("reshiram", 0.0), ("zekrom", 0.0)),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0.0
        self._last_tick = None
        self._backdrop = QPixmap()
        self._backdrop_key = None
        self._hoenn_tile = QPixmap()
        self._hoenn_tile_key = None
        self._hoenn_period = 1
        self._hoenn_top = 0.0
        self._hoenn_height = 1.0
        self._hoenn_mid_strip = QPixmap()
        self._hoenn_mid_key = None
        self._hoenn_mid_period = 1
        self._hoenn_mid_top = 0.0
        self._hoenn_mid_height = 1.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._anim_timer.setInterval(self.FRAME_MS)
        self._anim_timer.timeout.connect(self._advance_animation)

    def _retune_animation(self) -> None:
        """Reset the decorative clock and start from the 30 fps cap."""
        if self._anim_timer.interval() != self.FRAME_MS:
            self._anim_timer.setInterval(self.FRAME_MS)
        self._last_tick = None

    def _next_frame_delay(self) -> int:
        """Milliseconds until the next native sprite frame or decor tick."""
        delay = float(self.FRAME_MS)
        style = theme.THEME_MENU_STYLE
        for name, phase in self._SCENE_ANIMATIONS.get(style, ()):
            entry = _SPLASH_ANIM.get(name)
            delays = _SPLASH_TIMING.get(name)
            if entry is None or delays is None or entry[1] <= 1:
                continue
            if len(delays) != entry[1]:
                continue
            total = sum(delays)
            mean = total / len(delays)
            position = (self._t * 1000.0 + phase * mean) % total
            elapsed = 0
            for frame_delay in delays:
                elapsed += frame_delay
                if elapsed > position:
                    delay = min(delay, elapsed - position)
                    break
                # Landed exactly on a boundary: this frame has just started,
                # so schedule the end of the following frame instead.
        return max(self.MIN_FRAME_MS, int(math.ceil(delay)))

    def showEvent(self, event):
        super().showEvent(event)
        self._retune_animation()
        self._anim_timer.start()

    def hideEvent(self, event):
        self._anim_timer.stop()
        super().hideEvent(event)

    def resume_animation(self) -> None:
        """Restart cleanly after the window regains focus or is restored.

        Qt pauses repaints for obscured windows on some window managers.  The
        timer can keep running there, but the next visible frame would jump by
        a large amount of elapsed time.  Resetting the clock and restarting the
        timer makes the scene continue from the current frame instead.
        """
        if not self.isVisible() or self.window().isMinimized():
            return
        self._last_tick = None
        if not self._anim_timer.isActive():
            self._anim_timer.start()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._retune_animation()

    def _advance_animation(self):
        if not self.isVisible() or self.window().isMinimized():
            self._last_tick = None
            return
        # Keep the scene alive while the window is open, even when the user
        # is working in another application; only minimize/hide pauses it.
        now = time.monotonic()
        if self._last_tick is None:
            self._last_tick = now
            return
        # Real elapsed time keeps the motion speed stable even when the
        # scheduler stretches or shortens the interval around a sprite frame.
        self._t += min(0.25, max(0.0, now - self._last_tick))
        self._last_tick = now
        self.update()
        interval = self._next_frame_delay()
        if interval != self._anim_timer.interval():
            self._anim_timer.setInterval(interval)

    def _art(self, p: QPainter, name: str, cx: float, cy: float,
             size: int, *, opacity: float = 1.0, angle: float = 0.0,
             flip: bool = False, scale: float = 1.0, squash: float = 1.0):
        """Draw smooth official artwork with a small flight/flap transform."""
        pix = _splash_pixmap(name, max(32, int(size)), smooth=True)
        if pix.isNull():
            return
        p.save()
        p.setOpacity(opacity)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.translate(cx, cy)
        p.rotate(angle)
        if flip:
            p.scale(-1, 1)
        p.scale(scale, scale * squash)
        p.drawPixmap(QPointF(-pix.width() / 2, -pix.height() / 2), pix)
        p.restore()

    def _pixel(self, p: QPainter, name: str, cx: float, cy: float,
               size: int, *, opacity: float = 1.0, angle: float = 0.0,
               flip: bool = False):
        """Draw an actual game sprite without softening its pixels."""
        pix = _splash_pixmap(name, max(16, int(size)), smooth=False)
        if pix.isNull():
            return
        p.save()
        p.setOpacity(opacity)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.translate(cx, cy)
        p.rotate(angle)
        if flip:
            p.scale(-1, 1)
        p.drawPixmap(QPointF(-pix.width() / 2, -pix.height() / 2), pix)
        p.restore()

    def _animated(self, p: QPainter, name: str, cx: float, cy: float,
                  size: float, *, t: float,
                  opacity: float = 1.0, angle: float = 0.0,
                  flip: bool = False, flip_v: bool = False,
                  squash: float = 1.0, phase: float = 0.0):
        """Blit one frame of a native-resolution in-game animation strip.

        The frame index comes from the strip's native GIF delay table, so
        every source frame is shown for its real duration.  The strip is
        scaled by a whole *device-pixel* factor, not a fractional logical
        factor.  That is the difference between a crisp 3x sprite and a
        sprite whose pixels alternate between two and three screen pixels.
        Rotation is intentionally ignored: rotating pixel art resamples it
        and produces exactly the smeared edges this renderer exists to avoid.
        """
        entry = _SPLASH_ANIM.get(name)
        strip = _anim_strip(name)
        if entry is None or strip.isNull():
            return
        count = entry[1]
        cell_w = strip.width() // count
        cell_h = strip.height()
        if cell_w <= 0 or cell_h <= 0:
            return
        frame = _anim_frame(name, count, t, phase)
        dpr = max(1.0, self.devicePixelRatioF())
        target_phys = max(16.0, float(size) * dpr)
        scale = max(1, int(round(target_phys / max(cell_w, cell_h))))
        dest_w = cell_w * scale / dpr
        dest_h = cell_h * scale / dpr
        # Snap the sprite centre to a whole physical pixel; otherwise even a
        # perfect integer scale can land on a half-pixel and get blurred by
        # the compositor.
        cxp = round(cx * dpr) / dpr
        cyp = round(cy * dpr) / dpr
        p.save()
        p.setOpacity(opacity)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.translate(cxp, cyp)
        if flip:
            p.scale(-1, 1)
        if flip_v:
            p.scale(1, -1)
        p.drawPixmap(
            QRectF(-dest_w / 2, -dest_h / 2, dest_w, dest_h),
            strip,
            QRectF(frame * cell_w, 0, cell_w, cell_h),
        )
        p.restore()

    def _build_backdrop(self, w: int, h: int, style: str):
        """Rasterise the non-moving scenery once per size/theme combination."""
        dpr = max(1.0, self.devicePixelRatioF())
        pix = QPixmap(max(1, int(round(w * dpr))),
                      max(1, int(round(h * dpr))))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # A QPixmap with a device pixel ratio already maps logical coordinates
        # through that ratio; scaling the painter again would render only the
        # top-left 1/dpr of the scene on a 125-200% desktop.
        p.setClipRect(QRectF(0, 0, w, h))
        self._paint_sky(p, w, h, style)
        self._paint_static(p, w, h, style)
        p.end()
        self._backdrop = pix
        self._backdrop_key = (w, h, style, theme.THEME_ID, round(dpr, 2))

    def _sprite(self, p: QPainter, name: str, cx: float, cy: float,
                size: int, *, opacity: float = 1.0, flip: bool = False):
        pix = _splash_pixmap(name, size)
        if pix.isNull():
            return
        p.save()
        p.setOpacity(opacity)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        if flip:
            p.translate(cx, 0)
            p.scale(-1, 1)
            p.translate(-cx, 0)
        p.drawPixmap(QPointF(cx - pix.width() / 2, cy - pix.height() / 2), pix)
        p.restore()

    def _aura(self, p: QPainter, cx: float, cy: float, radius: float,
              color: str, alpha: int = 40):
        glow = QRadialGradient(QPointF(cx, cy), radius)
        c = QColor(color)
        c.setAlpha(alpha)
        glow.setColorAt(0.0, c)
        c.setAlpha(0)
        glow.setColorAt(1.0, c)
        p.fillRect(QRectF(cx - radius, cy - radius,
                          radius * 2, radius * 2), glow)

    def _paint_sky(self, p: QPainter, w: int, h: int, style: str):
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0.0, QColor(theme.MENU_SKY_TOP))
        sky.setColorAt(0.46, QColor(theme.MENU_SKY_MID))
        sky.setColorAt(0.72, QColor(theme.MENU_SKY_LOW))
        sky.setColorAt(1.0, QColor(theme.MENU_SKY_BOTTOM))
        p.fillRect(self.rect(), sky)

        if style in ("night", "platinum", "city"):
            p.setPen(Qt.PenStyle.NoPen)
            for i, (sx, sy, sr) in enumerate([
                (0.04, 0.08, 1.3), (0.12, 0.20, 0.9), (0.21, 0.06, 1.1),
                (0.31, 0.16, 1.5), (0.41, 0.09, 0.8), (0.56, 0.19, 1.2),
                (0.66, 0.07, 1.4), (0.76, 0.14, 0.9), (0.88, 0.06, 1.2),
                (0.95, 0.22, 1.0), (0.09, 0.34, 0.8), (0.48, 0.30, 0.8),
                (0.26, 0.39, 0.7), (0.58, 0.36, 0.9), (0.73, 0.44, 0.8),
            ]):
                p.setBrush(QColor(244, 237, 210, 115 + (i % 4) * 25))
                p.drawEllipse(QPointF(w * sx, h * sy), sr, sr)
            if style == "night":
                moon = QRadialGradient(QPointF(w * 0.80, h * 0.20), min(w, h) * 0.30)
                moon.setColorAt(0.0, QColor(240, 225, 178, 120))
                moon.setColorAt(0.25, QColor(240, 225, 178, 42))
                moon.setColorAt(1.0, QColor(240, 225, 178, 0))
                p.fillRect(self.rect(), moon)
                p.setBrush(QColor(245, 235, 203, 205))
                p.drawEllipse(QPointF(w * 0.80, h * 0.20), 24, 24)
            elif style == "city":
                glow = QRadialGradient(QPointF(w * 0.50, h * 0.67), w * 0.46)
                glow.setColorAt(0.0, QColor(91, 209, 218, 90))
                glow.setColorAt(0.50, QColor(60, 116, 160, 35))
                glow.setColorAt(1.0, QColor(8, 25, 38, 0))
                p.fillRect(self.rect(), glow)
            else:
                glow = QRadialGradient(QPointF(w * 0.72, h * 0.24), min(w, h) * 0.38)
                glow.setColorAt(0.0, QColor(205, 228, 247, 80))
                glow.setColorAt(0.45, QColor(160, 193, 220, 24))
                glow.setColorAt(1.0, QColor(160, 193, 220, 0))
                p.fillRect(self.rect(), glow)
        else:
            # Hoenn's intro is a late-afternoon ride: put the sun over the
            # water, where the Latios path can cut across its reflection.
            sx = 0.80 if style == "hoenn" else 0.18
            sy = 0.24 if style == "hoenn" else 0.10
            sun = QRadialGradient(QPointF(w * sx, h * sy), max(w, h) * 0.55)
            sun.setColorAt(0.0, QColor(255, 251, 220, 235))
            sun.setColorAt(0.35, QColor(255, 247, 207, 110))
            sun.setColorAt(1.0, QColor(255, 247, 207, 0))
            p.fillRect(self.rect(), sun)

        # Hoenn paints its own clouds in _animate_hoenn() so they can drift
        # with the camera instead of being baked into the backdrop.
        if style != "hoenn":
            cloud_alpha = (34 if style == "city"
                           else 48 if style == "platinum"
                           else 100 if style == "night" else 170)
            theme.draw_cloud(p, w * 0.06, h * 0.13, 1.7, cloud_alpha)
            theme.draw_cloud(p, w * 0.68, h * 0.09, 2.2, cloud_alpha - 15)
            theme.draw_cloud(p, w * 0.84, h * 0.32, 1.1, max(12, cloud_alpha - 30))
            # Keep the title/overline corridor clear; clouds sit beside it, not
            # directly under the lettering.
            theme.draw_cloud(p, w * 0.19, h * 0.35, 0.9, max(12, cloud_alpha - 35))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 18))
        for y in range(8, h, 16):
            offset = (y // 16) % 2 * 8
            for x in range(offset, w, 16):
                p.drawRect(x, y, 2, 2)

    def _paint_hills(self, p: QPainter, w: int, h: int,
                     *, path: bool = True, sea: bool = False,
                     hills: bool = True):
        def hill(base_y, amplitude, color, shift=0):
            shape = QPainterPath()
            shape.moveTo(0, h)
            shape.lineTo(0, base_y)
            step = max(24, w // 28)
            x = 0
            while x <= w:
                wave = math.sin((x / w) * math.pi * 2.2 + shift) * amplitude
                shape.lineTo(x, base_y + wave)
                shape.lineTo(x + step / 2, base_y + wave * 0.55)
                x += step
            shape.lineTo(w, h)
            shape.closeSubpath()
            p.setBrush(QColor(color))
            p.drawPath(shape)

        if sea:
            water = QLinearGradient(0, h * 0.52, 0, h * 0.82)
            water.setColorAt(0.0, QColor(theme.BLUE_LIGHT))
            water.setColorAt(0.42, QColor(theme.BLUE))
            water.setColorAt(1.0, QColor(theme.NAVY))
            p.fillRect(QRectF(0, h * 0.52, w, h * 0.34), water)
            p.setPen(QPen(QColor(255, 255, 255, 130), 2))
            p.drawLine(QPointF(0, h * 0.522), QPointF(w, h * 0.522))
            p.setPen(Qt.PenStyle.NoPen)

        # Hoenn supplies its own scrolling coastline.  Painting the static
        # ridges underneath it would leave a fixed green edge above moving
        # grass, which kills the camera-pan illusion.
        if not hills:
            return

        hill(h * 0.73, 16, theme.MENU_HILL_1, 0.4)
        hill(h * 0.81, 22, theme.MENU_HILL_2, 2.1)
        hill(h * 0.90, 14, theme.MENU_HILL_3, 4.2)

        if path:
            shape = QPainterPath()
            shape.moveTo(w * 0.47, h)
            shape.cubicTo(w * 0.46, h * 0.95, w * 0.55, h * 0.89,
                          w * 0.56, h * 0.82)
            shape.lineTo(w * 0.59, h * 0.82)
            shape.cubicTo(w * 0.58, h * 0.90, w * 0.52, h * 0.95,
                          w * 0.56, h)
            shape.closeSubpath()
            p.setBrush(QColor(theme.MENU_PATH))
            p.drawPath(shape)

        # The old three-pixel grass marks read as tiny signal bars sitting
        # above the bottom-left menu hint, especially on HGSS.  Each scene
        # that wants ground detail now draws its own vegetation.

    def _paint_bell_tower(self, p: QPainter, w: int, h: int):
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setOpacity(0.28)
        p.setBrush(QColor(theme.MENU_HILL_3))
        cx = w * 0.11
        base = h * 0.77
        body = w * 0.052
        p.drawRect(QRectF(cx - body / 2, base - h * 0.30, body, h * 0.30))
        for i, width in enumerate((0.078, 0.066, 0.052)):
            y = base - h * (0.14 + i * 0.09)
            p.drawRect(QRectF(cx - w * width / 2, y,
                              w * width, h * 0.020))
            roof = QPainterPath()
            roof.moveTo(cx - w * (width + 0.018) / 2, y)
            roof.lineTo(cx, y - h * 0.035)
            roof.lineTo(cx + w * (width + 0.018) / 2, y)
            roof.closeSubpath()
            p.drawPath(roof)
        spire = QPainterPath()
        spire.moveTo(cx - w * 0.008, base - h * 0.30)
        spire.lineTo(cx, base - h * 0.38)
        spire.lineTo(cx + w * 0.008, base - h * 0.30)
        spire.closeSubpath()
        p.drawPath(spire)
        p.restore()

    def _paint_static(self, p: QPainter, w: int, h: int, style: str):
        if style == "hgss":
            self._paint_hgss(p, w, h)
        elif style == "hoenn":
            self._paint_hoenn(p, w, h)
        elif style == "platinum":
            self._paint_platinum(p, w, h)
        elif style == "gba":
            self._paint_frlg(p, w, h)
        elif style == "city":
            self._paint_unova(p, w, h)
        elif style == "night":
            self._paint_night(p, w, h)
        else:
            self._paint_light(p, w, h)

    def _paint_hgss(self, p: QPainter, w: int, h: int):
        """A two-panel Johto title: sunrise and Bell Tower versus moonlit sea."""
        self._paint_hills(p, w, h, path=False)

        left = QLinearGradient(0, 0, w * 0.52, 0)
        left.setColorAt(0.0, QColor(255, 196, 105, 58))
        left.setColorAt(0.62, QColor(255, 166, 86, 18))
        left.setColorAt(1.0, QColor(255, 150, 80, 0))
        p.fillRect(QRectF(0, 0, w * 0.54, h), left)

        right = QLinearGradient(w * 0.46, 0, w, 0)
        right.setColorAt(0.0, QColor(14, 42, 68, 0))
        right.setColorAt(0.70, QColor(14, 42, 68, 112))
        right.setColorAt(1.0, QColor(10, 32, 55, 178))
        p.fillRect(QRectF(w * 0.46, 0, w * 0.54, h), right)

        sea = QLinearGradient(0, h * 0.62, 0, h)
        sea.setColorAt(0.0, QColor(21, 71, 98, 0))
        sea.setColorAt(0.18, QColor(21, 71, 98, 155))
        sea.setColorAt(1.0, QColor(8, 34, 55, 225))
        p.fillRect(QRectF(w * 0.48, h * 0.62, w * 0.52, h * 0.38), sea)

        p.setPen(QPen(QColor(177, 229, 244, 70), 1))
        for i in range(8):
            y = h * (0.68 + i * 0.027)
            x = w * (0.52 + (i % 3) * 0.06)
            p.drawLine(QPointF(x, y), QPointF(x + w * 0.12, y))

        # Whirl Islands: low, dark arches on the sea side.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 31, 48, 205))
        islands = QPainterPath()
        islands.moveTo(w * 0.62, h * 0.79)
        islands.cubicTo(w * 0.68, h * 0.69, w * 0.73, h * 0.70,
                        w * 0.78, h * 0.79)
        islands.cubicTo(w * 0.84, h * 0.72, w * 0.90, h * 0.73,
                        w * 0.96, h * 0.81)
        islands.lineTo(w, h * 0.86)
        islands.lineTo(w * 0.56, h * 0.86)
        islands.closeSubpath()
        p.drawPath(islands)

        self._paint_bell_tower(p, w, h)

        moon = QRadialGradient(QPointF(w * 0.84, h * 0.18), min(w, h) * 0.20)
        moon.setColorAt(0.0, QColor(231, 241, 255, 120))
        moon.setColorAt(0.28, QColor(191, 221, 250, 42))
        moon.setColorAt(1.0, QColor(191, 221, 250, 0))
        p.fillRect(self.rect(), moon)
        p.setBrush(QColor(235, 244, 255, 220))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(w * 0.84, h * 0.18), min(w, h) * 0.024,
                      min(w, h) * 0.024)

        sun = QRadialGradient(QPointF(w * 0.12, h * 0.19), min(w, h) * 0.25)
        sun.setColorAt(0.0, QColor(255, 226, 151, 138))
        sun.setColorAt(0.35, QColor(255, 197, 108, 38))
        sun.setColorAt(1.0, QColor(255, 197, 108, 0))
        p.fillRect(self.rect(), sun)

        # The two skies already meet through their own gradients.  An extra
        # seam strip here read as a stray vertical bar down the middle of the
        # title screen, so the halves now transition without a drawn divider.
        p.setPen(QPen(QColor(255, 226, 157, 60), 1))
        for i in range(10):
            x = w * (0.03 + (i * 0.043) % 0.34)
            y = h * (0.22 + (i * 0.067) % 0.45)
            p.drawLine(QPointF(x, y), QPointF(x + 3, y - 8))

    def _paint_hoenn(self, p: QPainter, w: int, h: int):
        """A late-afternoon Hoenn coast: sea, islands and a lighthouse.

        Only the sea lives in the static backdrop; the coastline and the
        horizon landmarks are painted live so they can drift with the camera
        pan.  The near coast is two scrolling bands in _animate_hoenn().
        """
        self._paint_hills(p, w, h, sea=True, path=False, hills=False)

    def _paint_hoenn_landmark(self, p: QPainter, w: int, h: int):
        """Sootopolis-style cliffs and a lighthouse on the horizon.

        Painted after the drifting island so that island passes behind this
        landmass instead of sliding across its face.  It still stays low so
        the menu row keeps its breathing room.
        """
        island = QPainterPath()
        island.moveTo(w * 0.615, h * 0.680)
        island.cubicTo(w * 0.670, h * 0.610, w * 0.735, h * 0.620,
                       w * 0.785, h * 0.678)
        island.lineTo(w * 0.815, h * 0.686)
        island.lineTo(w * 0.590, h * 0.686)
        island.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 79, 68, 190))
        p.drawPath(island)

        # Lilycove lighthouse: a tiny white tower and a warm gallery light.
        tower_x = w * 0.706
        tower_base = h * 0.674
        tower_w = max(5.0, w * 0.0052)
        tower_h = max(20.0, h * 0.048)
        p.setBrush(QColor(232, 244, 221, 225))
        p.drawRect(QRectF(tower_x - tower_w / 2, tower_base - tower_h,
                          tower_w, tower_h))
        p.setBrush(QColor(34, 87, 75, 230))
        p.drawRect(QRectF(tower_x - tower_w * 0.72, tower_base - tower_h * 1.18,
                          tower_w * 1.44, tower_h * 0.18))
        p.setBrush(QColor(246, 214, 124, 235))
        p.drawRect(QRectF(tower_x - tower_w * 0.44, tower_base - tower_h * 1.10,
                          tower_w * 0.88, tower_h * 0.14))
        beam = QLinearGradient(tower_x, 0, tower_x + w * 0.12, 0)
        beam.setColorAt(0.0, QColor(255, 238, 172, 35))
        beam.setColorAt(1.0, QColor(255, 238, 172, 0))
        p.setBrush(beam)
        p.drawPolygon(QPolygonF([
            QPointF(tower_x + tower_w * 0.4, tower_base - tower_h * 1.06),
            QPointF(tower_x + w * 0.13, tower_base - tower_h * 1.22),
            QPointF(tower_x + w * 0.13, tower_base - tower_h * 0.92),
        ]))

    def _paint_hoenn_clouds(self, p: QPainter, w: int, h: int, t: float):
        """Chunky clouds drifting slowly above the coast.

        These replace the static sky clouds for Hoenn.  Each cloud travels
        at its own slow speed and wraps outside the viewport, so the sky has
        the same unhurried parallax as the Ruby/Sapphire intro rather than a
        fixed painted backdrop.  Positions are snapped to the device pixel
        grid so the blocky edges stay crisp at fractional UI scales.
        """
        dpr = max(1.0, float(self.devicePixelRatioF()))
        span = w * 1.35
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for base, y_frac, cloud_scale, alpha, speed in (
            (0.02, 0.075, 1.30, 128, 9.0),
            (0.38, 0.125, 0.90, 112, 6.0),
            (0.66, 0.055, 0.72, 96, 4.5),
            (0.86, 0.235, 1.05, 104, 12.0),
            (0.19, 0.285, 1.15, 88, 14.0),
        ):
            x = (base * span + t * speed) % span - 0.12 * w
            theme.draw_cloud(p, round(x * dpr) / dpr, h * y_frac,
                             cloud_scale, alpha)
        p.restore()

    def _paint_hoenn_distant_island(self, p: QPainter, w: int, h: int, t: float):
        """A hazy island keeping its own slow pace on the horizon.

        It is painted before the lighthouse island and the scrolling coast
        bands, so those layers occlude it as it passes.  At roughly 7 px/s it
        reads as a distant landmark moving with the camera, not another
        scrolling hill.
        """
        dpr = max(1.0, float(self.devicePixelRatioF()))
        span = w * 1.60
        x = (0.30 * span + t * 7.0) % span - 0.18 * w
        x = round(x * dpr) / dpr
        island_w = max(46.0, w * 0.085)
        baseline = h * 0.668
        rise = max(8.0, h * 0.015)

        shape = QPainterPath()
        shape.moveTo(x, baseline)
        shape.cubicTo(x + island_w * 0.22, baseline - rise * 1.35,
                      x + island_w * 0.40, baseline - rise * 1.28,
                      x + island_w * 0.57, baseline - rise * 0.70)
        shape.cubicTo(x + island_w * 0.68, baseline - rise * 0.54,
                      x + island_w * 0.80, baseline - rise * 0.92,
                      x + island_w, baseline)
        shape.closeSubpath()

        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        # A little sea haze keeps the silhouette from reading as a sticker.
        haze = QLinearGradient(0, baseline - rise * 1.9, 0, baseline + 2)
        haze.setColorAt(0.0, QColor(196, 235, 221, 0))
        haze.setColorAt(0.55, QColor(196, 235, 221, 46))
        haze.setColorAt(1.0, QColor(196, 235, 221, 0))
        p.fillRect(QRectF(x - island_w * 0.22, baseline - rise * 1.9,
                          island_w * 1.44, rise * 2.2), haze)
        p.setBrush(QColor(44, 112, 96, 148))
        p.drawPath(shape)
        # One lighter patch and a dark waterline give it a little form.
        p.setBrush(QColor(112, 177, 151, 62))
        p.drawEllipse(QPointF(x + island_w * 0.34, baseline - rise * 0.62),
                      island_w * 0.15, rise * 0.20)
        p.setBrush(QColor(26, 82, 70, 155))
        p.drawRect(QRectF(x + island_w * 0.06, baseline - rise * 0.06,
                          island_w * 0.88, max(1.0, h / 1500)))
        p.restore()

    def _hoenn_scroll_tile(self, w: int, h: int):
        """Build the seamless foreground strip for the Hoenn coast.

        The strip is rasterised once per window size, theme and DPR, then
        blitted twice (or more, on ultrawide screens) at whole physical-pixel
        offsets.  Redrawing two dozen grass blades and flowers on every 33 ms
        tick would be wasteful at 4K; a cached strip keeps the scroll cheap
        while leaving the characters and their native timings untouched.
        """
        dpr = max(1.0, float(self.devicePixelRatioF()))
        key = (w, h, theme.THEME_ID, round(dpr, 2))
        if (self._hoenn_tile_key == key
                and not self._hoenn_tile.isNull()):
            return (self._hoenn_tile, self._hoenn_period,
                    self._hoenn_top, self._hoenn_height)

        period = max(360, min(760, int(round(w * 0.55))))
        top = h * 0.855
        height = max(80.0, h - top + 8.0)
        pix = QPixmap(max(1, int(round(period * dpr))),
                      max(1, int(round(height * dpr))))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # A periodic edge gives the strip a natural, seamless silhouette.
        # The two harmonics keep it from reading as a perfectly mechanical
        # sine wave as it slides past.
        edge_base = max(7.0, height * 0.10)
        amp_a = max(3.0, height * 0.055)
        amp_b = max(1.5, height * 0.022)

        def edge_y(x: float) -> float:
            return (edge_base
                    + amp_a * math.sin(math.tau * x / period)
                    + amp_b * math.sin(math.tau * 2.0 * x / period + 0.9))

        step = max(4, period // 96)
        # Bleed the coast a couple of pixels past both tile edges.  Without
        # that, antialiasing leaves the first and last pixmap columns half
        # transparent and two abutting strips show a dark hairline.
        bleed = 2.0
        ground = QPainterPath()
        ground.moveTo(-bleed, height)
        for x in range(-2, period + step + 2, step):
            ground.lineTo(min(period + bleed, x), edge_y(x))
        ground.lineTo(period + bleed, height)
        ground.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.MENU_HILL_3))
        p.drawPath(ground)

        rim = QPainterPath()
        rim.moveTo(-bleed, edge_y(-bleed))
        for x in range(0, period + step + 2, step):
            rim.lineTo(min(period + bleed, x), edge_y(x))
        rim.lineTo(period + bleed, edge_y(period + bleed))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(theme.MENU_HILL_2), max(1.0, height * 0.008)))
        p.drawPath(rim)

        # Grass tufts, flowers and stones are baked into the strip so they
        # travel with the ground rather than shimmering independently.
        grass_pen = QPen(QColor(theme.MENU_HILL_2), max(1.0, height * 0.010))
        grass_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(grass_pen)
        for i in range(11):
            gx = period * (i + 0.35) / 11.0
            gy = edge_y(gx) + height * (0.15 + (i % 3) * 0.045)
            p.drawLine(QPointF(gx, gy),
                       QPointF(gx - height * 0.012, gy - height * 0.038))
            p.drawLine(QPointF(gx, gy),
                       QPointF(gx + height * 0.010, gy - height * 0.050))
            p.drawLine(QPointF(gx, gy),
                       QPointF(gx + height * 0.022, gy - height * 0.022))

        for fx, color in (
            (0.070, "#f6dd8a"), (0.185, "#f0a6a0"),
            (0.310, "#ffffff"), (0.445, "#e88b8d"),
            (0.610, "#f6dd8a"), (0.760, "#ffffff"),
            (0.890, "#f0a6a0"),
        ):
            fx = period * fx
            fy = edge_y(fx) + height * 0.22
            p.setPen(QPen(QColor(20, 66, 45, 185), max(1.0, height * 0.008)))
            p.drawLine(QPointF(fx, fy), QPointF(fx, fy - height * 0.035))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(fx, fy - height * 0.040),
                          max(1.6, height * 0.014),
                          max(1.6, height * 0.014))
            p.setBrush(QColor(255, 248, 220, 210))
            p.drawEllipse(QPointF(fx, fy - height * 0.040),
                          max(0.6, height * 0.005),
                          max(0.6, height * 0.005))

        for fx, fy, rx, ry in (
            (0.135, 0.66, 0.016, 0.010),
            (0.525, 0.78, 0.022, 0.012),
            (0.825, 0.58, 0.013, 0.008),
        ):
            cx = period * fx
            cy = edge_y(cx) + height * fy
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(22, 60, 48, 195))
            p.drawEllipse(QPointF(cx, cy), period * rx, height * ry)
            p.setBrush(QColor(57, 104, 76, 150))
            p.drawEllipse(QPointF(cx - period * rx * 0.18,
                                  cy - height * ry * 0.22),
                          period * rx * 0.55, height * ry * 0.50)

        p.end()
        self._hoenn_tile = pix
        self._hoenn_tile_key = key
        self._hoenn_period = period
        self._hoenn_top = top
        self._hoenn_height = height
        return pix, period, top, height

    def _hoenn_mid_tile(self, w: int, h: int):
        """The slower, lighter ridge behind the foreground strip."""
        dpr = max(1.0, float(self.devicePixelRatioF()))
        key = (w, h, theme.THEME_ID, round(dpr, 2))
        if (self._hoenn_mid_key == key
                and not self._hoenn_mid_strip.isNull()):
            return (self._hoenn_mid_strip, self._hoenn_mid_period,
                    self._hoenn_mid_top, self._hoenn_mid_height)

        period = max(420, min(920, int(round(w * 0.68))))
        # Start the ridge at the waterline so the most visible edge of the
        # coast travels with the parallax instead of sitting still.
        top = h * 0.735
        height = max(120.0, h - top + 8.0)
        pix = QPixmap(max(1, int(round(period * dpr))),
                      max(1, int(round(height * dpr))))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        edge_base = max(8.0, height * 0.065)
        amp_a = max(3.0, height * 0.040)
        amp_b = max(1.5, height * 0.017)

        def edge_y(x: float) -> float:
            return (edge_base
                    + amp_a * math.sin(math.tau * x / period + 0.4)
                    + amp_b * math.sin(math.tau * 2.0 * x / period + 2.1))

        ground = QPainterPath()
        ground.moveTo(-2.0, height)
        step = max(5, period // 80)
        for x in range(-2, period + step + 2, step):
            ground.lineTo(min(period + 2.0, x), edge_y(x))
        ground.lineTo(period + 2.0, height)
        ground.closeSubpath()
        fill = QLinearGradient(0, 0, 0, height)
        fill.setColorAt(0.0, QColor(theme.MENU_HILL_2))
        fill.setColorAt(1.0, QColor(theme.MENU_HILL_3))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPath(ground)

        rim = QPainterPath()
        rim.moveTo(-2.0, edge_y(-2.0))
        for x in range(0, period + step + 2, step):
            rim.lineTo(min(period + 2.0, x), edge_y(x))
        rim.lineTo(period + 2.0, edge_y(period + 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(theme.MENU_HILL_1), max(1.0, height * 0.007)))
        p.drawPath(rim)

        p.setPen(QPen(QColor(theme.MENU_HILL_3), max(1.0, height * 0.007)))
        for i in range(15):
            gx = period * (i + 0.55) / 15.0
            gy = edge_y(gx) + height * (0.13 + (i % 3) * 0.045)
            p.drawLine(QPointF(gx, gy),
                       QPointF(gx - height * 0.010, gy - height * 0.026))
            p.drawLine(QPointF(gx, gy),
                       QPointF(gx + height * 0.009, gy - height * 0.034))
            p.drawLine(QPointF(gx, gy),
                       QPointF(gx + height * 0.019, gy - height * 0.018))
        for fx, color in (
            (0.095, "#f6dd8a"), (0.235, "#ffffff"),
            (0.390, "#f0a6a0"), (0.555, "#f6dd8a"),
            (0.720, "#ffffff"), (0.865, "#e88b8d"),
        ):
            fx = period * fx
            fy = edge_y(fx) + height * 0.28
            p.setPen(QPen(QColor(20, 66, 45, 155), max(1.0, height * 0.006)))
            p.drawLine(QPointF(fx, fy), QPointF(fx, fy - height * 0.025))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(fx, fy - height * 0.030),
                          max(1.2, height * 0.010),
                          max(1.2, height * 0.010))
        p.end()
        self._hoenn_mid_strip = pix
        self._hoenn_mid_key = key
        self._hoenn_mid_period = period
        self._hoenn_mid_top = top
        self._hoenn_mid_height = height
        return pix, period, top, height

    def _paint_hoenn_mid_scroll(self, p: QPainter, w: int, h: int, t: float):
        tile, period, top, _height = self._hoenn_mid_tile(w, h)
        if tile.isNull():
            return
        dpr = max(1.0, float(self.devicePixelRatioF()))
        offset = (t * 62.0) % period
        # Step by the tile's real physical width.  Rounding each logical
        # position independently can make the stride 1056 or 1057 px at
        # 150%, which opens a one-pixel seam between neighbouring strips.
        tile_w = max(1, tile.width())
        start_phys = int(round((offset - period) * dpr))
        count = int(math.ceil((w * dpr) / tile_w)) + 2
        y = round(top * dpr) / dpr
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        for i in range(count):
            x = (start_phys + i * tile_w) / dpr
            p.drawPixmap(QPointF(x, y), tile)
        p.restore()

    def _paint_hoenn_scroll(self, p: QPainter, w: int, h: int, t: float):
        """Scroll the foreground right, as if the camera is pacing left."""
        tile, period, top, _height = self._hoenn_scroll_tile(w, h)
        if tile.isNull():
            return
        dpr = max(1.0, float(self.devicePixelRatioF()))
        offset = (t * 100.0) % period
        tile_w = max(1, tile.width())
        start_phys = int(round((offset - period) * dpr))
        count = int(math.ceil((w * dpr) / tile_w)) + 2
        y = round(top * dpr) / dpr
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        for i in range(count):
            x = (start_phys + i * tile_w) / dpr
            p.drawPixmap(QPointF(x, y), tile)
        p.restore()

    def _paint_hoenn_water_scroll(self, p: QPainter, w: int, h: int, t: float):
        """Move the sea in layers: far chop slow, near-shore foam faster.

        The same camera pan that drives the coast reads through the water.
        Long, faint dashes at the horizon travel a few pixels a second, while
        the short foam lines just off the beach keep pace with the mid ridge.
        """
        p.save()
        p.setPen(QPen(QColor(236, 254, 240, 38), max(1.0, h / 1100)))
        for row in range(7):
            y = h * (0.560 + row * 0.020)
            offset = (t * 17.0 + row * 37.0) % (w * 0.31)
            for dash in range(4):
                x = (w * (0.04 + dash * 0.26) + offset) % (w * 1.04)
                p.drawLine(QPointF(x, y), QPointF(min(w, x + w * 0.065), y))

        p.setPen(QPen(QColor(236, 254, 240, 95), max(1.0, h / 950)))
        for row in range(4):
            y = h * (0.700 + row * 0.008)
            offset = (t * 44.0 + row * 61.0) % (w * 0.24)
            for dash in range(6):
                x = (w * (0.02 + dash * 0.205) + offset) % (w * 1.02)
                p.drawLine(QPointF(x, y), QPointF(min(w, x + w * 0.055), y))
        p.setPen(Qt.PenStyle.NoPen)
        p.restore()

    def _paint_hoenn_ledge(self, p: QPainter, w: int, h: int):
        """The dark cliff that frames the bottom-left corner."""
        p.save()
        ledge = QPainterPath()
        ledge.moveTo(0, h * 0.900)
        ledge.cubicTo(w * 0.07, h * 0.862, w * 0.13, h * 0.874,
                      w * 0.20, h * 0.918)
        ledge.lineTo(w * 0.22, h)
        ledge.lineTo(0, h)
        ledge.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(22, 73, 54, 230))
        p.drawPath(ledge)
        # The three palm silhouettes that used to sprout here sat directly
        # behind the SELECT A SYSTEM plate and read as stray marks.  The
        # foreground scroll already supplies the coast's vegetation.
        p.restore()

    def _platinum_lake(self, p: QPainter, cx: float, cy: float,
                       rx: float, ry: float, top: str, bottom: str,
                       rim: str, seed: float = 0.0,
                       shore: str = "#1a2c33"):
        """An irregular, perspective-flattened lake, not a neon target ring."""
        path = QPainterPath()
        points = []
        for i in range(30):
            angle = math.tau * i / 30.0
            wobble = (1.0 + 0.085 * math.sin(angle * 3.0 + seed)
                      + 0.040 * math.sin(angle * 5.0 + seed * 2.3))
            # The far shore is slightly narrower, which sells the perspective.
            x = cx + math.cos(angle) * rx * wobble
            y = cy + math.sin(angle) * ry * (0.92 + 0.10 * math.sin(angle + seed))
            points.append(QPointF(x, y))
        path.moveTo(points[0])
        for i in range(1, len(points) + 1):
            p0 = points[i % len(points)]
            p1 = points[(i + 1) % len(points)]
            path.quadTo(p0, QPointF((p0.x() + p1.x()) / 2,
                                    (p0.y() + p1.y()) / 2))
        path.closeSubpath()

        shadow = path.translated(0, max(2.0, ry * 0.14))
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 8, 12, 110))
        p.drawPath(shadow)
        # A visible bank ring seats the pool in the terrain instead of
        # leaving it floating as a flat blue oval on the dark ground.
        p.translate(cx, cy)
        p.scale(1.10, 1.26)
        p.translate(-cx, -cy)
        p.setBrush(QColor(shore))
        p.drawPath(path)
        p.restore()

        lake = QRadialGradient(QPointF(cx, cy - ry * 0.15), max(rx, ry) * 1.18)
        lake.setColorAt(0.0, QColor(top))
        lake.setColorAt(0.44, QColor(bottom))
        lake.setColorAt(1.0, QColor(4, 18, 25, 246))
        p.setBrush(lake)
        p.drawPath(path)

        # A soft reflected sky band on the far edge, not a neon rim.
        p.save()
        p.setClipPath(path)
        band_color = QColor(rim)
        band_color.setAlpha(85)
        sky_band = QLinearGradient(0, cy - ry * 0.42, 0, cy + ry * 0.10)
        sky_band.setColorAt(0.0, band_color)
        sky_band.setColorAt(0.35, QColor(255, 255, 255, 18))
        sky_band.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(cx - rx * 1.2, cy - ry * 0.5,
                          rx * 2.4, ry * 0.7), sky_band)
        p.restore()

        p.setBrush(Qt.BrushStyle.NoBrush)
        rim_color = QColor(rim)
        rim_color.setAlpha(38)
        p.setPen(QPen(rim_color, max(1.0, ry * 0.030),
                      Qt.PenStyle.SolidLine))
        p.drawPath(path)

        # Fine ripples are clipped to the water so the silhouette stays wild.
        p.save()
        p.setClipPath(path)
        p.setPen(QPen(QColor(223, 251, 255, 46), 1))
        for i in range(4):
            y = cy - ry * 0.20 + i * ry * 0.17
            left = cx - rx * (0.64 - i * 0.06)
            right = cx + rx * (0.44 - i * 0.04)
            p.drawLine(QPointF(left, y), QPointF(right, y))
        p.setPen(QPen(QColor(255, 255, 255, 64), 1))
        p.drawLine(QPointF(cx - rx * 0.30, cy - ry * 0.18),
                   QPointF(cx + rx * 0.16, cy - ry * 0.18))
        # Reeds at the near shore.
        p.setPen(QPen(QColor(17, 40, 38, 190), max(1.0, ry * 0.05)))
        for i in range(7):
            base_x = cx - rx * 0.82 + i * rx * 0.08
            base_y = cy + ry * 0.62
            p.drawLine(QPointF(base_x, base_y),
                       QPointF(base_x + rx * 0.012,
                               base_y - ry * (0.30 + (i % 3) * 0.10)))
        p.restore()

    def _paint_platinum(self, p: QPainter, w: int, h: int):
        """Three lakes, one ridge, and a sky that actually has colour in it."""
        ridge = QPainterPath()
        ridge.moveTo(0, h)
        points = [
            (0.00, 0.73), (0.05, 0.67), (0.10, 0.71), (0.16, 0.62),
            (0.21, 0.69), (0.27, 0.65), (0.32, 0.72), (0.39, 0.68),
            (0.44, 0.60), (0.50, 0.64), (0.56, 0.58), (0.62, 0.65),
            (0.69, 0.61), (0.75, 0.69), (0.82, 0.64), (0.88, 0.70),
            (0.94, 0.66), (1.00, 0.71),
        ]
        for x, y in points:
            ridge.lineTo(w * x, h * y)
        ridge.lineTo(w, h)
        ridge.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.MENU_HILL_2))
        p.setOpacity(0.92)
        p.drawPath(ridge)
        p.setOpacity(1.0)

        # Platinum's cold peaks get a periwinkle snow line, not white paint.
        p.setPen(QPen(QColor(190, 221, 238, 92), max(1.0, h / 800)))
        for x, y in [(0.16, 0.62), (0.44, 0.60), (0.56, 0.58), (0.82, 0.64)]:
            p.drawLine(QPointF(w * (x - 0.02), h * (y + 0.022)),
                       QPointF(w * x, h * y))
            p.drawLine(QPointF(w * x, h * y),
                       QPointF(w * (x + 0.025), h * (y + 0.018)))

        # Aurora ribbons: the lake colour families washed into the sky.
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, color, offset in [
            (max(2.0, h * 0.032), (111, 220, 226, 20), 0.0),
            (max(1.0, h * 0.012), (185, 179, 240, 33), 0.065),
            (max(1.0, h * 0.007), (240, 211, 124, 29), 0.115),
        ]:
            path = QPainterPath()
            path.moveTo(-w * 0.1, h * (0.21 + offset))
            path.cubicTo(w * 0.22, h * (0.08 + offset),
                         w * 0.37, h * (0.34 + offset),
                         w * 0.63, h * (0.18 + offset))
            path.cubicTo(w * 0.80, h * (0.07 + offset),
                         w * 0.92, h * (0.27 + offset),
                         w * 1.1, h * (0.16 + offset))
            p.setPen(QPen(QColor(*color), width, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawPath(path)
        p.restore()

        # The lake basin: a continuous dark water table with three bright
        # pools.  Start the gradient above the basin so the horizon does not
        # cut across the screen as a hard horizontal line.
        water = QLinearGradient(0, h * 0.675, 0, h)
        water.setColorAt(0.0, QColor(16, 60, 64, 0))
        water.setColorAt(0.16, QColor(16, 60, 64, 180))
        water.setColorAt(0.55, QColor(8, 40, 46, 248))
        water.setColorAt(1.0, QColor(4, 22, 26, 255))
        p.setBrush(water)
        p.drawRect(QRectF(0, h * 0.675, w, h * 0.325))

        # Low, soft shore shelves keep the pools sitting in a basin rather
        # than floating on a flat blue rectangle.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 27, 34, 210))
        bank = QPainterPath()
        bank.moveTo(0, h * 0.735)
        bank.cubicTo(w * 0.04, h * 0.765, w * 0.09, h * 0.75,
                     w * 0.13, h * 0.77)
        bank.cubicTo(w * 0.18, h * 0.79, w * 0.19, h * 0.84,
                     w * 0.24, h * 0.86)
        bank.lineTo(w * 0.25, h)
        bank.lineTo(0, h)
        bank.closeSubpath()
        p.drawPath(bank)
        bank2 = QPainterPath()
        bank2.moveTo(w * 0.76, h)
        bank2.cubicTo(w * 0.79, h * 0.84, w * 0.84, h * 0.80,
                      w * 0.88, h * 0.78)
        bank2.cubicTo(w * 0.94, h * 0.76, w * 0.98, h * 0.74,
                      w, h * 0.73)
        bank2.lineTo(w, h)
        bank2.closeSubpath()
        p.drawPath(bank2)

        # A darker treeline separates the basin from the open water so the
        # pools sit in a valley instead of on a flat blue floor.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(5, 26, 28, 235))
        treeline = QPainterPath()
        treeline.moveTo(0, h * 0.760)
        step = max(6, w // 90)
        for x in range(0, int(w) + step, step):
            crest = h * (0.735 + 0.012 * math.sin(x / w * 19.0))
            p.drawEllipse(QPointF(x, crest), step * 0.62, h * 0.020)
        treeline.lineTo(w, h)
        treeline.lineTo(0, h)
        treeline.closeSubpath()
        p.drawPath(treeline)

        # Lake Verity at dawn, Lake Acuity under the snow, Lake Valor at
        # dusk: three different Platinum colour families, one shoreline.
        self._platinum_lake(p, w * 0.145, h * 0.805, w * 0.135, h * 0.050,
                            "#e79ac0", "#6c3f7d", "#f2c3dd", 0.7,
                            shore="#322c42")
        self._platinum_lake(p, w * 0.500, h * 0.845, w * 0.170, h * 0.058,
                            "#65c9de", "#1e4a86", "#a8e8f2", 2.4,
                            shore="#263c4d")
        self._platinum_lake(p, w * 0.855, h * 0.805, w * 0.135, h * 0.050,
                            "#f0c070", "#7c4a28", "#f7dda3", 4.1,
                            shore="#3a302a")

        # Each lake has a small shrine island at its far shore, the way the
        # real lakes are drawn.  The silhouettes break the oval outline and
        # give the guardians a landmark to hover over.
        p.setPen(Qt.PenStyle.NoPen)
        for cx, cy, rx, ry, land, tree in [
            (0.145, 0.805, 0.135, 0.050, "#2a2438", "#102a28"),
            (0.855, 0.805, 0.135, 0.050, "#33291f", "#14251f"),
            (0.500, 0.845, 0.170, 0.058, "#22364a", "#0e2a2e"),
        ]:
            ix = w * cx
            iy = h * (cy - ry * 0.42)
            p.setBrush(QColor(land))
            island = QPainterPath()
            island.moveTo(ix - w * rx * 0.20, iy)
            island.cubicTo(ix - w * rx * 0.12, iy - h * 0.020,
                           ix + w * rx * 0.08, iy - h * 0.023,
                           ix + w * rx * 0.20, iy)
            island.cubicTo(ix + w * rx * 0.10, iy + h * 0.012,
                           ix - w * rx * 0.10, iy + h * 0.012,
                           ix - w * rx * 0.20, iy)
            island.closeSubpath()
            p.drawPath(island)
            # A dark cave mouth and a pair of conifers on the island.
            p.setBrush(QColor(4, 14, 17, 220))
            p.drawEllipse(QPointF(ix, iy + h * 0.002),
                          w * 0.008, h * 0.008)
            p.setBrush(QColor(tree))
            for tx, ts in ((-0.10, 0.010), (-0.055, 0.014), (0.085, 0.011)):
                base_x = ix + w * rx * tx
                tree_scale = h * ts
                tree_path = QPainterPath()
                tree_path.moveTo(base_x, iy - tree_scale * 2.4)
                tree_path.lineTo(base_x - tree_scale * 0.55, iy)
                tree_path.lineTo(base_x + tree_scale * 0.55, iy)
                tree_path.closeSubpath()
                p.drawPath(tree_path)

        # The near shore closes the bottom of the frame and hides the flat
        # near rim of each pool, which is what made them read as ovals.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(4, 22, 24, 245))
        foreground = QPainterPath()
        foreground.moveTo(0, h)
        foreground.lineTo(0, h * 0.892)
        for i in range(0, 17):
            x = w * i / 16.0
            y = h * (0.892 + 0.014 * math.sin(i * 0.9 + 0.4))
            foreground.lineTo(x, y)
        foreground.lineTo(w, h)
        foreground.closeSubpath()
        p.drawPath(foreground)
        p.setPen(QPen(QColor(46, 96, 78, 135), max(1.0, h / 900)))
        for i in range(26):
            x = w * (0.01 + (i * 0.039) % 0.98)
            base = h * (0.893 + 0.012 * math.sin(i * 1.3))
            p.drawLine(QPointF(x, base),
                       QPointF(x + w * 0.002, base - h * 0.012))

        # Reeds and small conifers frame the water.  The earlier elliptical
        # rocks read as black holes punched in the lake bank, so they are gone.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 34, 33, 210))
        for cx, scale in [(0.025, 0.030), (0.055, 0.022), (0.235, 0.018),
                          (0.765, 0.020), (0.945, 0.027), (0.975, 0.019)]:
            tree = QPainterPath()
            base_x = w * cx
            base_y = h * 0.795
            tree.moveTo(base_x, base_y - h * scale * 2.7)
            tree.lineTo(base_x - w * scale * 0.52, base_y)
            tree.lineTo(base_x + w * scale * 0.52, base_y)
            tree.closeSubpath()
            p.drawPath(tree)
        p.setPen(QPen(QColor(74, 130, 105, 120), max(1.0, h / 950)))
        for cx in (0.035, 0.065, 0.235, 0.295, 0.720, 0.760, 0.930, 0.970):
            for blade in range(3):
                x = w * (cx + blade * 0.004)
                base_y = h * 0.792
                p.drawLine(QPointF(x, base_y),
                           QPointF(x + w * (0.002 - blade * 0.002),
                                   base_y - h * (0.018 + blade * 0.006)))

        p.setBrush(QColor(190, 180, 240, 95))
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, s in [(0.035, 0.84, 2.0), (0.21, 0.855, 1.3),
                        (0.69, 0.85, 1.5), (0.96, 0.835, 2.0)]:
            p.drawEllipse(QPointF(w * x, h * y), s, s)

        # A low mist veil keeps the lakes from reading as flat stickers.
        mist = QLinearGradient(0, h * 0.65, 0, h * 0.76)
        mist.setColorAt(0.0, QColor(145, 212, 230, 0))
        mist.setColorAt(0.55, QColor(145, 212, 230, 27))
        mist.setColorAt(1.0, QColor(145, 212, 230, 0))
        p.fillRect(QRectF(0, h * 0.65, w, h * 0.11), mist)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(150, 235, 242, 47), 1))
        for i in range(5):
            y = h * (0.685 + i * 0.013)
            x = w * (0.08 + (i * 0.16) % 0.72)
            p.drawLine(QPointF(x, y), QPointF(x + w * 0.14, y))

    def _paint_frlg(self, p: QPainter, w: int, h: int):
        """The FireRed / LeafGreen box-art vortex, split on the diagonal.

        The old scene was another cream sky with hills, so the FRLG skin read
        as a recolour of the Light theme.  The box art pairs a red vortex with
        a green one; this rebuilds the backdrop as those two spirals without
        importing the artwork itself.  Charizard and Venusaur stay the native
        animated sprites and sit in their matching halves.
        """
        p.save()
        p.setPen(Qt.PenStyle.NoPen)

        # Top-left to bottom-right diagonal: red owns the upper-right half,
        # green owns the lower-left half.  Charizard and Venusaur already sit
        # in those corners, so the sprite placement now explains the split.
        red_half = QPainterPath()
        red_half.moveTo(0, 0)
        red_half.lineTo(w, 0)
        red_half.lineTo(w, h)
        red_half.closeSubpath()

        green_half = QPainterPath()
        green_half.moveTo(0, 0)
        green_half.lineTo(w, h)
        green_half.lineTo(0, h)
        green_half.closeSubpath()

        red = QLinearGradient(w * 0.38, 0, w, h * 0.90)
        red.setColorAt(0.0, QColor("#bb1d1a"))
        red.setColorAt(0.34, QColor("#e33121"))
        red.setColorAt(0.70, QColor("#ff6d39"))
        red.setColorAt(1.0, QColor("#d72b1f"))
        p.fillPath(red_half, red)

        green = QLinearGradient(w * 0.58, h, w * 0.08, h * 0.12)
        green.setColorAt(0.0, QColor("#2b763b"))
        green.setColorAt(0.38, QColor("#4da24a"))
        green.setColorAt(0.74, QColor("#8fce5e"))
        green.setColorAt(1.0, QColor("#3b8c41"))
        p.fillPath(green_half, green)

        def vortex(clip: QPainterPath, cx: float, cy: float, radius: float,
                   core: str, arms: tuple[tuple[str, int], ...],
                   phase: float, edge_alpha: int) -> None:
            """Paint one soft logarithmic spiral, clipped to its half."""
            p.save()
            p.setClipPath(clip)
            glow = QRadialGradient(QPointF(cx, cy), radius * 1.18)
            glow.setColorAt(0.0, QColor(core))
            core_color = QColor(core)
            core_color.setAlpha(90)
            glow.setColorAt(0.32, core_color)
            core_color.setAlpha(0)
            glow.setColorAt(1.0, core_color)
            p.setBrush(glow)
            p.drawEllipse(QPointF(cx, cy), radius * 1.18, radius * 1.18)

            for arm in range(4):
                outer: list[QPointF] = []
                inner: list[QPointF] = []
                for step in range(30):
                    f = step / 29.0
                    angle = (phase + arm * math.tau / 4.0
                             + f * math.tau * 1.16)
                    r = radius * (0.075 + 0.96 * f)
                    # Broad ribbons, not contour lines.  The box art reads as
                    # a handful of wide bands spiralling out from the mascot.
                    thickness = radius * (0.235 - 0.080 * f)
                    # A slightly flattened circle keeps the spirals lying on
                    # the floor of the scene instead of facing the viewer.
                    outer.append(QPointF(cx + math.cos(angle) * r,
                                         cy + math.sin(angle) * r * 0.72))
                    inner.append(QPointF(cx + math.cos(angle) * (r - thickness),
                                         cy + math.sin(angle) * (r - thickness) * 0.72))

                band = QPainterPath(outer[0])
                for point in outer[1:]:
                    band.lineTo(point)
                for point in reversed(inner):
                    band.lineTo(point)
                band.closeSubpath()
                color = QColor(arms[arm % len(arms)][0])
                color.setAlpha(arms[arm % len(arms)][1])
                p.setBrush(color)
                p.drawPath(band)

                edge = QPainterPath(outer[0])
                for point in outer[1:]:
                    edge.lineTo(point)
                edge_color = QColor("#ffe9b0" if arm % 2 else "#ffd08a")
                edge_color.setAlpha(edge_alpha)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(edge_color, max(1.0, radius * 0.006)))
                p.drawPath(edge)
            p.restore()

        vortex(red_half, w * 0.795, h * 0.255, min(w, h) * 0.72,
               "#ffb35c",
               (("#ffd79a", 70), ("#8a1516", 28), ("#ffbe79", 58),
                ("#a8201b", 22)),
               0.55, 32)
        vortex(green_half, w * 0.205, h * 0.745, min(w, h) * 0.74,
               "#d8ef8c",
               (("#e9f6b1", 66), ("#1b4b2a", 28), ("#b8e37b", 58),
                ("#2f6b36", 24)),
               2.25, 26)

        # A radial vignette seats the bright spirals in the frame and stops
        # the corners from looking like flat paint buckets.
        vignette = QRadialGradient(QPointF(w * 0.5, h * 0.48),
                                   max(w, h) * 0.76)
        vignette.setColorAt(0.0, QColor(17, 7, 10, 0))
        vignette.setColorAt(0.68, QColor(17, 7, 10, 0))
        vignette.setColorAt(1.0, QColor(17, 7, 10, 105))
        p.setBrush(vignette)
        p.drawRect(QRectF(0, 0, w, h))

        # The cream title sits over the meeting point of the two brightest
        # gradients.  A soft oval shadow behind the lock-up gives it enough
        # contrast without introducing a visible panel edge.
        title_wash = QRadialGradient(QPointF(w * 0.5, h * 0.295), w * 0.36)
        title_wash.setColorAt(0.0, QColor(15, 10, 9, 58))
        title_wash.setColorAt(0.60, QColor(15, 10, 9, 28))
        title_wash.setColorAt(1.0, QColor(15, 10, 9, 0))
        p.setBrush(title_wash)
        p.drawEllipse(QPointF(w * 0.5, h * 0.295), w * 0.36, h * 0.205)

        # A few crisp box-art flecks, kept sparse so they read as highlights
        # rather than a second texture layer.
        for i in range(26):
            red_side = i % 2 == 0
            x = w * (0.05 + ((i * 0.193) % 0.90))
            y = h * (0.08 + ((i * 0.137) % 0.80))
            color = QColor("#ffe7b1" if red_side else "#f2ffd2")
            color.setAlpha(55 + (i % 3) * 20)
            p.setBrush(color)
            p.drawRect(QRectF(x, y, 2.5, 2.5))
        p.restore()

    def _paint_unova(self, p: QPainter, w: int, h: int):
        """Black City on Reshiram's half, White Forest on Zekrom's.

        The old scene was a single dark skyline.  This keeps its composition
        -- legendaries at the edges and cards across the middle -- but makes
        the two halves inverse: a black, gold-lit city on the left and a pale
        forest of white trunks on the right.
        """
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        split = w * 0.5

        left_sky = QLinearGradient(0, 0, 0, h)
        left_sky.setColorAt(0.0, QColor("#020508"))
        left_sky.setColorAt(0.52, QColor("#07131a"))
        left_sky.setColorAt(1.0, QColor("#0c222c"))
        p.fillRect(QRectF(0, 0, split, h), left_sky)

        right_sky = QLinearGradient(0, 0, 0, h)
        right_sky.setColorAt(0.0, QColor("#fbfdfc"))
        right_sky.setColorAt(0.52, QColor("#eef7f1"))
        right_sky.setColorAt(1.0, QColor("#dcebe2"))
        p.fillRect(QRectF(split, 0, w - split, h), right_sky)

        # A very narrow blend keeps the two halves clean but not razor-cut.
        seam = QLinearGradient(split - 12, 0, split + 12, 0)
        seam.setColorAt(0.0, QColor(4, 11, 15, 0))
        seam.setColorAt(0.48, QColor(88, 139, 145, 26))
        seam.setColorAt(0.52, QColor(255, 255, 255, 28))
        seam.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(split - 12, 0, 24, h), seam)

        # Black City haze and White Forest sunlight.
        city_glow = QRadialGradient(QPointF(split * 0.62, h * 0.64), split * 0.72)
        city_glow.setColorAt(0.0, QColor(246, 198, 102, 36))
        city_glow.setColorAt(0.55, QColor(53, 126, 142, 18))
        city_glow.setColorAt(1.0, QColor(6, 18, 24, 0))
        p.setBrush(city_glow)
        p.drawRect(QRectF(0, 0, split, h))

        forest_sun = QRadialGradient(QPointF(w * 0.80, h * 0.18), w * 0.28)
        forest_sun.setColorAt(0.0, QColor(255, 249, 218, 190))
        forest_sun.setColorAt(0.38, QColor(255, 246, 211, 75))
        forest_sun.setColorAt(1.0, QColor(255, 246, 211, 0))
        p.setBrush(forest_sun)
        p.drawRect(QRectF(split, 0, w - split, h * 0.62))

        # --- Black City --------------------------------------------------
        def city_tower(x_frac: float, base_frac: float, width_frac: float,
                       height_frac: float, color: str,
                       rows: int, cols: int) -> None:
            bx = split * x_frac
            base = h * base_frac
            tw = split * width_frac
            th = h * height_frac
            top = base - th
            p.setBrush(QColor(color))
            p.drawRect(QRectF(bx, top, tw, th))
            p.drawRect(QRectF(bx + tw * 0.17, top - th * 0.055,
                              tw * 0.66, th * 0.060))
            p.setPen(QPen(QColor(color), max(1.0, w / 1400)))
            p.drawLine(QPointF(bx + tw * 0.5, top - th * 0.055),
                       QPointF(bx + tw * 0.5, top - th * 0.19))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(246, 200, 103))
            for row in range(rows):
                wy = top + th * (0.12 + row * 0.115)
                if wy > base - th * 0.08:
                    break
                for col in range(cols):
                    wx = bx + tw * (0.17 + col * (0.66 / max(1, cols - 1)))
                    p.setOpacity(0.18 + ((row * 3 + col) % 4) * 0.055)
                    p.drawRect(QRectF(wx, wy, max(1.5, tw * 0.070),
                                      max(2.0, th * 0.016)))
            p.setOpacity(1.0)

        # The far blocks sit in haze; the near towers carry the skyline.
        for x, base, bw, bh in (
            (0.01, 0.78, 0.12, 0.17), (0.10, 0.78, 0.08, 0.22),
            (0.18, 0.78, 0.13, 0.15), (0.29, 0.78, 0.09, 0.20),
            (0.36, 0.78, 0.12, 0.14),
        ):
            city_tower(x, base, bw, bh, "#0a1921", 3, 3)
        for x, base, bw, bh in (
            (0.00, 0.830, 0.17, 0.27), (0.14, 0.830, 0.10, 0.20),
            (0.235, 0.830, 0.15, 0.34), (0.375, 0.830, 0.08, 0.23),
        ):
            city_tower(x, base, bw, bh, "#061116", 4, 3)

        # Cyan signage and a pair of gold street lights keep the left side
        # from becoming a flat black rectangle.
        for sx, sy, sh in ((0.155, 0.620, 0.070), (0.300, 0.585, 0.040),
                           (0.405, 0.655, 0.035)):
            p.setBrush(QColor(94, 219, 231, 38))
            p.drawRect(QRectF(split * sx, h * sy, max(2.0, split * 0.008),
                              h * sh))
        for lx, ly in ((0.075, 0.812), (0.205, 0.830), (0.320, 0.848)):
            x = split * lx
            p.setPen(QPen(QColor(112, 177, 181, 80), max(1.0, w / 1100)))
            p.drawLine(QPointF(x, h * ly), QPointF(x, h * (ly - 0.075)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(249, 210, 118, 150))
            p.drawEllipse(QPointF(x, h * (ly - 0.078)),
                          max(1.4, w * 0.0018), max(1.4, w * 0.0018))

        # Street surface and its perspective lines.
        p.setBrush(QColor("#040b0f"))
        p.drawRect(QRectF(0, h * 0.805, split, h * 0.195))
        p.setPen(QPen(QColor(243, 201, 112, 28), max(1.0, h / 1200)))
        for i in range(4):
            y = h * (0.842 + i * 0.036)
            p.drawLine(QPointF(0, y), QPointF(split, h * 0.812))
        p.setPen(Qt.PenStyle.NoPen)

        # --- White Forest ------------------------------------------------
        # A soft far canopy and two layered crowns give the right half depth
        # before the white birches start.  Keeping it pale stops the forest
        # from fighting the dark menu cards.  Everything below belongs to the
        # right half: clip it so no canopy, branch or path can spill over the
        # seam into Black City.
        p.save()
        p.setClipRect(QRectF(split, 0, w - split, h))
        ridge = QPainterPath()
        ridge.moveTo(split, h * 0.742)
        ridge.lineTo(split, h * 0.704)
        step = max(12.0, (w - split) / 20.0)
        x = split
        index = 0
        while x <= w + step:
            y = h * (0.690 + 0.015 * math.sin(index * 1.4)
                     + 0.008 * math.sin(index * 3.1))
            ridge.lineTo(min(w, x), y)
            x += step
            index += 1
        ridge.lineTo(w, h * 0.742)
        ridge.closeSubpath()
        p.setBrush(QColor("#c6ddcc"))
        p.drawPath(ridge)

        # Keep the first crowns off the seam.  They used to be centred on
        # the centre line, so half of each ellipse landed in Black City.
        far_margin = (w - split) * 0.048
        for i in range(24):
            tx = split + far_margin + (w - split - far_margin) * (i / 23.0)
            ty = h * (0.681 + 0.010 * math.sin(i * 1.9))
            crown = max(9.0, (w - split) * 0.034)
            p.setBrush(QColor("#b2cfc4" if i % 2 else "#a6c5b1"))
            p.drawEllipse(QPointF(tx, ty), crown, h * 0.030)
        mid_margin = (w - split) * 0.060
        for i in range(18):
            tx = split + mid_margin + (w - split - mid_margin) * (i / 17.0)
            ty = h * (0.706 + 0.011 * math.sin(i * 1.3 + 0.7))
            crown = max(8.0, (w - split) * 0.040)
            p.setBrush(QColor("#94b99e" if i % 2 else "#a2c4a9"))
            p.drawEllipse(QPointF(tx, ty), crown, h * 0.026)

        # The forest floor picks up the same pale green, which makes the
        # cream path readable without turning the whole half grey.
        floor = QLinearGradient(0, h * 0.790, 0, h)
        floor.setColorAt(0.0, QColor("#d9e9da"))
        floor.setColorAt(1.0, QColor("#c4dcc8"))
        p.setBrush(floor)
        p.drawRect(QRectF(split, h * 0.790, w - split, h * 0.210))

        def white_tree(x_frac: float, base_frac: float, width_frac: float,
                       height_frac: float, canopy_colors: tuple[str, ...],
                       canopy_size: float, opacity: float = 1.0) -> None:
            x = split + (w - split) * x_frac
            base = h * base_frac
            tw = max(2.0, (w - split) * width_frac)
            th = h * height_frac
            top = base - th
            spread = (w - split) * canopy_size
            p.setOpacity(opacity)

            # Branches, then the trunk.  Drawing the branches first keeps the
            # pale bark crisp where it meets the canopy.
            p.setPen(QPen(QColor("#a9bbaa"), max(1.0, tw * 0.22),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for branch in range(3):
                by = top + th * (0.06 + branch * 0.055)
                side = -1 if branch % 2 else 1
                p.drawLine(QPointF(x + tw * 0.48, by),
                           QPointF(x + tw * 0.48 + side * spread * 0.52,
                                   by - th * (0.05 + branch * 0.012)))

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#bfd1c3"))
            p.drawRect(QRectF(x + tw * 0.38, top, tw, th))
            p.setBrush(QColor("#f9fcf5"))
            p.drawRect(QRectF(x, top, tw * 0.78, th))
            p.setBrush(QColor("#ffffff"))
            p.drawRect(QRectF(x, top, tw * 0.26, th))
            p.setPen(QPen(QColor("#8fa396"), max(1.0, tw * 0.075)))
            for mark in range(6):
                my = top + th * (0.12 + mark * 0.135)
                p.drawLine(QPointF(x + tw * 0.08, my),
                           QPointF(x + tw * 0.46, my - th * 0.010))
            p.setPen(Qt.PenStyle.NoPen)

            # A darker under-canopy gives the lobed silhouette some depth
            # instead of leaving a flat pale disc on the white sky.
            under = QColor(canopy_colors[-1])
            under.setAlpha(int(92 * opacity))
            p.setBrush(under)
            p.drawEllipse(QPointF(x + tw * 0.48, top - th * 0.035),
                          spread * 1.30, spread * 0.82)

            # A rounded, lobed canopy made from several green tones.  White
            # Forest's trees are broad and soft rather than conifers.
            lobes = (
                (-1.25, 0.02, 0.82), (-0.86, -0.40, 0.92),
                (-0.30, -0.66, 1.0), (0.28, -0.64, 1.02),
                (0.82, -0.36, 0.90), (1.22, 0.04, 0.78),
                (-0.48, 0.24, 0.78), (0.44, 0.26, 0.80),
            )
            for lobe, (ox, oy, scale) in enumerate(lobes):
                lx = x + tw * 0.48 + ox * spread
                ly = top - th * 0.035 + oy * spread * 0.82
                color = QColor(canopy_colors[lobe % len(canopy_colors)])
                color.setAlpha(int(255 * min(1.0, opacity)
                                    * (0.82 + 0.05 * (lobe % 3))))
                p.setBrush(color)
                p.drawEllipse(QPointF(lx, ly), spread * scale,
                              spread * 0.74 * scale)

            # One or two pale highlights on the sunward side.
            p.setBrush(QColor(207, 238, 231, int(95 * opacity)))
            p.drawEllipse(QPointF(x + tw * 0.48 + spread * 0.60,
                                  top - th * 0.035 - spread * 0.42),
                          spread * 0.46, spread * 0.30)
            p.setOpacity(1.0)

        # Cool teal-green highlights tie White Forest to Zekrom's cyan
        # accents instead of reading as a generic green meadow.
        forest_mid = ("#7fa98a", "#8fbbaa", "#a2c4a7", "#6f987d")
        forest_light = ("#9abfa0", "#a9cfc4", "#b6d3b4", "#8bb393")

        # Far and mid trunks.  The middle stays low enough for the cards.
        # The first birch starts clear of the seam; its broad canopy used to
        # graze the Black City edge even after the row shift above.
        white_tree(0.085, 0.862, 0.010, 0.20, forest_light, 0.038, 0.78)
        white_tree(0.155, 0.868, 0.009, 0.16, forest_light, 0.034, 0.72)
        white_tree(0.290, 0.864, 0.011, 0.22, forest_mid, 0.042, 0.82)
        white_tree(0.410, 0.870, 0.009, 0.17, forest_light, 0.034, 0.74)
        white_tree(0.535, 0.866, 0.012, 0.24, forest_mid, 0.044, 0.84)
        white_tree(0.640, 0.870, 0.010, 0.19, forest_light, 0.036, 0.78)
        white_tree(0.735, 0.864, 0.013, 0.27, forest_mid, 0.048, 0.88)

        # Taller birches frame the outer edge and rise behind Zekrom without
        # crossing the title lock-up.
        white_tree(0.825, 0.858, 0.016, 0.33, forest_mid, 0.056, 0.94)
        white_tree(0.910, 0.852, 0.019, 0.40, forest_mid, 0.064, 0.97)
        white_tree(0.975, 0.848, 0.015, 0.31, forest_light, 0.052, 0.90)

        # The winding clearing path.  Its edges and centre line make it read
        # as a path on the grass rather than a stray cream ribbon.
        path_shape = QPainterPath()
        path_shape.moveTo(split + (w - split) * 0.58, h)
        path_shape.cubicTo(split + (w - split) * 0.68, h * 0.940,
                           split + (w - split) * 0.68, h * 0.870,
                           split + (w - split) * 0.59, h * 0.803)
        path_shape.lineTo(split + (w - split) * 0.65, h * 0.803)
        path_shape.cubicTo(split + (w - split) * 0.76, h * 0.872,
                           split + (w - split) * 0.82, h * 0.942,
                           split + (w - split) * 0.78, h)
        path_shape.closeSubpath()
        p.setBrush(QColor("#f3eed9"))
        p.drawPath(path_shape)
        p.setPen(QPen(QColor(166, 201, 194, 135), max(1.0, h / 1100)))
        p.drawLine(QPointF(split + (w - split) * 0.585, h * 0.995),
                   QPointF(split + (w - split) * 0.60, h * 0.820))
        p.drawLine(QPointF(split + (w - split) * 0.595, h * 0.995),
                   QPointF(split + (w - split) * 0.625, h * 0.820))
        p.setPen(Qt.PenStyle.NoPen)

        # Grass clumps, ferns and a few small flowers fill the foreground.
        p.setBrush(QColor(128, 173, 158, 125))
        for i in range(30):
            gx = split + (w - split) * (0.02 + (i * 0.037) % 0.95)
            gy = h * (0.855 + (i % 7) * 0.019)
            for blade in range(3):
                p.drawEllipse(QPointF(gx + blade * 2.0, gy),
                              max(1.0, w * 0.0012),
                              max(1.6, h * (0.006 + blade * 0.002)))
        for gx, color in ((0.235, "#b7e4e0"), (0.405, "#f3d6d0"),
                          (0.690, "#ffffff"), (0.895, "#9ed8d2"),
                          (0.945, "#f4e8b8")):
            p.setBrush(QColor(color))
            p.setOpacity(0.90)
            p.drawEllipse(QPointF(split + (w - split) * gx, h * 0.878),
                          max(1.4, w * 0.0018), max(1.4, w * 0.0018))
        p.setOpacity(1.0)
        p.restore()

        # Gen 5's square/dither language, tinted to each side.
        p.setBrush(QColor(145, 226, 232, 16))
        step = 18 if w < 1800 else 28
        for y in range(int(h * 0.742), int(h * 0.800), step):
            offset = (y // step) % 2 * step // 2
            for x in range(offset, int(split), step):
                p.drawRect(x, y, 2, 2)
        p.setBrush(QColor(126, 164, 138, 17))
        for y in range(int(h * 0.742), int(h * 0.800), step):
            offset = (y // step) % 2 * step // 2
            for x in range(int(split) + offset, w, step):
                p.drawRect(x, y, 2, 2)
        p.restore()

    def _paint_light(self, p: QPainter, w: int, h: int):
        self._paint_hills(p, w, h)
        p.save()
        p.setOpacity(0.06)
        theme.draw_pokeball(p, w * 0.81, h * 0.44, min(w, h) * 0.22,
                            top="#ffffff", bottom="#ffffff",
                            outline=theme.MENU_INK, outline_width=3)
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 85), 1))
        for i in range(5):
            y = h * (0.10 + i * 0.06)
            x = w * (0.56 + (i % 3) * 0.08)
            p.drawLine(QPointF(x, y), QPointF(x + w * 0.10, y - 3))

    def _paint_night(self, p: QPainter, w: int, h: int):
        self._paint_hills(p, w, h)
        p.save()
        p.setOpacity(0.08)
        theme.draw_pokeball(p, w * 0.81, h * 0.44, min(w, h) * 0.22,
                            top="#ffffff", bottom="#ffffff",
                            outline=theme.MENU_INK, outline_width=3)
        p.restore()
        p.setPen(QPen(QColor(138, 196, 219, 55), 1))
        for i in range(7):
            y = h * (0.35 + i * 0.063)
            x = w * (0.03 + (i % 3) * 0.12)
            p.drawLine(QPointF(x, y), QPointF(x + w * 0.08, y))

    def _paint_animation(self, p: QPainter, w: int, h: int, style: str):
        t = self._t
        if style == "hgss":
            self._animate_hgss(p, w, h, t)
        elif style == "hoenn":
            self._animate_hoenn(p, w, h, t)
        elif style == "platinum":
            self._animate_platinum(p, w, h, t)
        elif style == "gba":
            self._animate_frlg(p, w, h, t)
        elif style == "city":
            self._animate_unova(p, w, h, t)
        elif style == "night":
            self._animate_night(p, w, h, t)
        else:
            self._animate_light(p, w, h, t)

    def _animate_frlg(self, p: QPainter, w: int, h: int, t: float):
        base = min(w, h)

        # The vortex itself is the box-art backdrop; the life comes from
        # embers rising through the red half and leaf motes in the green half.
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(28):
            red_side = i % 2 == 0
            phase = (t * (0.055 if red_side else 0.040) + i / 28.0) % 1.0
            sway = math.sin(t * 0.45 + i * 1.7) * w * 0.005
            if red_side:
                x = w * (0.54 + ((i * 0.071) % 0.43)) + sway
                y = h * (0.92 - phase * 0.78)
                color = QColor(255, 214, 142, int(60 * (1.0 - phase)))
            else:
                x = w * (0.03 + ((i * 0.067) % 0.42)) + sway
                y = h * (0.90 - phase * 0.66)
                color = QColor(232, 250, 174, int(52 * (1.0 - phase)))
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), 1.4 + (i % 3) * 0.7, 1.4)
        p.restore()

        char_size = int(max(205, min(400, base * 0.34)))
        cx = w * (0.800 - 0.022 * math.sin(t * 0.18))
        cy = h * (0.188 + 0.014 * math.cos(t * 0.24))

        self._aura(p, cx, cy, char_size * 0.82, "#ffd9a0", 68)
        # A warm motion trail, not a duplicate sprite.
        p.save()
        p.setPen(QPen(QColor(255, 227, 176, 90), max(1.0, h / 600),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(3):
            y = cy + char_size * (0.06 + i * 0.035)
            p.drawLine(QPointF(cx + char_size * 0.26, y),
                       QPointF(cx + char_size * (0.50 + i * 0.05), y + 2))
        p.restore()
        self._animated(p, "charizard", cx, cy, char_size, t=t)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(18):
            phase = (t * 0.20 + i / 18.0) % 1.0
            x = cx + math.sin(i * 2.3 + t * 0.45) * char_size * 0.35
            y = cy + char_size * 0.37 - phase * char_size * 0.80
            radius = 1.0 + (i % 4) * 0.7
            p.setBrush(QColor(255, 214, 132, int(190 * (1.0 - phase))))
            p.drawEllipse(QPointF(x, y), radius, radius)

        ven_size = int(max(165, min(300, base * 0.27)))
        vx = w * (0.120 + 0.004 * math.sin(t * 0.31))
        vy = h * (0.735 + 0.006 * math.cos(t * 0.52))
        # A grounded contact shadow keeps the big sprite from floating over
        # the painted spiral.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 48, 25, 115))
        p.drawEllipse(QPointF(vx, vy + ven_size * 0.355),
                      ven_size * 0.34, ven_size * 0.055)
        self._aura(p, vx, vy, ven_size * 0.60, "#f1f8b6", 55)
        self._animated(p, "venusaur", vx, vy, ven_size, t=t)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(12):
            phase = (t * 0.10 + i / 12.0) % 1.0
            x = vx + math.sin(i * 1.7 + t * 0.3) * ven_size * 0.48
            y = vy - ven_size * 0.10 - phase * ven_size * 0.55
            p.setBrush(QColor(241, 190, 174, int(125 * (1.0 - phase))))
            p.drawEllipse(QPointF(x, y), 2.4, 1.2)

    def _animate_hoenn(self, p: QPainter, w: int, h: int, t: float):
        base = min(w, h)

        # The coast scrolls under the title/menu, not the other way around.
        # Characters stay near their screen anchors with a small independent
        # drift, exactly like a camera pan in the GBA intros.  The sky, the
        # horizon island, the water and the two coast bands all travel at
        # different rates, so the scene has real depth.
        self._paint_hoenn_clouds(p, w, h, t)
        self._paint_hoenn_water_scroll(p, w, h, t)

        # The low sun lays a shimmering path across the water.  Paint it
        # before the coast so the light never bleeds onto the grass.
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(16):
            y = h * (0.545 + i * 0.0112)
            width = w * (0.020 + i * 0.0032) * (1.0 + 0.35 * math.sin(t * 0.8 + i))
            p.setBrush(QColor(255, 240, 183,
                              int(16 + 18 * (0.5 + 0.5 * math.sin(t * 0.6 + i)))))
            p.drawRect(QRectF(w * 0.80 - width / 2, y, width, max(1.0, h / 900)))
        p.restore()

        # Water diamonds catching the low sun.
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(20):
            x = w * (0.07 + ((i * 0.137 + t * 0.014) % 0.86))
            y = h * (0.575 + (i * 0.047) % 0.135)
            p.setBrush(QColor(255, 234, 169,
                              int(30 + 45 * (0.5 + 0.5 * math.sin(t + i)))))
            p.drawEllipse(QPointF(x, y), 1.0 + (i % 3) * 0.6, 0.8)

        self._paint_hoenn_distant_island(p, w, h, t)
        self._paint_hoenn_landmark(p, w, h)
        self._paint_hoenn_mid_scroll(p, w, h, t)
        self._paint_hoenn_scroll(p, w, h, t)
        self._paint_hoenn_ledge(p, w, h)

        # Latias stays high and distant, facing the same way as Latios and
        # Brendan (left) and gliding at a slightly slower cadence.
        latias_size = int(max(260, min(520, base * 0.34)))
        lx2 = w * (0.835 + 0.020 * math.sin(t * 0.15 + 1.1))
        ly2 = h * (0.190 + 0.017 * math.cos(t * 0.19 + 0.5))
        self._aura(p, lx2, ly2, latias_size * 0.50, theme.RED, 28)
        self._animated(p, "latias_full", lx2, ly2, latias_size, t=t)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(8):
            phase = (t * 0.24 + i / 8.0) % 1.0
            x = lx2 + latias_size * (0.17 + phase * 0.27)
            y = ly2 + math.sin(i * 1.9 + t * 0.8) * latias_size * 0.09
            p.setBrush(QColor(255, 126, 126, int(82 * (1.0 - phase))))
            p.drawEllipse(QPointF(x, y), 1.6, 1.6)
        p.restore()

        # A small Wingull flock keeps the air over the route busy.
        p.setPen(QPen(QColor(247, 250, 235, 150), max(1.0, h / 850)))
        for i in range(4):
            bx = w * (0.52 + ((t * 0.008 + i * 0.11) % 0.55))
            by = h * (0.40 + i * 0.032) + math.sin(t * 0.7 + i) * 3
            span = max(2.0, h * 0.009)
            p.drawLine(QPointF(bx - span, by - span * 0.4),
                       QPointF(bx, by))
            p.drawLine(QPointF(bx, by),
                       QPointF(bx + span, by - span * 0.4))

        # Latios and Latias are 128x64 creatures built from two 64x64 halves
        # in the GBA source.  Drawing the full composition at a whole-pixel
        # scale is what keeps the wings from looking clipped or smeared.
        # Keep the whole 128x64 creature inside the viewport even at the
        # minimum window width; the old 16% anchor could shave its left wing.
        latios_size = int(max(320, min(560, base * 0.44, w * 0.36)))
        lx = w * (0.180 + 0.020 * math.sin(t * 0.16))
        ly = h * (0.295 + 0.024 * math.sin(t * 0.24 + 0.8))
        self._aura(p, lx, ly, latios_size * 0.50, theme.BLUE_LIGHT, 38)
        self._animated(p, "latios_full", lx, ly, latios_size, t=t)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(10):
            phase = (t * 0.30 + i / 10.0) % 1.0
            # The sprite faces left, so its sparkle trail streams behind it.
            x = lx + latios_size * (0.26 + phase * 0.30)
            y = ly + math.sin(i * 2.1 + t * 0.8) * latios_size * 0.12
            p.setBrush(QColor(206, 250, 245, int(70 * (1.0 - phase))))
            p.drawEllipse(QPointF(x, y), 1.6, 1.6)

        # Brendan rides the coast road below the menu, using the actual GBA
        # intro rider and bicycle frames rather than a redrawn imitation.
        ride_size = int(max(150, min(232, base * 0.20)))
        rx = w * (0.185 + 0.010 * math.sin(t * 0.24))
        ry = h * (0.800 + 0.006 * math.cos(t * 0.44))
        # The old contact shadow sat below the bike's transparent frame
        # padding and overlapped the ledge behind SELECT A SYSTEM, where it
        # read as a dark hole.  The GBA intro has no contact shadow either.
        self._animated(p, "brendan", rx, ry, ride_size, t=t)

    def _animate_hgss(self, p: QPainter, w: int, h: int, t: float):
        base = min(w, h)
        ho_size = int(max(265, min(440, base * 0.36)))
        hx = w * (0.170 + 0.010 * math.sin(t * 0.16))
        hy = h * (0.245 + 0.010 * math.cos(t * 0.22))

        # Ho-oh's rainbow, painted as a living arc behind the bird.
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        for band, color in enumerate([
            (255, 122, 108), (255, 176, 96), (255, 224, 128),
            (135, 220, 150), (126, 194, 244), (178, 156, 236),
        ]):
            radius = ho_size * (0.64 + band * 0.026)
            pulse = 0.55 + 0.20 * math.sin(t * 0.55 + band * 0.9)
            p.setPen(QPen(QColor(*color, int(42 + 22 * pulse)),
                          max(2.0, h * 0.006),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            # Start above the bird and sweep across the top of the circle.
            # A 200-degree start put the whole bow underneath Ho-oh, which
            # is why the rainbow looked upside down.
            p.drawArc(QRectF(hx - radius, hy - radius * 0.82,
                             radius * 2, radius * 1.64),
                      20 * 16, 140 * 16)
        p.restore()

        self._aura(p, hx, hy, ho_size * 0.74, theme.GOLD, 52)
        self._animated(p, "hooh", hx, hy, ho_size, t=t)

        # Lugia is much wider than Ho-oh, so matching their longest side
        # made the silver bird look small.  Let its wingspan earn the same
        # visual weight as the rainbow bird on the other half.
        lug_size = int(max(330, min(520, base * 0.46)))
        lx = w * (0.815 + 0.010 * math.sin(t * 0.14 + 1.4))
        ly = h * (0.270 + 0.011 * math.cos(t * 0.20 + 0.6))

        # Whirlpool below Lugia: three slowly turning rings and a bright
        # centre that catches the moonlight.
        p.save()
        whirl = QPointF(lx, h * 0.700)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for ring in range(3):
            rr = lug_size * (0.110 + ring * 0.038)
            p.setPen(QPen(QColor(141, 213, 245,
                                 max(10, 42 - ring * 9)),
                          max(1.0, h / 700)))
            p.drawEllipse(whirl, rr, rr * 0.30)
        for spark in range(6):
            angle = t * 0.9 + spark * math.tau / 6
            sx = whirl.x() + math.cos(angle) * lug_size * 0.18
            sy = whirl.y() + math.sin(angle) * lug_size * 0.055
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(203, 241, 255, 105))
            p.drawEllipse(QPointF(sx, sy), 1.6, 1.4)
        p.restore()

        self._aura(p, lx, ly, lug_size * 0.76, theme.BLUE, 52)
        self._animated(p, "lugia", lx, ly, lug_size, t=t)

        p.setPen(Qt.PenStyle.NoPen)
        for i in range(18):
            phase = (t * 0.16 + i / 18.0) % 1.0
            side = i % 2
            if side == 0:
                x = hx + math.sin(i * 1.9 + t * 0.5) * ho_size * 0.45
                y = hy + ho_size * 0.18 - phase * ho_size * 0.55
                color = QColor(255, 214, 127, int(125 * (1.0 - phase)))
            else:
                x = lx + math.sin(i * 2.1 + t * 0.4) * lug_size * 0.42
                y = ly + lug_size * 0.16 - phase * lug_size * 0.46
                color = QColor(191, 232, 255, int(105 * (1.0 - phase)))
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), 1.6 + (i % 3) * 0.5, 1.2)

        # Moonlight walks down the right-hand sea.
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        moon_path = QRadialGradient(QPointF(w * 0.84, h * 0.80), w * 0.095)
        moon_path.setColorAt(0.0, QColor(215, 240, 255, 38))
        moon_path.setColorAt(0.55, QColor(180, 224, 250, 14))
        moon_path.setColorAt(1.0, QColor(180, 224, 250, 0))
        p.setBrush(moon_path)
        p.drawEllipse(QPointF(w * 0.84, h * 0.80), w * 0.095, h * 0.18)
        for i in range(13):
            y = h * (0.69 + i * 0.021)
            width = w * (0.030 + 0.004 * (i % 4))
            p.setBrush(QColor(223, 246, 255,
                              int(20 + 18 * (0.5 + 0.5 * math.sin(t * 0.7 + i)))))
            p.drawRect(QRectF(w * 0.84 - width / 2, y, width,
                              max(1.0, h / 1100)))
        p.restore()

        # Whirl Island bubbles and Bell Tower sparks.
        for i in range(12):
            phase = (t * 0.22 + i / 12.0) % 1.0
            x = w * (0.55 + (i * 0.035) % 0.40)
            y = h * (0.66 + (i * 0.024) % 0.22) - phase * h * 0.025
            p.setBrush(QColor(159, 224, 248, int(55 * (1.0 - phase))))
            p.drawEllipse(QPointF(x, y), 1.4, 1.4)

    def _animate_platinum(self, p: QPainter, w: int, h: int, t: float):
        base = min(w, h)
        size = int(max(165, min(320, base * 0.225)))

        # The trio hover low over their own lakes, clear of the menu cards,
        # so each guardian reads as part of the landscape rather than a
        # sticker crowded against the title lock-up.
        guardians = [
            # Uxie's strip is a dense 52x55 cell, while Mesprit's is 58x94
            # and Azelf's is 78x64 with much more transparent padding.  The
            # renderer scales each strip by its largest cell dimension, which
            # made Uxie's compact body read a full size larger than the other
            # two even with the old 0.95 multiplier.  Keep its draw scale
            # deliberately calmer so the trio share one visual weight.
            ("uxie", 0.145, 0.752, theme.GOLD, 0.78),
            ("mesprit", 0.500, 0.744, "#f2a3bd", 1.08),
            ("azelf", 0.855, 0.752, "#8fe0ee", 1.00),
        ]
        lake_specs = [
            (0.145, 0.805, 0.135),
            (0.500, 0.845, 0.170),
            (0.855, 0.805, 0.135),
        ]

        # Aura caught by the water, painted before the guardians so it can
        # never wash over their silhouettes.
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for lake_idx, (name, nx, ny, aura_color, multiplier) in enumerate(guardians):
            cx, cy, rx = lake_specs[lake_idx]
            color = QColor(aura_color)
            glow = QRadialGradient(QPointF(w * cx, h * cy),
                                   max(w * rx * 0.55, h * 0.045))
            glow.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 85))
            glow.setColorAt(0.55, QColor(color.red(), color.green(), color.blue(), 30))
            glow.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            p.setBrush(glow)
            p.drawEllipse(QPointF(w * cx, h * cy),
                          w * rx * 0.72, h * 0.042)
            for line in range(5):
                drift = math.sin(t * 0.19 + line + lake_idx) * w * 0.006
                x1 = w * cx - w * rx * (0.56 - line * 0.075) + drift
                x2 = w * cx + w * rx * (0.52 - line * 0.065) + drift
                y = h * cy + h * 0.006 * (line - 2)
                line_color = QColor(aura_color)
                line_color.setAlpha(34 + 20 * (line % 3))
                p.setPen(QPen(line_color, 1))
                p.drawLine(QPointF(x1, y), QPointF(x2, y))
        p.restore()

        for index, (name, nx, ny, aura_color, multiplier) in enumerate(guardians):
            phase = t * 0.34 + index * 1.8
            gx = w * (nx + 0.004 * math.sin(phase * 0.8))
            gy = h * (ny + 0.010 * math.sin(phase))
            gsize = int(size * multiplier)
            # A dim, vertically mirrored frame in the water sells the fact
            # that the guardians are hovering over a lake, not standing on a
            # painted disc.  Draw it first so the guardian always sits on top.
            strip = _anim_strip(name)
            if not strip.isNull():
                cell_w = strip.width() // _SPLASH_ANIM[name][1]
                cell_h = strip.height()
                if cell_w > 0 and cell_h > 0:
                    dpr = max(1.0, self.devicePixelRatioF())
                    scale = max(1, int(round(
                        max(16.0, gsize * dpr) / max(cell_w, cell_h)
                    )))
                    dest_h = cell_h * scale / dpr
                    self._animated(p, name, gx, gy + dest_h * 1.02,
                                   gsize, t=t,
                                   opacity=0.14, flip_v=True,
                                   phase=index * 2.7)
            self._aura(p, gx, gy, gsize * 0.78, aura_color, 44)
            self._animated(p, name, gx, gy, gsize, t=t,
                           phase=index * 2.7)
            # Three small orbs orbiting the guardian.
            p.setPen(Qt.PenStyle.NoPen)
            for orb in range(3):
                angle = phase * 1.4 + orb * math.tau / 3
                ox = gx + math.cos(angle) * gsize * 0.52
                oy = gy + math.sin(angle) * gsize * 0.22
                p.setBrush(QColor(aura_color))
                p.setOpacity(0.45 + 0.25 * math.sin(phase + orb))
                p.drawEllipse(QPointF(ox, oy), 2.0, 2.0)
            p.setOpacity(1.0)
            # Pixie dust drifting down toward the water.
            for dust in range(6):
                drop = (t * 0.10 + dust / 6.0 + index * 0.13) % 1.0
                dx = gx + math.sin(dust * 2.4 + t * 0.5) * gsize * 0.44
                dy = gy + gsize * 0.30 + drop * h * 0.09
                p.setBrush(QColor(aura_color))
                p.setOpacity(0.55 * (1.0 - drop))
                p.drawEllipse(QPointF(dx, dy), 1.5, 1.5)
            p.setOpacity(1.0)

        # Motes rising from each lake toward its guardian.
        p.setPen(Qt.PenStyle.NoPen)
        for lake_idx, (cx, cy, rx) in enumerate(lake_specs):
            color = guardians[lake_idx][3]
            target_y = h * guardians[lake_idx][2]
            for i in range(3):
                phase = (t * 0.14 + i / 3.0 + lake_idx * 0.21) % 1.0
                start_y = h * (cy - 0.005)
                x = w * cx + math.sin(phase * math.tau + i) * w * rx * 0.42
                y = start_y + (target_y - start_y) * phase
                alpha = max(0.0, math.sin(phase * math.pi))
                p.setBrush(QColor(color))
                p.setOpacity(alpha * 0.75)
                p.drawEllipse(QPointF(x, y), 1.4 + (i % 2) * 0.8, 1.4)
        p.setOpacity(1.0)

        # A slow mist band and one shooting star every few seconds.
        mist = QLinearGradient(w * (0.3 + 0.08 * math.sin(t * 0.07)), 0,
                               w * (0.65 + 0.08 * math.sin(t * 0.07)), 0)
        mist.setColorAt(0.0, QColor(160, 236, 245, 0))
        mist.setColorAt(0.5, QColor(160, 236, 245, 21))
        mist.setColorAt(1.0, QColor(160, 236, 245, 0))
        p.fillRect(QRectF(0, h * 0.66, w, h * 0.07), mist)

        phase = (t * 0.035) % 1.0
        if phase < 0.16:
            fade = math.sin((phase / 0.16) * math.pi)
            x = w * (0.12 + phase * 0.52)
            y = h * (0.13 + phase * 0.24)
            p.setPen(QPen(QColor(217, 247, 255, int(180 * fade)),
                          max(1.0, h / 700)))
            p.drawLine(QPointF(x, y), QPointF(x - w * 0.035, y - h * 0.035))

    def _animate_unova(self, p: QPainter, w: int, h: int, t: float):
        base = min(w, h)
        split = w * 0.5
        size = int(max(230, min(390, base * 0.35)))

        # Black City's searchlights stay on Reshiram's half; the forest side
        # keeps its light soft and natural.
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(3):
            base_x = split * (0.13 + i * 0.28)
            lean = 0.050 * math.sin(t * 0.11 + i * 1.7)
            path = QPainterPath()
            path.moveTo(base_x, h * 0.820)
            path.lineTo(base_x + w * lean - w * 0.009, h * 0.08)
            path.lineTo(base_x + w * lean + w * 0.009, h * 0.08)
            path.closeSubpath()
            p.setBrush(QColor(248, 211, 124, 8 + i * 3))
            p.drawPath(path)
            p.setBrush(QColor(109, 224, 235, 5 + i * 2))
            p.drawPath(path)
        p.restore()

        res_size = size
        rcx = w * (0.160 + 0.007 * math.sin(t * 0.15))
        rcy = h * (0.225 + 0.009 * math.cos(t * 0.20))
        zcx = w * (0.840 - 0.007 * math.sin(t * 0.15 + 0.4))
        zcy = h * (0.225 + 0.009 * math.cos(t * 0.20 + 1.1))

        self._aura(p, rcx, rcy, res_size * 0.72, "#f5c96f", 46)
        # Zekrom is nearly black on a white sky, so it needs a dark halo to
        # hold its silhouette before the cyan accent goes on top.
        self._aura(p, zcx, zcy, res_size * 0.76, "#2b4b51", 38)
        self._aura(p, zcx, zcy, res_size * 0.58, "#a8e6e8", 34)
        self._animated(p, "reshiram", rcx, rcy, res_size, t=t)
        self._animated(p, "zekrom", zcx, zcy, res_size, t=t, flip=True)

        # Truth and ideals as a pair of slow, thin light sheets.  The right
        # sheet is pale green so it still shows against White Forest.
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for side, x0, color in [
            (1, w * 0.08, QColor(255, 240, 184, 20)),
            (-1, w * 0.92, QColor(151, 197, 157, 26)),
        ]:
            shape = QPainterPath()
            shape.moveTo(x0, h * 0.08)
            shape.lineTo(x0 + side * w * 0.16, h * 0.56)
            shape.lineTo(x0 + side * w * 0.07, h * 0.66)
            shape.lineTo(x0, h * 0.30)
            shape.closeSubpath()
            p.setBrush(color)
            p.drawPath(shape)
        p.restore()

        # City windows blink awake only on the left; the right side gets a
        # few slow fireflies in the trees instead.
        for i in range(14):
            wx = split * (0.03 + (i * 0.061) % 0.92)
            wy = h * (0.60 + (i * 0.029) % 0.19)
            blink = 0.5 + 0.5 * math.sin(t * 0.7 + i * 2.1)
            p.setBrush(QColor(255, 238, 174, int(45 + 95 * blink)))
            p.drawRect(QRectF(wx, wy, 2.5, 4.0))

        p.setPen(Qt.PenStyle.NoPen)
        for i in range(22):
            phase = (t * 0.14 + i / 22.0) % 1.0
            if i % 2:
                x = split + (w - split) * (0.08 + (i * 0.041) % 0.86)
                y = h * (0.48 + (i * 0.027) % 0.36) - phase * h * 0.035
                color = QColor(183, 214, 164, int(85 * (1.0 - phase)))
            else:
                x = split * (0.03 + (i * 0.037) % 0.90)
                y = h * (0.58 + (i * 0.026) % 0.28) - phase * h * 0.045
                color = QColor(255, 231, 157, int(105 * (1.0 - phase)))
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), 1.2 + (i % 3) * 0.55, 1.2)
        p.setOpacity(1.0)

    def _animate_light(self, p: QPainter, w: int, h: int, t: float):
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(12):
            phase = (t * 0.045 + i / 12.0) % 1.0
            x = w * (0.05 + (i * 0.077) % 0.90)
            y = h * (0.16 + (i * 0.113) % 0.68) - phase * h * 0.03
            p.setBrush(QColor(255, 255, 255, int(24 + 20 * math.sin(t + i))))
            p.drawEllipse(QPointF(x, y), 1.8, 1.8)

    def _animate_night(self, p: QPainter, w: int, h: int, t: float):
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(16):
            phase = (t * 0.055 + i / 16.0) % 1.0
            x = w * (0.03 + (i * 0.061) % 0.92)
            y = h * (0.14 + (i * 0.087) % 0.68) + phase * h * 0.025
            alpha = int(60 + 80 * (0.5 + 0.5 * math.sin(t * 0.8 + i)))
            p.setBrush(QColor(191, 236, 218, alpha))
            p.drawEllipse(QPointF(x, y), 1.2 + (i % 3) * 0.4, 1.2)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        style = theme.THEME_MENU_STYLE
        key = (w, h, style, theme.THEME_ID, round(self.devicePixelRatioF(), 2))
        if self._backdrop.isNull() or self._backdrop_key != key:
            self._build_backdrop(w, h, style)

        p.drawPixmap(QPointF(0, 0), self._backdrop)
        self._paint_animation(p, w, h, style)

        frame_alpha = (220 if theme.THEME_ID == "light"
                       else 100 if theme.THEME_ID in ("dark", "sinnoh") else 150)
        p.setPen(QPen(QColor(theme.MENU_INK) if theme.THEME_ID == "light"
                      else QColor(255, 255, 255, frame_alpha), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(8, 8, w - 16, h - 16)
        footer = QColor(theme.MENU_FOOTER_BG)
        footer.setAlpha(220)
        p.fillRect(0, h - 38, w, 38, footer)
        p.setFont(theme.ui_font(12, gba=True))
        p.setPen(QColor(theme.MENU_FOOTER_FG))
        p.drawText(QRectF(18, h - 32, w - 36, 22),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   getattr(theme, "MENU_FOOTER_TAG",
                           "WIRELESS TRADE  •  STORAGE  •  LOCAL LINK"))


class PokeballEmblem(QWidget):
    def __init__(self, size: int = 58, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2
        half = min(self.width(), self.height()) / 2
        scale = half / 31.0
        # Leave room for the gold ring's own pen.  The old r+4 ring plus a
        # 3 px pen reached the widget edge, so Qt clipped its left and right
        # sides and the emblem looked slightly flattened.
        r = half - 7.0 * scale
        ring = r + 4.0 * scale
        ring_pen = max(2.0, 2.6 * scale)
        p.setPen(QPen(QColor(theme.GOLD), ring_pen))
        p.setBrush(QColor(theme.PANEL))
        p.drawEllipse(QPointF(cx, cy), ring, ring)
        theme.draw_pokeball(p, cx, cy, r, outline_width=2.2)


class MenuCard(QPushButton):
    """A cream GBA menu card with a coloured badge, drawn by hand.

    The card is painted in a fixed 190x204 coordinate space and the whole
    painter is scaled, so a maximized window gets genuinely larger art rather
    than four tiny cards stranded in the middle of a 1440p desktop.
    """

    BASE_WIDTH = 190
    BASE_HEIGHT = 204
    hovered = pyqtSignal()

    def __init__(self, label: str, icon_filename: str, accent: str, index: int, parent=None):
        super().__init__(parent)
        self.label = label
        self.accent = QColor(accent)
        self.index = index
        self._hover = False
        self._visual_scale = 1.0
        self._icon = QIcon(str(BASE_DIR / "assets" / "icons" / icon_filename))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(self.BASE_WIDTH, self.BASE_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0; }"
        )

    def sizeHint(self) -> QSize:
        return QSize(round(self.BASE_WIDTH * self._visual_scale),
                     round(self.BASE_HEIGHT * self._visual_scale))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def set_visual_scale(self, scale: float) -> None:
        scale = max(1.0, min(1.35, float(scale)))
        if abs(scale - self._visual_scale) < 0.005:
            return
        self._visual_scale = scale
        hint = self.sizeHint()
        self.setFixedSize(hint)
        self.updateGeometry()
        self.update()

    def enterEvent(self, event):
        first_entry = not self._hover
        self._hover = True
        self.update()
        if first_entry:
            self.hovered.emit()
        super().enterEvent(event)

    def focusInEvent(self, event):
        self.hovered.emit()
        super().focusInEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.scale(self._visual_scale, self._visual_scale)
        lift = 3 if self._hover else 0
        down = 2 if self.isDown() else 0
        card = QRectF(5, 5 + lift,
                      self.BASE_WIDTH - 10, self.BASE_HEIGHT - 10)

        p.setPen(Qt.PenStyle.NoPen)
        shadow = QColor(theme.SHADOW)
        shadow.setAlpha(60 if not self._hover else 88)
        p.setBrush(shadow)
        p.drawRoundedRect(card.translated(0, 5), 17, 17)

        p.setPen(QPen(QColor(theme.ORANGE if self._hover else theme.NAVY),
                      4 if self._hover else 3))
        p.setBrush(QColor(theme.PANEL_ALT if self._hover else theme.PANEL))
        p.drawRoundedRect(card, 17, 17)

        tile_size = 92
        tile = QRectF(card.center().x() - tile_size / 2,
                      card.top() + 20 + lift * 0.2 + down,
                      tile_size, tile_size)
        grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
        grad.setColorAt(0.0, self.accent.lighter(112))
        grad.setColorAt(0.55, self.accent)
        grad.setColorAt(1.0, self.accent.darker(128))
        p.setPen(QPen(self.accent.darker(155), 3))
        p.setBrush(grad)
        p.drawRoundedRect(tile, 18, 18)
        p.setPen(QPen(QColor(255, 255, 255, 105), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(tile.adjusted(4, 4, -4, -4), 14, 14)

        icon_rect = tile.adjusted(18, 18, -18, -18).toRect()
        if not self._icon.isNull():
            self._icon.paint(p, icon_rect, Qt.AlignmentFlag.AlignCenter)

        plate = QRectF(card.left() + 12, card.bottom() - 44 + lift * 0.1 + down,
                       card.width() - 24, 31)
        p.setPen(QPen(QColor(theme.ORANGE_DARK), 2))
        plate_fill = QColor(theme.GOLD)
        plate_fill = plate_fill.lighter(108) if self._hover else plate_fill
        p.setBrush(plate_fill)
        p.drawRoundedRect(plate, 7, 7)

        # Shrink the label rather than clipping it.  The previous fixed plate
        # cut MYSTERY GIFT on narrower cards.
        label = self.label.upper()
        size = 14
        while size > 10:
            font = theme.ui_font(size, gba=True, bold=True)
            if QFontMetrics(font).horizontalAdvance(label) <= plate.width() - 16:
                break
            size -= 1
        p.setFont(theme.ui_font(size, gba=True, bold=True))
        p.setPen(QColor(theme.ON_GOLD))
        p.drawText(plate, Qt.AlignmentFlag.AlignCenter, label)

        if self._hover:
            p.setFont(theme.ui_font(14, gba=True, bold=True))
            # The plate is gold in every theme, so the arrow needs the gold
            # foreground ink.  Dark's ORANGE_DARK is a light peach for dark
            # panels and vanished against this plate.
            p.setPen(QColor(theme.ON_GOLD))
            p.drawText(QRectF(card.left() + 12, plate.top(), 18, plate.height()),
                       Qt.AlignmentFlag.AlignCenter, "▶")


class TradeBackdrop(QWidget):
    """The deep-blue link room behind the trade cards."""

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(theme.TRADE_BG_1))
        grad.setColorAt(0.55, QColor(theme.TRADE_BG_2))
        grad.setColorAt(1.0, QColor(theme.TRADE_BG_3))
        p.fillRect(self.rect(), grad)

        pattern = QColor(theme.TRADE_PATTERN)
        pattern.setAlpha(28)
        p.setPen(QPen(pattern, 1))
        for y in range(24, int(h * 0.82), 34):
            for x in range((y // 34) % 2 * 17, w, 34):
                p.drawPoint(x, y)

        pattern.setAlpha(14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pattern)
        for y in range(0, h, 48):
            for x in range((y // 48) % 2 * 24, w, 48):
                p.drawRect(x, y, 24, 24)

        p.save()
        p.setOpacity(0.10 if theme.THEME_ID in ("dark", "sinnoh") else 0.14)
        motif = "#ffffff" if theme.THEME_ID != "light" else theme.NAVY
        theme.draw_pokeball(p, w / 2, h * 0.47, min(w, h) * 0.30,
                            top=motif, bottom=motif, outline=motif,
                            outline_width=2)
        p.restore()

        p.setBrush(QColor(theme.TRADE_PATTERN))
        p.setOpacity(0.08)
        p.drawRect(0, h - 12, w, 12)
        p.setOpacity(1.0)


class StatusBadge(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(26)
        self.set_state("neutral")

    def set_state(self, state: str):
        self._state = state
        self.apply_theme()

    def apply_theme(self):
        states = {
            "ok": (theme.GREEN_LIGHT, theme.GREEN_DARK, theme.GREEN),
            "warn": (theme.PANEL_ALT, theme.ORANGE_DARK, theme.GOLD),
            "bad": (theme.RED_LIGHT, theme.RED_DARK, theme.RED),
            "info": (theme.BLUE_LIGHT, theme.NAVY_DARK, theme.BLUE),
            "neutral": (theme.PANEL_ALT, theme.INK_SOFT, theme.BORDER_SOFT),
        }
        bg, fg, border = states.get(getattr(self, "_state", "neutral"), states["neutral"])
        self.setStyleSheet(
            "QLabel { background-color: %s; color: %s; border: 2px solid %s; "
            "border-radius: %spx; padding: 2px 9px; font-family: '%s'; font-size: 13px; }"
            % (bg, fg, border, theme.CONTROL_RADIUS, theme.FONT_DS)
        )

class TradeStageScroll(QScrollArea):
    """Scroll the trade stage only when the window is shorter than its content.

    A plain resizable QScrollArea keeps the stage at its size hint (which
    includes the log's preferred height), so it shows a scrollbar even when
    the stage could shrink enough to fit.  Capping the stage at the viewport
    height lets it use the available height first; the stage's layout minimum
    then decides whether a scrollbar is actually needed.
    """

    def __init__(self, stage: QWidget, parent=None):
        super().__init__(parent)
        self._stage = stage

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_stage()

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_stage()

    def _fit_stage(self) -> None:
        height = self.viewport().height()
        if height > 0 and self._stage.maximumHeight() != height:
            self._stage.setMaximumHeight(height)


class FRLGTradeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            f"{APP_NAME} {APP_VERSION} — FireRed / LeafGreen Wireless Tool"
        )
        self.setMinimumSize(1180, 820)
        self.resize(1280, 900)
        self._restore_window_geometry()
        self._fit_to_available_screen()
        icon_path = BASE_DIR / "assets" / "branding" / "frlg_studio_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._menu_scale = 1.0
        self._last_window_layout = (0, 0)
        self.trade_proc = None
        self.keys_path = find_prod_keys()
        self.staging_out_file = paths.STAGING_RECEIVED
        self.staging_preview_file = paths.STAGING_PREVIEW
        self._live_incoming_shown = False
        self._live_offer_shown = False
        self._live_offer_key = b""

        legacy_rec = paths.LEGACY_RECEIVED
        if legacy_rec.exists():
            finalize_received_pk3(legacy_rec)

        # --- Check if a file was left in slot2 from a previous session ---
        self.slot2_path = ""
        slot2_dir = paths.SLOT2_DIR
        if slot2_dir.exists():
            existing_slot2 = list(slot2_dir.glob("*.pk3"))
            if existing_slot2:
                self.slot2_path = str(existing_slot2[0])

        self.received_path = ""
        self.last_dir = str(app_prefs.get("last_dir", DATA_DIR))
        self._last_tab = max(0, min(3, int(app_prefs.get("last_tab", 0) or 0)))
        self._readiness_dialog = None
        self._journal_dialog = None
        self._journal_session = None
        self._trade_mode = "live"
        self._about_dialog = None
        self._sound_settings_dialog = None
        self._recorded_capture = ""
        self._trade_log_start = 0
        self._suppress_tab_sound = False
        self._pc_booted = False
        self._close_after_pc_logoff = False
        self._trade_sequence_started = False
        self._sound_link_state = ""
        self._trade_stopped_by_user = False

        # The sound layer is created before any widget so menu and tab
        # callbacks can reach the module-level manager.  It stays silent until
        # the first user action; preload only warms the pooled voices.
        self.sound = sound.init(self)
        self._sound_preload_timer = QTimer(self)
        self._sound_preload_timer.setSingleShot(True)
        self._sound_preload_timer.timeout.connect(self.sound.preload)
        self._sound_preload_timer.start(350)
        # Start the theme music only after the first frame is painted.  A
        # missing pack or device leaves this silent without delaying startup.
        self._sound_music_timer = QTimer(self)
        self._sound_music_timer.setSingleShot(True)
        self._sound_music_timer.timeout.connect(self.sound.refresh_music)
        self._sound_music_timer.start(1100)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.sound.shutdown)

        # --- Base Container: The Deck of Cards ---
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Build Card 0: The HD-remaster title screen
        self.main_menu_widget = MenuBackdrop()
        self._build_main_menu()
        self.stacked_widget.addWidget(self.main_menu_widget)

        # Build Card 1: The App Engine
        self.app_widget = QWidget()
        self._build_app_engine()
        self.stacked_widget.addWidget(self.app_widget)

        # Start on the boot screen
        self.stacked_widget.setCurrentIndex(0)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.editor_tab.last_dir = self.last_dir
        self.setAcceptDrops(True)

        self.refresh_wifi_status()
        self.apply_theme()
        self.refresh_setup_badge()
        self.update_resume_button()

        self.live_watch_timer = QTimer(self)
        self.live_watch_timer.timeout.connect(self._poll_incoming_switch_pokemon)
        self.live_watch_timer.start(250)

        self._settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self._settings_shortcut.activated.connect(lambda: self.open_settings(None))
        self._setup_shortcuts()

        if not app_prefs.get("readiness_seen"):
            app_prefs.update(readiness_seen=True)
            QTimer.singleShot(900, self.open_readiness)

    # =========================================================================
    # NAVIGATION LOGIC
    # =========================================================================
    def _open_tab(self, index: int):
        """Instantly switch to the app engine and select the target tab."""
        previous = self.tabs.currentIndex()
        if self.stacked_widget.currentIndex() == 0:
            # The title screen is not a tab.  Without this sentinel, opening
            # Trade after leaving Bill's PC would replay the PC logoff that
            # _go_to_menu already played.
            previous = -1
        self._suppress_tab_sound = True
        self.tabs.setCurrentIndex(index)
        self._suppress_tab_sound = False
        self._previous_tab = index
        self.stacked_widget.setCurrentIndex(1)
        if previous == index:
            # Resuming the tab that is already selected is still a button
            # press: boot the PC or clink instead of going silent.
            if index == 1:
                sound.play("pc_open", force=True)
                self._pc_booted = True
            else:
                sound.play("menu_select")
        else:
            self._play_tab_cue(previous, index)

    def _play_tab_cue(self, previous: int, index: int) -> None:
        """Use the cue the games use for this top-level tab transition."""
        if previous == index:
            return
        if index == 1:
            # Entering Bill's PC boots the storage system.
            sound.play("pc_open", force=True)
            self._pc_booted = True
        elif previous == 1 and getattr(self, "_pc_booted", False):
            # Leaving Bill's PC is a storage logoff, whether the destination
            # is another tab or the title screen.  Play it exactly once.
            sound.play("pc_close", force=True)
            self._pc_booted = False
        else:
            sound.play("menu_select")

    def _go_to_menu(self):
        """Instantly return to the main menu screen."""
        if self.stacked_widget.currentIndex() == 0:
            return
        if getattr(self, "_pc_booted", False):
            sound.play("pc_close", force=True)
            self._pc_booted = False
        else:
            # The MAIN MENU button is a normal top-level navigation press,
            # so it uses the A-button clink rather than a set-down cue.
            sound.play("menu_select")
        # The title screen is not a tab.  Record that the PC has already been
        # powered down so resuming another tab does not log off a second time.
        self._previous_tab = 0
        self.stacked_widget.setCurrentIndex(0)

    def _on_tab_changed(self, index: int) -> None:
        index = int(index)
        previous = getattr(self, "_previous_tab", 0)
        self._previous_tab = index
        self._last_tab = index
        app_prefs.set_value("last_tab", self._last_tab)
        self.update_resume_button()
        if self.stacked_widget.currentIndex() != 1 or self._suppress_tab_sound:
            return
        self._play_tab_cue(previous, index)

    def _resume_last_tab(self) -> None:
        index = max(0, min(self.tabs.count() - 1, int(self._last_tab)))
        self._open_tab(index)

    def update_resume_button(self) -> None:
        button = getattr(self, "btn_resume", None)
        if button is None or not hasattr(self, "tabs"):
            return
        index = max(0, min(self.tabs.count() - 1, int(self._last_tab)))
        if index <= 0:
            button.hide()
            return
        button.setText(f"⏵  RESUME — {self.tabs.tabText(index)}")
        button.setToolTip(f"Return to {self.tabs.tabText(index)}")
        button.show()

    # ------------------------------------------------------------------
    # Window state and keyboard flow
    # ------------------------------------------------------------------
    def _restore_window_geometry(self) -> None:
        raw = app_prefs.geometry_bytes(str(app_prefs.get("window_geometry", "")))
        if raw:
            self.restoreGeometry(QByteArray(raw))

    def _save_window_geometry(self) -> None:
        app_prefs.update(
            window_geometry=app_prefs.geometry_text(self.saveGeometry()),
            last_tab=self._last_tab,
            last_dir=self.last_dir,
        )

    def _setup_shortcuts(self) -> None:
        self._tab_shortcuts = []
        for index in range(4):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(
                lambda _checked=False, i=index: self._open_tab(i)
            )
            self._tab_shortcuts.append(shortcut)

        self._open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self._open_shortcut.activated.connect(self.open_pk3_dialog)
        self._undo_shortcut = QShortcut(QKeySequence("Alt+Z"), self)
        self._undo_shortcut.activated.connect(self.undo_last_change)
        self._mute_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self._mute_shortcut.activated.connect(self.toggle_sound)

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Escape
            and self.stacked_widget.currentIndex() == 1
        ):
            focus = QApplication.focusWidget()
            if (
                not isinstance(focus, (QLineEdit, QTextEdit, QComboBox, QSpinBox))
                and QApplication.activePopupWidget() is None
            ):
                self._go_to_menu()
                event.accept()
                return
        super().keyPressEvent(event)

    def open_pk3_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Gen 3 Pokémon",
            self.last_dir,
            "Gen 3 Pokemon (*.pk3 *.ek3)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.open_pk3_path(path)

    def open_pk3_path(self, path: str) -> None:
        target = Path(path)
        if not target.is_file() or target.stat().st_size < 80:
            sound.play("ui_error")
            QMessageBox.warning(
                self, "Invalid File",
                "Selected file is missing or smaller than 80 bytes.",
            )
            return
        self.last_dir = str(target.parent)
        self.editor_tab.last_dir = self.last_dir
        app_prefs.update(last_dir=self.last_dir)
        app_prefs.add_recent(target)
        self.editor_tab.load_file(str(target))
        self._open_tab(2)

    # ------------------------------------------------------------------
    # Setup check
    # ------------------------------------------------------------------
    def refresh_setup_badge(self) -> None:
        button = getattr(self, "btn_setup", None)
        if button is None:
            return
        try:
            checks = collect_checks(self)
            ready, summary = summarize(checks)
        except Exception as exc:
            ready, summary = False, f"SETUP: {exc}"
            checks = []
        button.setText("READY" if ready else "SETUP")
        lines = [summary]
        lines.extend(
            f"{'✓' if check.ok else '!'}  {check.title}: {check.detail}"
            for check in checks
        )
        button.setToolTip("\n".join(lines))
        bg = theme.GREEN_LIGHT if ready else theme.PANEL_ALT
        fg = theme.GREEN_DARK if ready else theme.ORANGE_DARK
        border = theme.GREEN if ready else theme.ORANGE
        button.setStyleSheet(
            "QPushButton { background-color: %s; color: %s;"
            " border: 2px solid %s; border-radius: 5px; padding: 2px 8px;"
            " min-height: 20px; font-family: '%s'; font-size: 11px; }"
            % (bg, fg, border, theme.FONT_DS)
        )

    def open_about(self) -> None:
        from about_dialog import AboutDialog

        dialog = getattr(self, "_about_dialog", None)
        if dialog is not None:
            try:
                opening = not dialog.isVisible()
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
                if opening:
                    sound.play("ui_open")
                return
            except RuntimeError:
                self._about_dialog = None
        self._about_dialog = AboutDialog(self)
        self._about_dialog.finished.connect(lambda _code: sound.play("ui_close"))
        self._about_dialog.show()
        sound.play("ui_open")

    def open_readiness(self) -> None:
        dialog = getattr(self, "_readiness_dialog", None)
        if dialog is not None:
            try:
                opening = not dialog.isVisible()
                dialog.rebuild()
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
                if opening:
                    sound.play("ui_open")
                return
            except RuntimeError:
                self._readiness_dialog = None
        self._readiness_dialog = show_readiness_dialog(self)
        self._readiness_dialog.finished.connect(lambda _code: sound.play("ui_close"))
        sound.play("ui_open")

    # ------------------------------------------------------------------
    # User data undo / folder
    # ------------------------------------------------------------------
    def open_data_folder(self) -> None:
        sound.play("ui_open")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR)))

    def undo_last_change(self) -> None:
        import user_data

        if user_data.latest_snapshot() is None:
            sound.play("ui_error")
            QMessageBox.information(
                self, "Undo",
                "No changes have been recorded yet. The app snapshots the "
                "Pokémon folders before each change.",
            )
            return
        sound.play("ui_warning")
        reply = QMessageBox.question(
            self,
            "Undo Last Change",
            f"Restore the data from before:\n\n{user_data.describe_latest()}\n\n"
            "The current state is saved first, so this can be reversed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, message = user_data.restore_latest()
        if ok:
            self.pc_tab.refresh_boxes()
            self._refresh_after_restore()
            self.refresh_setup_badge()
            sound.play("pc_undo")
        else:
            sound.play("ui_error")
        QMessageBox.information(self, "Undo Last Change", message)

    def _refresh_after_restore(self) -> None:
        for name in ("slot2_path", "received_path"):
            value = getattr(self, name, "")
            if value and not Path(value).exists():
                setattr(self, name, "")
        if hasattr(self, "panel_pc"):
            if self.slot2_path:
                self.panel_pc.load_pk3(self.slot2_path)
            else:
                self.panel_pc.set_waiting_state("SELECT A POKéMON FROM STORAGE")
        if hasattr(self, "panel_switch"):
            if self.received_path:
                self.panel_switch.load_pk3(self.received_path)
            else:
                self.panel_switch.set_waiting_state("WAITING FOR SWITCH TRADE")

    # ------------------------------------------------------------------
    # File drops
    # ------------------------------------------------------------------
    @staticmethod
    def _dropped_pk3_paths(mime) -> list[str]:
        if not mime.hasUrls():
            return []
        paths = []
        for url in mime.urls():
            local = url.toLocalFile()
            if local and local.lower().endswith((".pk3", ".ek3")):
                paths.append(local)
        return paths

    def dragEnterEvent(self, event):
        if self._dropped_pk3_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._dropped_pk3_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        paths = self._dropped_pk3_paths(event.mimeData())
        if not paths:
            super().dropEvent(event)
            return
        event.acceptProposedAction()
        if self.tabs.currentWidget() is self.pc_tab:
            self.pc_tab.import_files(paths)
        elif len(paths) == 1:
            self.open_pk3_path(paths[0])
        else:
            self.pc_tab.import_files(paths)
            self._open_tab(1)

    # =========================================================================
    # APPEARANCE & SETTINGS
    # =========================================================================
    def _fit_to_available_screen(self):
        """Keep the scaled window inside the current screen, never below its minimum."""
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = min(self.width(), max(1180, available.width() - 24))
        height = min(self.height(), max(820, available.height() - 48))
        if (width, height) != (self.width(), self.height()):
            self.resize(width, height)

    # ------------------------------------------------------------------
    # Responsive window treatment
    # ------------------------------------------------------------------
    def _menu_scale_for_window(self) -> float:
        """Scale the title screen with the window, not the desktop DPI.

        1280x900 gives scale 1.0; a 1440p maximized window reaches the 1.35
        cap.  The width drives the scale because the card row has room to
        spread horizontally even when the desktop bar leaves the window
        slightly shorter than 900.  The cap keeps the title screen from
        turning into billboards on a 4K desktop.
        """
        if not hasattr(self, "menu_cards"):
            return 1.0
        width_scale = self.width() / 1280.0
        if self.height() < 860:
            width_scale = min(width_scale, 1.0)
        return min(1.35, max(1.0, width_scale))

    def _apply_adaptive_layout(self, force: bool = False):
        """Grow the title screen and use wide canvases without breaking normal windows."""
        if not hasattr(self, "menu_cards"):
            return
        size = (self.width(), self.height())
        if not force and size == self._last_window_layout:
            return
        self._last_window_layout = size

        scale = self._menu_scale_for_window()
        if abs(scale - self._menu_scale) >= 0.005 or force:
            self._menu_scale = scale
            self.menu_layout.setContentsMargins(
                round(40 * scale), round(26 * scale),
                round(40 * scale), round(44 * scale),
            )
            self.menu_btn_row.setSpacing(round(24 * scale))
            self.menu_emblem.setFixedSize(round(62 * scale), round(62 * scale))
            self.menu_rule.setFixedSize(round(240 * scale),
                                        max(3, round(4 * scale)))
            for card in self.menu_cards:
                card.set_visual_scale(scale)
            self._style_menu_text()
            # A synchronous repaint also clears the old backdrop from the gap
            # left by the previous card geometry during maximize/restore.
            self.main_menu_widget.repaint()

        if hasattr(self, "trade_stage"):
            # The old 1640 px cap left a maximized 1440p window looking like a
            # small app in the middle of the desktop.  Keep a generous ceiling
            # for ultrawide screens but let the trading stage breathe.
            self.trade_stage.setMaximumWidth(
                max(1180, min(2200, self.width() - 20))
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_adaptive_layout()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.ActivationChange,
                            QEvent.Type.WindowStateChange):
            backdrop = getattr(self, "main_menu_widget", None)
            if backdrop is not None:
                backdrop.resume_animation()

    def _style_menu_text(self):
        """Apply the title-screen font sizes for the current window scale."""
        if not hasattr(self, "menu_title_left"):
            return
        s = getattr(self, "_menu_scale", 1.0)
        overline_ink = getattr(theme, "MENU_OVERLINE_INK", theme.INK_SOFT)
        overline_alt = getattr(theme, "MENU_OVERLINE_INK_ALT", overline_ink)
        subtitle_ink = getattr(theme, "MENU_SUBTITLE_INK", theme.INK_SOFT)
        subtitle_alt = getattr(theme, "MENU_SUBTITLE_INK_ALT", subtitle_ink)
        title_ink = getattr(theme, "MENU_TITLE_INK", theme.MENU_INK)
        title_alt = getattr(theme, "MENU_TITLE_INK_ALT", title_ink)

        # Keep one centre gap for every theme.  Hoenn and Unova used to get
        # a wider gap because their two inks meet at the seam, which made the
        # wordmark visibly change tracking when switching themes.
        split_layout = title_ink.lower() != title_alt.lower()
        gap = max(8, round(10 * s))
        for grid in (self.menu_overline_grid, self.menu_title_grid,
                     self.menu_subtitle_grid):
            grid.setColumnMinimumWidth(1, gap)

        overline_css = (
            "font-family: '%s'; font-size: %dpx; letter-spacing: %dpx; color: %%s;"
            % (theme.FONT_DS, round(15 * s), round(4 * s))
        )
        self.menu_overline_left.setStyleSheet(overline_css % overline_ink)
        self.menu_overline_right.setStyleSheet(overline_css % overline_alt)

        title_css = (
            "font-family: '%s'; font-size: %dpx; letter-spacing: %dpx; color: %%s;"
            % (theme.FONT_GBA, round(50 * s), round(2 * s))
        )
        self.menu_title_left.setStyleSheet(title_css % title_ink)
        self.menu_title_right.setStyleSheet(title_css % title_alt)

        for shadow in getattr(self, "_menu_title_shadows", ()):
            shadow.setEnabled(not split_layout)
            shadow.setOffset(round(3 * s), round(3 * s))
            # The shadow is always the opposite value of the title, so a
            # cream title on FRLG's vortex gets a dark offset and the dark
            # titles on pale themes keep their light offset.
            shadow.setColor(QColor(
                theme.PANEL if QColor(title_ink).lightness() < 128
                else theme.MENU_FOOTER_BG
            ))
        self.menu_rule.setStyleSheet(
            "background-color: %s; border: none; border-radius: 2px;" % theme.GOLD
        )

        subtitle_css = (
            "font-family: '%s'; font-size: %dpx; letter-spacing: %dpx; color: %%s;"
            % (theme.FONT_GBA, round(15 * s), round(2 * s))
        )
        self.menu_subtitle_left.setStyleSheet(subtitle_css % subtitle_ink)
        self.menu_subtitle_right.setStyleSheet(subtitle_css % subtitle_alt)
        # The prompt sits over painted scenery in every theme, so it gets the
        # same dark footer ink as the strip below it.  A faint plate keeps the
        # word legible whether it lands on grass, water or a night sky.
        hint_bg = QColor(theme.MENU_FOOTER_BG)
        hint_bg.setAlpha(205)
        hint_fg = QColor(theme.MENU_FOOTER_FG)
        hint_edge = QColor(theme.MENU_FOOTER_FG)
        hint_edge.setAlpha(60)
        self.menu_hint.setStyleSheet(
            "QLabel { color: %s; background-color: rgba(%d,%d,%d,%d);"
            " border: 1px solid rgba(%d,%d,%d,%d); border-radius: %dpx;"
            " padding: %dpx %dpx; font-family: '%s'; font-size: %dpx;"
            " letter-spacing: 1px; }"
            % (hint_fg.name(), hint_bg.red(), hint_bg.green(), hint_bg.blue(),
               hint_bg.alpha(), hint_edge.red(), hint_edge.green(),
               hint_edge.blue(), hint_edge.alpha(),
               round(int(theme.CONTROL_RADIUS) * s), round(2 * s),
               round(9 * s), theme.FONT_GBA, round(11 * s))
        )
        panel = QColor(theme.PANEL)
        panel.setAlpha(200)
        button_size = round(12 * s)
        button_pad = round(5 * s)
        self.btn_power.setStyleSheet(
            "QPushButton { background-color: rgba(%d,%d,%d,%d); color: %s; "
            "border: 2px solid %s; border-radius: %spx; padding: %dpx %dpx; "
            "font-family: '%s'; font-size: %dpx; }"
            "QPushButton:hover { background-color: %s; color: %s; border-color: %s; }"
            % (panel.red(), panel.green(), panel.blue(), panel.alpha(),
               theme.INK_SOFT, theme.BORDER, round(int(theme.CONTROL_RADIUS) * s),
               button_pad, round(13 * s), theme.FONT_GBA, button_size,
               theme.RED_LIGHT, theme.RED_DARK, theme.RED)
        )
        self.btn_menu_settings.setStyleSheet(
            "QPushButton { background-color: rgba(%d,%d,%d,%d); color: %s; "
            "border: 2px solid %s; border-radius: %spx; padding: %dpx %dpx; "
            "font-family: '%s'; font-size: %dpx; }"
            "QPushButton:hover { background-color: %s; color: %s; border-color: %s; }"
            % (panel.red(), panel.green(), panel.blue(), panel.alpha(),
               theme.INK_SOFT, theme.BORDER, round(int(theme.CONTROL_RADIUS) * s),
               button_pad, round(11 * s), theme.FONT_GBA, button_size,
               theme.HOVER, theme.ORANGE_DARK, theme.ORANGE)
        )
        for button in (self.btn_resume, self.btn_menu_setup):
            button.setStyleSheet(
                "QPushButton { background-color: rgba(%d,%d,%d,%d); color: %s; "
                "border: 2px solid %s; border-radius: %spx; padding: %dpx %dpx; "
                "font-family: '%s'; font-size: %dpx; }"
                "QPushButton:hover { background-color: %s; color: %s; border-color: %s; }"
                % (panel.red(), panel.green(), panel.blue(), panel.alpha(),
                   theme.INK_SOFT, theme.BORDER, round(int(theme.CONTROL_RADIUS) * s),
                   button_pad, round(11 * s), theme.FONT_GBA, button_size,
                   theme.HOVER, theme.ORANGE_DARK, theme.ORANGE)
            )

    def open_settings(self, anchor=None):
        """Open the small, themed settings popup over the current window."""
        opening = True
        if not hasattr(self, "_settings_popup"):
            self._settings_popup = SettingsPopup(self)
            self._settings_popup.theme_selected.connect(self._on_settings_theme)
            self._settings_popup.restart_requested.connect(self._restart_for_scale)
            self._settings_popup.readiness_requested.connect(self.open_readiness)
            self._settings_popup.about_requested.connect(self.open_about)
            self._settings_popup.undo_requested.connect(self.undo_last_change)
            self._settings_popup.open_data_requested.connect(self.open_data_folder)
            self._settings_popup.sound_enabled_changed.connect(self._on_sound_enabled)
            self._settings_popup.sound_volume_changed.connect(self._on_sound_volume)
            self._settings_popup.sound_preview_requested.connect(self._preview_sound)
            self._settings_popup.sound_settings_requested.connect(self.open_sound_settings)
            self._settings_popup.closed.connect(self._on_settings_closed)
            self._settings_popup.attach_link_controls(
                self.wifi_status_lbl, self.phy_lbl, self.keys_badge_btn,
                self.game_lbl, self.version_combo,
            )
        else:
            opening = not self._settings_popup.isVisible()
        if anchor is None:
            anchor = getattr(self, "btn_settings", None)
            if anchor is None or not anchor.isVisible():
                anchor = getattr(self, "btn_menu_settings", None)
        self.sound.retry_audio()
        self._settings_popup.set_sound_state(
            self.sound.enabled,
            self.sound.sfx_volume,
            self.sound.available,
            summary=self.sound.summary(),
            muted=self.sound.master_muted,
        )
        self._settings_popup.show_at(anchor)
        if opening:
            sound.play("open_settings")

    def _on_settings_theme(self, key: str):
        theme.set_theme(str(key), target=self)
        self.sound.set_theme(str(key))
        self.apply_theme()
        if hasattr(self, "_settings_popup"):
            self._settings_popup.apply_theme()
        dialog = getattr(self, "_sound_settings_dialog", None)
        if dialog is not None:
            dialog.refresh()

    def _on_settings_closed(self) -> None:
        sound.play("ui_close")

    def open_sound_settings(self) -> None:
        """Open the full three-bus mixer, independent of the compact popup."""
        if self._sound_settings_dialog is None:
            self._sound_settings_dialog = SoundSettingsDialog(self)
        self._sound_settings_dialog.refresh()
        self._sound_settings_dialog.show()
        self._sound_settings_dialog.raise_()
        self._sound_settings_dialog.activateWindow()
        sound.play("open_settings")

    def _on_sound_enabled(self, enabled: bool) -> None:
        self.sound.set_sfx_enabled(bool(enabled))
        if enabled:
            self.sound.play("ui_toggle", force=True)
        self._sync_sound_ui()

    def _on_sound_volume(self, volume: float) -> None:
        self.sound.set_sfx_volume(float(volume))
        self.sound.play("ui_click", force=True)

    def _preview_sound(self) -> None:
        self.sound.play("ui_confirm", force=True)

    def toggle_sound(self) -> None:
        """Ctrl+M: mute or restore all three buses together."""
        muted = not self.sound.master_muted
        self.sound.set_master_muted(muted)
        if not muted:
            self.sound.play("ui_toggle", force=True)
        self._sync_sound_ui()

    def _sync_sound_ui(self) -> None:
        popup = getattr(self, "_settings_popup", None)
        if popup is not None:
            popup.set_sound_state(
                self.sound.enabled,
                self.sound.sfx_volume,
                self.sound.available,
                summary=self.sound.summary(),
                muted=self.sound.master_muted,
            )
        dialog = getattr(self, "_sound_settings_dialog", None)
        if dialog is not None:
            dialog.refresh()

    def _restart_for_scale(self, scale: float):
        """Save the new UI size and relaunch so Qt can install it at startup."""
        busy = bool(self.trade_proc and
                    self.trade_proc.state() != QProcess.ProcessState.NotRunning)
        mg_proc = getattr(getattr(self, "mg_tab", None), "mg_proc", None)
        busy = busy or bool(mg_proc and
                            mg_proc.state() != QProcess.ProcessState.NotRunning)
        if busy:
            QMessageBox.warning(
                self, "UI Size",
                "Stop the active link trade or Wonder Card broadcast before "
                "restarting to a new UI size.",
            )
            return

        if not theme.save_scale(scale):
            QMessageBox.warning(
                self, "UI Size",
                f"The UI size setting could not be saved. Check that {paths.CONFIG_DIR} is writable.",
            )
            return

        previous_qt = os.environ.get("QT_SCALE_FACTOR")
        previous_base = os.environ.get("FRLG_BASE_QT_SCALE")
        base = theme.base_scale()
        os.environ["FRLG_BASE_QT_SCALE"] = f"{base:g}"
        os.environ["QT_SCALE_FACTOR"] = f"{base * scale:g}"
        if getattr(sys, "frozen", False):
            program, arguments = sys.executable, []
        else:
            program, arguments = sys.executable, [str(Path(__file__).resolve())]
        started, _pid = QProcess.startDetached(
            program, arguments, str(DATA_DIR)
        )
        if not started:
            for key, previous in (
                ("QT_SCALE_FACTOR", previous_qt),
                ("FRLG_BASE_QT_SCALE", previous_base),
            ):
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
            QMessageBox.warning(
                self, "Restart Failed",
                "FRLG Studio could not restart automatically.\n\n"
                "The new UI size is saved and will apply the next time you open the app.",
            )
            return

        QApplication.quit()

    def apply_theme(self):
        """Refresh every hand-painted or inline-styled surface.

        The global QSS is already updated by theme.set_theme(); this method
        covers the custom paintings and the small labels that intentionally
        carry their own font/colour treatment.
        """
        if hasattr(self, "menu_overline_left"):
            self._style_menu_text()
            self.main_menu_widget.repaint()
            self.menu_emblem.update()
            for card in self.menu_cards:
                card.update()

        if hasattr(self, "btn_settings"):
            self.btn_settings.setStyleSheet(
                "QPushButton { background: transparent; color: %s; border: 1px solid transparent;"
                " border-radius: 5px; padding: 0; font-family: '%s'; font-size: 17px; }"
                "QPushButton:hover { background-color: %s; color: %s; border-color: %s; }"
                % (theme.INK_SOFT, theme.FONT_DS, theme.PANEL_ALT,
                   theme.ORANGE_DARK, theme.BORDER_SOFT)
            )

        if hasattr(self, "phy_lbl"):
            self.phy_lbl.setStyleSheet(
                "color: %s; font-family: '%s'; font-size: 12px; padding: 0 2px;"
                % (theme.INK_SOFT, theme.FONT_DS)
            )
            self.game_lbl.setStyleSheet(
                "color: %s; font-family: '%s'; font-size: 12px;"
                % (theme.INK_SOFT, theme.FONT_GBA)
            )
            self.wifi_status_lbl.apply_theme()
            self.update_keys_badge()
            if hasattr(self, "dummy_badge"):
                self.dummy_badge.apply_theme()
            self.app_widget.update()

        dialog = getattr(self, "_sound_settings_dialog", None)
        if dialog is not None:
            dialog.apply_theme()
            dialog.refresh()

        if hasattr(self, "panel_pc"):
            self.panel_pc.apply_theme()
            self.panel_switch.apply_theme()
            self.log_output.setStyleSheet(
                "QTextEdit { background-color: %s; color: %s; border: 3px solid %s; "
                "border-radius: %spx; padding: 8px; font-family: '%s'; font-size: 14px; }"
                % (theme.FIELD, theme.INK, theme.NAVY, theme.PANEL_RADIUS, theme.FONT_GBA)
            )
            self.trade_dummy_lbl.setStyleSheet(
                "color: %s; font-family: '%s'; font-size: 12px; letter-spacing: 1px;"
                % (theme.TRADE_INK, theme.FONT_GBA)
            )
            self.trade_tab.update()
            self.tunnel_widget.update()

        for tab_name in ("pc_tab", "editor_tab", "mg_tab"):
            tab = getattr(self, tab_name, None)
            if tab is not None and hasattr(tab, "apply_theme"):
                tab.apply_theme()

        popup = getattr(self, "_settings_popup", None)
        if popup is not None:
            popup.apply_theme()

    # =========================================================================
    # CORE UI BUILDERS
    # =========================================================================
    def _build_main_menu(self):
        layout = QVBoxLayout(self.main_menu_widget)
        self.menu_layout = layout
        layout.setContentsMargins(40, 26, 40, 44)
        layout.setSpacing(0)

        layout.addStretch(2)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)

        self.menu_emblem = PokeballEmblem(62)
        title_block.addWidget(self.menu_emblem, alignment=Qt.AlignmentFlag.AlignHCenter)

        def split_title_row(left_text: str, right_text: str):
            """Two labels in equal columns, with a centred gap between them.

            A single centred label splits wherever its glyphs happen to fall,
            which put half of Unova's "S" on the black side.  Equal columns
            pin the gap to the window centre, so the two inks meet in the
            space between words at every UI scale.
            """
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(0)
            grid.setVerticalSpacing(0)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(2, 1)
            grid.setColumnMinimumWidth(1, 18)
            left = QLabel(left_text)
            left.setAlignment(Qt.AlignmentFlag.AlignRight
                              | Qt.AlignmentFlag.AlignVCenter)
            right = QLabel(right_text)
            right.setAlignment(Qt.AlignmentFlag.AlignLeft
                               | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(left, 0, 0)
            grid.addWidget(right, 0, 2)
            return grid, left, right

        (self.menu_overline_grid, self.menu_overline_left,
         self.menu_overline_right) = split_title_row(
            "POKéMON  •", "WIRELESS LINK"
        )
        title_block.addLayout(self.menu_overline_grid)

        (self.menu_title_grid, self.menu_title_left,
         self.menu_title_right) = split_title_row("FRLG", "STUDIO")
        self._menu_title_shadows = []
        for title_part in (self.menu_title_left, self.menu_title_right):
            title_shadow = QGraphicsDropShadowEffect(title_part)
            title_shadow.setBlurRadius(0)
            title_shadow.setOffset(3, 3)
            title_shadow.setColor(QColor(255, 255, 255, 70))
            title_part.setGraphicsEffect(title_shadow)
            self._menu_title_shadows.append(title_shadow)
        title_block.addLayout(self.menu_title_grid)

        self.menu_rule = QFrame()
        self.menu_rule.setFixedSize(240, 4)
        title_block.addWidget(self.menu_rule, alignment=Qt.AlignmentFlag.AlignHCenter)
        title_block.addSpacing(6)

        (self.menu_subtitle_grid, self.menu_subtitle_left,
         self.menu_subtitle_right) = split_title_row(
            "WIRELESS TRADE  &", "STORAGE SYSTEM"
        )
        title_block.addLayout(self.menu_subtitle_grid)

        layout.addLayout(title_block)
        layout.addSpacing(22)

        btn_row = QHBoxLayout()
        self.menu_btn_row = btn_row
        btn_row.setSpacing(24)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.menu_cards = []
        for text, icon_filename, accent, idx in [
            ("Trade", "menu_trade.svg", "#d94b47", 0),
            ("Storage", "menu_storage.svg", "#e2a13b", 1),
            ("Editor", "menu_editor.svg", "#3a9b7c", 2),
            ("Mystery Gift", "menu_gift.svg", "#6d84c8", 3),
        ]:
            card = MenuCard(text, icon_filename, accent, idx)
            card.clicked.connect(lambda _checked=False, i=idx: self._open_tab(i))
            card.hovered.connect(lambda: sound.play("menu_move"))
            self.menu_cards.append(card)
            btn_row.addWidget(card)

        layout.addLayout(btn_row)
        layout.addStretch(3)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        self.menu_hint = QLabel("SELECT A SYSTEM")
        bottom_row.addWidget(self.menu_hint)
        bottom_row.addStretch()

        self.btn_resume = QPushButton("⏵  RESUME")
        self.btn_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_resume.setToolTip("Return to the last open tab")
        self.btn_resume.clicked.connect(self._resume_last_tab)
        self.btn_resume.hide()
        bottom_row.addWidget(self.btn_resume)

        self.btn_menu_setup = QPushButton("✓  SETUP CHECK")
        self.btn_menu_setup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu_setup.setToolTip("Check keys, adapter, PKHeX and trade slots")
        self.btn_menu_setup.clicked.connect(self.open_readiness)
        bottom_row.addWidget(self.btn_menu_setup)

        self.btn_menu_settings = QPushButton("⚙  SETTINGS")
        self.btn_menu_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu_settings.setToolTip("Theme and UI size (Ctrl+,)")
        self.btn_menu_settings.clicked.connect(
            lambda: self.open_settings(self.btn_menu_settings)
        )
        bottom_row.addWidget(self.btn_menu_settings)

        self.btn_power = QPushButton("⏻  POWER OFF")
        self.btn_power.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_power.clicked.connect(QApplication.quit)
        bottom_row.addWidget(self.btn_power)

        layout.addLayout(bottom_row)
        self._last_window_layout = (0, 0)
        self._apply_adaptive_layout(force=True)

    def _build_app_engine(self):
        self.app_widget.setObjectName("AppEngine")
        main_layout = QVBoxLayout(self.app_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ==================== TOP BAR ====================
        top_group = QFrame()
        top_group.setObjectName("TopBar")
        self.top_group = top_group
        top_layout = QHBoxLayout(top_group)
        top_layout.setContentsMargins(9, 5, 9, 5)
        top_layout.setSpacing(6)

        # The link readout, keys button and game selector live in Settings
        # now.  Keep the widgets alive here for their existing status and
        # trade code, then reparent them into the popup when it opens.
        self.wifi_status_lbl = StatusBadge("WIRELESS: CHECKING...", self)
        self.phy_lbl = QLabel(f"({detect_wiphy(bring_up=False)})", self)
        self.keys_badge_btn = QPushButton(self)
        self.keys_badge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keys_badge_btn.setToolTip("Locate a different prod.keys file")
        self.keys_badge_btn.clicked.connect(self.browse_keys_file)
        self.update_keys_badge()

        self.game_lbl = QLabel("GAME", self)
        self.version_combo = theme.AppComboBox(self)
        self.version_combo.addItems(["firered", "leafgreen"])
        self.version_combo.setFixedWidth(108)

        for widget in (self.wifi_status_lbl, self.phy_lbl,
                       self.keys_badge_btn, self.game_lbl,
                       self.version_combo):
            widget.hide()

        # Initialize Dummy Badge; it is placed in the trade footer below.
        self.dummy_badge = MiniDummyLeadBadge(ensure_slot1_dummy())

        # Center the working actions.  Brand and setup moved out of this bar
        # in the UI pass, so the row has room to breathe around them.  The
        # fixed lead cancels the settings button on the right, keeping the
        # three-button group on the window's true centreline.
        top_layout.addSpacing(36)
        top_layout.addStretch(1)

        self.btn_main_menu = QPushButton("◄  MAIN MENU")
        self.btn_main_menu.setToolTip("Return to the title screen")
        self.btn_main_menu.clicked.connect(self._go_to_menu)
        top_layout.addWidget(self.btn_main_menu)

        self.btn_wifi_trade = QPushButton("ATTACH ADAPTER")
        self.btn_wifi_trade.setToolTip("Attach the wireless adapter for link trades")
        self.btn_wifi_trade.clicked.connect(self.enable_trade_wifi)
        top_layout.addWidget(self.btn_wifi_trade)

        self.btn_wifi_normal = QPushButton("DETACH ADAPTER")
        self.btn_wifi_normal.setToolTip("Restore normal Wi-Fi / NetworkManager")
        self.btn_wifi_normal.clicked.connect(self.restore_normal_wifi)
        top_layout.addWidget(self.btn_wifi_normal)

        top_layout.addStretch(1)

        # Always reachable while the app deck is open, independent of the
        # active tab.  The title screen keeps its labelled settings button.
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setFixedSize(30, 26)
        self.btn_settings.setToolTip("Settings — theme and UI size (Ctrl+,)")
        self.btn_settings.setAccessibleName("Settings")
        self.btn_settings.clicked.connect(lambda: self.open_settings(self.btn_settings))
        top_layout.addWidget(self.btn_settings)

        main_layout.addWidget(top_group)

        # ==================== TABS ====================
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        main_layout.addWidget(self.tabs)

        self.trade_tab = TradeBackdrop()

        self.editor_tab = PKMDSEditorTab(DATA_DIR)
        self.mg_tab = WonderCardTab(self, self.editor_tab)

        self.pc_tab = BillsPCTab(self.editor_tab)
        self.pc_tab.send_to_editor.connect(self.open_in_editor)
        self.pc_tab.send_to_slot2.connect(self.on_editor_sent_to_slot2)

        self.tabs.addTab(self.trade_tab, "TRADE CENTER")
        self.tabs.addTab(self.pc_tab, "BILL'S PC")
        self.tabs.addTab(self.editor_tab, "POKéMON EDITOR")
        self.tabs.addTab(self.mg_tab, "WONDER CARDS")

        self.build_trade_tab()
        self.editor_tab.send_to_slot2.connect(self.on_editor_sent_to_slot2)

    def update_keys_badge(self):
        if self.keys_path.exists() and self.keys_path.stat().st_size > 64:
            self.keys_badge_btn.setText("KEYS: OK")
            bg, fg, border = theme.GREEN_LIGHT, theme.GREEN_DARK, theme.GREEN
        else:
            self.keys_badge_btn.setText("KEYS: MISSING")
            bg, fg, border = theme.RED_LIGHT, theme.RED_DARK, theme.RED
        self.keys_badge_btn.setStyleSheet(
            "QPushButton { background-color: %s; color: %s; border: 2px solid %s; "
            "border-radius: %spx; padding: 2px 8px; min-height: 20px; "
            "font-family: '%s'; font-size: 12px; }"
            % (bg, fg, border, theme.CONTROL_RADIUS, theme.FONT_DS)
        )

    def browse_keys_file(self):
        start = self.keys_path.parent if self.keys_path.parent.exists() else DATA_DIR
        path, _ = QFileDialog.getOpenFileName(
            self, "Locate prod.keys", str(start), "Keys (*.keys *)"
        )
        if path:
            self.keys_path = Path(path)
            self.update_keys_badge()
            self.refresh_setup_badge()

    def on_editor_sent_to_slot2(self, path: str):
        self.slot2_path = path
        self.panel_pc.load_pk3(path)
        self.tabs.setCurrentWidget(self.trade_tab)

    def refresh_wifi_status(self):
        phy = detect_wiphy(bring_up=False)
        self.phy_lbl.setText(f"({phy})")
        if network_manager_active():
            self.wifi_status_lbl.setText("WIRELESS: NORMAL WI-FI")
            self.wifi_status_lbl.set_state("ok")
        else:
            self.wifi_status_lbl.setText("WIRELESS: ADAPTER ATTACHED")
            self.wifi_status_lbl.set_state("warn")

    def enable_trade_wifi(self):
        if not acquire_admin():
            self.log_output.append("[System] Admin access denied. Cannot modify Wi-Fi.")
            return
        # Added -n (non-interactive) to prevent faillock if something goes weird
        subprocess.run(["sudo", "-n", "modprobe", "mt7921e"])
        subprocess.run(["sudo", "-n", "rfkill", "unblock", "wifi"])
        subprocess.run(["sudo", "-n", "systemctl", "stop", "NetworkManager", "wpa_supplicant"])
        self.refresh_wifi_status()
        self.log_output.append(f"[System] Attached Wireless Adapter. Intercepting {detect_wiphy()}.")

    def restore_normal_wifi(self):
        if not acquire_admin():
            self.log_output.append("[System] Admin access denied. Cannot modify Wi-Fi.")
            return
        # Added -n (non-interactive) to prevent faillock if something goes weird
        subprocess.run(["sudo", "-n", "rfkill", "unblock", "wifi"])
        subprocess.run(["sudo", "-n", "systemctl", "start", "NetworkManager"])
        subprocess.run(["sudo", "-n", "chown", "-R", f"{USER_NAME}:{USER_NAME}", str(DATA_DIR)])
        self.refresh_wifi_status()
        self.log_output.append(f"[System] Detached Adapter. Restored Normal Wi-Fi.")

    def closeEvent(self, event):
        # Closing the window while Bill's PC is open is a PC logoff too.  Play
        # the cue and keep the window alive for its short tail; otherwise the
        # immediate audio teardown would cut it off before the first frame is
        # heard.  The second closeEvent finishes the shutdown normally.
        if (
            getattr(self, "_pc_booted", False)
            and not getattr(self, "_close_after_pc_logoff", False)
        ):
            self._pc_booted = False
            sound.play("pc_close", force=True)
            self._close_after_pc_logoff = True
            if self.sound.available and not self.sound.master_muted and self.sound.sfx_enabled:
                event.ignore()
                QTimer.singleShot(430, self.close)
                return
        self._close_after_pc_logoff = True
        # Stop audio before any teardown; aboutToQuit is a second safety net.
        self.sound.shutdown()
        # Gracefully shut down active sub-processes
        if hasattr(self, 'mg_tab'):
            self.mg_tab.stop_broadcast(silent=True)

        if self.trade_proc and self.trade_proc.state() != QProcess.ProcessState.NotRunning:
            self.trade_proc.kill()
            self.trade_proc.waitForFinished(1000)

        self._save_window_geometry()

        # Detect if we have commandeered the Wi-Fi card by checking NetworkManager
        if not network_manager_active():
            # Silently force a restoration using the cached admin token from earlier
            subprocess.run(["sudo", "-n", "rfkill", "unblock", "wifi"])
            subprocess.run(["sudo", "-n", "systemctl", "start", "NetworkManager"])
            subprocess.run(["sudo", "-n", "chown", "-R", f"{USER_NAME}:{USER_NAME}", str(DATA_DIR)])

        event.accept()

    def build_trade_tab(self):
        self.trade_tab.setObjectName("TradeStageBackdrop")
        root = QVBoxLayout(self.trade_tab)
        root.setSpacing(0)
        root.setContentsMargins(10, 10, 10, 10)

        stage = QWidget()
        self.trade_stage = stage
        stage.setObjectName("TradeStage")
        stage.setStyleSheet("#TradeStage { background: transparent; }")
        stage.setMaximumWidth(1640)
        stage.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # The trade stage has a tall summary card plus the tunnel, mode row,
        # log and link cable.  At 150% on a short window those rows used to
        # fight for the same pixels and the losing row was clipped.  A scroll
        # area lets the stage keep its minimum height and scroll instead of
        # hiding any control, at every scale and window size.
        stage_scroll = TradeStageScroll(stage)
        stage_scroll.setObjectName("TradeStageScroll")
        stage_scroll.setWidgetResizable(True)
        stage_scroll.setFrameShape(QFrame.Shape.NoFrame)
        stage_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        stage_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        stage_scroll.setStyleSheet(
            "#TradeStageScroll { background: transparent; border: none; }"
            "#TradeStageScroll > QWidget > QWidget { background: transparent; }"
        )
        stage_body = QWidget()
        stage_body.setObjectName("TradeStageScrollBody")
        stage_body.setStyleSheet("#TradeStageScrollBody { background: transparent; }")
        stage_row = QHBoxLayout(stage_body)
        stage_row.setContentsMargins(0, 0, 0, 0)
        stage_row.addStretch(1)
        stage_row.addWidget(stage, 20)
        stage_row.addStretch(1)
        stage_scroll.setWidget(stage_body)
        root.addWidget(stage_scroll, 1)

        layout = QVBoxLayout(stage)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        screens_row = QHBoxLayout()
        screens_row.setSpacing(12)

        self.panel_pc = GBATradeCenterPanel("PC — SENDING TO SWITCH", is_pc_side=True)
        self.panel_switch = GBATradeCenterPanel("SWITCH — RECEIVED POKéMON", is_pc_side=False)

        # OUTGOING SIDE BUTTONS
        btn_open_pc = QPushButton("►  POKéMON STORAGE")
        btn_open_pc.setToolTip("Open Bill's PC to choose the Pokémon you send")
        btn_open_pc.clicked.connect(lambda: self.tabs.setCurrentWidget(self.pc_tab))

        btn_return_pc = QPushButton("►  RETURN TO PC")
        btn_return_pc.setToolTip("Cancel this trade and return the staged Pokémon to Bill's PC")
        btn_return_pc.clicked.connect(self.return_slot2_to_pc)

        self.panel_pc.btn_row.addWidget(btn_open_pc)
        self.panel_pc.btn_row.addWidget(btn_return_pc)

        # RECEIVED SIDE BUTTONS
        btn_send_pc = QPushButton("►  DEPOSIT IN PC")
        btn_send_pc.clicked.connect(self.move_received_to_pc)

        btn_edit_rec = QPushButton("►  EDIT")
        btn_edit_rec.clicked.connect(lambda: self.open_in_editor(self.received_path))

        btn_release_rec = QPushButton("►  RELEASE")
        btn_release_rec.setProperty("role", "danger")
        btn_release_rec.clicked.connect(self.release_received_pokemon)

        self.panel_switch.btn_row.addWidget(btn_send_pc)
        self.panel_switch.btn_row.addWidget(btn_edit_rec)
        self.panel_switch.btn_row.addWidget(btn_release_rec)

        # Keep the two link-room screens compact on tall monitors.  Without a
        # ceiling they stretch into several hundred pixels of empty panel and
        # push the useful log into a thin strip.
        for panel in (self.panel_pc, self.panel_switch):
            panel.setMaximumHeight(430)
            panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        screens_row.addWidget(self.panel_pc, stretch=1)
        screens_row.addWidget(self.panel_switch, stretch=1)
        layout.addLayout(screens_row)

        if self.slot2_path:
            self.panel_pc.load_pk3(self.slot2_path)
        else:
            self.panel_pc.set_waiting_state("SELECT A POKéMON FROM STORAGE")

        if self.received_path:
            self.panel_switch.load_pk3(self.received_path)
        else:
            self.panel_switch.set_waiting_state("WAITING FOR SWITCH TRADE")

        self.tunnel_widget = TradeTunnelWidget()
        layout.addWidget(self.tunnel_widget)

        # LIVE / REHEARSAL MODE.  Rehearsal replays a recorded host stream
        # through the real RX stack, so it needs no Switch, adapter or root.
        # The control lives in the bottom bar, between the Slot 1 lead and
        # JOURNAL.  Keeping it inside one fixed-width panel stops the combo
        # from re-centering when the record checkbox is hidden in rehearsal.
        self.trade_mode_panel = QWidget()
        self.trade_mode_panel.setObjectName("TradeModePanel")
        self.trade_mode_panel.setFixedWidth(440)
        mode_panel_layout = QHBoxLayout(self.trade_mode_panel)
        mode_panel_layout.setContentsMargins(0, 0, 0, 0)
        mode_panel_layout.setSpacing(7)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(7)
        self.trade_mode_lbl = QLabel("MODE")
        mode_row.addWidget(self.trade_mode_lbl)
        self.trade_mode_combo = theme.AppComboBox()
        self.trade_mode_combo.addItem("LIVE SWITCH", "live")
        self.trade_mode_combo.addItem("REHEARSAL (OFFLINE)", "rehearsal")
        self.trade_mode_combo.setFixedWidth(188)
        self.trade_mode_combo.setToolTip(
            "Live talks to a real Switch. Rehearsal replays a recorded capture "
            "through the same receive stack with no console or root."
        )
        self.trade_mode_combo.currentIndexChanged.connect(self._on_trade_mode_changed)
        mode_row.addWidget(self.trade_mode_combo)
        self.chk_record_capture = QCheckBox("RECORD LIVE RUN")
        self.chk_record_capture.setToolTip(
            "Save every Pia datagram of a live attempt so it can be replayed "
            "later without the Switch"
        )
        mode_row.addWidget(self.chk_record_capture)

        # Rehearsal swaps the record checkbox for its capture picker in the
        # same single row.  The panel width is fixed, so the mode combo stays
        # at the same x when the two states swap.
        self.btn_capture = QPushButton("CAPTURE…")
        self.btn_capture.setToolTip(
            "Choose a .jsonl capture recorded from a live attempt"
        )
        self.btn_capture.clicked.connect(self.choose_rehearsal_capture)
        mode_row.addWidget(self.btn_capture)

        self.lbl_capture = QLabel("No capture selected")
        self.lbl_capture.setFixedWidth(100)
        self.lbl_capture.setWordWrap(False)
        self.lbl_capture.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        mode_row.addWidget(self.lbl_capture)
        mode_row.addStretch(1)
        mode_panel_layout.addLayout(mode_row)

        self.trade_capture_path = str(app_prefs.get("rehearsal_capture", ""))
        self.chk_record_capture.setChecked(
            bool(app_prefs.get("record_capture", False))
        )
        saved_mode = str(app_prefs.get("rehearsal_mode", "live"))
        index = self.trade_mode_combo.findData(saved_mode)
        if index >= 0:
            self.trade_mode_combo.blockSignals(True)
            self.trade_mode_combo.setCurrentIndex(index)
            self.trade_mode_combo.blockSignals(False)
        self._update_capture_label()
        self._on_trade_mode_changed()

        # START / STOP LINK TRADE BUTTONS
        btn_row = QHBoxLayout()
        self.btn_start_trade = QPushButton("[ A ]   START LINK TRADE")
        self.btn_start_trade.setProperty("role", "primary")
        self.btn_start_trade.setStyleSheet("min-height: 42px; font-size: 15px;")
        self.btn_start_trade.clicked.connect(self.start_trade)

        self.btn_stop_trade = QPushButton("[ B ]   CANCEL / STOP")
        self.btn_stop_trade.setProperty("role", "danger")
        self.btn_stop_trade.setStyleSheet("min-height: 42px; font-size: 15px;")
        self.btn_stop_trade.setEnabled(False)
        self.btn_stop_trade.clicked.connect(self.stop_trade)

        btn_row.addWidget(self.btn_start_trade, stretch=2)
        btn_row.addWidget(self.btn_stop_trade, stretch=1)
        layout.addLayout(btn_row)

        # FRLG dialogue box for the link log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(60)
        self.log_output.setPlaceholderText(
            "LINK LOG  •  Connection and trade messages will appear here."
        )
        self.log_output.setMaximumHeight(420)
        self.log_output.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.log_output.setStyleSheet(
            "QTextEdit { background-color: %s; color: %s; border: 3px solid %s; "
            "border-radius: 9px; padding: 7px; font-family: '%s'; font-size: 14px; }"
            % (theme.FIELD, theme.INK, theme.NAVY, theme.FONT_GBA)
        )
        layout.addWidget(self.log_output, stretch=1)

        # LINK CABLE LEAD
        dummy_row = QHBoxLayout()
        self.trade_dummy_lbl = QLabel("LINK CABLE LEAD  (SLOT 1)")
        dummy_row.addWidget(self.trade_dummy_lbl)
        # The badge sizes itself from its sprite plate: at 150% that plate is
        # 56 px, so a fixed 56 px ceiling clipped the bottom of the icon.
        dummy_row.addWidget(self.dummy_badge)
        dummy_row.addStretch(1)
        dummy_row.addWidget(self.trade_mode_panel)
        dummy_row.addStretch(1)
        self.btn_journal = QPushButton("JOURNAL")
        self.btn_journal.setToolTip("Browse and export the trade journal")
        self.btn_journal.clicked.connect(self.open_journal)
        dummy_row.addWidget(self.btn_journal)
        layout.addLayout(dummy_row)

        self._on_trade_mode_changed()

    def _update_capture_label(self) -> None:
        path = Path(str(getattr(self, "trade_capture_path", "")))
        if path.is_file():
            label = path.name
            self.lbl_capture.setToolTip(str(path))
            color = theme.GREEN_DARK
        else:
            label = "No capture selected" if not path else "Capture missing"
            self.lbl_capture.setToolTip(
                str(path) if path else
                "Record a live attempt with RECORD LIVE RUN, or choose a .jsonl capture."
            )
            color = theme.INK_SOFT
        available = max(72, self.lbl_capture.width() - 4)
        self.lbl_capture.setText(
            self.lbl_capture.fontMetrics().elidedText(
                label, Qt.TextElideMode.ElideMiddle, available
            )
        )
        self.lbl_capture.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px;"
            % (color, theme.FONT_DS)
        )

    def _on_trade_mode_changed(self) -> None:
        mode = str(self.trade_mode_combo.currentData() or "live")
        rehearsal = mode == "rehearsal"
        self.btn_capture.setVisible(rehearsal)
        self.lbl_capture.setVisible(rehearsal)
        self.chk_record_capture.setVisible(not rehearsal)
        if hasattr(self, "btn_start_trade"):
            self.btn_start_trade.setText(
                "[ A ]   START REHEARSAL" if rehearsal else "[ A ]   START LINK TRADE"
            )
            self.btn_start_trade.setToolTip(
                "Replay the selected capture offline — no Switch, adapter or root"
                if rehearsal else "Join the Switch at the Direct Corner"
            )
        if rehearsal:
            self.lbl_capture.setStyleSheet(
                "color: %s; font-family: '%s'; font-size: 11px;"
                % (theme.ORANGE_DARK, theme.FONT_DS)
            )
        app_prefs.update(
            rehearsal_mode=mode,
            record_capture=self.chk_record_capture.isChecked(),
        )

    def choose_rehearsal_capture(self) -> None:
        start = paths.CAPTURES_DIR
        if not start.is_dir():
            start = DATA_DIR
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a recorded trade capture",
            str(start),
            "Capture (*.jsonl);;All files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        self.trade_capture_path = path
        app_prefs.update(rehearsal_capture=path)
        self._update_capture_label()

    def open_journal(self) -> None:
        from trade_journal_ui import TradeJournalDialog

        dialog = getattr(self, "_journal_dialog", None)
        if dialog is not None:
            try:
                opening = not dialog.isVisible()
                dialog.refresh()
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
                if opening:
                    sound.play("ui_open")
                return
            except RuntimeError:
                self._journal_dialog = None
        self._journal_dialog = TradeJournalDialog(self)
        self._journal_dialog.finished.connect(lambda _code: sound.play("ui_close"))
        self._journal_dialog.show()
        sound.play("ui_open")

    def return_slot2_to_pc(self):
        if not self.slot2_path or not Path(self.slot2_path).exists():
            return
        sound.play("ui_back")
        file_path = Path(self.slot2_path)
        self.pc_tab.store_pokemon(str(file_path), move_file=True)
        self.log_output.append(f'<span style="color: {theme.ORANGE_DARK};">[System] Cancelled Trade: {file_path.name} returned to Bill\'s PC.</span>')
        self.slot2_path = ""
        self.panel_pc.set_waiting_state("NO POKéMON STAGED")

    def release_received_pokemon(self):
        if not self.received_path or not Path(self.received_path).exists():
            return
        sound.play("ui_warning")
        reply = QMessageBox.question(
            self, "Confirm Release",
            "Are you sure you want to release this POKéMON?\n\nThis will permanently delete the file.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            user_data.snapshot("Release the received Pokémon")
            Path(self.received_path).unlink(missing_ok=True)
            self.received_path = ""
            self.panel_switch.header_plate.setText("SWITCH — WAITING FOR SELECTION")
            self.panel_switch.set_waiting_state("WAITING FOR SWITCH TRADE")
            self.log_output.append(f'<span style="color: {theme.RED_DARK};">[System] Received POKéMON was permanently released.</span>')
            sound.play("ui_confirm")

    def move_received_to_pc(self):
        if not self.received_path or not Path(self.received_path).exists():
            return
        file_path = Path(self.received_path)
        self.pc_tab.store_pokemon(str(file_path), move_file=True)
        self.log_output.append(f'<span style="color: {theme.ORANGE_DARK};">[System] {file_path.name} deposited to Bill\'s PC!</span>')
        sound.play("ui_confirm")
        self.received_path = ""
        self.panel_switch.header_plate.setText("SWITCH — WAITING FOR SELECTION")
        self.panel_switch.set_waiting_state("WAITING FOR SWITCH TRADE")

    def open_in_editor(self, filepath: str):
        p = filepath.strip()
        if p and Path(p).exists():
            self.editor_tab.load_file(p)
            self.tabs.setCurrentWidget(self.editor_tab)
        else:
            sound.play("ui_error")
            QMessageBox.warning(self, "No POKéMON", "Select a valid .pk3 POKéMON first.")

    def _poll_incoming_switch_pokemon(self):
        if not self.trade_proc or self.trade_proc.state() == QProcess.ProcessState.NotRunning:
            return

        # SET_MONS_TO_TRADE carries the host's selection before the trade
        # animation.  Show it immediately; the committed file still replaces
        # this preview when the trade actually lands.
        preview = self.staging_preview_file
        if preview.exists():
            try:
                data = preview.read_bytes()
                if len(data) >= 80:
                    key = bytes(data[:100])
                    if key != self._live_offer_key:
                        if self._trade_mode == "live":
                            subprocess.run(
                                ["sudo", "-n", "chown",
                                 f"{USER_NAME}:{USER_NAME}", str(preview)]
                            )
                        self._live_offer_key = key
                        self._live_offer_shown = True
                        sound.play("link_incoming")
                        self.panel_switch.header_plate.setText(
                            "SWITCH — POKéMON SELECTED!"
                        )
                        self.panel_switch.load_pk3(str(preview))
            except (OSError, ValueError):
                pass

        if not self._live_incoming_shown and self.staging_out_file.exists():
            try:
                if self.staging_out_file.stat().st_size >= 80:
                    subprocess.run(["sudo", "-n", "chown", f"{USER_NAME}:{USER_NAME}", str(self.staging_out_file)])

                    # --- AUTHENTIC TRADE FIX ---
                    if hasattr(self, '_traded_away_file') and self._traded_away_file.exists():
                        try:
                            user_data.snapshot("Trade consumed the offered Pokémon")
                            self._traded_away_file.unlink()
                        except Exception:
                            pass

                        self.slot2_path = ""
                        self.panel_pc.set_waiting_state("POKéMON SENT...")

                    self._live_incoming_shown = True
                    sound.play("link_incoming")
                    self.panel_switch.header_plate.setText("SWITCH — INCOMING SELECTION!")
                    self.tunnel_widget.begin_arrival()
                    self.panel_switch.load_pk3(str(self.staging_out_file))
            except Exception:
                pass

    def start_trade(self):
        if self.trade_proc and self.trade_proc.state() != QProcess.ProcessState.NotRunning:
            self._trade_stopped_by_user = True
            self.trade_proc.kill()
            self.trade_proc.waitForFinished()

        p1 = self.dummy_badge.filepath.strip()
        p2 = self.slot2_path.strip()
        if not p1 or not Path(p1).exists():
            sound.play("ui_error")
            QMessageBox.warning(self, "Missing Slot 1 Dummy", "Click 'Swap' on the top-bar Dummy widget to pick a Slot 1 .pk3.")
            return
        if not p2 or not Path(p2).exists():
            sound.play("ui_error")
            QMessageBox.warning(self, "Missing POKéMON", "Please send a POKéMON from Bill's PC to Trade Slot 2 first.")
            return

        mode = str(self.trade_mode_combo.currentData() or "live")
        capture = Path(str(self.trade_capture_path))
        if mode == "rehearsal":
            if not capture.is_file():
                sound.play("ui_error")
                QMessageBox.warning(
                    self,
                    "No Rehearsal Capture",
                    "Choose a .jsonl capture first. You can record one during a "
                    "live attempt with RECORD LIVE RUN.",
                )
                return
            self.phy_lbl.setText("(offline)")
        else:
            if not acquire_admin():
                sound.play("ui_error")
                self.log_output.append("\n[System] Authentication failed. Cannot start trade server.")
                return
            if network_manager_active():
                self.log_output.append("[System] Wireless adapter is on normal Wi-Fi. Automatically attaching...")
                self.enable_trade_wifi()

        if self.staging_out_file.exists():
            self.staging_out_file.unlink()
        if self.staging_preview_file.exists():
            try:
                self.staging_preview_file.unlink()
            except OSError:
                # A previous live run may have left a root-owned preview.
                if mode == "live":
                    subprocess.run(
                        ["sudo", "-n", "rm", "-f", str(self.staging_preview_file)]
                    )
        self._live_incoming_shown = False
        self._live_offer_shown = False
        self._live_offer_key = b""

        self.panel_switch.header_plate.setText("SWITCH — WAITING FOR SELECTION")
        self.panel_switch.set_waiting_state(
            "REPLAYING CAPTURE..." if mode == "rehearsal" else "WAITING FOR SWITCH..."
        )

        version = self.version_combo.currentText()
        self._trade_mode = mode
        self._recorded_capture = ""
        self._trade_log_start = len(self.log_output.toPlainText())

        if mode == "rehearsal":
            self.tunnel_widget.set_state(
                "SCANNING", f"REHEARSAL — REPLAYING {capture.name.upper()} THROUGH THE RX STACK..."
            )
            command, command_args = self._build_trade_args(
                "rehearsal", p1, p2, capture=str(capture)
            )
        else:
            phy = detect_wiphy()
            self.phy_lbl.setText(f"({phy})")
            self.tunnel_widget.set_state(
                "SCANNING",
                f"SCANNING FOR SWITCH WIRELESS ADAPTER BEACON ON {phy.upper()}...",
            )
            if self.chk_record_capture.isChecked():
                capture_dir = paths.CAPTURES_DIR
                capture_dir.mkdir(parents=True, exist_ok=True)
                self._recorded_capture = str(
                    capture_dir / f"capture-{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
                )
                self.log_output.append(
                    f"[System] Recording every Pia datagram to {Path(self._recorded_capture).name}"
                )
            command, command_args = self._build_trade_args(
                "live", p1, p2, phy=phy, record_path=self._recorded_capture
            )

        self.log_output.append(
            f"\n>>> Launching frlgtrade.py ({'rehearsal' if mode == 'rehearsal' else 'live'})..."
        )
        self._sound_link_state = ""
        self._trade_sequence_started = False
        self._trade_stopped_by_user = False
        self._traded_away_file = Path(p2)
        self.sound.set_music_context("trade")
        sound.play("trade_start")

        self._journal_session = None
        try:
            self._journal_session = trade_journal.TradeSession(
                mode, version, p2, p1
            )
        except Exception:
            self._journal_session = None

        self.trade_proc = QProcess(self)
        self.trade_proc.setWorkingDirectory(str(DATA_DIR))
        self.trade_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.trade_proc.readyReadStandardOutput.connect(self.read_trade_output)
        self.trade_proc.finished.connect(self.on_trade_finished)
        self.trade_proc.start(command, command_args)
        self.btn_stop_trade.setEnabled(True)
        self.btn_start_trade.setEnabled(False)

    def _build_trade_args(
        self,
        mode: str,
        p1: str,
        p2: str,
        *,
        phy: str = "",
        capture: str = "",
        record_path: str = "",
    ) -> tuple[str, list[str]]:
        """Build the exact command for live or offline replay.

        Kept separate from start_trade so the argument surface can be tested
        without a wireless card or a Switch.
        """
        if getattr(sys, "frozen", False):
            # The packaged executable dispatches to frlgtrade.main before any
            # Qt import.  No source file or venv exists inside the AppImage.
            py_bin = sys.executable
            launcher = ["--trade-cli"]
        else:
            py_bin = str(BASE_DIR / "venv" / "bin" / "python")
            launcher = ["-u", str(BASE_DIR / "frlgtrade.py")]
        version = self.version_combo.currentText()
        if mode == "rehearsal":
            return py_bin, launcher + [
                "--replay", capture,
                "--version", version, "--verbose", "--ot", "FRLGSwT",
                "--preview-out", str(self.staging_preview_file),
                "-o", str(self.staging_out_file), p1, p2,
            ]
        args = launcher + [
            "--live", "--phy", phy,
            "--version", version, "--verbose", "--keys", str(self.keys_path),
            "--ot", "FRLGSwT",
            "--preview-out", str(self.staging_preview_file),
            "-o", str(self.staging_out_file), p1, p2,
        ]
        if record_path:
            args.extend(["--capture", record_path])
        return "sudo", [py_bin] + args

    def read_trade_output(self):
        if self.trade_proc:
            text = bytes(self.trade_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.log_output.insertPlainText(text)
            self.log_output.ensureCursorVisible()
            low = text.lower()
            if "beacon decoded" in low or "saw network" in low:
                if self._sound_link_state != "connected":
                    self._sound_link_state = "connected"
                    sound.play("link_connected")
                self.tunnel_widget.set_state("LINKED", "LINK ESTABLISHED — SELECT POKéMON IN TRADE CENTER!")
                self.panel_switch.set_waiting_state("CONNECTED! SELECT ON SWITCH...")
            elif "retrying ldn join" in low:
                self.tunnel_widget.set_state("SCANNING", "RETRYING HANDSHAKE WITH SWITCH...")
            # The simulator reports the console's START_TRADE animation and
            # its READY_FINISH confirmation.  Use those real events to drive
            # the tunnel instead of a free-running loop; the received .pk3 is
            # still the authority for the final arrival pass.
            if (
                "trade animation started" in low
                and not getattr(self, "_trade_sequence_started", False)
            ):
                self._trade_sequence_started = True
                self.tunnel_widget.start_trade_sequence()
                self.panel_switch.set_waiting_state("TRADE IN PROGRESS ON SWITCH...")
            if "confirming trade" in low:
                self.tunnel_widget.set_finalizing()

    def stop_trade(self):
        self._trade_stopped_by_user = True
        self.sound.set_music_context("menu")
        sound.play("trade_cancel")
        if self.trade_proc and self.trade_proc.state() != QProcess.ProcessState.NotRunning:
            self.trade_proc.terminate()
            self.log_output.append("\n[System] Trade process stopped.")
        self.tunnel_widget.set_state("IDLE", "TRADE STOPPED — LINK STANDBY")
        self._trade_sequence_started = False
        if self.received_path and Path(self.received_path).exists():
            self.panel_switch.header_plate.setText("SWITCH — LAST RECEIVED")
            self.panel_switch.load_pk3(self.received_path)

    def on_trade_finished(self, exit_code=0, _exit_status=None):
        self.btn_stop_trade.setEnabled(False)
        self.btn_start_trade.setEnabled(True)
        mode = str(getattr(self, "_trade_mode", "live"))
        if mode == "live":
            subprocess.run(["sudo", "-n", "chown", "-R", f"{USER_NAME}:{USER_NAME}", str(DATA_DIR)])

        final_path = None
        success = False
        if exit_code == 0 and self.staging_out_file.exists():
            final_path = finalize_received_pk3(self.staging_out_file)
            if final_path:
                success = True
                if self.slot2_path and Path(self.slot2_path).exists():
                    user_data.snapshot("Trade completed")
                    Path(self.slot2_path).unlink(missing_ok=True)
                self.slot2_path = ""
                self.panel_pc.set_waiting_state("TRADE COMPLETED")

                if not getattr(self, "_live_incoming_shown", False):
                    # A fast rehearsal can finish before the 250 ms poll sees
                    # the staging file.  Still give the arrival pass a chance
                    # to land instead of jumping straight to the green check.
                    self._live_incoming_shown = True
                    self.tunnel_widget.begin_arrival()
                self.received_path = str(final_path)
                self.panel_switch.header_plate.setText(f"SWITCH — RECEIVED ({final_path.name})")
                self.panel_switch.load_pk3(self.received_path)
                self.log_output.append(f"\n[System] Trade complete! Saved to received/{final_path.name}")
                if self.tunnel_widget.state == "ARRIVAL":
                    QTimer.singleShot(760, lambda: self._show_tunnel_done(final_path.name))
                else:
                    self._show_tunnel_done(final_path.name)

        recorded = str(getattr(self, "_recorded_capture", ""))
        if recorded and Path(recorded).is_file() and Path(recorded).stat().st_size > 0:
            self.trade_capture_path = recorded
            app_prefs.update(rehearsal_capture=recorded)
            self._update_capture_label()
            self.log_output.append(
                f"[System] Capture saved: {Path(recorded).name}. "
                "Switch MODE to REHEARSAL to replay it without the Switch."
            )

        if not success:
            self.log_output.append("\n[System] Process exited & file permissions unlocked.")
            self.tunnel_widget.set_state("ERROR", "CONNECTION TIMED OUT — CLICK 'START LINK TRADE'")

        session = getattr(self, "_journal_session", None)
        if session is not None:
            try:
                log_text = self.log_output.toPlainText()
                start = int(getattr(self, "_trade_log_start", 0))
                session.finish(
                    str(final_path) if success and final_path else None,
                    success,
                    log_text[start:] if start <= len(log_text) else log_text,
                )
            except Exception:
                pass
            self._journal_session = None

        if success:
            sound.play("trade_complete")
        elif not getattr(self, "_trade_stopped_by_user", False):
            sound.play("trade_failed")
        self.sound.set_music_context("menu")

        if success and final_path is not None:
            if mode == "live":
                self._offer_to_learn_trainer(final_path)
            return

    def _show_tunnel_done(self, filename: str) -> None:
        """Set the final tunnel caption without interrupting an arrival pass."""
        if self.tunnel_widget.state != "ERROR":
            self.tunnel_widget.set_state("DONE", f"TRADE COMPLETE! SAVED: {filename}")

    def _offer_to_learn_trainer(self, pk3_path: Path):
        """Offer to lock a received Pokémon's OT/TID/SID as My Trainer.

        Only asked while no profile exists.  A Pokémon received through the
        trade was caught in the player's own game, so it is the one
        trustworthy source for the real TID/SID.  Declining is fine; the
        offer is repeated on the next received Pokémon.
        """
        if load_profile(DATA_DIR):
            return
        info = parse_pk3_file(str(pk3_path))
        if not info:
            return
        ot = str(info.get("ot_name") or "").strip()
        tid = int(info.get("tid") or 0)
        sid = int(info.get("sid") or 0)
        if not ot:
            return
        reply = QMessageBox.question(
            self,
            "Learn My Trainer?",
            f"A POKéMON was received from {ot} (TID {tid} / SID {sid}).\n\n"
            "Lock this in as My Trainer? New POKéMON you generate will use it, "
            "and POKéMON loaded from files keep their own OT/TID/SID.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.log_output.append(
                f'<span style="color: {theme.INK_SOFT};">[System] My Trainer not saved — will offer again on the next received POKéMON.</span>'
            )
            return
        saved = save_profile(DATA_DIR, ot, tid, sid, source=pk3_path.name)
        if not saved:
            return
        if hasattr(self, "editor_tab"):
            self.editor_tab.reload_trainer_profile()
        self.log_output.append(
            f'<span style="color: {theme.GREEN_DARK};">[System] My Trainer locked: {ot} (TID {tid} / SID {sid}).</span>'
        )

def main(argv: list[str] | None = None) -> int:
    """Build the Qt application and run it.

    Kept as a function so the frozen entry point can dispatch CLI modes
    before importing any of the Qt-heavy modules.
    """
    if argv is None:
        argv = sys.argv
    paths.ensure_layout()
    theme.apply_scale_environment()
    app = QApplication(argv)
    # Match the installed desktop entry so Wayland uses its icon and groups
    # the window under FRLG Studio instead of the Python interpreter.
    app.setDesktopFileName("frlg-studio")
    theme.init_app(app)

    # The title screen is the launch screen.  There is no interim splash:
    # building and painting the main window takes about a second, and the
    # menu backdrop already has something to look at on its first frame.
    win = FRLGTradeGUI()
    win.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
