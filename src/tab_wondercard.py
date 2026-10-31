import os
import sys
import time
import json
import math
import struct
import subprocess
import zipfile
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import Qt, QProcess, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget, QCompleter, QSizePolicy
)

import core_data
import theme
import paths
from utils import (
    BASE_DIR, USER_NAME, acquire_admin, detect_wiphy, network_manager_active,
)

# Need the string decoder to read raw .wc3 files
from pkmds_editor import decode_gen3_str

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


# ---------------------------------------------------------------------------
# 2. Text Wrapping & Utility Functions
# ---------------------------------------------------------------------------
def _ensure_pokeldn_imports():
    root_str = str(SRC_DIR)
    ldn_str = str(SRC_DIR / "vendor" / "LDN")
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    if os.path.isdir(ldn_str) and ldn_str not in sys.path:
        sys.path.insert(0, ldn_str)

def format_gen3_npc_text(text: str, max_line_len: int = 35) -> str:
    """
    Formats text to fit into the authentic GBA 2-line text box.
    Automatically word wraps and inserts '\n' for newlines, and '\f'
    to signal the game to wait for the user to press 'A' and clear the box.
    """
    if not text:
        return ""

    text = text.replace("\\n", "\n")
    user_lines = text.split("\n")

    wrapped_lines = []
    for u_line in user_lines:
        u_line = u_line.strip()
        if not u_line:
            continue
        words = u_line.split(" ")
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= max_line_len:
                current += " " + word
            else:
                wrapped_lines.append(current)
                current = word
        if current:
            wrapped_lines.append(current)

    if not wrapped_lines:
        return ""

    chunks = []
    for i in range(0, len(wrapped_lines), 2):
        chunk = wrapped_lines[i:i+2]
        chunks.append("\n".join(chunk))

    return "\f".join(chunks)

# GBA Wonder Card 8 background palettes (bg_type 0..7)
WC_BG_THEMES = [
    ("0 — Warm Gold / Sunset",   "#f59e0b", "#fef3c7", "#b45309"),
    ("1 — Ocean Blue / Sapphire", "#3b82f6", "#dbeafe", "#1d4ed8"),
    ("2 — Meadow Green / Leaf",   "#10b981", "#d1fae5", "#047857"),
    ("3 — Crimson / FireRed",     "#ef4444", "#fee2e2", "#b91c1c"),
    ("4 — Amethyst / Psychic",    "#a855f7", "#f3e8ff", "#7e22ce"),
    ("5 — Cyan / Crystal Ice",    "#06b6d4", "#cffafe", "#0e7490"),
    ("6 — Slate / Steel Silver",  "#64748b", "#f1f5f9", "#334155"),
    ("7 — Royal Rose / Mythic",   "#ec4899", "#fce7f3", "#be185d"),
]


