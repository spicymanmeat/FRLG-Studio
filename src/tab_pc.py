import shutil
import struct
import json
import math
from pathlib import Path

from PyQt6.QtCore import (
    Qt, pyqtSignal, QSize, QRect, QRectF, QPoint, QPointF, QMimeData,
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtProperty, QTimer
)
from PyQt6.QtGui import (
    QPixmap, QMovie, QIcon, QPainter, QColor, QPen, QDrag, QFont,
    QFontMetrics, QKeySequence, QLinearGradient, QRegion, QShortcut,
    QCursor,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QComboBox, QMessageBox, QGroupBox, QSizePolicy,
    QToolTip,
)

import sound
import theme
import user_data
from ui_widgets import SpritePlate
from pixel_sprite import integer_device_scale, sprite_plate_extent
import paths
from utils import BASE_DIR
from core_data import NATURES, GEN3_ITEMS

from pkmds_editor import HOENN_INTERNAL_TO_NAT, GEN3_EN_TABLE
from sprite_paths import animated_sprite_path, icon_path as form_icon_path, unown_form_from_pid
from summary_sprites import SummaryIconSlot

PC_SELECTION_MIME = "application/x-frlg-studio-pc-selection"

BOX_THEMES = {
    "Forest": ("assets/wallpapers/forest.png", "#16a34a"),
    "City": ("assets/wallpapers/city.png", "#475569"),
    "Desert": ("assets/wallpapers/desert.png", "#d97706"),
    "Savanna": ("assets/wallpapers/savanna.png", "#65a30d"),
    "Crag": ("assets/wallpapers/crag.png", "#57534e"),
    "Volcano": ("assets/wallpapers/volcano.png", "#dc2626"),
    "Snow": ("assets/wallpapers/snow.png", "#38bdf8"),
    "Cave": ("assets/wallpapers/cave.png", "#3f3f46"),
    "Beach": ("assets/wallpapers/beach.png", "#3b82f6"),
    "Seafloor": ("assets/wallpapers/seafloor.png", "#1d4ed8"),
    "River": ("assets/wallpapers/river.png", "#2563eb"),
    "Sky": ("assets/wallpapers/sky.png", "#0284c7"),
    # FireRed/LeafGreen's Etcetera set.  Ruby/Sapphire use a different
    # four-wallpaper Etcetera group; these are the four FRLG designs.
    "Stars": ("assets/wallpapers/stars.png", "#a35fbf"),
    "PokéCenter": ("assets/wallpapers/pokecenter.png", "#4f9f8f"),
    "Tiles": ("assets/wallpapers/tiles.png", "#b9823e"),
    "Simple": ("assets/wallpapers/simple.png", "#8fa7c7")
}

TYPE_COLORS = {
    "NORMAL": "#A8A878", "FIRE": "#F08030", "WATER": "#6890F0",
    "ELECTRIC": "#F8D030", "GRASS": "#78C850", "ICE": "#98D8D8",
    "FIGHTING": "#C03028", "POISON": "#A040A0", "GROUND": "#E0C068",
    "FLYING": "#A890F0", "PSYCHIC": "#F85888", "BUG": "#A8B820",
    "ROCK": "#B8A038", "GHOST": "#705898", "DRAGON": "#7038F8",
    "DARK": "#705848", "STEEL": "#B8B8D0", "???": "#68A090"
}