# ---------------------------------------------------------------------------
# 3. Authentic GBA Wonder Card Live Preview Canvas
# ---------------------------------------------------------------------------
class GBAWonderCardPreview(QWidget):
    """Paints an authentic Game Boy Advance 240x160 aspect-ratio Wonder Card preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # A 240x160 card needs room for its smallest type to remain readable.
        # The canvas is deliberately allowed to grow with the window; the
        # painter always keeps the card's 3:2 aspect ratio.
        self.setMinimumSize(360, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.title = "MYSTERY GIFT"
        self.subtitle = "Special Distribution"
        self.body_lines = [
            "Thank you for playing",
            "POKéMON FIRERED and LEAFGREEN!",
            "Pick up your gift from the",
            "deliveryman in any POKéMON CENTER.",
        ]
        self.footer1 = "POKéMON CENTER"
        self.footer2 = "Wireless Distribution"
        self.flag_id = 1003
        self.id_number = 0
        self.bg_type = 0
        self.icon_species = 412
        self.repeatable = False
        self.reward_summary = ""

    def update_card(
        self,
        *,
        title: str,
        subtitle: str,
        body_lines: list[str],
        footer1: str,
        footer2: str,
        flag_id: int,
        id_number: int = 0,
        bg_type: int = 0,
        icon_species: int = 412,
        repeatable: bool = False,
        reward_summary: str = "",
    ):
        self.title = title
        self.subtitle = subtitle
        self.body_lines = (list(body_lines) + ["", "", "", ""])[:4]
        self.footer1 = footer1
        self.footer2 = footer2
        self.flag_id = flag_id
        self.id_number = id_number
        self.bg_type = max(0, min(7, bg_type))
        self.icon_species = int(icon_species) if icon_species is not None else 412
        self.repeatable = repeatable
        self.reward_summary = reward_summary
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Draw at the native 240x160 GBA card resolution, uniformly scaled to
        # the preview panel.  A 3.8x ceiling keeps the card from ballooning
        # into a billboard on 1440p/4K displays while remaining crisp.
        painter.fillRect(self.rect(), QColor(theme.PANEL_ALT))
        scale = min((self.width() - 22) / 240.0, (self.height() - 22) / 160.0, 3.8)
        scale = max(0.8, scale)
        painter.save()
        painter.translate((self.width() - 240 * scale) / 2.0,
                          (self.height() - 160 * scale) / 2.0)
        painter.scale(scale, scale)

        _, accent_hex, _body_hex, header_hex = WC_BG_THEMES[self.bg_type]
        accent = QColor(accent_hex)
        header = QColor(header_hex)
        # The Wonder Card is a preview of a real GBA asset, so its paper and
        # ink stay fixed even while the surrounding application is dark.
        paper = QColor("#fff8e6")
        ink = QColor("#2b2b33")

        card = QRectF(1.5, 1.5, 237, 157)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 36, 52, 55))
        painter.drawRoundedRect(card.translated(1.5, 2.5), 5, 5)
        painter.setPen(QPen(header, 2.4))
        painter.setBrush(paper)
        painter.drawRoundedRect(card, 5, 5)
        painter.save()
        painter.setClipPath(self._rounded_path(card, 5))

        # Header banner.  The label, title and subtitle get three separate,
        # fixed-height bands so none of them can be clipped by the rounded
        # card edge at any preview scale.
        header_rect = QRectF(3, 3, 234, 38)
        grad = QLinearGradient(header_rect.topLeft(), header_rect.bottomLeft())
        grad.setColorAt(0.0, accent)
        grad.setColorAt(0.7, accent.darker(112))
        grad.setColorAt(1.0, header)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRect(header_rect)
        painter.setPen(QPen(QColor(theme.GOLD), 1.6))
        painter.drawLine(QPointF(3, 41.2), QPointF(237, 41.2))

        painter.setFont(theme.ui_font(6, gba=True))
        painter.setPen(QColor(255, 248, 230, 225))
        painter.drawText(QRectF(9, 4, 130, 9),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         "WONDER CARD")

        title = self.title or "(Empty Title)"
        title_size = 10
        title_font = theme.ui_font(title_size, gba=True, bold=True)
        metrics = QFontMetrics(title_font)
        while title_size > 7 and metrics.horizontalAdvance(title) > 126:
            title_size -= 1
            title_font = theme.ui_font(title_size, gba=True, bold=True)
            metrics = QFontMetrics(title_font)
        painter.setFont(title_font)
        painter.setPen(QColor("#fffdf4"))
        title = metrics.elidedText(title, Qt.TextElideMode.ElideRight, 126)
        painter.drawText(QRectF(9, 12, 126, 15),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         title)

        painter.setFont(theme.ui_font(7))
        painter.setPen(QColor(255, 248, 230, 235))
        sub = QFontMetrics(theme.ui_font(7)).elidedText(
            self.subtitle, Qt.TextElideMode.ElideRight, 126
        )
        painter.drawText(QRectF(9, 26, 126, 10),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         sub)

        disp_id = self.id_number if self.id_number > 0 else (self.flag_id % 100)
        stamp = QRectF(141, 8, 45, 11)
        painter.setPen(QPen(QColor(255, 253, 246, 120), 0.8))
        painter.setBrush(QColor(24, 32, 50, 150))
        painter.drawRoundedRect(stamp, 2.5, 2.5)
        painter.setFont(theme.ui_font(6, gba=True))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(stamp, Qt.AlignmentFlag.AlignCenter, f"No.{disp_id:02d} F{self.flag_id}")

        # Sprite window.  The 40x30 icon is composited after the card
        # transform, at a whole number of device pixels, so its source pixels
        # never land on fractional boundaries.  A 43x33 card-unit window
        # gives the artwork the same apparent footprint at 100% and 150%.
        icon_box = QRectF(189, 3, 47, 37)
        icon_inner = QRectF(192, 5, 43, 33)
        painter.setPen(QPen(QColor(255, 253, 246, 200), 1.2))
        painter.setBrush(QColor("#fff8e6"))
        painter.drawRoundedRect(icon_box, 3, 3)
        icon_file = BASE_DIR / "assets" / "icons" / f"{self.icon_species}.png"
        icon_pixmap = QPixmap(str(icon_file)) if icon_file.exists() else QPixmap()
        if icon_pixmap.isNull():
            painter.setFont(theme.ui_font(14, gba=True, bold=True))
            painter.setPen(QColor("#34477c"))
            icon_txt = "?" if self.icon_species >= 412 else f"{self.icon_species}"
            painter.drawText(icon_box, Qt.AlignmentFlag.AlignCenter, icon_txt)

        # Paper body with a faint Poké Ball watermark
        body_rect = QRectF(5, 42, 230, 84)
        painter.setPen(QPen(QColor("#e3d6b4"), 0.9))
        painter.setBrush(QColor("#fffdf4"))
        painter.drawRoundedRect(body_rect, 2.5, 2.5)

        painter.save()
        painter.setClipPath(self._rounded_path(body_rect, 2.5))
        painter.setOpacity(0.07)
        theme.draw_pokeball(painter, 203, 86, 35,
                            top=theme.NAVY, bottom=theme.NAVY,
                            outline=theme.NAVY, outline_width=1.2)
        painter.setOpacity(1.0)
        painter.restore()

        body_font = theme.ui_font(9, gba=True)
        painter.setFont(body_font)
        painter.setPen(ink)
        for idx, line in enumerate(self.body_lines[:4]):
            if not line:
                continue
            text = QFontMetrics(body_font).elidedText(
                line, Qt.TextElideMode.ElideRight, 210
            )
            painter.drawText(
                QRectF(10, 46 + idx * 18, 218, 15),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

        # Perforated ticket line
        painter.setPen(QPen(QColor("#cdbf9b"), 1))
        for x in range(8, 232, 7):
            painter.drawPoint(QPointF(x, 128.5))

        # Footer
        footer_rect = QRectF(3, 131, 234, 26)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f6ebcc"))
        painter.drawRect(footer_rect)
        painter.setPen(QPen(accent, 1.2))
        painter.drawLine(QPointF(3, 131), QPointF(237, 131))

        painter.setFont(theme.ui_font(8, gba=True, bold=True))
        painter.setPen(header)
        painter.drawText(QRectF(9, 133, 135, 10),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         QFontMetrics(theme.ui_font(8, gba=True, bold=True)).elidedText(
                             self.footer1, Qt.TextElideMode.ElideRight, 130))
        painter.setFont(theme.ui_font(7))
        painter.setPen(QColor("#4b4f5e"))
        painter.drawText(QRectF(9, 143, 135, 9),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         QFontMetrics(theme.ui_font(7)).elidedText(
                             self.footer2, Qt.TextElideMode.ElideRight, 130))

        pill = QRectF(166, 134, 64, 18)
        painter.setPen(QPen(header, 1))
        painter.setBrush(QColor("#e3f5e5") if self.repeatable else QColor("#e8effc"))
        painter.drawRoundedRect(pill, 3, 3)
        painter.setFont(theme.ui_font(6, gba=True, bold=True))
        painter.setPen(QColor("#2f7d4f") if self.repeatable else QColor("#26345c"))
        painter.drawText(
            pill, Qt.AlignmentFlag.AlignCenter,
            "REPEATABLE" if self.repeatable else "ONE-TIME",
        )

        painter.restore()  # card clip
        painter.setPen(QPen(header, 2.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(card, 5, 5)
        painter.restore()  # logical 240x160 transform

        if not icon_pixmap.isNull():
            self._draw_icon_overlay(
                painter, icon_pixmap, icon_inner, card_scale=scale
            )

    def _draw_icon_overlay(
        self,
        painter: QPainter,
        pixmap: QPixmap,
        icon_inner: QRectF,
        *,
        card_scale: float,
    ) -> None:
        """Blit the box icon at an exact whole-device-pixel multiplier.

        ``icon_inner`` is in the card's 240x160 coordinate space.  The card
        itself is scaled by ``card_scale`` and the window by its DPR; choosing
        an integer multiplier from that combined scale means the icon never
        inherits the card's fractional vector transform.
        """
        dpr = max(0.1, float(self.devicePixelRatioF()))
        device_scale = max(0.1, card_scale * dpr)
        avail_w = max(1.0, icon_inner.width() * device_scale)
        avail_h = max(1.0, icon_inner.height() * device_scale)
        source_w = max(1, pixmap.width())
        source_h = max(1, pixmap.height())
        step = max(
            1,
            int(math.floor(min(avail_w / source_w, avail_h / source_h) + 1e-6)),
        )
        draw_w = source_w * step
        draw_h = source_h * step

        # Center in the card, then convert to this widget's logical space.
        card_w = 240.0 * card_scale
        card_h = 160.0 * card_scale
        origin_x = (self.width() - card_w) / 2.0
        origin_y = (self.height() - card_h) / 2.0
        center_x = origin_x + icon_inner.center().x() * card_scale
        center_y = origin_y + icon_inner.center().y() * card_scale
        x_phys = round(center_x * dpr - draw_w / 2.0)
        y_phys = round(center_y * dpr - draw_h / 2.0)

        source_image = pixmap.toImage()
        source_image.setDevicePixelRatio(1.0)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(
            QRectF(
                x_phys / dpr, y_phys / dpr,
                draw_w / dpr, draw_h / dpr,
            ),
            source_image,
            QRectF(0, 0, source_w, source_h),
        )
        painter.restore()

    @staticmethod
    def _rounded_path(rect: QRectF, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path


# ---------------------------------------------------------------------------
# 4. Main WonderCardTab Widget
# ---------------------------------------------------------------------------
class WonderCardTab(QWidget):
    def __init__(self, parent_gui, editor_tab=None):
        super().__init__(parent_gui)
        self._ui_ready = False
        self.parent_gui = parent_gui
        self.editor_tab = editor_tab
        self.mg_proc: QProcess | None = None

        self.src_dir = SRC_DIR
        self.staging_pokegift = Path("/tmp/frlg_studio_active.pokegift")
        self.external_gift_file: str = ""

        self._registry_entries = {}
        self._build_ui()
        self._ui_ready = True
        self._load_pokeldn_registry()
        self._apply_custom_template("nugget_10")
        self.apply_theme()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(5, 5, 5, 5)
        root_layout.setSpacing(4)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter = self.splitter
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(9)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter, stretch=1)

        # ================= LEFT PANEL: STUDIO & PRESETS =================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(4)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.setObjectName("SubTabs")
        self.custom_page = QWidget()
        self.authentic_page = QWidget()
        self.janitor_page = QWidget()

        self.mode_tabs.addTab(self.custom_page, "CARD STUDIO")
        self.mode_tabs.addTab(self.authentic_page, "GAME EVENTS")
        self.mode_tabs.addTab(self.janitor_page, "FLAG JANITOR")
        self.mode_tabs.currentChanged.connect(self._on_mode_changed)

        self._build_custom_studio_page()
        self._build_authentic_events_page()
        self._build_janitor_page()
        left_layout.addWidget(self.mode_tabs, stretch=1)

        # Shared Distribution & Radio CCMP Rules
        shared_group = QGroupBox("Distribution && Radio Encryption Rules")
        shared_grid = QGridLayout(shared_group)
        shared_grid.setContentsMargins(8, 5, 8, 7)
        shared_grid.setSpacing(3)

        self.chk_repeatable = QCheckBox("Repeatable Delivery (Claim infinitely from Pokemon Center deliveryman)")
        self.chk_repeatable.setChecked(True)
        self.chk_repeatable.setStyleSheet("font-weight: bold; color: %s;" % theme.GREEN_DARK)
        self.chk_repeatable.toggled.connect(self._refresh_preview_and_validate)
        shared_grid.addWidget(self.chk_repeatable, 0, 0, 1, 4)

        shared_grid.addWidget(QLabel("Flag ID (1000-1019):"), 1, 0)
        self.spin_flag_id = QSpinBox()
        self.spin_flag_id.setRange(1000, 1019)
        self.spin_flag_id.setValue(1010)
        self.spin_flag_id.valueChanged.connect(self._refresh_preview_and_validate)
        shared_grid.addWidget(self.spin_flag_id, 1, 1)

        self.chk_auto_rotate_flag = QCheckBox("Auto-Rotate Flag ID on Start")
        self.chk_auto_rotate_flag.setChecked(True)
        shared_grid.addWidget(self.chk_auto_rotate_flag, 1, 2, 1, 2)

        shared_grid.addWidget(QLabel("Card Shareable:"), 2, 0)
        self.combo_shareable = theme.AppComboBox()
        self.combo_shareable.addItems(["never", "once", "always"])
        self.combo_shareable.setCurrentText("always")
        self.combo_shareable.currentTextChanged.connect(self._refresh_preview_and_validate)
        shared_grid.addWidget(self.combo_shareable, 2, 1)

        shared_grid.addWidget(QLabel("Block / Script Repeat:"), 2, 2)
        rep_box = QHBoxLayout()
        self.spin_block_repeat = QSpinBox()
        self.spin_block_repeat.setRange(1, 8)
        self.spin_block_repeat.setValue(3)
        self.spin_script_repeat = QSpinBox()
        self.spin_script_repeat.setRange(1, 8)
        self.spin_script_repeat.setValue(4)
        rep_box.addWidget(self.spin_block_repeat)
        rep_box.addWidget(self.spin_script_repeat)
        shared_grid.addLayout(rep_box, 2, 3)

        # Radio CCMP & Nonce Settings for mt7921e
        shared_grid.addWidget(QLabel("TX CCMP Mode:"), 3, 0)
        self.combo_tx_ccmp = theme.AppComboBox()
        self.combo_tx_ccmp.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.combo_tx_ccmp.setMinimumContentsLength(16)
        self.combo_tx_ccmp.addItems([
            "Config Default",
            "Skip encryption (TX HW)",
            "No skip (TX SW)",
        ])
        self.combo_tx_ccmp.setCurrentIndex(1)
        self.combo_tx_ccmp.setToolTip("--skip-encryption (HW/mac80211 TX)")
        shared_grid.addWidget(self.combo_tx_ccmp, 3, 1)

        shared_grid.addWidget(QLabel("RX CCMP Mode:"), 3, 2)
        self.combo_rx_ccmp = theme.AppComboBox()
        self.combo_rx_ccmp.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.combo_rx_ccmp.setMinimumContentsLength(16)
        self.combo_rx_ccmp.addItems([
            "Config Default",
            "Accept decrypted (RX HW)",
            "No accept (RX SW)",
        ])
        self.combo_rx_ccmp.setCurrentIndex(1)
        self.combo_rx_ccmp.setToolTip("--accept-decrypted-ccmp (HW RX)")
        shared_grid.addWidget(self.combo_rx_ccmp, 3, 3)
        shared_grid.setColumnStretch(1, 1)
        shared_grid.setColumnStretch(3, 1)

        self.chk_native_nonce = QCheckBox("--native-nonce-sequence")
        self.chk_native_nonce.setChecked(True)
        shared_grid.addWidget(self.chk_native_nonce, 4, 0, 1, 2)

        self.chk_session_first = QCheckBox("--session-response-first")
        self.chk_session_first.setChecked(False)
        shared_grid.addWidget(self.chk_session_first, 4, 2)

        self.chk_end_on_success = QCheckBox("Auto-Stop on Success")
        self.chk_end_on_success.setChecked(False)
        shared_grid.addWidget(self.chk_end_on_success, 4, 3)

        left_layout.addWidget(shared_group)
        splitter.addWidget(left_widget)

        # ================= RIGHT PANEL: PREVIEW & BROADCAST =================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        preview_group = QGroupBox("LIVE GBA WONDER CARD")
        preview_vbox = QVBoxLayout(preview_group)
        preview_vbox.setContentsMargins(8, 8, 8, 8)
        preview_vbox.setSpacing(6)

        self.preview_canvas = GBAWonderCardPreview()
        preview_vbox.addWidget(self.preview_canvas, stretch=1)

        self.lbl_validation = QLabel("Ready to compile Wonder Card")
        self.lbl_validation.setWordWrap(True)
        self.lbl_validation.setStyleSheet(
            "background-color: #f2ecd9; color: %s; padding: 5px 8px; border: 2px solid #c8bea3;"
            " border-radius: 6px; font-weight: bold; font-size: 12px;" % theme.INK_SOFT
        )
        preview_vbox.addWidget(self.lbl_validation)

        file_btn_row = QHBoxLayout()
        file_btn_row.setSpacing(5)
        btn_export = QPushButton("EXPORT .POKEGIFT")
        btn_export.clicked.connect(self.export_pokegift_dialog)
        btn_load_file = QPushButton("LOAD .POKEGIFT / .WC3")
        btn_load_file.clicked.connect(self.load_external_gift_file)
        self.btn_clear_file = QPushButton("CLEAR FILE")
        self.btn_clear_file.setProperty("role", "danger")
        self.btn_clear_file.setVisible(False)
        self.btn_clear_file.clicked.connect(self.clear_external_gift_file)
        file_btn_row.addWidget(btn_export)
        file_btn_row.addWidget(btn_load_file)
        file_btn_row.addWidget(self.btn_clear_file)
        preview_vbox.addLayout(file_btn_row)

        right_layout.addWidget(preview_group, 6)

        # Broadcast Status & Controls
        bcast_group = QGroupBox("WIRELESS BROADCAST")
        bcast_layout = QVBoxLayout(bcast_group)
        bcast_layout.setContentsMargins(8, 8, 8, 8)
        bcast_layout.setSpacing(6)

        self.lbl_bcast_state = QLabel("STANDBY — SELECT A CARD & CLICK START BROADCAST")
        self.lbl_bcast_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_bcast_state.setWordWrap(True)
        self.lbl_bcast_state.setStyleSheet(
            "background-color: #e8effc; color: %s; border: 2px solid #9db2dc;"
            " font-weight: bold; font-size: 12px; padding: 6px; border-radius: 6px;" % theme.NAVY_DARK
        )
        bcast_layout.addWidget(self.lbl_bcast_state)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(5)
        self.btn_start_mg = QPushButton("START BROADCAST")
        self.btn_start_mg.setProperty("role", "primary")
        self.btn_start_mg.setMinimumHeight(36)
        self.btn_start_mg.clicked.connect(self.start_broadcast)

        self.btn_stop_mg = QPushButton("STOP")
        self.btn_stop_mg.setProperty("role", "danger")
        self.btn_stop_mg.setMinimumHeight(36)
        self.btn_stop_mg.setEnabled(False)
        self.btn_stop_mg.clicked.connect(self.stop_broadcast)

        self.btn_reset_radio = QPushButton("RESET RADIO")
        self.btn_reset_radio.setProperty("role", "blue")
        self.btn_reset_radio.setMinimumHeight(36)
        self.btn_reset_radio.setToolTip("Reloads mt7921e and deletes stuck ldn/ldn-mon/ldn-tap interfaces")
        self.btn_reset_radio.clicked.connect(self.reset_wifi_radio)

        ctrl_row.addWidget(self.btn_start_mg, stretch=3)
        ctrl_row.addWidget(self.btn_stop_mg, stretch=1)
        ctrl_row.addWidget(self.btn_reset_radio, stretch=2)
        bcast_layout.addLayout(ctrl_row)

        self.mg_log = QTextEdit()
        self.mg_log.setReadOnly(True)
        self.mg_log.setStyleSheet(
            "QTextEdit { font-family: '%s'; font-size: 12px; background-color: #fffbe9;"
            " color: %s; border: 3px solid %s; border-radius: 9px; padding: 6px; }"
            % (theme.FONT_GBA, theme.INK, theme.NAVY)
        )
        bcast_layout.addWidget(self.mg_log, stretch=1)

        right_layout.addWidget(bcast_group, 4)
        splitter.addWidget(right_widget)
        splitter.setSizes([700, 480])

    # ------------------------------------------------------------------
    # Page 1: Custom Wonder Card Studio Builder
    # ------------------------------------------------------------------
    def _build_custom_studio_page(self):
        outer = QVBoxLayout(self.custom_page)
        outer.setContentsMargins(2, 2, 2, 2)

        # Dense but still comfortable at the app's 1180x820 minimum.  The
        # text keeps its full size; only the redundant padding is trimmed.
        self.custom_page.setStyleSheet(
            "QGroupBox { margin-top: 9px; padding-top: 2px; }"
            "QGroupBox::title { padding: 1px 8px; }"
            "QLineEdit, QComboBox, QSpinBox { min-height: 18px; padding: 1px 6px; }"
            "QCheckBox { min-height: 19px; }"
            "QPushButton { min-height: 20px; padding: 3px 8px; }"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(3)
        layout.setContentsMargins(3, 3, 3, 3)

        tpl_group = QGroupBox("QUICK CUSTOM TEMPLATES")
        tpl_grid = QGridLayout(tpl_group)
        tpl_grid.setContentsMargins(6, 6, 6, 6)
        tpl_grid.setSpacing(4)

        btn_t_nugget = QPushButton("NUGGET ×10")
        btn_t_nugget.clicked.connect(lambda: self._apply_custom_template("nugget_10"))
        btn_t_candy = QPushButton("RARE CANDY ×50")
        btn_t_candy.clicked.connect(lambda: self._apply_custom_template("rare_candy_50"))
        btn_t_mball = QPushButton("MASTER BALL ×10")
        btn_t_mball.clicked.connect(lambda: self._apply_custom_template("master_ball_10"))
        btn_t_aurora = QPushButton("AURORA")
        btn_t_aurora.clicked.connect(lambda: self._apply_custom_template("aurora_item"))
        btn_t_mystic = QPushButton("MYSTIC")
        btn_t_mystic.clicked.connect(lambda: self._apply_custom_template("mystic_item"))

        for idx, b in enumerate((btn_t_nugget, btn_t_candy, btn_t_mball, btn_t_aurora, btn_t_mystic)):
            b.setStyleSheet("font-size: 11px; padding: 4px 5px; min-height: 26px;")
            tpl_grid.addWidget(b, 0, idx)
            tpl_grid.setColumnStretch(idx, 1)
        layout.addWidget(tpl_group)

        disp_group = QGroupBox("Deliveryman Dispenser Payload")
        disp_grid = QGridLayout(disp_group)
        disp_grid.setContentsMargins(7, 6, 7, 7)
        disp_grid.setSpacing(4)

        disp_grid.addWidget(QLabel("Reward Type:"), 0, 0)
        self.combo_reward_kind = theme.AppComboBox()
        self.combo_reward_kind.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.combo_reward_kind.setMinimumContentsLength(22)
        self.combo_reward_kind.addItems([
            "Dispense Item (Any FRLG Item x Quantity)",
            "Dispense Pokemon (Species + Level + Held Item)",
        ])
        self.combo_reward_kind.currentIndexChanged.connect(self._on_reward_kind_changed)
        disp_grid.addWidget(self.combo_reward_kind, 0, 1, 1, 3)

        self.lbl_item_search = QLabel("Search / Filter Item:")
        disp_grid.addWidget(self.lbl_item_search, 1, 0)
        self.txt_item_filter = QLineEdit()
        self.txt_item_filter.setPlaceholderText("Type item name (e.g. Nugget, Rare Candy, TM26, AuroraTicket)...")
        self.txt_item_filter.textChanged.connect(self._filter_items_combo)
        disp_grid.addWidget(self.txt_item_filter, 1, 1, 1, 3)

        self.lbl_item_select = QLabel("Item to Dispense:")
        disp_grid.addWidget(self.lbl_item_select, 2, 0)
        self.combo_item = theme.AppComboBox()
        self.combo_item.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.combo_item.setMinimumContentsLength(22)
        self._populate_items_combo("")
        self.combo_item.currentIndexChanged.connect(self._refresh_preview_and_validate)
        disp_grid.addWidget(self.combo_item, 2, 1)

        self.lbl_item_qty = QLabel("Quantity:")
        disp_grid.addWidget(self.lbl_item_qty, 2, 2)
        self.spin_item_qty = QSpinBox()
        self.spin_item_qty.setRange(1, 999)
        self.spin_item_qty.setValue(10)
        self.spin_item_qty.valueChanged.connect(self._refresh_preview_and_validate)
        disp_grid.addWidget(self.spin_item_qty, 2, 3)

        self.chk_bonus_item = QCheckBox("Also dispense a 2nd item in the same visit:")
        self.chk_bonus_item.toggled.connect(self._refresh_preview_and_validate)
        disp_grid.addWidget(self.chk_bonus_item, 3, 0, 1, 2)

        self.combo_bonus_item = theme.AppComboBox()
        self.combo_bonus_item.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.combo_bonus_item.setMinimumContentsLength(18)
        for item_id in sorted(FULL_FRLG_ITEMS.keys()):
            self.combo_bonus_item.addItem(f"[{item_id:03d}] {FULL_FRLG_ITEMS[item_id]}", item_id)
        self.combo_bonus_item.currentIndexChanged.connect(self._refresh_preview_and_validate)
        disp_grid.addWidget(self.combo_bonus_item, 3, 2)

        self.spin_bonus_qty = QSpinBox()
        self.spin_bonus_qty.setRange(1, 999)
        self.spin_bonus_qty.setValue(1)
        self.spin_bonus_qty.valueChanged.connect(self._refresh_preview_and_validate)
        disp_grid.addWidget(self.spin_bonus_qty, 3, 3)

        self.lbl_poke_species = QLabel("Species ID (1-411):")
        self.combo_poke_species = theme.AppComboBox()
        self.combo_poke_species.setEditable(True)
        self.combo_poke_species.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.combo_poke_species.setMinimumContentsLength(18)
        self.combo_poke_species.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_poke_species.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.combo_poke_species.completer().setFilterMode(Qt.MatchFlag.MatchContains)

        for ndex, sname in sorted(POKEMON_NAMES.items()):
            self.combo_poke_species.addItem(f"#{ndex:03d} {sname}", ndex)

        # Set Default to 151 (Mew)
        idx_mew = self.combo_poke_species.findData(151)
        if idx_mew >= 0:
            self.combo_poke_species.setCurrentIndex(idx_mew)

        self.combo_poke_species.currentIndexChanged.connect(self._refresh_preview_and_validate)

        self.lbl_poke_level = QLabel("Level (1-100):")
        self.spin_poke_level = QSpinBox()
        self.spin_poke_level.setRange(1, 100)
        self.spin_poke_level.setValue(30)
        self.spin_poke_level.valueChanged.connect(self._refresh_preview_and_validate)

        self.chk_fateful = QCheckBox("Fateful Encounter Flag")
        self.chk_fateful.setChecked(True)
        self.chk_fateful.toggled.connect(self._refresh_preview_and_validate)

        disp_grid.addWidget(self.lbl_poke_species, 4, 0)
        disp_grid.addWidget(self.combo_poke_species, 4, 1)
        disp_grid.addWidget(self.lbl_poke_level, 4, 2)
        disp_grid.addWidget(self.spin_poke_level, 4, 3)
        disp_grid.addWidget(self.chk_fateful, 5, 0, 1, 2)

        btn_autofill = QPushButton("AUTO-WRITE CARD TEXT")
        btn_autofill.setProperty("role", "blue")
        btn_autofill.setToolTip("Fill the card text from the selected reward")
        btn_autofill.clicked.connect(self._autofill_card_from_reward)
        disp_grid.addWidget(btn_autofill, 5, 2, 1, 2)

        layout.addWidget(disp_group)

        card_group = QGroupBox("Wonder Card Text && Visual Theme (Max 39 Bytes per Line)")
        card_grid = QGridLayout(card_group)
        card_grid.setContentsMargins(7, 6, 7, 7)
        card_grid.setHorizontalSpacing(8)
        card_grid.setVerticalSpacing(2)
        card_grid.setColumnStretch(1, 1)
        card_grid.setColumnStretch(3, 1)

        def add_card_field(row: int, col: int, label: str, widget: QWidget, span: int = 1) -> None:
            field_lbl = QLabel(label)
            field_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            card_grid.addWidget(field_lbl, row, col)
            card_grid.addWidget(widget, row, col + 1, 1, span)

        self.txt_title = QLineEdit()
        self.txt_title.setMaxLength(39)
        self.txt_title.textChanged.connect(self._refresh_preview_and_validate)
        add_card_field(0, 0, "Card Title:", self.txt_title)

        self.txt_subtitle = QLineEdit()
        self.txt_subtitle.setMaxLength(39)
        self.txt_subtitle.textChanged.connect(self._refresh_preview_and_validate)
        add_card_field(0, 2, "Card Subtitle:", self.txt_subtitle)

        self.txt_body_lines = []
        for i in range(4):
            le = QLineEdit()
            le.setMaxLength(39)
            le.setPlaceholderText(f"Body Line {i + 1} (max 39 chars)...")
            le.textChanged.connect(self._refresh_preview_and_validate)
            self.txt_body_lines.append(le)
            add_card_field(1 + i // 2, 2 * (i % 2), f"Body Line {i + 1}:", le)

        self.txt_footer1 = QLineEdit()
        self.txt_footer1.setMaxLength(39)
        self.txt_footer1.textChanged.connect(self._refresh_preview_and_validate)
        add_card_field(3, 0, "Footer Line 1:", self.txt_footer1)

        self.txt_footer2 = QLineEdit()
        self.txt_footer2.setMaxLength(39)
        self.txt_footer2.textChanged.connect(self._refresh_preview_and_validate)
        add_card_field(3, 2, "Footer Line 2:", self.txt_footer2)

        self.combo_bg = theme.AppComboBox()
        for label, *_ in WC_BG_THEMES:
            self.combo_bg.addItem(label)
        self.combo_bg.currentIndexChanged.connect(self._refresh_preview_and_validate)
        add_card_field(4, 0, "Card Color:", self.combo_bg)

        self.combo_icon_species = theme.AppComboBox()
        self.combo_icon_species.setEditable(True)
        self.combo_icon_species.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.combo_icon_species.setMinimumContentsLength(16)
        self.combo_icon_species.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_icon_species.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.combo_icon_species.completer().setFilterMode(Qt.MatchFlag.MatchContains)

        self.combo_icon_species.addItem("[412] ? (Mystery Gift Box)", 412)
        for ndex, sname in sorted(POKEMON_NAMES.items()):
            self.combo_icon_species.addItem(f"[{ndex:03d}] {sname}", ndex)

        self.combo_icon_species.currentIndexChanged.connect(self._refresh_preview_and_validate)
        add_card_field(4, 2, "Icon Species:", self.combo_icon_species)

        self.txt_intro_msg = QLineEdit()
        self.txt_intro_msg.setText("Good day, {PLAYER}!\nWe have received a special gift for you!")
        self.txt_intro_msg.textChanged.connect(self._refresh_preview_and_validate)
        add_card_field(5, 0, "NPC Intro Dialogue:", self.txt_intro_msg, span=3)

        self.txt_done_msg = QLineEdit()
        self.txt_done_msg.setText("You already received this MYSTERY GIFT.\nPlease look forward to future gifts!")
        self.txt_done_msg.textChanged.connect(self._refresh_preview_and_validate)
        add_card_field(6, 0, "NPC Completed Text:", self.txt_done_msg, span=3)

        layout.addWidget(card_group)
        layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        self._on_reward_kind_changed(0)

    # ------------------------------------------------------------------
    # Page 2: Authentic & Official Game Events (pokeldn Registry)
    # ------------------------------------------------------------------
    def _build_authentic_events_page(self):
        layout = QVBoxLayout(self.authentic_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        marquee_group = QGroupBox("MARQUEE NINTENDO EVENTS")
        marquee_grid = QGridLayout(marquee_group)
        marquee_grid.setSpacing(6)

        btn_deoxys = QPushButton("AURORA TICKET — DEOXYS")
        btn_deoxys.setProperty("role", "blue")
        btn_deoxys.setToolTip("AuroraTicket — Deoxys (Birth Island)")
        btn_deoxys.clicked.connect(lambda: self._select_authentic_keyword("aurora"))

        btn_lugia = QPushButton("MYSTIC TICKET — LUGIA & HO-OH")
        btn_lugia.setProperty("role", "accent")
        btn_lugia.setToolTip("MysticTicket — Lugia and Ho-Oh (Navel Rock)")
        btn_lugia.clicked.connect(lambda: self._select_authentic_keyword("mystic"))

        btn_altering = QPushButton("ALTERING CAVE OUTBREAK")
        btn_altering.setToolTip("Altering Cave Event (Outbreak)")
        btn_altering.clicked.connect(lambda: self._select_authentic_keyword("altering"))

        btn_beast = QPushButton("LEGENDARY CUTSCENE GIFT")
        btn_beast.setToolTip("Legendary cutscene / special gift")
        btn_beast.clicked.connect(lambda: self._select_authentic_keyword("beast"))

        marquee_grid.addWidget(btn_deoxys, 0, 0)
        marquee_grid.addWidget(btn_lugia, 0, 1)
        marquee_grid.addWidget(btn_altering, 1, 0)
        marquee_grid.addWidget(btn_beast, 1, 1)
        layout.addWidget(marquee_group)

        reg_group = QGroupBox("ALL REGISTERED POKELDN DISTRIBUTIONS")
        reg_layout = QVBoxLayout(reg_group)

        self.combo_authentic = theme.AppComboBox()
        self.combo_authentic.currentIndexChanged.connect(self._on_authentic_selected)
        reg_layout.addWidget(self.combo_authentic)

        self.txt_authentic_info = QTextEdit()
        self.txt_authentic_info.setReadOnly(True)
        self.txt_authentic_info.setMaximumHeight(130)
        reg_layout.addWidget(self.txt_authentic_info)

        btn_copy_to_studio = QPushButton("LOAD SELECTED CARD INTO STUDIO")
        btn_copy_to_studio.setProperty("role", "blue")
        btn_copy_to_studio.clicked.connect(self._copy_authentic_to_studio)
        reg_layout.addWidget(btn_copy_to_studio)

        layout.addWidget(reg_group)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Page 3: Flag & Event Janitor
    # ------------------------------------------------------------------
    def _build_janitor_page(self):
        layout = QVBoxLayout(self.janitor_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        janitor_group = QGroupBox("SAVE FILE FLAG & EVENT JANITOR")
        # The title plate is 29 px tall; a 24 px margin clipped its top edge.
        janitor_group.setStyleSheet(
            "QGroupBox { margin-top: 32px; padding-top: 6px; }"
            "QGroupBox::title { font-size: 15px; padding: 3px 10px; }"
        )
        j_layout = QVBoxLayout(janitor_group)
        j_layout.setContentsMargins(12, 12, 12, 12)
        j_layout.setSpacing(10)

        self.lbl_desc = QLabel(
            "This utility generates a clean, repeatable Wonder Card that clears event delivery flags "
            "upon speaking to the Pokémon Center 2F Deliveryman. Use this to unblock your save file "
            "slots if you have reached your Wonder Card limit."
        )
        self.lbl_desc.setWordWrap(True)
        # A wrapped QLabel's own size hint cannot be trusted inside a nested
        # QGroupBox; without this floor the third line was cropped away.
        self.lbl_desc.setMinimumHeight(68)
        self.lbl_desc.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.lbl_desc.setStyleSheet("color: %s; font-size: 14px;" % theme.INK_SOFT)
        j_layout.addWidget(self.lbl_desc)

        self.chk_clear_wc_flags = QCheckBox("Wipe All Standard Wonder Card Delivery Flags (1000–1019)")
        self.chk_clear_wc_flags.setChecked(True)
        self.chk_clear_wc_flags.setStyleSheet("font-weight: bold; color: %s; font-size: 14px;" % theme.GREEN_DARK)
        self.chk_clear_wc_flags.toggled.connect(self._refresh_preview_and_validate)
        j_layout.addWidget(self.chk_clear_wc_flags)

        layout.addWidget(janitor_group)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Item Filtering & Helpers
    # ------------------------------------------------------------------
    def _populate_items_combo(self, filter_text: str):
        current_id = self.combo_item.currentData()
        self.combo_item.blockSignals(True)
        self.combo_item.clear()
        q = filter_text.strip().lower()
        for item_id in sorted(FULL_FRLG_ITEMS.keys()):
            name = FULL_FRLG_ITEMS[item_id]
            label = f"[{item_id:03d}] {name}"
            if not q or q in label.lower():
                self.combo_item.addItem(label, item_id)
        if current_id is not None:
            idx = self.combo_item.findData(current_id)
            if idx >= 0:
                self.combo_item.setCurrentIndex(idx)
        self.combo_item.blockSignals(False)

    def _filter_items_combo(self, text: str):
        self._populate_items_combo(text)
        self._refresh_preview_and_validate()

    def _on_reward_kind_changed(self, idx: int):
        is_item = (idx == 0)
        for w in (
            self.lbl_item_search, self.txt_item_filter, self.lbl_item_select,
            self.combo_item, self.lbl_item_qty, self.spin_item_qty,
            self.chk_bonus_item, self.combo_bonus_item, self.spin_bonus_qty
        ):
            w.setVisible(is_item)
        for w in (
            self.lbl_poke_species, self.combo_poke_species,
            self.lbl_poke_level, self.spin_poke_level, self.chk_fateful
        ):
            w.setVisible(not is_item)
        self._refresh_preview_and_validate()

    def _apply_custom_template(self, preset_key: str):
        self.mode_tabs.setCurrentIndex(0)
        self.combo_reward_kind.setCurrentIndex(0)
        self.chk_bonus_item.setChecked(False)
        self.txt_item_filter.clear()

        if preset_key == "nugget_10":
            self._set_selected_item(110, 10)
            self.chk_repeatable.setChecked(True)
            self.combo_bg.setCurrentIndex(0)
            self._set_card_strings(
                "NUGGET GIFT",
                "10x Nugget Delivery",
                [
                    "A special delivery of 10x",
                    "NUGGET has arrived!",
                    "Speak to the deliveryman in any",
                    "POKéMON CENTER to claim your gift.",
                ],
                "POKéMON CENTER",
                "Custom Wonder Card",
            )
        elif preset_key == "rare_candy_50":
            self._set_selected_item(68, 50)
            self.chk_repeatable.setChecked(True)
            self.combo_bg.setCurrentIndex(1)
            self._set_card_strings(
                "RARE CANDY BUNDLE",
                "50x Level-Up Candies",
                [
                    "Power up your party with a bundle",
                    "of 50 RARE CANDIES!",
                    "Pick them up from the deliveryman",
                    "on the 2nd floor of POKéMON CENTER.",
                ],
                "TRAINER SUPPLY DROP",
                "Repeatable Gift",
            )
        elif preset_key == "master_ball_10":
            self._set_selected_item(1, 10)
            self.chk_repeatable.setChecked(True)
            self.combo_bg.setCurrentIndex(4)
            self._set_card_strings(
                "MASTER BALL SUPPLY",
                "10x Ultimate Poké Balls",
                [
                    "Catch any wild POKéMON without",
                    "fail using these 10 MASTER BALLS!",
                    "Speak to the green deliveryman in",
                    "any POKéMON CENTER to receive them.",
                ],
                "SILPH CO. SPECIAL",
                "Repeatable Gift",
            )
        elif preset_key == "aurora_item":
            self._set_selected_item(371, 1)
            self.chk_repeatable.setChecked(False)
            self.combo_bg.setCurrentIndex(3)
            self._set_card_strings(
                "AURORA TICKET",
                "For Birth Island",
                [
                    "A ticket required to board the",
                    "ferry to BIRTH ISLAND.",
                    "Pick it up from the deliveryman",
                    "at any POKéMON CENTER.",
                ],
                "VERMILION PORT FERRY",
                "Official Event Item",
            )
        elif preset_key == "mystic_item":
            self._set_selected_item(370, 1)
            self.chk_repeatable.setChecked(False)
            self.combo_bg.setCurrentIndex(4)
            self._set_card_strings(
                "MYSTIC TICKET",
                "For Navel Rock",
                [
                    "A ticket required to board the",
                    "ferry to NAVEL ROCK.",
                    "Pick it up from the deliveryman",
                    "at any POKéMON CENTER.",
                ],
                "VERMILION PORT FERRY",
                "Official Event Item",
            )
        self._refresh_preview_and_validate()

    def _set_selected_item(self, item_id: int, qty: int):
        idx = self.combo_item.findData(item_id)
        if idx >= 0:
            self.combo_item.setCurrentIndex(idx)
        self.spin_item_qty.setValue(qty)

    def _set_card_strings(self, title: str, subtitle: str, body: list[str], f1: str, f2: str):
        self.txt_title.setText(title[:39])
        self.txt_subtitle.setText(subtitle[:39])
        padded = (list(body) + ["", "", "", ""])[:4]
        for le, line in zip(self.txt_body_lines, padded):
            le.setText(line[:39])
        self.txt_footer1.setText(f1[:39])
        self.txt_footer2.setText(f2[:39])

    def _autofill_card_from_reward(self):
        if self.combo_reward_kind.currentIndex() == 0:
            item_id = self.combo_item.currentData() or 110
            qty = self.spin_item_qty.value()
            item_name = FULL_FRLG_ITEMS.get(item_id, f"Item #{item_id}").upper()
            self._set_card_strings(
                f"{item_name} GIFT"[:39],
                f"{qty}x {FULL_FRLG_ITEMS.get(item_id, 'Item')} Delivery"[:39],
                [
                    f"A special delivery of {qty}x",
                    f"{item_name} has arrived!",
                    "Speak to the deliveryman in any",
                    "POKéMON CENTER to claim your gift.",
                ],
                "POKéMON CENTER",
                "Custom Wonder Card",
            )
        else:
            sp = int(self.combo_poke_species.currentData() or 151)
            lv = self.spin_poke_level.value()
            idx = self.combo_icon_species.findData(sp)
            if idx >= 0:
                self.combo_icon_species.setCurrentIndex(idx)
            self._set_card_strings(
                f"POKéMON #{sp:03d} GIFT",
                f"Special Lv. {lv} Partner",
                [
                    f"A special Lv. {lv} POKéMON (#{sp:03d})",
                    "is waiting for you!",
                    "Make space in your party and talk",
                    "to the POKéMON CENTER deliveryman.",
                ],
                "POKéMON CENTER",
                "Special Distribution",
            )
        self._refresh_preview_and_validate()

    # ------------------------------------------------------------------
    # pokeldn Registry Loading & Authentic Presets
    # ------------------------------------------------------------------
    def _load_pokeldn_registry(self):
        self.combo_authentic.blockSignals(True)
        self.combo_authentic.clear()
        self._registry_entries.clear()
        try:
            _ensure_pokeldn_imports()
            from pokeldn.frlg.gift import gift_registry
            reg = gift_registry.GIFT_REGISTRY
            for slug in reg.live_choices:
                entry = reg.entry(slug)
                self._registry_entries[slug] = entry
                defn = getattr(entry, "definition", None)
                title = defn.card.title if (defn and hasattr(defn, "card")) else slug
                self.combo_authentic.addItem(f"{slug}  —  [{title}]", slug)
        except Exception as exc:
            self.combo_authentic.addItem(f"(Registry load warning: {exc})", "")
        self.combo_authentic.blockSignals(False)

    def _select_authentic_keyword(self, keyword: str):
        self.mode_tabs.setCurrentIndex(1)
        kw = keyword.lower()
        for i in range(self.combo_authentic.count()):
            slug = str(self.combo_authentic.itemData(i) or "").lower()
            text = self.combo_authentic.itemText(i).lower()
            if kw in slug or kw in text:
                self.combo_authentic.setCurrentIndex(i)
                self._on_authentic_selected()
                return
        if "aurora" in kw:
            self._apply_custom_template("aurora_item")
        elif "mystic" in kw:
            self._apply_custom_template("mystic_item")

    def _on_authentic_selected(self):
        if not self._ui_ready:
            return
        slug = self.combo_authentic.currentData()
        entry = self._registry_entries.get(slug)
        if not entry:
            return
        defn = getattr(entry, "definition", None)
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        if defn and hasattr(defn, "card"):
            c = defn.card
            self.spin_flag_id.blockSignals(True)
            self.spin_flag_id.setValue(c.default_flag_id)
            self.spin_flag_id.blockSignals(False)
            is_rep = getattr(defn.event, "repeatable", False)
            self.chk_repeatable.blockSignals(True)
            self.chk_repeatable.setChecked(bool(is_rep))
            self.chk_repeatable.blockSignals(False)
            self.txt_authentic_info.setPlainText(
                f"Slug: {slug}\n"
                f"Title: {c.title} | Subtitle: {c.subtitle}\n"
                f"Default Flag ID: {c.default_flag_id} | Repeatable: {is_rep}\n"
                f"Summary: {summary}\n"
                f"Body:\n  " + "\n  ".join(c.body)
            )
        else:
            self.txt_authentic_info.setPlainText(
                f"Slug: {slug}\nSpecial procedural/Dynamic pokeldn gift.\n{summary}"
            )
        self._refresh_preview_and_validate()

    def _copy_authentic_to_studio(self):
        slug = self.combo_authentic.currentData()
        entry = self._registry_entries.get(slug)
        defn = getattr(entry, "definition", None) if entry else None
        if not defn or not hasattr(defn, "card"):
            QMessageBox.information(
                self, "Procedural Gift",
                "This gift generates native/procedural code on the fly and must be run from the Authentic tab."
            )
            return
        c = defn.card
        self._set_card_strings(c.title, c.subtitle, list(c.body), c.footer1, c.footer2)
        self.combo_bg.setCurrentIndex(max(0, min(7, c.bg_type)))

        idx = self.combo_icon_species.findData(c.icon_species)
        if idx >= 0:
            self.combo_icon_species.setCurrentIndex(idx)

        self.spin_flag_id.setValue(c.default_flag_id)
        self.txt_intro_msg.setText(defn.intro_message.replace("\n", "\\n"))
        self.mode_tabs.setCurrentIndex(0)
        self._refresh_preview_and_validate()

    def _on_mode_changed(self, _idx: int):
        self._refresh_preview_and_validate()

    def _set_validation(self, text: str, kind: str = "neutral"):
        colours = {
            "neutral": (theme.PANEL_ALT, theme.INK_SOFT, theme.BORDER_SOFT),
            "info": (theme.BLUE_LIGHT, theme.NAVY_DARK, theme.BLUE),
            "ok": (theme.GREEN_LIGHT, theme.GREEN_DARK, theme.GREEN),
            "bad": (theme.RED_LIGHT, theme.RED_DARK, theme.RED),
        }
        bg, fg, border = colours.get(kind, colours["neutral"])
        self._validation_text = text
        self._validation_kind = kind
        self.lbl_validation.setText(text)
        self.lbl_validation.setStyleSheet(
            "background-color: %s; color: %s; padding: 6px 8px; border: 2px solid %s;"
            " border-radius: %spx; font-weight: bold; font-size: 12px;"
            % (bg, fg, border, theme.CONTROL_RADIUS)
        )

    def _set_bcast_state(self, text: str, kind: str = "info"):
        colours = {
            "info": (theme.BLUE_LIGHT, theme.NAVY_DARK, theme.BLUE),
            "wait": (theme.PANEL_ALT, theme.ORANGE_DARK, theme.GOLD),
            "ok": (theme.GREEN_LIGHT, theme.GREEN_DARK, theme.GREEN),
            "bad": (theme.RED_LIGHT, theme.RED_DARK, theme.RED),
            "neutral": (theme.PANEL_ALT, theme.INK_SOFT, theme.BORDER_SOFT),
        }
        bg, fg, border = colours.get(kind, colours["info"])
        self._bcast_text = text
        self._bcast_kind = kind
        self.lbl_bcast_state.setText(text)
        self.lbl_bcast_state.setStyleSheet(
            "background-color: %s; color: %s; border: 2px solid %s;"
            " font-weight: bold; font-size: 12px; padding: 7px; border-radius: %spx;"
            % (bg, fg, border, theme.CONTROL_RADIUS)
        )

    def apply_theme(self):
        """Refresh the Wonder Card shell after a system-wide theme change.

        The card itself keeps its fixed GBA paper/ink so it remains a faithful
        preview; only the surrounding studio chrome changes.
        """
        self.chk_repeatable.setStyleSheet("font-weight: bold; color: %s;" % theme.GREEN_DARK)
        self.chk_clear_wc_flags.setStyleSheet(
            "font-weight: bold; color: %s; font-size: 13px;" % theme.GREEN_DARK
        )
        self.lbl_desc.setStyleSheet("color: %s; font-size: 13px;" % theme.INK_SOFT)
        self.mg_log.setStyleSheet(
            "QTextEdit { font-family: '%s'; font-size: 12px; background-color: %s;"
            " color: %s; border: 3px solid %s; border-radius: %spx; padding: 7px; }"
            % (theme.FONT_GBA, theme.FIELD, theme.INK, theme.NAVY, theme.PANEL_RADIUS)
        )
        if hasattr(self, "_bcast_text"):
            self._set_bcast_state(self._bcast_text, getattr(self, "_bcast_kind", "info"))
        else:
            self._set_bcast_state(
                "STANDBY — SELECT A CARD & CLICK START BROADCAST", "info"
            )
        self.preview_canvas.update()
        if not getattr(self, "_ui_ready", False):
            return
        if self.external_gift_file:
            self._set_validation(
                f"External File Override Active: {Path(self.external_gift_file).name}", "info"
            )
        else:
            self._refresh_preview_and_validate()

    # ------------------------------------------------------------------
    # Building & Validating WonderGift via pokeldn.frlg.gift.gift_composer
    # ------------------------------------------------------------------
    def _build_current_wondergift(self):
        _ensure_pokeldn_imports()
        from pokeldn.frlg.gift import gift_composer as gc
        from pokeldn.frlg.gift.wonder_card import GIFT_BEAST_CUTSCENE

        flag_id = self.spin_flag_id.value()
        repeatable = self.chk_repeatable.isChecked()
        shareable = self.combo_shareable.currentText()

        if self.mode_tabs.currentIndex() == 2:
            stages = []
            if self.chk_clear_wc_flags.isChecked():
                clear_actions = [gc.ClearFlag(flag=f) for f in range(1000, 1020)]
                stages.append(gc.DeliveryStage(actions=tuple(clear_actions)))
            stages.append(gc.DeliveryStage(gc.Message("All Wonder Card delivery flags have been wiped clean!")))

            card_spec = gc.WonderCardSpec(
                icon_species=412,
                title="FLAG JANITOR",
                subtitle="Save File Utility",
                body=("Clears Wonder Card delivery flags", "so you can receive new gifts!", "", ""),
                footer1="POKéMON CENTER",
                footer2="Save State Utility",
                bg_type=0,
                card_type=gc.CARD_TYPE_GIFT,
                default_flag_id=flag_id,
            )
            wg = gc.WonderGift(
                slug=GIFT_BEAST_CUTSCENE,
                card=card_spec,
                intro_message=format_gen3_npc_text("Hello! I have a maintenance utility gift for your save file."),
                event=gc.GiftSpec(repeatable=True, shareable=shareable),
                delivery=gc.DeliveryPlan(delivery=tuple(stages)),
                completed_message=format_gen3_npc_text("Your save file flags are fully cleared and ready for new events!"),
            )
            gc.validate_definition(wg, flag_id=flag_id)
            return wg

        if self.mode_tabs.currentIndex() == 1:
            slug = self.combo_authentic.currentData()
            entry = self._registry_entries.get(slug)
            defn = getattr(entry, "definition", None) if entry else None
            if defn is not None and isinstance(defn.event, gc.GiftSpec):
                modified_event = replace(defn.event, repeatable=repeatable, shareable=shareable)
                modified_card = replace(defn.card, default_flag_id=flag_id)
                updated = replace(defn, card=modified_card, event=modified_event)
                gc.validate_definition(updated, flag_id=flag_id)
                return updated
            return None

        body_tuple = tuple(le.text().strip() for le in self.txt_body_lines if le.text().strip())
        if not body_tuple:
            body_tuple = ("Thank you for playing!",)

        icon_val = self.combo_icon_species.currentData()
        icon_num = int(icon_val) if icon_val is not None else 412

        card_spec = gc.WonderCardSpec(
            icon_species=icon_num,
            title=self.txt_title.text().strip() or "MYSTERY GIFT",
            subtitle=self.txt_subtitle.text().strip(),
            body=body_tuple,
            footer1=self.txt_footer1.text().strip(),
            footer2=self.txt_footer2.text().strip(),
            id_number=0,
            bg_type=self.combo_bg.currentIndex(),
            card_type=gc.CARD_TYPE_GIFT,
            default_flag_id=flag_id,
        )

        stages = []
        if self.combo_reward_kind.currentIndex() == 0:
            item_id = int(self.combo_item.currentData() or 110)
            qty = int(self.spin_item_qty.value())
            stages.append(gc.DeliveryStage(gc.GiveItem(item=item_id, quantity=qty)))
            if self.chk_bonus_item.isChecked():
                b_id = int(self.combo_bonus_item.currentData() or 1)
                b_qty = int(self.spin_bonus_qty.value())
                stages.append(gc.DeliveryStage(gc.GiveItem(item=b_id, quantity=b_qty)))
        else:
            sp = int(self.combo_poke_species.currentData() or 151)
            lv = int(self.spin_poke_level.value())
            item_id = int(self.combo_item.currentData() or 0)
            stages.append(
                gc.DeliveryStage(
                    gc.GivePokemon(
                        species=sp,
                        level=lv,
                        held_item=item_id,
                        fateful_encounter=self.chk_fateful.isChecked(),
                    )
                )
            )

        intro_raw = self.txt_intro_msg.text()
        done_raw = self.txt_done_msg.text()

        intro_text = format_gen3_npc_text(intro_raw) if intro_raw.strip() else format_gen3_npc_text("Here is your gift!")
        done_text = format_gen3_npc_text(done_raw) if done_raw.strip() else format_gen3_npc_text(gc.DEFAULT_COMPLETED_MESSAGE)

        wg = gc.WonderGift(
            slug=GIFT_BEAST_CUTSCENE,
            card=card_spec,
            intro_message=intro_text,
            event=gc.GiftSpec(repeatable=repeatable, shareable=shareable),
            delivery=gc.DeliveryPlan(delivery=tuple(stages)),
            completed_message=done_text,
        )
        gc.validate_definition(wg, flag_id=flag_id)
        return wg

    def _refresh_preview_and_validate(self):
        if not getattr(self, "_ui_ready", False):
            return

        flag_id = self.spin_flag_id.value()
        repeatable = self.chk_repeatable.isChecked()

        # ONLY update the canvas from the UI if we DO NOT have an external file override loaded
        if not self.external_gift_file:
            if self.mode_tabs.currentIndex() == 2:
                self.preview_canvas.update_card(
                    title="FLAG JANITOR",
                    subtitle="Save File Utility",
                    body_lines=["Clears Wonder Card delivery flags", "so you can receive new gifts!", "", ""],
                    footer1="POKéMON CENTER",
                    footer2="Save State Utility",
                    flag_id=flag_id,
                    bg_type=0,
                    icon_species=412,
                    repeatable=True,
                )
            elif self.mode_tabs.currentIndex() == 1:
                slug = self.combo_authentic.currentData()
                entry = self._registry_entries.get(slug)
                defn = getattr(entry, "definition", None) if entry else None
                if defn and hasattr(defn, "card"):
                    c = defn.card
                    self.preview_canvas.update_card(
                        title=c.title,
                        subtitle=c.subtitle,
                        body_lines=list(c.body),
                        footer1=c.footer1,
                        footer2=c.footer2,
                        flag_id=flag_id,
                        id_number=c.id_number,
                        bg_type=c.bg_type,
                        icon_species=c.icon_species,
                        repeatable=repeatable,
                    )
            else:
                icon_val = self.combo_icon_species.currentData()
                icon_num = int(icon_val) if icon_val is not None else 412
                self.preview_canvas.update_card(
                    title=self.txt_title.text(),
                    subtitle=self.txt_subtitle.text(),
                    body_lines=[le.text() for le in self.txt_body_lines],
                    footer1=self.txt_footer1.text(),
                    footer2=self.txt_footer2.text(),
                    flag_id=flag_id,
                    bg_type=self.combo_bg.currentIndex(),
                    icon_species=icon_num,
                    repeatable=repeatable,
                )

        try:
            # If an external file is active, just confirm it and bail out of validation
            if self.external_gift_file:
                self._set_validation(
                    f"External File Override Active: {Path(self.external_gift_file).name}", "info"
                )
                return

            _ensure_pokeldn_imports()
            from pokeldn.frlg.gift import gift_composer as gc

            wg = self._build_current_wondergift()
            if wg is not None:
                dist = gc.compile_definition(wg, flag_id=flag_id)
                ram_len = len(dist.ram_script)
                self._set_validation(
                    f"Valid Wonder Card — Compiled RAM Script: {ram_len} / {gc.MAX_RAM_SCRIPT_SIZE} bytes (Flag {flag_id})",
                    "ok",
                )
            else:
                slug = self.combo_authentic.currentData()
                self._set_validation(
                    f"Authentic Built-In Gift Ready: --gift {slug} (Flag {flag_id})", "ok"
                )
        except Exception as exc:
            self._set_validation(f"Validation Issue: {exc}", "bad")

    # ------------------------------------------------------------------
    # Exporting / Loading .pokegift Files
    # ------------------------------------------------------------------
    def _compile_to_pokegift_file(self, target_path: Path) -> Path:
        _ensure_pokeldn_imports()
        from pokeldn import gifts
        from pokeldn.frlg import config as configmod
        from pokeldn.frlg.gift.file import from_payload
        from pokeldn.frlg.gift.wonder_card import GIFT_BEAST_CUTSCENE

        wg = self._build_current_wondergift()
        if wg is None:
            raise ValueError("Selected gift must be hosted directly via --gift.")

        flag_id = self.spin_flag_id.value()
        version = self.parent_gui.version_combo.currentText()

        carrier_slug = wg.slug if wg.slug in self._registry_entries else GIFT_BEAST_CUTSCENE
        wg_aligned = replace(wg, slug=carrier_slug)

        payload = configmod.MysteryGiftPayload(
            gift=carrier_slug,
            flag_id=flag_id,
            questionnaire=None,
            denied_message=None,
            definition=wg_aligned,
        )
        gift_obj = from_payload(payload, console_build="auto", version=version)
        gifts.save(str(target_path), gift_obj, build=None)
        return target_path

    def export_pokegift_dialog(self):
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export .pokegift File", str(paths.STAGING_POKEGIFT),
                "PokéGift Files (*.pokegift)"
            )
            if not path:
                return
            if not path.endswith(".pokegift"):
                path += ".pokegift"
            self._compile_to_pokegift_file(Path(path))
            QMessageBox.information(self, "Export Complete", f"Saved Wonder Gift to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def _decode_wonder_card(self, card: bytes) -> dict:
        """Decode the WonderCard struct shared by .pokegift variants and .wc3 files."""
        _ensure_pokeldn_imports()
        from pokeldn.frlg.gift import wonder_card

        if len(card) not in (wonder_card.WONDER_CARD_SIZE, wonder_card.JAPANESE_WONDER_CARD_SIZE):
            raise ValueError(f"card is {len(card)} bytes; expected 332 or 164")
        title, subtitle, body1, body2, body3, body4, footer1, footer2 = wonder_card.text_fields(card)
        bitfield = card[8]
        return {
            "title": title,
            "subtitle": subtitle,
            "body": [body1, body2, body3, body4],
            "footer1": footer1,
            "footer2": footer2,
            "flag_id": int.from_bytes(card[0:2], "little"),
            "icon_species": int.from_bytes(card[2:4], "little"),
            "id_number": int.from_bytes(card[4:8], "little"),
            "bg_type": (bitfield >> 2) & 0xF,
            "shareable": {0: "never", 1: "once", 2: "always"}.get((bitfield >> 6) & 0x3, "never"),
        }

    def _read_gift_card(self, path: Path) -> dict:
        """The decoded Wonder Card a .pokegift/.wc3 broadcasts, read with pokeldn's own loader."""
        _ensure_pokeldn_imports()
        from pokeldn import gifts
        from pokeldn.frlg.rom import builds

        try:
            gift = gifts.load(path)
        except ValueError:
            # A .wc3 whose delivery script holds a cartridge address needs --build to load; its
            # card is still the raw struct after the 4-byte CRC header, so preview it directly.
            from pokeldn.frlg.gift.mystery_gift import crc16

            raw = path.read_bytes() if path.suffix.lower() == ".wc3" else b""
            card_size = {1420: 332, 1252: 164}.get(len(raw))
            if card_size is not None:
                card = raw[4:4 + card_size]
                if int.from_bytes(raw[0:2], "little") == crc16(card):
                    return self._decode_wonder_card(card)
            raise

        # Prefer the variant for the console version selected in the toolbar, then English, so a
        # card that differs per cartridge previews its readable text.
        version = self.parent_gui.version_combo.currentText()
        variants = sorted(
            gift.variants.items(),
            key=lambda item: (
                builds.BUILDS[item[0]].version != version,
                builds.BUILDS[item[0]].language != "english",
                item[0],
            ),
        )
        for _code, variant in variants:
            card = variant.data.get("card")
            if card is not None:
                return self._decode_wonder_card(card)
        raise ValueError(
            "this gift carries console code instead of a Wonder Card, so it has no card text"
        )

    def load_external_gift_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load .pokegift or .wc3 File", str(paths.DATA_DIR),
            "Gift Files (*.pokegift *.wc3);;All Files (*)"
        )
        if not path:
            return

        p = Path(path)
        try:
            card = self._read_gift_card(p)
        except Exception as exc:
            QMessageBox.warning(
                self, "Could Not Read Gift File",
                f"{p.name} could not be read:\n\n{exc}\n\nThe file was not loaded as an override."
            )
            return

        self.external_gift_file = path
        self.btn_clear_file.setVisible(True)

        # Show the imported card's own text in the studio, so a previously made gift is editable
        # again instead of leaving whatever happened to be in the form.
        self.mode_tabs.setCurrentIndex(0)
        self._set_card_strings(
            card["title"], card["subtitle"], card["body"], card["footer1"], card["footer2"]
        )
        self.combo_bg.setCurrentIndex(max(0, min(7, card["bg_type"])))
        icon_index = self.combo_icon_species.findData(card["icon_species"])
        if icon_index >= 0:
            self.combo_icon_species.setCurrentIndex(icon_index)
        self.spin_flag_id.setValue(max(1000, min(1019, card["flag_id"])))
        shareable_index = self.combo_shareable.findText(card["shareable"])
        if shareable_index >= 0:
            self.combo_shareable.setCurrentIndex(shareable_index)

        # The normal refresh loop deliberately leaves an override's canvas alone, so paint the
        # imported card once here.
        self.preview_canvas.update_card(
            title=card["title"],
            subtitle=card["subtitle"],
            body_lines=card["body"],
            footer1=card["footer1"],
            footer2=card["footer2"],
            flag_id=card["flag_id"],
            id_number=card["id_number"],
            bg_type=card["bg_type"],
            icon_species=card["icon_species"],
            repeatable=self.chk_repeatable.isChecked(),
        )

        self._set_validation(
            f"External File Override Active: {p.name} — card text loaded into the studio", "info"
        )

    def clear_external_gift_file(self):
        self.external_gift_file = ""
        self.btn_clear_file.setVisible(False)
        self._refresh_preview_and_validate()

    # ------------------------------------------------------------------
    # Wireless Broadcast Lifecycle & Radio Reset
    # ------------------------------------------------------------------
    def _cleanup_stale_ldn_interfaces(self):
        # Added -n (non-interactive) to prevent faillock if sudo token is expired.
        # A source run shows frlg_mg_host.py in the process list; the frozen
        # AppImage dispatches through ``frlg-studio --mg-host`` instead.
        for pattern in ("frlg_mg_host.py", "frlg-studio --mg-host"):
            subprocess.run(
                ["sudo", "-n", "pkill", "-INT", "-f", pattern],
                stderr=subprocess.DEVNULL,
            )
        for iface in ("ldn-mon", "ldn-tap", "ldn"):
            subprocess.run(["sudo", "-n", "ip", "link", "delete", iface], stderr=subprocess.DEVNULL)

    def reset_wifi_radio(self):
        if not acquire_admin():
            self.mg_log.append("[System] Admin authentication failed.")
            return
        self.stop_broadcast(silent=True)
        self.mg_log.append("[System] Resetting mt7921e driver and clearing stale LDN virtual interfaces...")
        self._cleanup_stale_ldn_interfaces()
        # Added -n flags to completely banish faillock on headless systems
        subprocess.run(["sudo", "-n", "systemctl", "stop", "NetworkManager", "wpa_supplicant", "iwd"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "-n", "modprobe", "-r", "mt7921e"], stderr=subprocess.DEVNULL)
        time.sleep(0.8)
        subprocess.run(["sudo", "-n", "modprobe", "mt7921e"], stderr=subprocess.DEVNULL)
        time.sleep(0.8)
        subprocess.run(["sudo", "-n", "rfkill", "unblock", "wifi"], stderr=subprocess.DEVNULL)
        phy = detect_wiphy()
        self.parent_gui.phy_lbl.setText(f"({phy})")
        self.mg_log.append(f"[System] Radio reset complete! Active phy is now: {phy}")
        self._set_bcast_state(f"RADIO RESET COMPLETE ({phy.upper()}) — READY TO BROADCAST", "info")

    def _find_python_and_host_script(self) -> tuple[str, str]:
        if getattr(sys, "frozen", False):
            # The executable's entry point dispatches --mg-host before Qt is
            # imported, so no source file is needed inside the AppImage.
            return sys.executable, "--mg-host"
        py_candidates = [
            BASE_DIR / "venv" / "bin" / "python",
            Path(sys.executable),
        ]
        py_bin = next((str(p) for p in py_candidates if p.exists()), sys.executable)

        host_script = str(SRC_DIR / "frlg_mg_host.py")
        return py_bin, host_script

    def start_broadcast(self):
        # CRITICAL FIX: Ensure admin is acquired BEFORE any cleanup logic is called.
        # This prevents `stop_broadcast` from firing unauthenticated sudo commands,
        # which triggers the faillock panic.
        if not acquire_admin():
            self.mg_log.append("[System] Admin authentication failed. Cannot start Mystery Gift host.")
            return

        # NEW: Automatically configure the wireless adapter for broadcasting if not already attached!
        if network_manager_active():
            self.mg_log.append("[System] Wireless adapter is on normal Wi-Fi. Automatically attaching...")
            self.parent_gui.enable_trade_wifi()

        self.stop_broadcast(silent=True)

        if self.chk_auto_rotate_flag.isChecked() and not self.external_gift_file:
            nxt = 1000 + ((self.spin_flag_id.value() - 1000 + 1) % 20)
            self.spin_flag_id.setValue(nxt)

        py_bin, host_script = self._find_python_and_host_script()
        frozen_host = host_script == "--mg-host"
        if not frozen_host and not Path(host_script).exists():
            QMessageBox.critical(
                self, "Missing frlg_mg_host.py",
                f"Could not find frlg_mg_host.py inside {SRC_DIR}."
            )
            return

        self._cleanup_stale_ldn_interfaces()

        phy = detect_wiphy()
        self.parent_gui.phy_lbl.setText(f"({phy})")
        version = self.parent_gui.version_combo.currentText()
        keys_path = str(self.parent_gui.keys_path)

        host_args = [
            "--live",
            "--phy", phy,
            "--version", version,
            "--keys", keys_path,
            "--console-build", "auto",
            "--block-repeat", str(self.spin_block_repeat.value()),
            "--ram-script-block-repeat", str(self.spin_script_repeat.value()),
            "--ot", "FRLGSwT",
            "--verbose",
        ]
        if frozen_host:
            args = [py_bin, "--mg-host"] + host_args
        else:
            args = ["-E", py_bin, "-u", host_script] + host_args

        # The flags are appended to the option list, not the launcher prefix.
        option_args = host_args

        tx_idx = self.combo_tx_ccmp.currentIndex()
        if tx_idx == 1:
            option_args.append("--skip-encryption")
        elif tx_idx == 2:
            option_args.append("--no-skip-encryption")

        rx_idx = self.combo_rx_ccmp.currentIndex()
        if rx_idx == 1:
            option_args.append("--accept-decrypted-ccmp")
        elif rx_idx == 2:
            option_args.append("--no-accept-decrypted-ccmp")

        if self.chk_native_nonce.isChecked():
            option_args.append("--native-nonce-sequence")
        else:
            option_args.append("--no-native-nonce-sequence")

        if self.chk_session_first.isChecked():
            option_args.append("--session-response-first")

        if self.chk_end_on_success.isChecked():
            option_args.append("--end-on-success")

        try:
            if self.external_gift_file:
                option_args += ["--gift-file", self.external_gift_file]
                mode_desc = f"File: {Path(self.external_gift_file).name}"
            else:
                wg = self._build_current_wondergift()
                if wg is not None:
                    self._compile_to_pokegift_file(self.staging_pokegift)
                    option_args += ["--gift-file", str(self.staging_pokegift)]
                    mode_desc = f"Card '{wg.card.title}' (Flag {self.spin_flag_id.value()}, Repeatable={wg.event.repeatable})"
                else:
                    slug = str(self.combo_authentic.currentData())
                    option_args += ["--gift", slug, "--flag-id", str(self.spin_flag_id.value())]
                    mode_desc = f"Authentic Gift '{slug}' (Flag {self.spin_flag_id.value()})"
        except Exception as exc:
            QMessageBox.critical(self, "Wonder Card Build Error", f"Failed to compile Wonder Card:\n\n{exc}")
            return

        self.mg_log.clear()
        self.mg_log.append(f">>> Starting Mystery Gift Host on {phy} ({version})...")
        self.mg_log.append(f">>> Payload: {mode_desc}")
        self.mg_log.append(f">>> Flags: {' '.join(option_args)}\n")

        self._set_bcast_state(
            f"ADVERTISING ON {phy.upper()} — SELECT 'WONDER CARDS -> FRIEND' ON SWITCH", "wait"
        )

        self.mg_proc = QProcess(self)
        self.mg_proc.setWorkingDirectory(str(paths.DATA_DIR))
        self.mg_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.mg_proc.readyReadStandardOutput.connect(self._on_mg_stdout)
        self.mg_proc.finished.connect(self._on_mg_finished)
        self.mg_proc.start("sudo", args)

        self.btn_stop_mg.setEnabled(True)

    def _on_mg_stdout(self):
        if not self.mg_proc:
            return
        text = bytes(self.mg_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.mg_log.insertPlainText(text)
        self.mg_log.ensureCursorVisible()

        low = text.lower()
        if "joined" in low or "station" in low or "linkplayer" in low or "connected" in low:
            self._set_bcast_state("SWITCH CONNECTED — TRANSFERRING WONDER CARD PAYLOAD...", "info")
        if "succeeded" in low or "delivered" in low or "post-delivery" in low or "complete" in low:
            self._set_bcast_state(
                "WONDER CARD DELIVERED! VISIT ANY POKÉMON CENTER 2F DELIVERYMAN!", "ok"
            )

    def stop_broadcast(self, silent: bool = False):
        if self.mg_proc and self.mg_proc.state() != QProcess.ProcessState.NotRunning:
            # Added -n to gracefully fail rather than prompt
            for pattern in ("frlg_mg_host.py", "frlg-studio --mg-host"):
                subprocess.run(
                    ["sudo", "-n", "pkill", "-INT", "-f", pattern],
                    stderr=subprocess.DEVNULL,
                )
            if not self.mg_proc.waitForFinished(2000):
                self.mg_proc.terminate()
                self.mg_proc.waitForFinished(1000)
        self._cleanup_stale_ldn_interfaces()
        self.btn_stop_mg.setEnabled(False)
        if not silent:
            self.mg_log.append("\n[System] Mystery Gift broadcast stopped.")
            self._set_bcast_state("STANDBY — BROADCAST STOPPED", "neutral")

    def _on_mg_finished(self, exit_code: int, _exit_status):
        self.btn_stop_mg.setEnabled(False)
        if exit_code == 0:
            self._set_bcast_state(
                "DELIVERY SUCCEEDED — CLAIM YOUR GIFT IN ANY POKÉMON CENTER!", "ok"
            )
            self.mg_log.append("\n[System] Host exited cleanly (Delivery Succeeded).")
        elif exit_code != 130:
            self.mg_log.append(f"\n[System] Host process exited (code {exit_code}).")