GEN3_MOVE_BASE_PP = (
    0, 35, 25, 10, 15, 20, 20, 15, 15, 15, 35, 30, 5, 10, 30, 30, 35, 35, 20, 15, 20,
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

SUBSTRUCT_ORDER = [
    (0,1,2,3), (0,1,3,2), (0,2,1,3), (0,3,1,2), (0,2,3,1), (0,3,2,1),
    (1,0,2,3), (1,0,3,2), (2,0,1,3), (3,0,1,2), (2,0,3,1), (3,0,2,1),
    (1,2,0,3), (1,3,0,2), (2,1,0,3), (3,1,0,2), (2,3,0,1), (3,2,0,1),
    (1,2,3,0), (1,3,2,0), (2,1,3,0), (3,1,2,0), (2,3,1,0), (3,2,1,0)
]

def calc_max_pp(move_id: int, pp_ups: int) -> int:
    if move_id <= 0 or move_id >= len(GEN3_MOVE_BASE_PP): return 0
    base = GEN3_MOVE_BASE_PP[move_id]
    if base == 1: return 1
    return base + (base * max(0, min(3, pp_ups))) // 5

def decode_gen3_str(raw: bytes) -> str:
    out = []
    for b in raw:
        if b == 0xFF: break
        ch = GEN3_EN_TABLE[b] if 0 <= b < 256 else None
        if ch is not None:
            out.append(ch)
    return "".join(out).strip() or "PKMN"

def read_pk3_data(raw_data: bytes) -> dict:
    if len(raw_data) < 80: return {}

    pid, otid = struct.unpack("<II", raw_data[0:8])
    tid = otid & 0xFFFF
    sid = (otid >> 16) & 0xFFFF
    is_shiny = ((tid ^ sid ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8)

    nick = decode_gen3_str(raw_data[0x08:0x12])
    ot = decode_gen3_str(raw_data[0x14:0x1B])

    chk = struct.unpack("<H", raw_data[0x1C:0x1E])[0]
    sub_raw = raw_data[0x20:0x50]
    raw_sum = sum(struct.unpack("<24H", sub_raw)) & 0xFFFF
    order = SUBSTRUCT_ORDER[pid % 24]

    if raw_sum == chk:
        dec = sub_raw
        sp0, it0, _ = struct.unpack("<HHI", dec[0:8])
        orig3 = struct.unpack("<H", dec[36 + 2 : 36 + 4])[0]
        unshuf_ok = (1 <= sp0 <= 411) and (it0 <= 376) and (1 <= ((orig3 >> 11) & 0xF) <= 12)
        was_shuffled = not unshuf_ok
    else:
        key = pid ^ otid
        words = struct.unpack("<12I", sub_raw)
        dec = b"".join(struct.pack("<I", w ^ key) for w in words)
        sp_test = struct.unpack("<H", dec[order[0]*12 : order[0]*12 + 2])[0]
        was_shuffled = (1 <= sp_test <= 411)

    g_i, a_i, e_i, m_i = order if was_shuffled else (0, 1, 2, 3)
    block_g = dec[g_i*12 : (g_i+1)*12]
    block_a = dec[a_i*12 : (a_i+1)*12]
    block_e = dec[e_i*12 : (e_i+1)*12]
    block_m = dec[m_i*12 : (m_i+1)*12]

    internal_sp, item_id, exp, pp_bonuses, friend = struct.unpack("<HHIBB", block_g[0:10])
    nat_dex = internal_sp if 1 <= internal_sp <= 251 else HOENN_INTERNAL_TO_NAT.get(internal_sp, 1)

    m1, m2, m3, m4, pp1, pp2, pp3, pp4 = struct.unpack("<HHHHBBBB", block_a)
    ev_hp, ev_atk, ev_def, ev_spe, ev_spa, ev_spd = struct.unpack("<6B", block_e[0:6])

    _, _, origins, iv_word = struct.unpack("<BBHI", block_m[0:8])

    iv_hp = iv_word & 31
    iv_atk = (iv_word >> 5) & 31
    iv_def = (iv_word >> 10) & 31
    iv_spe = (iv_word >> 15) & 31
    iv_spa = (iv_word >> 20) & 31
    iv_spd = (iv_word >> 25) & 31

    lvl = raw_data[0x54] if len(raw_data) >= 85 and 1 <= raw_data[0x54] <= 100 else 5

    return {
        "pid": pid,
        "species": nat_dex,
        "nickname": nick,
        "ot": ot,
        "tid": tid,
        "sid": sid,
        "level": lvl,
        "is_shiny": is_shiny,
        "nature": pid % 25,
        "item": item_id,
        "ball": (origins >> 11) & 0xF,
        "moves": [m1, m2, m3, m4],
        "pp": [pp1, pp2, pp3, pp4],
        "pp_ups": [(pp_bonuses) & 3, (pp_bonuses >> 2) & 3, (pp_bonuses >> 4) & 3, (pp_bonuses >> 6) & 3],
        "ivs": (iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe),
        "evs": (ev_hp, ev_atk, ev_def, ev_spa, ev_spd, ev_spe)
    }

class BannerLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_pixmap = QPixmap()

    def set_background(self, image_path: str):
        self.bg_pixmap = QPixmap(image_path)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        # A sliver of the box wallpaper peeks out behind the name plate.
        if not self.bg_pixmap.isNull():
            source_rect = QRect(0, 0, self.bg_pixmap.width(), 24)
            raw_banner = self.bg_pixmap.copy(source_rect)
            scaled = raw_banner.scaled(
                max(1, int(w * 0.72)), max(1, int(h * 0.72)),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            painter.setOpacity(0.55)
            painter.drawPixmap((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
            painter.setOpacity(1.0)

        plate = QRectF(w * 0.12, 3, w * 0.76, h - 7)
        painter.setPen(Qt.PenStyle.NoPen)
        shadow = QColor(theme.SHADOW)
        shadow.setAlpha(60)
        painter.setBrush(shadow)
        painter.drawRoundedRect(plate.translated(0, 3), 9, 9)
        painter.setPen(QPen(QColor(theme.GOLD), 2))
        painter.setBrush(QColor(theme.BANNER_BG))
        painter.drawRoundedRect(plate, 9, 9)
        plate_line = QColor(theme.PANEL)
        plate_line.setAlpha(100)
        painter.setPen(QPen(plate_line, 1))
        painter.drawRoundedRect(plate.adjusted(3, 3, -3, -3), 7, 7)

        theme.draw_pokeball(painter, plate.left() + 24, plate.center().y(), 8, outline_width=1.4)
        theme.draw_pokeball(
            painter, plate.right() - 24, plate.center().y(), 8,
            top=theme.BLUE, outline_width=1.4,
        )
        size = 20
        while size > 13 and QFontMetrics(theme.ui_font(size, gba=True, bold=True)).horizontalAdvance(self.text()) > plate.width() - 62:
            size -= 1
        painter.setFont(theme.ui_font(size, gba=True, bold=True))
        painter.setPen(QColor(theme.BANNER_TEXT))
        painter.drawText(plate, Qt.AlignmentFlag.AlignCenter, self.text())


class WallpaperFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bg_pixmap = QPixmap()
        self.border_color = "#16a34a"
        self._flash = 0.0
        self._flash_anim = None
        self._pending_wallpaper = None

    def set_background(self, image_path: str, border_color: str):
        if self._flash_anim is not None:
            self._flash_anim.stop()
        self._flash = 0.0
        self._pending_wallpaper = None
        self.bg_pixmap = QPixmap(image_path)
        self.border_color = border_color
        self.update()

    def transition_to(self, image_path: str, border_color: str):
        """Change wallpaper with FRLG's white palette flash.

        The game fades the wallpaper palettes to white, loads the new
        tilemap at full white, then fades the new palette back in
        [pokemon_storage_system_graphics.c: DoWallpaperGfxChange].  Keep that
        order: old wallpaper -> white -> new wallpaper -> normal.
        """
        if self._flash_anim is not None:
            self._flash_anim.stop()
        self._pending_wallpaper = (image_path, border_color)
        anim = QPropertyAnimation(self, b"flash", self)
        anim.setDuration(270)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        anim.finished.connect(self._show_pending_wallpaper)
        self._flash_anim = anim
        anim.start()

    def _show_pending_wallpaper(self):
        if self._pending_wallpaper is not None:
            image_path, border_color = self._pending_wallpaper
            self._pending_wallpaper = None
            self.bg_pixmap = QPixmap(image_path)
            self.border_color = border_color
            self.update()
        anim = QPropertyAnimation(self, b"flash", self)
        anim.setDuration(280)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._flash_anim = anim
        anim.start()

    def _get_flash(self) -> float:
        return self._flash

    def _set_flash(self, value: float) -> None:
        self._flash = max(0.0, min(1.0, float(value)))
        self.update()

    flash = pyqtProperty(float, fget=_get_flash, fset=_set_flash)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.bg_pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            crop_y = 27
            source_rect = QRect(0, crop_y, self.bg_pixmap.width(), self.bg_pixmap.height() - crop_y)
            cropped_pixmap = self.bg_pixmap.copy(source_rect)
            scaled_bg = cropped_pixmap.scaled(
                self.rect().width(),
                self.rect().height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            painter.drawPixmap(self.rect().topLeft(), scaled_bg)

        # The box is framed like a storage screen: outer case, cream gasket,
        # theme accent and the selected wallpaper rim.  The extra accent line
        # is what lets Sinnoh's periwinkle/cyan and Hoenn's blue/gold casing
        # read without replacing the player's chosen wallpaper.
        painter.setPen(QPen(QColor(getattr(theme, "BOX_FRAME", theme.NAVY_DARK)), 5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 9, 9)
        painter.setPen(QPen(QColor(theme.PANEL), 2))
        painter.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), 7, 7)
        painter.setPen(QPen(
            QColor(getattr(theme, "BOX_FRAME_INNER", theme.NAVY)), 2
        ))
        painter.drawRoundedRect(self.rect().adjusted(6, 6, -6, -6), 7, 7)
        painter.setPen(QPen(QColor(self.border_color), 2))
        painter.drawRoundedRect(self.rect().adjusted(8, 8, -8, -8), 6, 6)

        if self._flash > 0.0:
            # Palette fade in the ROM affects the wallpaper, not the frame or
            # the Pokémon buttons.  Paint the wash inside the rim so the case
            # stays put and the sprites remain readable.
            wash = QColor(248, 248, 248)
            wash.setAlpha(max(0, min(255, int(round(255 * self._flash)))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(wash)
            painter.drawRoundedRect(self.rect().adjusted(9, 9, -9, -9), 6, 6)
        painter.end()


def _move_row_style(type_color: str | None) -> str:
    color = type_color or theme.BORDER_SOFT
    return (
        "QFrame { background-color: %s; border: 2px solid %s;"
        " border-left: 7px solid %s; border-radius: %spx; }"
        % (theme.PANEL, color, color, theme.CONTROL_RADIUS)
    )


def _readable_type_ink(color: str) -> str:
    """Pick dark or light badge text from the type colour's luminance."""
    c = QColor(color)
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return "#1f2328" if lum > 145 else "#ffffff"


def _type_badge_style(color: str) -> str:
    return (
        "background-color: %s; color: %s; border-radius: 4px;"
        " font-family: '%s'; font-size: 12px; border: 1px solid rgba(0,0,0,0.22);"
        % (color, _readable_type_ink(color), theme.FONT_DS)
    )


# ==============================================================================
# GBA STORAGE CURSOR
# ==============================================================================
class BoxHandCursor(QWidget):
    """The floating white glove from the GBA storage UI.

    It lives on the box frame rather than inside a slot so it can overlap the
    selected cell exactly like the in-game cursor does.  Mouse input is passed
    through to the slot beneath it.
    """

    BASE_W = float(theme.HAND_CURSOR_W)
    BASE_H = float(theme.HAND_CURSOR_H)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._scale = 1.0
        self._multi = False
        self._pixmap = QPixmap()
        self.hide()

    def set_multi(self, multi: bool) -> None:
        """Switch the glove to the green multi-select palette."""
        multi = bool(multi)
        if multi == self._multi:
            return
        self._multi = multi
        self.set_scale(self._scale)

    def set_scale(self, scale: float) -> None:
        # Render the glove once at an exact device-pixel multiplier.  A 1.5
        # logical hand would otherwise resample every glove pixel; 2x device
        # blocks keep it as crisp as the box icons beside it.
        dpr = max(0.1, float(self.devicePixelRatioF()))
        logical_scale = max(1.0, float(scale))
        device_scale = max(1, int(round(logical_scale * dpr)))
        pm = QPixmap(
            int(round(self.BASE_W * device_scale)),
            int(round(self.BASE_H * device_scale)),
        )
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        theme.draw_hand_cursor(
            painter, 0, 0, scale=device_scale, multi=self._multi
        )
        painter.end()
        pm.setDevicePixelRatio(dpr)
        self._pixmap = pm
        self._scale = device_scale / dpr
        self.setFixedSize(
            int(round(pm.width() / dpr)),
            int(round(pm.height() / dpr)),
        )
        self.update()

    def paintEvent(self, _event):
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(0, 0, self._pixmap)


# ==============================================================================
# CUSTOM POKÉMON DRAG AND DROP / HOPPING BUTTON
# ==============================================================================
class BoxNavButton(QPushButton):
    """Box arrow that pages while a Pokémon is held over it.

    A native QDrag cannot continue after a drop, so the arrow does not accept
    the Pokémon as a destination.  It holds a short timer while the pointer is
    over it, asks the tab to slide one box, and then keeps the same drag alive
    so the player can drop into a chosen slot in the new box.
    """

    page_requested = pyqtSignal(int)
    HOVER_MS = 300

    def __init__(self, delta: int, text: str, parent=None):
        super().__init__(text, parent)
        self.delta = int(delta)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._paged = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.HOVER_MS)
        self._timer.timeout.connect(self._page)

    def dragEnterEvent(self, event):
        if not event.mimeData().hasText():
            event.ignore()
            return
        event.acceptProposedAction()
        if not self._paged:
            self._timer.start()
        self.setProperty("dropTarget", True)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._timer.stop()
        self._paged = False
        self.setProperty("dropTarget", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        # Only page.  The held Pokémon stays with the cursor; releasing over
        # the arrow returns it to its source instead of guessing a slot.
        self._timer.stop()
        self._paged = False
        self.setProperty("dropTarget", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.acceptProposedAction()

    def _page(self):
        if self._paged:
            return
        self._paged = True
        self.page_requested.emit(self.delta)


class PokemonSlotButton(QPushButton):
    swap_requested = pyqtSignal(int, int, float, float) # src, dest, offset_x, offset_y
    selection_drop_requested = pyqtSignal(object, int, float, float)
    cancel_drop_requested = pyqtSignal(int, float, float)
    selection_changed = pyqtSignal(int)
    drag_state_changed = pyqtSignal(int, bool)
    drag_entered = pyqtSignal()
    lift_changed = pyqtSignal()

    LIFT = 6.0

    def __init__(self, slot_idx, parent=None):
        super().__init__(parent)
        self.slot_idx = slot_idx
        self.setAcceptDrops(True)
        # Expanding makes the entire box a seamless hit-target
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: transparent; border: none;")

        self._is_selected = False
        self._lift = 0.0
        self._lift_anim = None
        self.is_drag_hover = False
        self.is_dragging = False
        self.is_animating = False

        self.filepath = ""
        self.nat_dex = 0
        self.normal_pixmap = None
        self.legality_state = None
        self.legality_messages = ()
        # Set by the PC tab so a drag can carry the whole selection and use
        # the green multi-select glove without the slot needing a tab ref.
        self.drag_context_provider = None
        self.hand_multi = False
        self.source_box = 0
        # Set by the PC tab to one common multiplier for the whole 6x5
        # grid.  Without this, a cell that is one pixel wider can cross the
        # integer-scale threshold and render a small Pokémon larger than a
        # big one in the neighbouring cell.
        self.shared_icon_factor = None
        self._scaled_cache = {}
        self._outlined_cache = {}
        self._visible_cache = {}

    def _get_lift(self) -> float:
        return self._lift

    def _set_lift(self, value: float) -> None:
        self._lift = float(value)
        self.update()
        self.lift_changed.emit()

    lift = pyqtProperty(float, fget=_get_lift, fset=_set_lift)

    def set_legality(self, valid: bool | None, messages=()) -> None:
        state = None if valid is None else ("legal" if valid else "illegal")
        if state == self.legality_state and tuple(messages) == self.legality_messages:
            return
        self.legality_state = state
        self.legality_messages = tuple(messages)
        if state == "illegal":
            self.setToolTip("PKHeX: illegal\n" + "\n".join(self.legality_messages[:6]))
        elif state == "legal":
            self.setToolTip("PKHeX: legal")
        else:
            self.setToolTip("")
        self.update()

    def reset_selection(self) -> None:
        """Clear selection and lift without animating.

        The 30 slot widgets are reused for every box.  If a box switch only
        flipped `_is_selected` to False, the old box's selected widget would
        animate the new box's Pokémon down from an inherited -6 px lift.  A
        load must start from a clean physical state, not the previous box's.
        """
        if self._lift_anim is not None:
            self._lift_anim.stop()
            self._lift_anim = None
        self._is_selected = False
        self._lift = 0.0
        # A swap animation belongs to the box that started it.  When the grid
        # is reused for another box, its flag must not hide the new Pokémon at
        # the same slot indices.
        self.is_animating = False
        self.is_drag_hover = False
        self.update()

    def set_selected(self, selected: bool):
        if selected == self._is_selected:
            return
        self._is_selected = selected
        target = -self.LIFT if selected else 0.0
        if self._lift_anim is not None:
            self._lift_anim.stop()
        # A quiet 90 ms hop, like the game lifting the icon under the glove.
        anim = QPropertyAnimation(self, b"lift", self)
        anim.setDuration(90)
        anim.setStartValue(self._lift)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()
        self._lift_anim = anim
        self.update()

    @staticmethod
    def _pixmap_dpr(pix: QPixmap | None) -> float:
        try:
            dpr = float(pix.devicePixelRatio()) if pix is not None else 1.0
        except (AttributeError, RuntimeError):
            dpr = 1.0
        return dpr if dpr > 0 else 1.0

    def _pixmap_logical_size(self, pix: QPixmap) -> tuple[float, float]:
        dpr = self._pixmap_dpr(pix)
        return pix.width() / dpr, pix.height() / dpr

    def _display_pixmap(self) -> QPixmap | None:
        base = self.normal_pixmap
        if not base or base.isNull():
            return None
        # Box sprites are 40x30 native icons.  The multiplier is stored in
        # *device* pixels, not logical pixels: at 150% a two-pixel source
        # block becomes 3x3 device pixels, and tagging the result with the
        # real DPR prevents Qt from stretching the finished icon again.
        dpr = max(0.1, float(self.devicePixelRatioF()))
        avail_phys_w = max(1, int(math.floor(max(1, self.width() - 26) * dpr)))
        avail_phys_h = max(1, int(math.floor(max(1, self.height() - 24) * dpr)))
        # Every icon canvas is 40x30, but the artwork inside is normalised.
        # A Rattata's 20x21 body and a Venusaur's 30x24 body must therefore
        # share one multiplier and rely on the art itself for the size
        # hierarchy.  The PC tab supplies that common multiplier for all 30
        # cells so a one-pixel layout difference cannot scale one species
        # more than its neighbour.
        factor = self.shared_icon_factor
        if factor is None:
            factor = integer_device_scale(dpr)
        # A form icon may be larger than the nominal 40x30 canvas; never let
        # that source overflow its cell.
        factor = max(1, min(int(factor), avail_phys_w // max(1, base.width()),
                            avail_phys_h // max(1, base.height())))
        cache_key = (factor, round(dpr, 4))
        cached = self._scaled_cache.get(cache_key)
        if cached is not None:
            return cached
        scaled = base.scaled(
            base.width() * factor, base.height() * factor,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        self._scaled_cache[cache_key] = scaled
        self._outlined_cache.clear()
        return scaled

    def _visible_sprite_rect(self) -> QRectF:
        """Bounds of the actual artwork inside the icon's transparent padding.

        Returned in logical widget coordinates so the hand/cursor maths is
        independent of the device multiplier.
        """
        pix = self._display_pixmap()
        if pix is None or pix.isNull():
            return QRectF()
        dpr = self._pixmap_dpr(pix)
        key = (pix.cacheKey(), pix.width(), pix.height(), round(dpr, 4))
        cached = self._visible_cache.get(key)
        if cached is not None:
            return cached
        rect = QRegion(pix.mask()).boundingRect()
        if rect.isNull():
            rect = pix.rect()
        result = QRectF(
            rect.x() / dpr, rect.y() / dpr,
            rect.width() / dpr, rect.height() / dpr,
        )
        self._visible_cache[key] = result
        return result

    def _white_silhouette(self, pix: QPixmap) -> QPixmap:
        """The same sprite filled with white, used for the thin GBA rim."""
        dpr = self._pixmap_dpr(pix)
        key = ("silhouette", pix.width(), pix.height(), round(dpr, 4))
        cached = self._outlined_cache.get(key)
        if cached is not None:
            return cached
        source_image = pix.toImage()
        source_image.setDevicePixelRatio(1.0)
        white = QPixmap(source_image.size())
        white.fill(Qt.GlobalColor.transparent)
        painter = QPainter(white)
        painter.drawImage(0, 0, source_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(white.rect(), QColor("#ffffff"))
        painter.end()
        white.setDevicePixelRatio(dpr)
        self._outlined_cache[key] = white
        return white

    def _selected_pixmap(self) -> QPixmap | None:
        """Sprite with the game's 1-2 px white selection rim baked in."""
        pix = self._display_pixmap()
        if pix is None or pix.isNull():
            return None
        dpr = self._pixmap_dpr(pix)
        # Keep the rim visually thin at every scale: one source-pixel of rim
        # at 100%, a proportional whole number of device pixels otherwise.
        base_rim = 1 if min(pix.width(), pix.height()) < 100 else 2
        rim = max(1, int(round(base_rim * dpr)))
        key = ("selected", pix.width(), pix.height(), rim, round(dpr, 4))
        cached = self._outlined_cache.get(key)
        if cached is not None:
            return cached

        white = self._white_silhouette(pix)
        canvas = QPixmap(pix.width() + rim * 2, pix.height() + rim * 2)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        white_image = white.toImage()
        white_image.setDevicePixelRatio(1.0)
        source_image = pix.toImage()
        source_image.setDevicePixelRatio(1.0)
        for dx in range(-rim, rim + 1):
            for dy in range(-rim, rim + 1):
                if dx or dy:
                    painter.drawImage(rim + dx, rim + dy, white_image)
        painter.drawImage(rim, rim, source_image)
        painter.end()
        canvas.setDevicePixelRatio(dpr)
        self._outlined_cache[key] = canvas
        return canvas

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        pix = self._display_pixmap()

        # Draw the sprite with the same thin 1-2 px white rim the games use
        # for the picked-up Pokémon, lifted six pixels under the glove.
        if pix and not pix.isNull() and not self.is_dragging and not self.is_animating:
            dpr = self._pixmap_dpr(pix)
            # Keep the white rim through the whole reverse hop.  Switching to
            # the plain sprite as soon as selection clears made the icon lose
            # its outline at the top of the descent, which read as a pop even
            # though the position was animating.
            if self._is_selected or self._lift < -0.05:
                drawn = self._selected_pixmap()
                if drawn is not None and not drawn.isNull():
                    # Align the blit to a whole device pixel.  The image is
                    # already source*k physical pixels with a DPR tag; any
                    # logical rounding would risk Qt resampling one edge.
                    x_phys = round((self.width() * dpr - drawn.width()) / 2.0)
                    y_phys = round((self.height() * dpr - drawn.height()) / 2.0)
                    painter.drawPixmap(
                        QPointF(x_phys / dpr, y_phys / dpr + self._lift), drawn
                    )
            else:
                x_phys = round((self.width() * dpr - pix.width()) / 2.0)
                y_phys = round((self.height() * dpr - pix.height()) / 2.0)
                # Keep the reverse hop: the lift animation runs after the
                # selection is cleared, so the normal sprite must also honour
                # whatever lift remains.  Without the + self._lift the sprite
                # snapped to its resting position on deselect.
                painter.drawPixmap(
                    QPointF(x_phys / dpr, y_phys / dpr + self._lift), pix
                )

        if self.legality_state == "illegal" and not self.is_animating:
            size = 10.0
            x = self.width() - size - 5.0
            y = 5.0
            painter.setPen(QPen(QColor(theme.PANEL), 1.5))
            painter.setBrush(QColor(theme.RED))
            painter.drawEllipse(QRectF(x, y, size, size))
            painter.setPen(QColor(theme.PANEL))
            font = QFont(theme.FONT_GBA)
            font.setPixelSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "!"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Selection happens on release (QPushButton.clicked).  Selecting
            # on press would toggle a slot out of a multi-selection just
            # before QDrag starts, so the group would lose the Pokémon under
            # the pointer.  Box icons deliberately do not play a cry; only
            # the summary portraits do.
            if self.filepath:
                self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def _hand_metrics(self, sprite_h: float):
        """Same integer glove scale the floating storage cursor uses.

        The GBA draws the 20 px glove next to 32 px box icons, so the glove
        stays just over half the icon height at every window size.  Scaling it
        with the grid keeps that ratio on 1080p, 1440p and 4K instead of
        leaving a tiny cursor beside huge 4K sprites.
        """
        hand_h = max(30.0, sprite_h * 0.56)
        scale = max(1, int(round(hand_h / float(theme.HAND_CURSOR_H))))
        return (
            theme.HAND_CURSOR_W * scale,
            theme.HAND_CURSOR_H * scale,
            scale,
        )

    def drag_pixmap(self):
        """Full-size Pokémon plus the glove, exactly as it looks in the box.

        The dragged image must not shrink to the icon file's native size:
        it is the same scaled sprite that sits in the grid, with the storage
        glove holding it from the upper-left like the GBA games.  The canvas
        is composed in device pixels and tagged once, so the sprite keeps its
        exact source blocks while it is under the pointer.
        """
        sprite = self._display_pixmap()
        if sprite is None or sprite.isNull():
            return None, QPoint(0, 0)

        dpr = self._pixmap_dpr(sprite)
        sw_phys, sh_phys = sprite.width(), sprite.height()
        sw, sh = sw_phys / dpr, sh_phys / dpr
        _hw, _hh, hand_scale = self._hand_metrics(sh)
        hscale = max(1, int(round(hand_scale * dpr)))
        hw = theme.HAND_CURSOR_W * hscale
        hh = theme.HAND_CURSOR_H * hscale

        # Glove fingertip on the visible artwork's upper-left, matching
        # BillsPCTab._position_hand_cursor().  Icon PNGs carry transparent
        # padding, so anchoring to the image would leave the hand floating.
        vis = self._visible_sprite_rect()
        vis_x = vis.left() * dpr
        vis_y = vis.top() * dpr
        vis_w = vis.width() * dpr
        vis_h = vis.height() * dpr
        tip_x = vis_x + vis_w * 0.18
        tip_y = vis_y + vis_h * 0.12
        hx = int(round(tip_x - 0.5 * hscale))
        hy = int(round(tip_y - (theme.HAND_CURSOR_H - 0.5) * hscale))

        pad = max(2, int(round(2 * dpr)))
        left = min(0, hx) - pad
        top = min(0, hy) - pad
        right = max(sw_phys, hx + hw) + pad
        bottom = max(sh_phys, hy + hh) + pad

        canvas = QPixmap(right - left, bottom - top)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        sprite_image = sprite.toImage()
        sprite_image.setDevicePixelRatio(1.0)
        painter.drawImage(
            QRect(-left, -top, sw_phys, sh_phys), sprite_image,
            QRect(0, 0, sw_phys, sh_phys),
        )
        painter.translate(hx - left, hy - top)
        theme.draw_hand_cursor(
            painter, 0, 0, scale=hscale, multi=self.hand_multi
        )
        painter.end()
        canvas.setDevicePixelRatio(dpr)

        # Keep the Pokémon under the pointer where the user grabbed it.
        sprite_x = (self.width() - sw) / 2.0
        sprite_y = (self.height() - sh) / 2.0
        grab_x = max(0.0, min(sw, self.drag_start_pos.x() - sprite_x)) * dpr
        grab_y = max(0.0, min(sh, self.drag_start_pos.y() - sprite_y)) * dpr
        hotspot = QPoint(
            int(round((grab_x - left) / dpr)),
            int(round((grab_y - top) / dpr)),
        )
        return canvas, hotspot

    def mouseMoveEvent(self, event):
        if not self.filepath or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < 5:
            return

        payload = {
            "source_box": int(self.source_box),
            "anchor": int(self.slot_idx),
            "slots": [int(self.slot_idx)],
        }
        pixmap = None
        hotspot = QPoint(0, 0)
        provider = self.drag_context_provider
        if callable(provider):
            supplied = provider(self.slot_idx)
            if supplied is not None:
                candidate, candidate_pixmap, candidate_hotspot = supplied
                if isinstance(candidate, dict):
                    payload = candidate
                if candidate_pixmap is not None and not candidate_pixmap.isNull():
                    pixmap = candidate_pixmap
                    hotspot = candidate_hotspot
        if pixmap is None or pixmap.isNull():
            pixmap, hotspot = self.drag_pixmap()

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(
            PC_SELECTION_MIME,
            json.dumps(payload).encode("utf-8"),
        )
        # Keep the plain-text fallback for any older drop target in a mixed
        # build; the PC tab reads the structured payload first.
        mime.setText(str(self.slot_idx))
        drag.setMimeData(mime)

        if pixmap is not None and not pixmap.isNull():
            drag.setPixmap(pixmap)
            drag.setHotSpot(hotspot)

        self.is_dragging = True
        self.update()
        self.drag_state_changed.emit(self.slot_idx, True)

        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.is_dragging = False
            self.update()
            self.drag_state_changed.emit(self.slot_idx, False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.is_drag_hover = True
            self.update()
            # A drop target must match what is on screen.  If a box slide is
            # still running, snap it to the loaded box before the pointer can
            # choose a slot in the half-visible old snapshot.
            self.drag_entered.emit()

    def dragLeaveEvent(self, event):
        self.is_drag_hover = False
        self.update()

    @staticmethod
    def _drop_payload(mime: QMimeData) -> dict | None:
        raw = bytes(mime.data(PC_SELECTION_MIME))
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        slots = payload.get("slots")
        if not isinstance(slots, list):
            return None
        cleaned = []
        for value in slots:
            try:
                index = int(value)
            except (TypeError, ValueError):
                return None
            if not 0 <= index < 30 or index in cleaned:
                return None
            cleaned.append(index)
        if not cleaned:
            return None
        try:
            anchor = int(payload.get("anchor", cleaned[0]))
        except (TypeError, ValueError):
            anchor = cleaned[0]
        if anchor not in cleaned:
            anchor = cleaned[0]
        try:
            source_box = int(payload.get("source_box", 0))
        except (TypeError, ValueError):
            source_box = 0
        return {
            "source_box": source_box,
            "anchor": anchor,
            "slots": cleaned,
        }

    def dropEvent(self, event):
        self.is_drag_hover = False
        self.update()

        drop_pos = event.position()
        center_pos = QPointF(self.width() / 2.0, self.height() / 2.0)
        offset = drop_pos - center_pos
        payload = self._drop_payload(event.mimeData())
        if payload is None:
            # Text-only fallback for a payload from an older widget.
            try:
                src_idx = int(event.mimeData().text())
            except (TypeError, ValueError):
                event.ignore()
                return
            payload = {
                "source_box": int(self.source_box),
                "anchor": src_idx,
                "slots": [src_idx],
            }

        # A same-index drop is still a swap gesture (or a cross-box move),
        # not a cancellation.  Let the PC tab decide using the source box.
        self.selection_drop_requested.emit(
            payload, self.slot_idx, offset.x(), offset.y()
        )

        event.acceptProposedAction()


# ==============================================================================
# BILL'S PC TAB
# ==============================================================================
class BillsPCTab(QWidget):
    send_to_editor = pyqtSignal(str)
    send_to_slot2 = pyqtSignal(str)

    def __init__(self, editor_tab_ref):
        super().__init__()
        self.editor_tab = editor_tab_ref
        self.pc_dir = paths.PC_DIR
        self.pc_dir.mkdir(parents=True, exist_ok=True)

        self._current_movie = None # Garbage collection protection for QMovie

        self.current_box_index = 1
        self.selected_slot_idx = -1
        self.selected_slots = set()
        self.multi_mode = False
        self.selected_pk3_path = None
        self._cry_dex = 0
        self.box_slots = []
        self._shared_icon_factor = None
        self.move_widgets = []
        # Suppresses the resting glove while an icon is being dragged.  The
        # selection lift keeps emitting lift_changed during that drag, which
        # would otherwise re-show the floating hand on top of the drag image.
        self._drag_in_progress = False
        # A drop that lands back on the pressed icon still emits clicked in
        # Qt.  Swallow that one synthetic click so a same-slot drop does not
        # deselect the Pokémon or replay a placement cue after the swap.
        self._suppress_next_slot_click = False
        self._drag_source_box = None
        self._drag_source_slot = None
        self._drag_source_slots = []
        self._legality_cache = {}
        self._audit_dialog = None

        self.current_box_layout = {}

        (self.pc_dir / "Box1").mkdir(exist_ok=True)
        self._build_ui()
        self.refresh_boxes()

    def get_move_type(self, move_id: int) -> str:
        if move_id == 0: return "NORMAL"
        data_file = BASE_DIR / "assets" / "data" / "move_types.json"
        if data_file.exists():
            try:
                types = json.loads(data_file.read_text())
                return types.get(str(move_id), "NORMAL")
            except: pass
        return "NORMAL"

    def _build_ui(self):
        self.setObjectName("BillsPC")
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        self.left_panel = QFrame()
        self.left_panel.setMinimumWidth(350)
        self.left_panel.setMaximumWidth(448)
        self.left_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        theme.soft_shadow(self.left_panel, blur=18, dy=3, alpha=40)
        left_layout = QVBoxLayout(self.left_panel)
        # The summary column must fit the 1180x820 minimum window without
        # scrollbars or a clipped corner, so its rows are sized from the
        # loaded font metrics rather than a generous fixed layout.
        left_layout.setContentsMargins(12, 9, 12, 11)
        left_layout.setSpacing(6)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.summary_plate = QLabel("POKéMON SUMMARY")
        self.summary_plate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_plate.setFixedHeight(30)
        left_layout.addWidget(self.summary_plate)

        self.lbl_name_lvl = QLabel("NO POKÉMON SELECTED")
        self.lbl_name_lvl.setWordWrap(True)
        self.lbl_name_lvl.setMinimumHeight(26)
        left_layout.addWidget(self.lbl_name_lvl)

        self.lbl_sprite = SpritePlate()
        sprite_extent = sprite_plate_extent(112)
        self.lbl_sprite.set_plate_base(sprite_extent)
        self.lbl_sprite.setFixedSize(sprite_extent, sprite_extent)
        self.lbl_sprite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sprite.set_clickable(True)
        self.lbl_sprite.setToolTip("Click to hear this Pokémon's cry")
        self.lbl_sprite.clicked.connect(self._play_selected_cry)
        self._cry_dex = 0

        self.summary_ball_badge = SummaryIconSlot(self)
        # The held-item badge is half the ball's size and sits directly beside
        # it.  Both share the portrait row, so neither adds a vertical row.
        self.summary_item_badge = SummaryIconSlot(self, base=22, reserve=True)

        # The ball belongs beside the portrait, not in a row of its own.  It
        # shares the portrait's height, so showing or hiding it can never
        # move the summary card or squeeze the details below it.
        sprite_row = QHBoxLayout()
        sprite_row.setSpacing(3)
        sprite_row.addWidget(self.lbl_sprite)
        sprite_row.addWidget(
            self.summary_ball_badge, 0, Qt.AlignmentFlag.AlignBottom
        )
        sprite_row.addWidget(
            self.summary_item_badge, 0, Qt.AlignmentFlag.AlignBottom
        )
        sprite_row.addStretch()
        left_layout.addLayout(sprite_row)

        # Separate, generously spaced rows instead of one cramped rich-text
        # block.  At a glance these are the values players actually read.
        details_box = QFrame()
        details_box.setObjectName("PCDetails")
        details_layout = QHBoxLayout(details_box)
        details_layout.setContentsMargins(0, 2, 4, 1)
        details_layout.setSpacing(6)
        details_text = QVBoxLayout()
        details_text.setContentsMargins(0, 0, 0, 0)
        details_text.setSpacing(1)

        self.detail_ot = QLabel("OT: —")
        self.detail_nature = QLabel("Nature: —")
        self.detail_item = QLabel("Item: —")
        self.detail_ivs = QLabel("IVs: —")
        self.detail_evs = QLabel("EVs: —")
        self.detail_labels = (
            self.detail_ot, self.detail_nature, self.detail_item,
            self.detail_ivs, self.detail_evs,
        )
        for lbl in self.detail_labels:
            lbl.setWordWrap(False)
            lbl.setMinimumHeight(20)
            lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Nature and held item share one line: the summary column has to fit
        # the 820 px minimum window, and both values are short in Gen 3.
        nature_item_row = QHBoxLayout()
        nature_item_row.setContentsMargins(0, 0, 0, 0)
        nature_item_row.setSpacing(10)
        nature_item_row.addWidget(self.detail_nature)
        nature_item_row.addWidget(self.detail_item, stretch=1)
        details_text.addWidget(self.detail_ot)
        details_text.addLayout(nature_item_row)
        details_text.addWidget(self.detail_ivs)
        details_text.addWidget(self.detail_evs)
        details_layout.addLayout(details_text, 1)
        left_layout.addWidget(details_box)

        moves_group = QFrame()
        moves_group.setObjectName("PCMoveGroup")
        moves_layout = QVBoxLayout(moves_group)
        moves_layout.setContentsMargins(0, 0, 0, 0)
        moves_layout.setSpacing(4)

        for i in range(4):
            mf = QFrame()
            mf.setFixedHeight(42)
            mf.setStyleSheet(_move_row_style(None))
            mfl = QHBoxLayout(mf)
            mfl.setContentsMargins(8, 2, 8, 2)
            mfl.setSpacing(6)

            lbl_type = QLabel("---")
            lbl_type.setFixedSize(68, 22)
            lbl_type.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_type.setStyleSheet(_type_badge_style(theme.BORDER_SOFT))

            lbl_name = QLabel("— None —")
            lbl_name.setMinimumWidth(0)
            lbl_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

            lbl_pp = QLabel("PP --/--")

            mfl.addWidget(lbl_name, stretch=1)
            mfl.addWidget(lbl_type)
            mfl.addWidget(lbl_pp)

            self.move_widgets.append({'frame': mf, 'type': lbl_type, 'name': lbl_name, 'pp': lbl_pp})
            moves_layout.addWidget(mf)

        left_layout.addWidget(moves_group)

        self.lbl_flavor = QLabel("")
        self.lbl_flavor.setWordWrap(True)
        self.lbl_flavor.setMinimumHeight(52)
        self.lbl_flavor.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        left_layout.addWidget(self.lbl_flavor)
        self.lbl_flavor.hide()

        left_layout.addStretch()

        action_group = QGroupBox("POKéMON MANAGEMENT")
        self.pc_action_group = action_group
        # 34 px leaves the 15 px gold plate inside the group's own rect; a
        # smaller margin clips its top edge even when the layout has room.
        action_group.setStyleSheet(
            "QGroupBox { margin-top: 34px; padding-top: 5px; }"
            "QGroupBox::title { font-size: 15px; padding: 5px 11px; }"
            "QPushButton { padding: 4px 9px; min-height: 20px; }"
        )
        # Fixed height keeps a short window from crushing the two action rows
        # into the group title, which is what clipped it before.
        action_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        action_layout = QVBoxLayout(action_group)
        action_layout.setContentsMargins(8, 9, 8, 8)
        action_layout.setSpacing(5)

        transfer_row = QHBoxLayout()
        self.combo_target_box = theme.AppComboBox()
        self._update_box_dropdown()
        transfer_row.addWidget(self.combo_target_box, stretch=2)

        self.btn_move_box = QPushButton("MOVE")
        self.btn_move_box.setProperty("role", "accent")
        self.btn_move_box.setToolTip("Move the selected Pokémon to the chosen box")
        self.btn_move_box.clicked.connect(self.move_selected_pokemon)
        transfer_row.addWidget(self.btn_move_box, stretch=1)
        action_layout.addLayout(transfer_row)

        edit_release_row = QHBoxLayout()
        edit_release_row.setSpacing(6)

        self.btn_trade = QPushButton("TRADE")
        self.btn_trade.setProperty("role", "primary")
        self.btn_trade.setToolTip("Send the selected Pokémon to Trade Slot 2")
        self.btn_trade.clicked.connect(self.send_to_trade_slot)

        self.btn_edit = QPushButton("EDIT")
        self.btn_edit.setProperty("role", "blue")
        self.btn_edit.setToolTip("Open the selected Pokémon in the editor")
        self.btn_edit.clicked.connect(self._send_to_editor)

        self.btn_release = QPushButton("RELEASE")
        self.btn_release.setProperty("role", "danger")
        self.btn_release.setToolTip("Permanently release the selected Pokémon")
        self.btn_release.clicked.connect(self.release_pokemon)

        edit_release_row.addWidget(self.btn_trade)
        edit_release_row.addWidget(self.btn_edit)
        edit_release_row.addWidget(self.btn_release)
        action_layout.addLayout(edit_release_row)

        left_layout.addWidget(action_group)
        main_layout.addWidget(self.left_panel)
        self._current_move_types = [None, None, None, None]

        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(7)
        self.btn_prev = BoxNavButton(-1, "◀")
        self.btn_prev.setFixedSize(46, 36)
        self.btn_prev.setToolTip(
            "Previous box (hold a dragged Pokémon here to page back)"
        )
        self.btn_prev.clicked.connect(lambda: self.change_box(-1))
        self.btn_prev.page_requested.connect(self._auto_page_during_drag)

        self.lbl_box_name = BannerLabel("BOX 1")
        self.lbl_box_name.setFixedHeight(50)
        self.lbl_box_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_box_name.setStyleSheet("background: transparent; border: none;")

        self.btn_next = BoxNavButton(1, "▶")
        self.btn_next.setFixedSize(46, 36)
        self.btn_next.setToolTip(
            "Next box (hold a dragged Pokémon here to page forward)"
        )
        self.btn_next.clicked.connect(lambda: self.change_box(1))
        self.btn_next.page_requested.connect(self._auto_page_during_drag)

        self.btn_audit = QPushButton("AUDIT")
        self.btn_audit.setToolTip("Check every Pokémon in this box with PKHeX")
        self.btn_audit.clicked.connect(self.audit_current_box)

        self.btn_undo = QPushButton("UNDO")
        self.btn_undo.setToolTip(
            "Undo the last recorded change to the Pokémon data (Alt+Z)"
        )
        self.btn_undo.clicked.connect(self._undo_last_change)

        self.btn_multi = QPushButton("MULTI")
        self.btn_multi.setCheckable(True)
        self.btn_multi.setToolTip(
            "Multi-select (M) — click Pokémon to add or remove them, "
            "then drag any selected Pokémon to move the group"
        )
        self.btn_multi.setAccessibleName("Multi-select")
        self.btn_multi.toggled.connect(self.set_multi_mode)

        self.btn_new_box = QPushButton("+  NEW BOX")
        self.btn_new_box.setProperty("role", "accent")
        self.btn_new_box.setToolTip("Create the next empty box")
        self.btn_new_box.clicked.connect(self.create_new_box)

        self.combo_theme = theme.AppComboBox()
        for theme_name in BOX_THEMES.keys():
            self.combo_theme.addItem(theme_name)
        self.combo_theme.setFixedWidth(126)
        self.combo_theme.setToolTip("Change this box's wallpaper")
        self.combo_theme.currentIndexChanged.connect(
            lambda _index: self.apply_box_theme(animate=True)
        )
        self.combo_theme.activated.connect(
            lambda _index: sound.play("menu_select")
        )

        nav_row.addWidget(self.btn_prev)
        nav_row.addWidget(self.lbl_box_name, stretch=1)
        nav_row.addWidget(self.btn_next)
        nav_row.addWidget(self.btn_audit)
        nav_row.addWidget(self.btn_undo)
        nav_row.addWidget(self.btn_multi)
        nav_row.addWidget(self.btn_new_box)
        nav_row.addWidget(self.combo_theme)
        right_panel.addLayout(nav_row)

        self.grid_frame = WallpaperFrame()
        self.grid_frame.setObjectName("grid_frame")
        grid_layout = QGridLayout(self.grid_frame)
        grid_layout.setSpacing(0)
        grid_layout.setContentsMargins(14, 14, 14, 14)

        for i in range(30):
            btn = PokemonSlotButton(slot_idx=i)
            # QPushButton emits clicked only after a real press/release, so a
            # drag can start from a selected slot without toggling it off in
            # the multi-selection first.
            btn.clicked.connect(
                lambda _checked=False, index=i: self.on_slot_clicked(index)
            )
            btn.selection_drop_requested.connect(self._on_selection_drop)
            btn.cancel_drop_requested.connect(self.cancel_drop)
            btn.drag_state_changed.connect(self._on_slot_drag_state)
            btn.drag_entered.connect(self._on_slot_drag_enter)
            btn.lift_changed.connect(self._position_hand_cursor)
            btn.drag_context_provider = self._drag_context_for
            self.box_slots.append(btn)
            grid_layout.addWidget(btn, i // 6, i % 6)

        # A floating cursor, not a bordered selection plate.  It is positioned
        # over the chosen slot by _position_hand_cursor().
        self.hand_cursor = BoxHandCursor(self.grid_frame)

        # The games toggle multi-move with Select; the desktop equivalent is
        # M while Bill's PC has focus, plus the visible MULTI button.
        self._multi_shortcut = QShortcut(QKeySequence("M"), self)
        self._multi_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._multi_shortcut.activated.connect(self.btn_multi.toggle)

        right_panel.addWidget(self.grid_frame, stretch=1)
        main_layout.addLayout(right_panel, stretch=1)
        self.apply_theme()

    def _update_box_dropdown(self):
        # Preserve the selected box by its data value, not its display text:
        # the text includes the live "(n/30)" count and changes as files move.
        current_selection = self.combo_target_box.currentData()
        self.combo_target_box.blockSignals(True)
        self.combo_target_box.clear()

        boxes = sorted([d for d in self.pc_dir.iterdir() if d.is_dir() and d.name.startswith("Box")],
                       key=lambda x: int(x.name.replace("Box", "")) if x.name.replace("Box", "").isdigit() else 999)

        for b in boxes:
            count = len(list(b.glob("*.pk3")))
            self.combo_target_box.addItem(f"{b.name} ({count}/30)", b.name)

        idx = self.combo_target_box.findData(current_selection)
        if idx >= 0:
            self.combo_target_box.setCurrentIndex(idx)

        self.combo_target_box.blockSignals(False)

    # ------------------------------------------------------------------
    # Multi-selection
    # ------------------------------------------------------------------
    def _active_selection(self) -> set[int]:
        """Slots that should currently carry the white selection rim."""
        if self.multi_mode:
            return {
                index for index in self.selected_slots
                if 0 <= index < len(self.box_slots)
                and self.box_slots[index].filepath
            }
        index = self.selected_slot_idx
        if 0 <= index < len(self.box_slots) and self.box_slots[index].filepath:
            return {index}
        return set()

    def _update_multi_button(self) -> None:
        button = getattr(self, "btn_multi", None)
        if button is None:
            return
        count = len(self.selected_slots) if self.multi_mode else 0
        button.setText("MULTI" if count <= 0 else f"MULTI {count}")

    def set_multi_mode(self, enabled: bool) -> None:
        """Toggle grouped storage movement, like the games' Select button."""
        enabled = bool(enabled)
        if enabled == self.multi_mode:
            self._update_multi_button()
            return
        self.multi_mode = enabled
        if self.btn_multi.isChecked() != enabled:
            self.btn_multi.blockSignals(True)
            self.btn_multi.setChecked(enabled)
            self.btn_multi.blockSignals(False)

        if enabled:
            if 0 <= self.selected_slot_idx < len(self.box_slots):
                self.selected_slots = {self.selected_slot_idx}
            else:
                self.selected_slots.clear()
        else:
            keep = self.selected_slot_idx
            if keep not in self.selected_slots and self.selected_slots:
                keep = min(self.selected_slots)
            self.selected_slots.clear()
            self.selected_slot_idx = keep if 0 <= keep < len(self.box_slots) else -1

        if hasattr(self, "hand_cursor"):
            self.hand_cursor.set_multi(enabled)
        for slot in self.box_slots:
            slot.hand_multi = enabled
        self._apply_selection_visuals()
        sound.play("menu_select")

    def _apply_selection_visuals(self) -> None:
        active = self._active_selection()
        for index, slot in enumerate(self.box_slots):
            slot.set_selected(index in active)
        self._position_hand_cursor()
        self._update_multi_button()
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        """Keep one-Pokémon actions off a multi-selection.

        Dragging is the group operation; EDIT / TRADE / RELEASE still describe
        a single Pokémon and would otherwise silently act on just the anchor.
        """
        group = self.multi_mode and len(self.selected_slots) > 1
        has_one = bool(self.selected_pk3_path)
        for button in (
            self.btn_move_box, self.btn_trade, self.btn_edit, self.btn_release
        ):
            button.setEnabled(has_one and not group)
        if group:
            hint = "Multiple Pokémon selected — drag the group to move it"
            self.btn_move_box.setToolTip(hint)
            self.btn_trade.setToolTip(hint)
            self.btn_edit.setToolTip(hint)
            self.btn_release.setToolTip(hint)
        else:
            self.btn_move_box.setToolTip(
                "Move the selected Pokémon to the chosen box"
            )
            self.btn_trade.setToolTip("Send the selected Pokémon to Trade Slot 2")
            self.btn_edit.setToolTip("Open the selected Pokémon in the editor")
            self.btn_release.setToolTip("Permanently release the selected Pokémon")

    def apply_box_theme(self, animate: bool = False):
        theme_name = self.combo_theme.currentText()
        bg_file, border_color = BOX_THEMES.get(theme_name, BOX_THEMES["Forest"])

        target_box = self.pc_dir / f"Box{self.current_box_index}"
        if target_box.exists():
            (target_box / "theme.txt").write_text(theme_name)

        bg_path = (BASE_DIR / bg_file).as_posix()
        if animate:
            self.grid_frame.transition_to(bg_path, border_color)
        else:
            self.grid_frame.set_background(bg_path, border_color)
        self.lbl_box_name.set_background(bg_path)

    def apply_theme(self):
        """Apply the active app palette to Bill's PC without touching its data."""
        self.setStyleSheet(
            "#BillsPC { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 %s, stop:1 %s); }" % (theme.APP_BG_TOP, theme.APP_BG_BOTTOM)
        )
        self.left_panel.setStyleSheet(
            "QFrame { background-color: %s; border: 2px solid %s;"
            " border-radius: %spx; }"
            % (theme.PANEL, theme.NAVY, theme.PANEL_RADIUS)
        )
        self.summary_plate.setStyleSheet(
            "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 %s, stop:0.55 %s, stop:1 %s);"
            " color: %s; border: 2px solid %s; border-radius: %spx;"
            " font-family: '%s'; font-size: 15px; padding: 2px;"
            % (theme.HEADER_LIGHT, theme.HEADER, theme.HEADER_DARK,
               theme.ON_HEADER, theme.GOLD, theme.CONTROL_RADIUS, theme.FONT_GBA)
        )
        self.lbl_name_lvl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 18px;"
            " border: none; background: transparent;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.lbl_sprite.setStyleSheet(
            "background: transparent; border: none; color: %s;"
            " font-family: '%s'; font-size: 12px;" % (theme.INK_SOFT, theme.FONT_GBA)
        )
        for lbl in self.detail_labels:
            lbl.setStyleSheet(
                "color: %s; font-family: '%s'; font-size: 17px; border: none;"
                " background: transparent;" % (theme.INK, theme.FONT_DS)
            )
        for i, mw in enumerate(self.move_widgets):
            mw['frame'].setStyleSheet(_move_row_style(self._current_move_types[i]))
            mw['type'].setStyleSheet(_type_badge_style(
                self._current_move_types[i] or theme.BORDER_SOFT
            ))
            mw['name'].setStyleSheet(
                "font-family: '%s'; font-size: 15px; color: %s;"
                " border: none; background: transparent;" % (theme.FONT_DS, theme.INK)
            )
            mw['pp'].setStyleSheet(
                "font-family: '%s'; font-size: 14px; color: %s;"
                " border: none; background: transparent;" % (theme.FONT_DS, theme.INK_SOFT)
            )
        self.lbl_flavor.setStyleSheet(
            "background-color: %s; border: 2px solid %s;"
            " border-radius: %spx; padding: 8px; color: %s;"
            " font-family: '%s'; font-size: 16px; margin-top: 2px;"
            % (theme.PANEL_ALT, theme.BORDER_SOFT, theme.CONTROL_RADIUS,
               theme.INK, theme.FONT_DS)
        )
        self.combo_target_box.setStyleSheet("")
        self.btn_multi.setStyleSheet(
            "QPushButton:checked { background-color: %s; color: %s;"
            " border: 2px solid %s; }"
            "QPushButton:checked:hover { background-color: %s; }"
            % (theme.GREEN_DARK, theme.ON_HEADER, theme.GREEN, theme.GREEN)
        )
        for btn in (self.btn_prev, self.btn_next):
            btn.setStyleSheet(
                "font-family: '%s'; font-size: 16px; padding: 0;" % theme.FONT_GBA
            )
        self.lbl_box_name.update()
        self.grid_frame.update()
        if hasattr(self, "hand_cursor"):
            self.hand_cursor.update()
        for slot in self.box_slots:
            slot.update()

    def get_max_box_num(self):
        boxes = [d for d in self.pc_dir.iterdir() if d.is_dir() and d.name.startswith("Box")]
        if not boxes: return 1
        nums = [int(b.name.replace("Box", "")) for b in boxes if b.name.replace("Box", "").isdigit()]
        return max(nums) if nums else 1

    def create_new_box(self):
        next_num = self.get_max_box_num() + 1
        self._snapshot(f"Create Box{next_num}")
        (self.pc_dir / f"Box{next_num}").mkdir(exist_ok=True)
        self._update_box_dropdown()
        self.change_box(next_num - self.current_box_index)

    def refresh_boxes(self):
        # Any programmatic refresh supersedes a box-slide snapshot.  Leaving a
        # stale snapshot over the grid is what made a dropped Pokémon appear
        # missing until the 250 ms animation ended.
        self._cancel_box_slide()
        self._update_box_dropdown()
        self.load_box(self.current_box_index)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Slot geometry changes after the grid layout settles.
        QTimer.singleShot(0, self._sync_grid_metrics)

    def _sync_grid_metrics(self) -> None:
        self._update_shared_icon_factor()
        self._position_hand_cursor()

    def _update_shared_icon_factor(self) -> None:
        """Use one whole-device-pixel icon scale for every cell in the grid.

        Qt can hand neighbouring cells a width or height that differs by a
        pixel.  Deriving the integer scale per button made a small species in
        a wider cell jump to the next scale while a large species in a
        narrower cell stayed put, which visually inverted their sizes.  The
        minimum usable cell defines a safe factor that fits all 30 slots.
        """
        if not self.box_slots:
            return
        widths = [b.width() for b in self.box_slots]
        heights = [b.height() for b in self.box_slots]
        if min(widths) < 40 or min(heights) < 30:
            return
        dpr = max(0.1, float(self.devicePixelRatioF()))
        avail_w = max(1, min(widths) - 26)
        avail_h = max(1, min(heights) - 24)
        avail_phys_w = max(1, int(math.floor(avail_w * dpr)))
        avail_phys_h = max(1, int(math.floor(avail_h * dpr)))
        # Five whole source pixels per cell is already a 200x150 icon.  A
        # maximized 4K grid can ask for seven or more, which turns 40x30 box
        # icons into billboards and exaggerates the compact species.
        logical_factor = max(1, min(5, avail_w // 40, avail_h // 30))
        factor = max(1, int(math.floor(logical_factor * dpr + 0.5)))
        factor = min(
            factor,
            max(1, int(math.floor(5.0 * dpr))),
            max(1, avail_phys_w // 40),
            max(1, avail_phys_h // 30),
        )
        if factor == self._shared_icon_factor and all(
            b.shared_icon_factor == factor for b in self.box_slots
        ) and abs(getattr(self, "_shared_icon_dpr", 0.0) - dpr) < 1e-4:
            return
        self._shared_icon_factor = factor
        self._shared_icon_dpr = dpr
        for btn in self.box_slots:
            btn.shared_icon_factor = factor
            btn._scaled_cache.clear()
            btn._outlined_cache.clear()
            btn.update()

    def _on_slot_drag_enter(self) -> None:
        """Make the grid under a held Pokémon a stable, fully visible target."""
        if self._drag_in_progress:
            self._cancel_box_slide()

    def _drag_slots_for(self, slot_idx: int) -> list[int]:
        """Source slots represented by a drag that starts on ``slot_idx``."""
        if not self.multi_mode:
            return [int(slot_idx)]
        slots = set(self.selected_slots)
        if 0 <= slot_idx < len(self.box_slots) and self.box_slots[slot_idx].filepath:
            slots.add(int(slot_idx))
        slots = {
            index for index in slots
            if 0 <= index < len(self.box_slots) and self.box_slots[index].filepath
        }
        return sorted(slots) or [int(slot_idx)]

    def _drag_context_for(self, slot_idx: int):
        """Payload and optional group preview for a drag starting at a slot."""
        slots = self._drag_slots_for(slot_idx)
        payload = {
            "source_box": int(self.current_box_index),
            "anchor": int(slot_idx),
            "slots": slots,
        }
        if len(slots) <= 1:
            return payload, None, QPoint(0, 0)
        pixmap, hotspot = self._group_drag_pixmap(slot_idx, slots)
        return payload, pixmap, hotspot

    def _group_drag_pixmap(self, anchor: int, slots: list[int]):
        """Compose the selected block under one green glove.

        The preview keeps each Pokémon in its relative grid position, so a
        rectangular selection looks like the block the GBA would lift.  It is
        painted in device pixels and tagged once, just like the single-slot
        drag image, so source pixels are never resampled.
        """
        if not (0 <= anchor < len(self.box_slots)):
            return None, QPoint(0, 0)
        anchor_btn = self.box_slots[anchor]
        dpr = max(0.1, float(self.devicePixelRatioF()))
        entries = []
        for index in slots:
            if not 0 <= index < len(self.box_slots):
                continue
            btn = self.box_slots[index]
            sprite = btn._display_pixmap()
            if sprite is None or sprite.isNull():
                continue
            sw, sh = btn._pixmap_logical_size(sprite)
            cell = btn.geometry()
            x = cell.x() + (cell.width() - sw) / 2.0
            y = cell.y() + (cell.height() - sh) / 2.0 + btn._lift
            entries.append((index, sprite, x, y, sw, sh))
        if not entries:
            return None, QPoint(0, 0)

        anchor_sprite = anchor_btn._display_pixmap()
        if anchor_sprite is None or anchor_sprite.isNull():
            anchor_sprite = entries[0][1]
        anchor_h = anchor_btn._pixmap_logical_size(anchor_sprite)[1]
        hand_scale = max(1, int(round(max(30.0, anchor_h * 0.56) /
                                      float(theme.HAND_CURSOR_H))))
        hscale = max(1, int(round(hand_scale * dpr)))
        hw = theme.HAND_CURSOR_W * hscale
        hh = theme.HAND_CURSOR_H * hscale

        # Find the anchor by its slot index rather than object identity: a
        # stale entry list should never put the glove on a neighbouring mon.
        anchor_entry = next(
            (entry for entry in entries if entry[0] == anchor), entries[0]
        )
        _index, _sprite, ax, ay, _aw, ah = anchor_entry
        vis = anchor_btn._visible_sprite_rect()
        if vis.isNull():
            tip_x = ax + _aw * 0.22
            tip_y = ay + ah * 0.22
        else:
            tip_x = ax + vis.left() + vis.width() * 0.18
            tip_y = ay + vis.top() + vis.height() * 0.12
        hx = int(round(tip_x * dpr - 0.5 * hscale))
        hy = int(round(tip_y * dpr - (theme.HAND_CURSOR_H - 0.5) * hscale))

        left = min(int(round(x * dpr)) for _i, _s, x, _y, _w, _h in entries)
        top = min(int(round(y * dpr)) for _i, _s, _x, y, _w, _h in entries)
        right = max(
            int(round((x + w) * dpr)) for _i, _s, x, _y, w, _h in entries
        )
        bottom = max(
            int(round((y + h) * dpr)) for _i, _s, _x, y, _w, h in entries
        )
        left = min(left, hx)
        top = min(top, hy)
        right = max(right, hx + hw)
        bottom = max(bottom, hy + hh)
        pad = max(2, int(round(2 * dpr)))
        left -= pad
        top -= pad
        right += pad
        bottom += pad

        canvas = QPixmap(right - left, bottom - top)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        for _index, sprite, x, y, w, h in entries:
            image = sprite.toImage()
            image.setDevicePixelRatio(1.0)
            target_x = int(round(x * dpr)) - left
            target_y = int(round(y * dpr)) - top
            target_w = int(round(w * dpr))
            target_h = int(round(h * dpr))
            painter.drawImage(
                QRect(target_x, target_y, target_w, target_h), image,
                QRect(0, 0, image.width(), image.height()),
            )
        painter.translate(hx - left, hy - top)
        theme.draw_hand_cursor(
            painter, 0, 0, scale=hscale, multi=True
        )
        painter.end()
        canvas.setDevicePixelRatio(dpr)

        start = getattr(anchor_btn, "drag_start_pos", QPoint(0, 0))
        sprite_w, sprite_h = anchor_btn._pixmap_logical_size(anchor_sprite)
        local_sprite_x = (anchor_btn.width() - sprite_w) / 2.0
        local_sprite_y = (anchor_btn.height() - sprite_h) / 2.0
        grab_x = ax + max(
            0.0, min(sprite_w, start.x() - local_sprite_x)
        )
        grab_y = ay + max(
            0.0, min(sprite_h, start.y() - local_sprite_y)
        )
        hotspot = QPoint(
            int(round(grab_x * dpr - left)),
            int(round(grab_y * dpr - top)),
        )
        return canvas, hotspot

    def _on_slot_drag_state(self, slot_idx: int, dragging: bool) -> None:
        """Track the drag's source box and hide the resting glove."""
        self._drag_in_progress = bool(dragging)
        if dragging:
            # BOX02 is both the lift and the move cue.  Play it when the drag
            # actually starts, not on every box click that opens a summary.
            self._suppress_next_slot_click = True
            sound.play("pc_pick", force=True)
            self._drag_source_box = self.current_box_index
            self._drag_source_slot = int(slot_idx)
            self._drag_source_slots = self._drag_slots_for(slot_idx)
            for slot in self.box_slots:
                should_hide = (
                    self._drag_source_box == self.current_box_index
                    and slot.slot_idx in self._drag_source_slots
                )
                if slot.is_dragging != should_hide:
                    slot.is_dragging = should_hide
                    slot.update()
        else:
            # drag.exec() has returned, so any drop has already been handled.
            # Clear now rather than on a zero-delay timer: the timer left the
            # source slot hidden for one event-loop turn, and a same-box swap
            # could be refreshed in that window with the flag still set.
            self._clear_drag_source()
            # Give Qt's synthetic post-drag release enough room to arrive;
            # 80 ms was short enough for a late click to deselect and replay
            # a placement cue after the swap had already sounded.
            QTimer.singleShot(250, self._release_drag_click_guard)
        # A cancelled drag can skip dragLeaveEvent on the slot it started
        # over; clear every stale hover flag so no orange plate is left on an
        # empty cell.
        for slot in self.box_slots:
            if slot.is_drag_hover:
                slot.is_drag_hover = False
                slot.update()
        if not hasattr(self, "hand_cursor"):
            return
        if dragging:
            self.hand_cursor.hide()
        else:
            self._position_hand_cursor()

    def _position_hand_cursor(self):
        """Place the GBA glove over the selected slot's upper-left corner."""
        if not hasattr(self, "hand_cursor"):
            return
        if getattr(self, "_drag_in_progress", False):
            # The drag image already carries the glove.  Selecting the source
            # at mouse-press starts a 90 ms lift; without this guard every
            # lift tick re-showed a second hand above the moving sprite.
            self.hand_cursor.hide()
            return
        idx = self.selected_slot_idx
        if idx < 0 or idx >= len(self.box_slots):
            self.hand_cursor.hide()
            return
        btn = self.box_slots[idx]
        if not btn.filepath or btn.width() < 20 or btn.height() < 20:
            self.hand_cursor.hide()
            return

        cell = btn.geometry()
        sprite = btn._display_pixmap()
        if sprite is not None and not sprite.isNull():
            sprite_w, sprite_h = btn._pixmap_logical_size(sprite)
            sprite_x = cell.x() + (cell.width() - sprite_w) / 2.0
            sprite_y = cell.y() + (cell.height() - sprite_h) / 2.0 + btn._lift
        else:
            sprite_w, sprite_h = cell.width() * 0.6, cell.height() * 0.6
            sprite_x = cell.x() + cell.width() * 0.2
            sprite_y = cell.y() + cell.height() * 0.2 + btn._lift

        # Just over half the sprite height, rounded to a whole pixel scale so
        # the glove never blurs and keeps the GBA's hand-to-icon proportion on
        # every screen from 1080p through 4K.
        hand_h = max(30.0, sprite_h * 0.56)
        scale = hand_h / float(theme.HAND_CURSOR_H)
        self.hand_cursor.set_multi(self.multi_mode)
        self.hand_cursor.set_scale(scale)

        # The glove's index fingertip (bottom-left of the sprite) hangs just
        # inside the visible Pokémon's upper-left, exactly like the in-game
        # cursor.  Anchor to the artwork, not the icon's transparent padding.
        vis = btn._visible_sprite_rect()
        if vis.isNull():
            tip_x = sprite_x + sprite_w * 0.22
            tip_y = sprite_y + sprite_h * 0.22
        else:
            tip_x = sprite_x + vis.left() + vis.width() * 0.18
            tip_y = sprite_y + vis.top() + vis.height() * 0.12
        sx = float(self.hand_cursor._scale)
        x = int(tip_x - 0.5 * sx)
        y = int(tip_y - (theme.HAND_CURSOR_H - 0.5) * sx)
        x = max(2, min(x, self.grid_frame.width() - self.hand_cursor.width() - 2))
        y = max(2, min(y, self.grid_frame.height() - self.hand_cursor.height() - 2))

        self.hand_cursor.move(x, y)
        self.hand_cursor.raise_()
        self.hand_cursor.show()

    def _refresh_grid_visuals(self):
        target_box = self.pc_dir / f"Box{self.current_box_index}"
        # A load replaces every icon in the grid.  Do not let a selection
        # animation from the previous box carry its lift onto the new sprite,
        # and only hide the drag source when the visible box is its own box.
        dragging_here = (
            self._drag_in_progress
            and self._drag_source_box == self.current_box_index
        )
        hidden_slots = set(self._drag_source_slots) if dragging_here else set()
        for index, btn in enumerate(self.box_slots):
            btn.reset_selection()
            btn.source_box = int(self.current_box_index)
            btn.is_dragging = index in hidden_slots

        for i, btn in enumerate(self.box_slots):
            btn.nat_dex = 0
            fname = self.current_box_layout.get(str(i))
            cached_legality = None
            if fname and (target_box / fname).exists():
                filepath = target_box / fname
                try:
                    pk = read_pk3_data(filepath.read_bytes())
                    if pk and pk.get("species", 0) > 0:
                        dex_id = pk["species"]
                        btn.nat_dex = int(dex_id)
                        icon_path = form_icon_path(dex_id, unown_form_from_pid(pk["pid"]))
                        if icon_path.exists():
                            pixmap = QPixmap(str(icon_path))
                            if not pixmap.isNull():
                                btn.filepath = str(filepath)
                                btn.normal_pixmap = pixmap
                                btn._scaled_cache.clear()
                            else:
                                btn.filepath = str(filepath)
                                btn.normal_pixmap = None
                        else:
                            btn.filepath = str(filepath)
                            btn.normal_pixmap = None
                    else:
                        btn.filepath = ""
                        btn.normal_pixmap = None
                except Exception:
                    btn.filepath = ""
                    btn.normal_pixmap = None
            else:
                btn.filepath = ""
                btn.normal_pixmap = None
            if btn.filepath:
                cached_legality = self._legality_cache.get(str(btn.filepath))
            btn.set_legality(
                cached_legality[0] if cached_legality else None,
                cached_legality[1] if cached_legality else (),
            )
            btn._scaled_cache.clear()
            btn._outlined_cache.clear()
        if self.multi_mode:
            self.selected_slots = {
                index for index in self.selected_slots
                if 0 <= index < len(self.box_slots)
                and self.box_slots[index].filepath
            }
            if (
                self.selected_slot_idx not in self.selected_slots
                and self.selected_slots
            ):
                self.selected_slot_idx = min(self.selected_slots)
        active = self._active_selection()
        for i, btn in enumerate(self.box_slots):
            btn.set_selected(i in active)
        self._update_shared_icon_factor()
        self._update_multi_button()
        self._position_hand_cursor()

    def load_box(self, box_num):
        self.lbl_box_name.setText(f"BOX {box_num}")
        target_box = self.pc_dir / f"Box{box_num}"
        target_box.mkdir(exist_ok=True)

        theme_file = target_box / "theme.txt"
        if theme_file.exists():
            saved_theme = theme_file.read_text().strip()
            idx = self.combo_theme.findText(saved_theme)
            if idx >= 0:
                self.combo_theme.blockSignals(True)
                self.combo_theme.setCurrentIndex(idx)
                self.combo_theme.blockSignals(False)
        else:
            theme_keys = list(BOX_THEMES.keys())
            theme_idx = (box_num - 1) % len(theme_keys)
            self.combo_theme.blockSignals(True)
            self.combo_theme.setCurrentIndex(theme_idx)
            self.combo_theme.blockSignals(False)

        self.apply_box_theme(animate=False)

        layout_file = target_box / "layout.json"
        try:
            box_layout = json.loads(layout_file.read_text()) if layout_file.exists() else {}
        except (OSError, json.JSONDecodeError):
            box_layout = {}

        valid_layout = {}
        mapped_files = set()

        for slot_str, fname in box_layout.items():
            # Bad JSON types must not crash a box switch.  A file may also
            # appear in two slots after a bad import; keep the first slot and
            # leave the duplicate file to the stray pass below.
            if not isinstance(fname, str) or not isinstance(slot_str, str):
                continue
            if slot_str.isdigit() and 0 <= int(slot_str) < 30:
                if fname in mapped_files:
                    continue
                if (target_box / fname).is_file():
                    valid_layout[slot_str] = fname
                    mapped_files.add(fname)

        # Sort the stray pass.  Directory iteration order is not stable across
        # filesystems; without a sort, a repair could put a file in a different
        # free slot on every load, which looks like Pokémon moving by themselves.
        all_pk3s = sorted(target_box.glob("*.pk3"), key=lambda path: path.name.lower())
        stray_files = [p.name for p in all_pk3s if p.name not in mapped_files]

        for stray in stray_files:
            for i in range(30):
                if str(i) not in valid_layout:
                    valid_layout[str(i)] = stray
                    break

        if valid_layout != box_layout:
            layout_file.write_text(json.dumps(valid_layout))
        self.current_box_layout = valid_layout

        self.selected_slot_idx = -1
        self.selected_slots.clear()
        self.selected_pk3_path = None
        self._current_move_types = [None, None, None, None]
        self._cry_dex = 0
        self.lbl_name_lvl.setText("NO POKÉMON SELECTED")
        self.lbl_name_lvl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 18px; border: none; background: transparent;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )

        if self._current_movie:
            self._current_movie.stop()
            self._current_movie = None
        if self.lbl_sprite.movie():
            self.lbl_sprite.movie().stop()
        self.lbl_sprite.setPixmap(QPixmap())

        self._set_detail_rows()
        self.summary_ball_badge.clear()
        self.summary_item_badge.clear()
        self.lbl_flavor.hide()

        for mw in self.move_widgets:
            mw['frame'].setStyleSheet(_move_row_style(None))
            mw['name'].setText("— None —")
            mw['type'].setText("---")
            mw['type'].setStyleSheet(_type_badge_style("#b8b2a3"))
            mw['pp'].setText("PP --/--")

        self.btn_move_box.setEnabled(False)
        self.btn_trade.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.btn_release.setEnabled(False)

        self._refresh_grid_visuals()

    def _snapshot(self, reason: str) -> None:
        try:
            user_data.snapshot(reason)
        except Exception:
            pass

    def _release_drag_click_guard(self) -> None:
        """Stop swallowing clicks once Qt's synthetic release has passed."""
        self._suppress_next_slot_click = False

    def _clear_drag_source(self) -> None:
        self._drag_source_box = None
        self._drag_source_slot = None
        self._drag_source_slots = []
        # The drag-source flag hides a slot's sprite.  Once the drag is over
        # (or the drop has been applied), every slot must be painted again:
        # a same-box swap puts a *different* Pokémon in the source slot, and
        # leaving that slot flagged hid the displaced Pokémon until the next
        # box load, which looked like it had vanished.
        for btn in self.box_slots:
            if btn.is_dragging:
                btn.is_dragging = False
                btn.update()

    def _auto_page_during_drag(self, delta: int) -> None:
        """Page once while a held Pokémon rests over an arrow."""
        if not self._drag_in_progress:
            return
        target = self.current_box_index + int(delta)
        if target < 1 or not (self.pc_dir / f"Box{target}").is_dir():
            return
        group = getattr(self, "slide_anim_group", None)
        if group is not None and group.state() == QParallelAnimationGroup.State.Running:
            return
        self.change_box(int(delta))

    @staticmethod
    def _read_layout(box_dir: Path) -> dict:
        try:
            value = json.loads((box_dir / "layout.json").read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _write_layout(box_dir: Path, layout: dict) -> None:
        (box_dir / "layout.json").write_text(json.dumps(layout))

    @staticmethod
    def _unique_name(directory: Path, filename: str) -> str:
        dest = directory / filename
        if not dest.exists():
            return filename
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while True:
            candidate = f"{stem}_{counter}{suffix}"
            if not (directory / candidate).exists():
                return candidate
            counter += 1

    def _move_across_boxes(self, src_box: int, src_slot: int, dest_slot: int) -> None:
        """Drop a held Pokémon into a different box, swapping if occupied.

        The two files and the two layouts form one transaction.  Moving the
        files first and then failing to write a layout used to leave an orphan
        file that the next box load would repair into the first free slot.  On
        any failure both files and both layouts are put back before refreshing.
        """
        src_dir = self.pc_dir / f"Box{src_box}"
        dest_dir = self.pc_dir / f"Box{self.current_box_index}"
        src_layout = self._read_layout(src_dir)
        dest_layout = self._read_layout(dest_dir)
        src_name = src_layout.get(str(src_slot))
        if not isinstance(src_name, str) or not (src_dir / src_name).is_file():
            return
        dest_name = dest_layout.get(str(dest_slot))
        if not isinstance(dest_name, str) or not (dest_dir / dest_name).is_file():
            dest_name = None

        self._snapshot(
            f"Move {src_name} from Box{src_box} to Box{self.current_box_index}"
        )
        parked_name = ""
        moved_name = ""
        src_path = src_dir / src_name
        dest_path = dest_dir / dest_name if dest_name else None
        try:
            if dest_path is not None:
                # The occupied slot moves into the source slot, so a dragged
                # swap keeps both Pokémon instead of overwriting either file.
                parked_name = self._unique_name(src_dir, dest_name)
                shutil.move(str(dest_path), str(src_dir / parked_name))
            moved_name = self._unique_name(dest_dir, src_name)
            shutil.move(str(src_path), str(dest_dir / moved_name))

            new_src_layout = dict(src_layout)
            new_dest_layout = dict(dest_layout)
            new_src_layout.pop(str(src_slot), None)
            if parked_name:
                new_src_layout[str(src_slot)] = parked_name
            # Remove any stale duplicate reference before assigning the slot.
            new_dest_layout = {
                slot: name for slot, name in new_dest_layout.items()
                if name != moved_name
            }
            new_dest_layout[str(dest_slot)] = moved_name
            self._write_layout(src_dir, new_src_layout)
            self._write_layout(dest_dir, new_dest_layout)
        except OSError as exc:
            # Best-effort rollback.  If a rollback step itself fails, refresh
            # repairs the strays deterministically rather than losing anything.
            try:
                if moved_name and (dest_dir / moved_name).exists():
                    shutil.move(str(dest_dir / moved_name), str(src_path))
                if parked_name and (src_dir / parked_name).exists():
                    shutil.move(str(src_dir / parked_name), str(dest_path))
                self._write_layout(src_dir, src_layout)
                self._write_layout(dest_dir, dest_layout)
            except OSError:
                pass
            QMessageBox.warning(self, "Move failed", f"Could not move the Pokémon: {exc}")
            self._drag_source_box = None
            self._drag_source_slot = None
            self.refresh_boxes()
            return
        self._legality_cache.clear()
        self._drag_source_box = None
        self._drag_source_slot = None
        self._cancel_box_slide()
        self.refresh_boxes()
        # A drop is exactly one set-down.  An occupied slot is a swap and an
        # empty slot is a place, but both use a single BOX01 hit; pc_swap is
        # never a doubled cue.
        sound.play("pc_swap" if dest_name else "pc_place", force=True)
        self._select_slot_after_move(dest_slot)

    def import_files(self, paths: list[str]) -> int:
        """Copy external .pk3 files into the current box, first free slots."""
        sources = [Path(path) for path in paths if Path(path).is_file()]
        if not sources:
            return 0
        target_box = self.pc_dir / f"Box{self.current_box_index}"
        target_box.mkdir(exist_ok=True)
        layout = self._read_layout(target_box)
        free_slots = [index for index in range(30) if str(index) not in layout]
        if not free_slots:
            QMessageBox.warning(
                self, "Box Full",
                f"Box {self.current_box_index} is full. Create a new box first.",
            )
            return 0
        self._snapshot("Import .pk3 files")
        imported = 0
        for source in sources:
            if not free_slots:
                break
            name = self._unique_name(target_box, source.name)
            try:
                shutil.copy2(source, target_box / name)
            except OSError as exc:
                QMessageBox.warning(
                    self, "Import failed", f"Could not import {source.name}: {exc}"
                )
                break
            layout[str(free_slots.pop(0))] = name
            imported += 1
        self._write_layout(target_box, layout)
        self.refresh_boxes()
        if imported:
            sound.play("pc_import")
            QMessageBox.information(
                self, "Imported to Bill's PC",
                f"Copied {imported} Pokémon into Box {self.current_box_index}.",
            )
        return imported

    def _undo_last_change(self) -> None:
        window = self.window()
        if hasattr(window, "undo_last_change"):
            window.undo_last_change()

    def _on_audit_changed(self, findings: list) -> None:
        for finding in findings:
            self._legality_cache[str(finding.path)] = (
                bool(finding.valid), tuple(finding.messages)
            )
        for slot in self.box_slots:
            if not slot.filepath:
                continue
            cached = self._legality_cache.get(str(slot.filepath))
            slot.set_legality(
                cached[0] if cached else None,
                cached[1] if cached else (),
            )

    def audit_current_box(self) -> None:
        sound.play("menu_select")
        from legality_dialog import LegalityAuditDialog

        box_dir = self.pc_dir / f"Box{self.current_box_index}"
        layout = self._read_layout(box_dir)
        items: list[tuple[int, str]] = []
        for index in range(30):
            name = layout.get(str(index))
            if name and (box_dir / name).is_file():
                items.append((index, str(box_dir / name)))
        if not items:
            QMessageBox.information(
                self, "Audit Box", f"Box {self.current_box_index} is empty."
            )
            return
        dialog = LegalityAuditDialog(
            self, f"Box {self.current_box_index}", items, self
        )
        # Connect before the first audit: the dialog used to run it in its
        # constructor, so the initial finding never reached the PC grid and
        # the red badges only appeared after a second RE-AUDIT.
        dialog.data_changed.connect(self._on_audit_changed)
        dialog.run_audit()
        self._audit_dialog = dialog
        dialog.show()

    def change_box(self, delta):
        target_index = self.current_box_index + delta
        if target_index < 1: return

        target_box = self.pc_dir / f"Box{target_index}"
        if not target_box.exists() and delta > 0:
            return

        # A second box change before the first slide finishes used to leave
        # the old snapshot labels alive, where they could cover the new grid.
        self._cancel_box_slide()
        # Changing box pages is a tab press, not a Pokémon placement.
        sound.play("menu_select")
        old_pixmap = self.grid_frame.grab()

        self.current_box_index = target_index
        self.load_box(self.current_box_index)

        new_pixmap = self.grid_frame.grab()

        for btn in self.box_slots: btn.hide()

        self.anim_old = QLabel(self.grid_frame)
        self.anim_old.setPixmap(old_pixmap)
        self.anim_old.setGeometry(0, 0, self.grid_frame.width(), self.grid_frame.height())
        # The slide is scenery, not a drop target.  Without this, a drop made
        # while the slide was still running landed on the QLabel instead of the
        # slot underneath it.
        self.anim_old.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.anim_old.show()

        start_x = self.grid_frame.width() if delta > 0 else -self.grid_frame.width()

        self.anim_new = QLabel(self.grid_frame)
        self.anim_new.setPixmap(new_pixmap)
        self.anim_new.setGeometry(start_x, 0, self.grid_frame.width(), self.grid_frame.height())
        self.anim_new.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.anim_new.show()

        self.slide_anim_group = QParallelAnimationGroup(self)

        anim1 = QPropertyAnimation(self.anim_old, b"pos", self)
        anim1.setEndValue(QPoint(-start_x, 0))
        anim1.setDuration(250)
        anim1.setEasingCurve(QEasingCurve.Type.InOutQuad)

        anim2 = QPropertyAnimation(self.anim_new, b"pos", self)
        anim2.setEndValue(QPoint(0, 0))
        anim2.setDuration(250)
        anim2.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.slide_anim_group.addAnimation(anim1)
        self.slide_anim_group.addAnimation(anim2)

        self.slide_anim_group.finished.connect(self._on_slide_finished)
        self.slide_anim_group.start()

    def _cancel_box_slide(self):
        """Stop a box transition and remove its snapshot labels immediately."""
        # A swap animation is also box-specific.  Its floating labels must not
        # survive a box change and cover the new grid.
        self._kill_swap_anim()
        group = getattr(self, "slide_anim_group", None)
        if group is not None:
            try:
                group.stop()
            except RuntimeError:
                pass
            self.slide_anim_group = None
        for name in ("anim_old", "anim_new"):
            label = getattr(self, name, None)
            if label is not None:
                try:
                    label.hide()
                    label.deleteLater()
                except RuntimeError:
                    pass
                setattr(self, name, None)
        for btn in getattr(self, "box_slots", []):
            btn.show()

    def _on_slide_finished(self):
        label_old = getattr(self, "anim_old", None)
        label_new = getattr(self, "anim_new", None)
        if label_old is not None:
            label_old.deleteLater()
        if label_new is not None:
            label_new.deleteLater()
        self.anim_old = None
        self.anim_new = None
        self.slide_anim_group = None
        for btn in self.box_slots: btn.show()
        self._position_hand_cursor()

    def cancel_drop(self, slot_idx: int, offset_x: float, offset_y: float):
        sound.play("pc_place")
        self._kill_swap_anim()
        # The drop is over; the return animation below is the only thing that
        # should hide this slot.  Do not carry the drag-source flag into the
        # next box load, where it would hide whichever Pokémon occupies the
        # same index.
        self._clear_drag_source()

        btn = self.box_slots[slot_idx]
        pix = btn._display_pixmap()
        if not pix or pix.isNull(): return

        self.anim_labels = []
        self.swap_anim_group = QParallelAnimationGroup(self)

        lbl = QLabel(self.grid_frame)
        lbl.setPixmap(pix)
        lbl.setFixedSize(btn.size())
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        start_pos = btn.pos() + QPoint(int(offset_x), int(offset_y))
        end_pos = btn.pos()

        lbl.move(start_pos)
        lbl.show()
        lbl.raise_()

        anim = QPropertyAnimation(lbl, b"pos", self)
        anim.setEndValue(end_pos)
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.swap_anim_group.addAnimation(anim)
        self.anim_labels.append(lbl)

        btn.is_animating = True
        self.swap_anim_group.finished.connect(self._cleanup_swap_anim)
        self.swap_anim_group.start()

    def _on_selection_drop(
        self, payload: dict, dest_idx: int, offset_x: float, offset_y: float
    ) -> None:
        """Handle a drop carrying one slot or a whole multi-selection."""
        slots = payload.get("slots") if isinstance(payload, dict) else None
        if not isinstance(slots, list) or not slots:
            return
        try:
            slots = [int(value) for value in slots]
        except (TypeError, ValueError):
            return
        if len(slots) <= 1:
            src_idx = slots[0] if slots else int(payload.get("anchor", dest_idx))
            # Same-index drops are handled by swap_slots: same-box becomes the
            # single set-down swap cue, while a cross-box drag still moves the
            # file.
            self.swap_slots(src_idx, dest_idx, offset_x, offset_y)
            return
        self._move_selected_group(payload, dest_idx, offset_x, offset_y)

    @staticmethod
    def _group_targets(
        slots: list[int], anchor: int, dest_idx: int
    ) -> list[int] | None:
        """Translate a selection block so its anchor lands on ``dest_idx``."""
        anchor_row, anchor_col = divmod(int(anchor), 6)
        dest_row, dest_col = divmod(int(dest_idx), 6)
        row_delta = dest_row - anchor_row
        col_delta = dest_col - anchor_col
        targets = []
        for slot in slots:
            row, col = divmod(int(slot), 6)
            target_row = row + row_delta
            target_col = col + col_delta
            if not (0 <= target_row < 5 and 0 <= target_col < 6):
                return None
            targets.append(target_row * 6 + target_col)
        return targets

    def _reject_group_drop(self, message: str) -> None:
        sound.play("pc_error")
        self._clear_drag_source()
        for slot in self.box_slots:
            slot.is_drag_hover = False
        self._refresh_grid_visuals()
        QToolTip.showText(QCursor.pos(), message, self.grid_frame)

    def _move_selected_group(
        self, payload: dict, dest_idx: int, offset_x: float, offset_y: float
    ) -> None:
        try:
            source_slots = sorted({int(value) for value in payload["slots"]})
            anchor = int(payload.get("anchor", source_slots[0]))
            source_box = int(payload.get("source_box", self.current_box_index))
        except (KeyError, TypeError, ValueError):
            return
        if len(source_slots) < 2 or anchor not in source_slots:
            anchor = source_slots[0]
        targets = self._group_targets(source_slots, anchor, dest_idx)
        if targets is None:
            self._reject_group_drop("The selected block does not fit there")
            return
        if source_box == self.current_box_index:
            self._move_group_in_box(source_slots, targets, dest_idx)
        else:
            self._move_group_across_boxes(source_box, source_slots, targets, dest_idx)

    def _move_group_in_box(
        self, source_slots: list[int], targets: list[int], dest_idx: int
    ) -> None:
        source_set = set(source_slots)
        target_set = set(targets)
        source_names = {}
        for slot in source_slots:
            name = self.current_box_layout.get(str(slot))
            if not isinstance(name, str) or not (
                self.pc_dir / f"Box{self.current_box_index}" / name
            ).is_file():
                self._reject_group_drop("One of the selected Pokémon is missing")
                return
            source_names[slot] = name
        if target_set == source_set:
            self._clear_drag_source()
            self._refresh_grid_visuals()
            sound.play("pc_swap", force=True)
            return
        occupied = [
            slot for slot in targets
            if slot not in source_set
            and self.current_box_layout.get(str(slot))
        ]
        if occupied:
            self._reject_group_drop("There is not room for the whole block there")
            return

        self._snapshot(f"Move {len(source_slots)} Pokémon in a box")
        new_layout = dict(self.current_box_layout)
        for slot in source_slots:
            new_layout.pop(str(slot), None)
        for source, target in zip(source_slots, targets):
            new_layout[str(target)] = source_names[source]
        layout_path = (
            self.pc_dir / f"Box{self.current_box_index}" / "layout.json"
        )
        try:
            layout_path.write_text(json.dumps(new_layout))
        except OSError as exc:
            QMessageBox.warning(
                self, "Move failed", f"Could not save the box layout: {exc}"
            )
            self._refresh_grid_visuals()
            return
        self.current_box_layout = new_layout
        self._clear_drag_source()
        self._cancel_box_slide()
        self.selected_slots = set(targets)
        self.selected_slot_idx = int(dest_idx)
        self.selected_pk3_path = str(
            self.pc_dir / f"Box{self.current_box_index}"
            / new_layout[str(dest_idx)]
        )
        self._refresh_grid_visuals()
        self._show_slot_summary(dest_idx, user=False)
        sound.play("pc_place", force=True)

    def _move_group_across_boxes(
        self,
        source_box: int,
        source_slots: list[int],
        targets: list[int],
        dest_idx: int,
    ) -> None:
        src_dir = self.pc_dir / f"Box{source_box}"
        dest_dir = self.pc_dir / f"Box{self.current_box_index}"
        if not src_dir.is_dir() or not dest_dir.is_dir():
            self._reject_group_drop("That box no longer exists")
            return
        src_layout = self._read_layout(src_dir)
        dest_layout = dict(self.current_box_layout)
        source_names = {}
        for slot in source_slots:
            name = src_layout.get(str(slot))
            if not isinstance(name, str) or not (src_dir / name).is_file():
                self._reject_group_drop("One of the selected Pokémon is missing")
                return
            source_names[slot] = name
        occupied = [slot for slot in targets if dest_layout.get(str(slot))]
        if occupied:
            self._reject_group_drop("There is not room for the whole block there")
            return

        self._snapshot(
            f"Move {len(source_slots)} Pokémon from Box{source_box} "
            f"to Box{self.current_box_index}"
        )
        moved = []
        new_src = dict(src_layout)
        new_dest = dict(dest_layout)
        try:
            for source_slot, target_slot in zip(source_slots, targets):
                source_path = src_dir / source_names[source_slot]
                dest_name = self._unique_name(dest_dir, source_names[source_slot])
                dest_path = dest_dir / dest_name
                shutil.move(str(source_path), str(dest_path))
                moved.append((source_path, dest_path))
                new_src.pop(str(source_slot), None)
                new_dest[str(target_slot)] = dest_name
            self._write_layout(src_dir, new_src)
            self._write_layout(dest_dir, new_dest)
        except OSError as exc:
            for source_path, dest_path in reversed(moved):
                try:
                    if dest_path.exists():
                        shutil.move(str(dest_path), str(source_path))
                except OSError:
                    pass
            try:
                self._write_layout(src_dir, src_layout)
                self._write_layout(dest_dir, dest_layout)
            except OSError:
                pass
            QMessageBox.warning(
                self, "Move failed", f"Could not move the selected Pokémon: {exc}"
            )
            self._clear_drag_source()
            self.refresh_boxes()
            return

        self._legality_cache.clear()
        self._clear_drag_source()
        self._cancel_box_slide()
        self.refresh_boxes()
        self.selected_slots = set(targets)
        self.selected_slot_idx = int(dest_idx)
        self._refresh_grid_visuals()
        self._show_slot_summary(dest_idx, user=False)
        sound.play("pc_place", force=True)

    def swap_slots(self, src_idx: int, dest_idx: int, offset_x: float, offset_y: float):
        self._kill_swap_anim()
        # A drop ends any in-flight box page; keeping its snapshot on top
        # would hide the swap that is about to happen beneath it.
        self._cancel_box_slide()

        if src_idx == dest_idx and (
            self._drag_source_box is None
            or self._drag_source_box == self.current_box_index
        ):
            # A same-place drop is still a completed swap gesture.  Do not
            # rewrite the layout or replay the placement cue; the single
            # set-down swap cue is what the player expects to hear.  A
            # cross-box drag to the same slot index still moves to the other
            # box.
            self._clear_drag_source()
            self.refresh_boxes()
            sound.play("pc_swap", force=True)
            self._select_slot_after_move(dest_idx)
            return

        if (
            self._drag_source_box is not None
            and self._drag_source_box != self.current_box_index
        ):
            self._move_across_boxes(
                self._drag_source_box,
                self._drag_source_slot if self._drag_source_slot is not None else src_idx,
                dest_idx,
            )
            return

        # The drop has been handled.  Reveal both slots before refreshing:
        # after a swap the source index holds a different Pokémon, so keeping
        # the drag-source flag on that index would paint the displaced Pokémon
        # invisibly.
        self._clear_drag_source()
        self._snapshot("Reorder a box")

        file_a = self.current_box_layout.get(str(src_idx))
        file_b = self.current_box_layout.get(str(dest_idx))

        if file_a: self.current_box_layout[str(dest_idx)] = file_a
        else: self.current_box_layout.pop(str(dest_idx), None)

        if file_b: self.current_box_layout[str(src_idx)] = file_b
        else: self.current_box_layout.pop(str(src_idx), None)

        layout_path = self.pc_dir / f"Box{self.current_box_index}" / "layout.json"
        layout_path.write_text(json.dumps(self.current_box_layout))

        # The drop ends the old selection; select the destination once, after
        # the new icons are in place, instead of briefly lifting the source
        # slot and then animating it down again.
        self.selected_slot_idx = -1
        self.selected_pk3_path = None
        self._refresh_grid_visuals()
        sound.play("pc_swap" if file_b else "pc_place", force=True)
        self._select_slot_after_move(dest_idx)

        dest_btn = self.box_slots[dest_idx]
        src_btn = self.box_slots[src_idx]

        self.anim_labels = []
        self.swap_anim_group = QParallelAnimationGroup(self)

        # Dest btn holds the dropped Pokemon from cursor
        if dest_btn.filepath:
            pix = dest_btn._display_pixmap()
            if pix and not pix.isNull():
                lbl = QLabel(self.grid_frame)
                lbl.setPixmap(pix)
                lbl.setFixedSize(dest_btn.size())
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

                start_pos = dest_btn.pos() + QPoint(int(offset_x), int(offset_y))
                end_pos = dest_btn.pos()

                lbl.move(start_pos)
                lbl.show()
                lbl.raise_()

                anim = QPropertyAnimation(lbl, b"pos", self)
                anim.setEndValue(end_pos)
                anim.setDuration(220)
                anim.setEasingCurve(QEasingCurve.Type.OutQuad)
                self.swap_anim_group.addAnimation(anim)
                self.anim_labels.append(lbl)
                dest_btn.is_animating = True

        # Src btn holds the displaced Pokemon smoothly gliding across the screen to its new home
        if src_btn.filepath:
            pix = src_btn._display_pixmap()
            if pix and not pix.isNull():
                lbl = QLabel(self.grid_frame)
                lbl.setPixmap(pix)
                lbl.setFixedSize(src_btn.size())
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

                start_pos = dest_btn.pos()
                end_pos = src_btn.pos()

                lbl.move(start_pos)
                lbl.show()
                lbl.raise_()

                anim = QPropertyAnimation(lbl, b"pos", self)
                anim.setEndValue(end_pos)
                anim.setDuration(220)
                anim.setEasingCurve(QEasingCurve.Type.OutQuad)
                self.swap_anim_group.addAnimation(anim)
                self.anim_labels.append(lbl)
                src_btn.is_animating = True

        if self.anim_labels:
            self.swap_anim_group.finished.connect(self._cleanup_swap_anim)
            self.swap_anim_group.start()

    def _kill_swap_anim(self):
        group = getattr(self, "swap_anim_group", None)
        if group is not None and group.state() == QParallelAnimationGroup.State.Running:
            group.stop()
        # Clean up even when the group has already stopped but its floating
        # labels or is_animating flags survived (for example a box change in
        # the same event-loop turn as the swap's finish signal).
        if getattr(self, "anim_labels", []) or any(
            btn.is_animating for btn in self.box_slots
        ):
            self._cleanup_swap_anim()

    def _cleanup_swap_anim(self):
        for lbl in getattr(self, "anim_labels", []):
            # deleteLater() is asynchronous; until it runs the floating sprite
            # is still visible above the reused grid.  Hide it first so a box
            # change can never show last box's swap sprites drifting over the
            # newly loaded slots.
            lbl.hide()
            lbl.deleteLater()
        self.anim_labels = []
        for btn in self.box_slots:
            btn.is_animating = False
            btn.update()

    def _set_detail_rows(self, *, ot="—", nature="—", item="—", ivs="—", evs="—"):
        self.detail_ot.setText(f"OT: {ot}")
        self.detail_nature.setText(f"Nature: {nature}")
        self.detail_item.setText(f"Item: {item}")
        self.detail_ivs.setText(f"IVs: {ivs}")
        self.detail_evs.setText(f"EVs: {evs}")

    def _select_slot_after_move(self, slot_idx: int) -> None:
        """Select a destination after a drop without toggling it again."""
        self.selected_slot_idx = int(slot_idx)
        if self.multi_mode:
            self.selected_slots = {int(slot_idx)}
        else:
            self.selected_slots.clear()
        self._refresh_grid_visuals()
        self._show_slot_summary(slot_idx, user=False)

    def _clear_selection(self):
        """Return the storage screen to its neutral, no-selection state."""
        self._cry_dex = 0
        self.selected_slot_idx = -1
        self.selected_slots.clear()
        self.selected_pk3_path = None
        self._current_move_types = [None, None, None, None]
        for i, btn in enumerate(self.box_slots):
            btn.set_selected(False)
        self._update_multi_button()
        if hasattr(self, "hand_cursor"):
            self.hand_cursor.hide()

        if self._current_movie:
            self._current_movie.stop()
            self._current_movie = None
        if self.lbl_sprite.movie():
            self.lbl_sprite.movie().stop()
            self.lbl_sprite.setMovie(None)
        self.lbl_sprite.setPixmap(QPixmap())
        self.lbl_name_lvl.setText("NO POKÉMON SELECTED")
        self.lbl_name_lvl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 18px; border: none; background: transparent;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self._set_detail_rows()
        self.summary_ball_badge.clear()
        self.summary_item_badge.clear()
        self.lbl_flavor.hide()
        self.btn_move_box.setEnabled(False)
        self.btn_trade.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.btn_release.setEnabled(False)
        self._update_action_buttons()
        for i, mw in enumerate(self.move_widgets):
            mw['frame'].setStyleSheet(_move_row_style(None))
            mw['name'].setText("— None —")
            mw['type'].setText("---")
            mw['type'].setStyleSheet(_type_badge_style(theme.BORDER_SOFT))
            mw['pp'].setText("PP --/--")

    def _play_selected_cry(self) -> None:
        if self._cry_dex:
            sound.play_cry(self._cry_dex)

    def on_slot_clicked(self, slot_idx, user: bool = True):
        if self._suppress_next_slot_click:
            self._suppress_next_slot_click = False
            return
        if self.multi_mode:
            self._on_multi_slot_clicked(slot_idx, user=user)
            return

        # A second click on the already-selected slot is a deliberate
        # deselect, matching the hand cursor acting as a toggle.
        if self.selected_slot_idx == slot_idx:
            if user:
                sound.play("pc_place")
            self._clear_selection()
            return

        self.selected_slots.clear()
        self.selected_slot_idx = slot_idx
        self._apply_selection_visuals()
        self._show_slot_summary(slot_idx, user=user)

    def _on_multi_slot_clicked(self, slot_idx, user: bool = True):
        """Click-to-toggle membership while the green glove is active."""
        if not 0 <= slot_idx < len(self.box_slots):
            return
        if not self.box_slots[slot_idx].filepath:
            if user:
                sound.play("pc_place")
            self._clear_selection()
            return

        if slot_idx in self.selected_slots:
            self.selected_slots.discard(slot_idx)
            if user:
                sound.play("pc_place")
            if not self.selected_slots:
                self._clear_selection()
                return
            if self.selected_slot_idx == slot_idx:
                self.selected_slot_idx = min(self.selected_slots)
            self._apply_selection_visuals()
            self._show_slot_summary(self.selected_slot_idx, user=False)
            return

        self.selected_slots.add(slot_idx)
        self.selected_slot_idx = slot_idx
        if user:
            sound.play("pc_pick")
        self._apply_selection_visuals()
        self._show_slot_summary(slot_idx, user=False)

    def _show_slot_summary(self, slot_idx, *, user: bool = False):
        """Populate the left panel for ``slot_idx`` without changing selection."""
        filepath = self.box_slots[slot_idx].filepath
        if not filepath or not Path(filepath).exists():
            if user:
                sound.play("pc_place")
            self._clear_selection()
            return
        if user:
            # Selecting a Pokémon and lifting it are the same gesture in the
            # games; both use the official BOX02 pick-up cue.
            sound.play("pc_pick")

        # Clear active movie if it exists before potentially loading a new one
        if self._current_movie:
            self._current_movie.stop()
            self._current_movie = None
        if self.lbl_sprite.movie():
            self.lbl_sprite.movie().stop()

        self.selected_pk3_path = filepath
        self.btn_move_box.setEnabled(True)
        self.btn_trade.setEnabled(True)
        self.btn_edit.setEnabled(True)
        self.btn_release.setEnabled(True)
        self._update_action_buttons()

        try:
            pk = read_pk3_data(Path(filepath).read_bytes())
            if not pk: return

            name = pk["nickname"]
            lvl = pk["level"]
            pid = pk["pid"]
            self._cry_dex = int(pk["species"])

            gender_sym = ""
            try:
                import clr
                from PKHeX.Core import PK3
                temp_pk = PK3()
                temp_pk.Species = pk["species"]
                ratio = temp_pk.PersonalInfo.Gender
                if ratio == 255:
                    gender_sym = ""
                elif ratio == 254:
                    gender_sym = " ♀"
                elif ratio == 0:
                    gender_sym = " ♂"
                else:
                    gender_sym = " ♀" if (pid & 0xFF) < ratio else " ♂"
            except Exception:
                pass

            star = " ★" if pk["is_shiny"] else ""
            self.lbl_name_lvl.setText(f"{name}{gender_sym} (Lv. {lvl}){star}")

            if pk["is_shiny"]:
                self.lbl_name_lvl.setStyleSheet(
                    "color: %s; font-family: '%s'; font-size: 18px; border: none; background: transparent;"
                    % (theme.ORANGE_DARK, theme.FONT_GBA)
                )
            else:
                self.lbl_name_lvl.setStyleSheet(
                    "color: %s; font-family: '%s'; font-size: 18px; border: none; background: transparent;"
                    % (theme.NAVY_DARK, theme.FONT_GBA)
                )

            nat_idx = pk["nature"]
            nat_str = NATURES[nat_idx] if nat_idx < len(NATURES) else "Unknown"
            item_str = GEN3_ITEMS.get(pk["item"], ("None", ""))[0]

            ot_str = pk["ot"]
            tid_str = f"{pk['tid']:05d}"
            sid_str = f"{pk['sid']:05d}"

            iv = pk["ivs"]
            ev = pk["evs"]

            inc = nat_idx // 5
            dec = nat_idx % 5
            stat_map = {0: 1, 2: 5, 3: 3, 4: 4}

            iv_strs = []
            ev_strs = []
            for i in range(6):
                iv_val = f"{iv[i]:02d}"
                ev_val = f"{ev[i]:03d}"
                if inc != dec and i != 0:
                    if i == stat_map.get(inc, -1):
                        iv_val = f'<span style="color: {theme.RED_DARK};">{iv_val}</span>'
                        ev_val = f'<span style="color: {theme.RED_DARK};">{ev_val}</span>'
                    elif i == stat_map.get(dec, -1):
                        iv_val = f'<span style="color: {theme.BLUE};">{iv_val}</span>'
                        ev_val = f'<span style="color: {theme.BLUE};">{ev_val}</span>'
                iv_strs.append(iv_val)
                ev_strs.append(ev_val)

            iv_html = "/".join(iv_strs)
            ev_html = "/".join(ev_strs)

            self._set_detail_rows(
                ot=f"{ot_str} ({tid_str} / {sid_str})",
                nature=nat_str,
                item=item_str,
                ivs=iv_html,
                evs=ev_html,
            )
            self.summary_ball_badge.set_ball(int(pk.get("ball", 4) or 4))
            self.summary_item_badge.set_item(int(pk.get("item", 0) or 0))

            flavors = ["Spicy", "Sour", "Sweet", "Dry", "Bitter"]
            if inc == dec:
                flavor_text = "It will happily eat anything without complaining."
            else:
                flavor_text = f"It has a preference for {flavors[inc]} food, but strongly dislikes {flavors[dec]} food."

            tb_ivs = [iv[0], iv[1], iv[2], iv[5], iv[3], iv[4]]
            max_iv = max(tb_ivs)
            winners = [i for i, v in enumerate(tb_ivs) if v == max_iv]

            tie_breaker = pid % 6
            while tie_breaker not in winners:
                tie_breaker = (tie_breaker + 1) % 6

            characteristics = {
                0: ["Loves to eat.", "Takes plenty of snoozes.", "Nods off a lot.", "Scatters things often.", "Likes to relax."],
                1: ["Proud of its power.", "Likes to thrash about.", "A little quick tempered.", "Likes to fight.", "Quick tempered."],
                2: ["Sturdy body.", "Capable of taking hits.", "Highly persistent.", "Good endurance.", "Good perseverance."],
                3: ["Likes to run.", "Alert to sounds.", "Impetuous and silly.", "Somewhat of a clown.", "Quick to flee."],
                4: ["Highly curious.", "Mischievous.", "Thoroughly cunning.", "Often lost in thought.", "Very finicky."],
                5: ["Strong willed.", "Somewhat vain.", "Strongly defiant.", "Hates to lose.", "Somewhat stubborn."]
            }
            char_text = characteristics[tie_breaker][max_iv % 5]

            self.lbl_flavor.setText(f'"{char_text} {flavor_text}"')
            self.lbl_flavor.show()

            for i, m_id in enumerate(pk["moves"]):
                mw = self.move_widgets[i]
                if m_id != 0:
                    m_name = self.editor_tab.moves_map.get(m_id, f"Move {m_id}")
                    m_type = self.get_move_type(m_id)
                    m_color = TYPE_COLORS.get(m_type, "#A8A878")

                    cur_pp = pk["pp"][i]
                    max_pp = calc_max_pp(m_id, pk["pp_ups"][i])

                    self._current_move_types[i] = m_color
                    mw['frame'].setStyleSheet(_move_row_style(m_color))
                    mw['name'].setText(m_name)
                    mw['type'].setText(m_type)
                    mw['type'].setStyleSheet(_type_badge_style(m_color))
                    mw['pp'].setText(f"PP {cur_pp}/{max_pp}")
                else:
                    self._current_move_types[i] = None
                    mw['frame'].setStyleSheet(_move_row_style(None))
                    mw['name'].setText("— None —")
                    mw['type'].setText("---")
                    mw['type'].setStyleSheet(_type_badge_style(theme.BORDER_SOFT))
                    mw['pp'].setText("PP --/--")

            is_shiny = pk["is_shiny"]
            gif_path = animated_sprite_path(pk["species"], unown_form_from_pid(pk["pid"]), is_shiny)

            if gif_path.exists():
                self._current_movie = QMovie(str(gif_path))
                self.lbl_sprite.setMovie(self._current_movie)
                self._current_movie.start()
            else:
                tag = "shiny" if is_shiny else "normal"
                fallback = BASE_DIR / "assets" / "sprites" / tag / f"{pk['species']}.png"
                if fallback.exists():
                    self.lbl_sprite.setPixmap(QPixmap(str(fallback)))
                else:
                    self.lbl_sprite.setText("No Sprite")
        except Exception as e:
            self.lbl_name_lvl.setText(f"ERROR READING PK3")

    def _send_to_editor(self):
        if self.selected_pk3_path:
            self.send_to_editor.emit(self.selected_pk3_path)
            QMessageBox.information(self, "Sent to Editor", "Loaded Pokémon into the Editor.\n\nSaving over it in the Editor will preserve its position in this Box.")

    def release_pokemon(self):
        if not self.selected_pk3_path or not Path(self.selected_pk3_path).exists():
            return

        pkmn_name = self.lbl_name_lvl.text().split(" (Lv.")[0]
        sound.play("menu_select")

        reply = QMessageBox.question(
            self, "Confirm Release",
            f"Are you sure you want to release {pkmn_name}?\n\nThis will permanently delete the file.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._snapshot(f"Release {pkmn_name}")
            self._legality_cache.pop(str(self.selected_pk3_path), None)
            Path(self.selected_pk3_path).unlink(missing_ok=True)
            self.current_box_layout.pop(str(self.selected_slot_idx), None)

            layout_path = self.pc_dir / f"Box{self.current_box_index}" / "layout.json"
            layout_path.write_text(json.dumps(self.current_box_layout))

            self._update_box_dropdown()
            self._refresh_grid_visuals()
            sound.play("pc_release")
            self._clear_selection()

    def send_to_trade_slot(self):
        if not self.selected_pk3_path: return

        slot2_dir = paths.SLOT2_DIR
        slot2_dir.mkdir(parents=True, exist_ok=True)

        existing_files = list(slot2_dir.glob("*.pk3"))
        if existing_files:
            try:
                pk_data = read_pk3_data(existing_files[0].read_bytes())
                occupant_name = pk_data.get("nickname", "A Pokémon")
            except:
                occupant_name = "A Pokémon"
            sound.play("pc_error")
            QMessageBox.warning(self, "Trade Slot Occupied", f"{occupant_name} is still being offered for Trade.\n\nPlease send it back to Bill's PC from the Trade Center before trying to trade another Pokémon.")
            return

        src = Path(self.selected_pk3_path)
        dest = slot2_dir / src.name
        self._snapshot(f"Send {src.name} to Trade Slot 2")
        self._legality_cache.pop(str(src), None)
        shutil.move(str(src), str(dest))

        self.current_box_layout.pop(str(self.selected_slot_idx), None)
        layout_path = self.pc_dir / f"Box{self.current_box_index}" / "layout.json"
        layout_path.write_text(json.dumps(self.current_box_layout))

        self.refresh_boxes()
        sound.play("pc_withdraw")

        self.send_to_slot2.emit(str(dest))
        QMessageBox.information(self, "Ready to Trade", f"Moved {src.stem} to the Trade Center.")

    def _add_to_box_layout(self, target_box: Path, filename: str):
        layout_file = target_box / "layout.json"
        layout = self._read_layout(target_box)
        cleaned: dict[str, str] = {}
        mapped: set[str] = set()
        for slot, name in layout.items():
            if not isinstance(slot, str) or not isinstance(name, str):
                continue
            if not slot.isdigit() or not 0 <= int(slot) < 30:
                continue
            if name in mapped or not (target_box / name).is_file():
                continue
            cleaned[str(int(slot))] = name
            mapped.add(name)

        for i in range(30):
            if str(i) not in cleaned:
                cleaned[str(i)] = filename
                layout_file.write_text(json.dumps(cleaned))
                return True
        return False

    def move_selected_pokemon(self):
        if not self.selected_pk3_path: return
        target_box_name = self.combo_target_box.currentData()
        if not target_box_name: return

        target_dir = self.pc_dir / target_box_name
        if target_dir.resolve() == (self.pc_dir / f"Box{self.current_box_index}").resolve():
            sound.play("pc_error")
            QMessageBox.information(
                self, "Already There",
                "That Pokémon is already in this box. Drag it to another slot to reorder it.",
            )
            return

        if len(list(target_dir.glob("*.pk3"))) >= 30:
            sound.play("pc_error")
            QMessageBox.warning(self, "Box Full", f"{target_box_name} is full! (30/30)\n\nPlease select a different box or create a new one.")
            return

        src = Path(self.selected_pk3_path)
        dest = target_dir / src.name
        self._snapshot(f"Move {src.name} to {target_box_name}")
        self._legality_cache.pop(str(src), None)

        counter = 1
        while dest.exists():
            dest = target_dir / f"{src.stem}_{counter}{src.suffix}"
            counter += 1

        shutil.move(str(src), str(dest))
        dest.touch()

        self._add_to_box_layout(target_dir, dest.name)

        self.current_box_layout.pop(str(self.selected_slot_idx), None)
        layout_path = self.pc_dir / f"Box{self.current_box_index}" / "layout.json"
        layout_path.write_text(json.dumps(self.current_box_layout))

        self.refresh_boxes()
        # The MOVE action lifts the selected Pokémon to another box; it uses
        # the same BOX02 cue as a drag lift.
        sound.play("pc_move")

    def store_pokemon(self, filepath: str, move_file: bool = False):
        src = Path(filepath)
        if not src.exists(): return
        self._snapshot("Deposit into Bill's PC")
        self._legality_cache.pop(str(src), None)

        box_num = 1
        while True:
            target_box = self.pc_dir / f"Box{box_num}"
            target_box.mkdir(exist_ok=True)
            count = len(list(target_box.glob("*.pk3")))
            if count < 30:
                break
            box_num += 1

        dest = target_box / src.name

        counter = 1
        while dest.exists():
            dest = target_box / f"{src.stem}_{counter}{src.suffix}"
            counter += 1

        if move_file:
            shutil.move(str(src), str(dest))
        else:
            shutil.copy2(str(src), str(dest))

        dest.touch()

        self._add_to_box_layout(target_box, dest.name)

        self.refresh_boxes()
        sound.play("pc_deposit")
