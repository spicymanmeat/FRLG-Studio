"""Shared visual language for FRLG Studio.

Seven complete UI palettes are available at runtime, named by region rather
than generation number:

* ``hgss``   - HeartGold/SoulSilver ivory, gold and soft Johto teal.
* ``hoenn``  - Ruby/Sapphire/Emerald turquoise coast, sand and coral.
* ``sinnoh`` - Platinum's cold graphite, silver and lake blue.
* ``frlg``   - strictly FireRed/LeafGreen cobalt, cream and orange.
* ``unova``  - the black/white/cyan PC-box and summary language of Unova.
* ``light``  - a true white light mode with sky-blue windows and trade room.
* ``dark``   - a deep graphite/indigo night palette.

The module exposes the *active* palette as ordinary module attributes (``INK``,
``NAVY``, ``PAPER`` ...) so custom-painted widgets can simply repaint after a
theme change.  Call :func:`set_theme` to switch and :func:`build_stylesheet`
to refresh the application-wide Qt stylesheet.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from string import Template

from PyQt6.QtCore import (
    QEvent, QModelIndex, QObject, QPoint, QPointF, QRectF,
    QSortFilterProxyModel, QStringListModel, Qt, QTimer,
)
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter,
    QPainterPath, QPalette, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFrame, QLabel, QListView,
    QProxyStyle, QStyle, QVBoxLayout, QWidget,
)

import paths

ROOT = paths.APP_DIR
FONT_DIR = ROOT / "assets" / "fonts"
ASSET_DIR = ROOT / "assets"
UI_ROOT = ASSET_DIR / "ui"
UI_DIR = UI_ROOT / "hgss"
SETTINGS_FILE = paths.THEME_PATH
SCALE_FILE = paths.SCALE_PATH

# ---------------------------------------------------------------------------
# Palette definitions
# ---------------------------------------------------------------------------
# A palette is deliberately flat: every visual token is a string so the same
# value can be fed to QSS, QColor, QPainter and inline style sheets.
PALETTES: dict[str, dict[str, str]] = {
    "hgss": {
        "LABEL": "HGSS",
        "SHORT_LABEL": "HGSS",
        "DESCRIPTION": "HeartGold and SoulSilver ivory, warm gold and Johto teal.",
        "MENU_STYLE": "hgss",
        "INK": "#2b2b33",
        "INK_SOFT": "#5c6172",
        "INK_MUTED": "#7c8090",
        "NAVY": "#34477c",
        "NAVY_DARK": "#26345c",
        "BLUE": "#5b78c7",
        "BLUE_LIGHT": "#a9c1ef",
        "CREAM": "#fbf5df",
        "CREAM_ALT": "#f0e6c9",
        "PAPER": "#fffdf6",
        "PANEL": "#fffdf6",
        "PANEL_ALT": "#f8f1dc",
        "FIELD": "#fffdf6",
        "FIELD_ALT": "#f7f0dd",
        "READONLY": "#f3ead2",
        "ORANGE": "#e9822e",
        "ORANGE_DARK": "#b8591d",
        "HEADER_LIGHT": "#f09a4e",
        "HEADER": "#e9822e",
        "HEADER_DARK": "#b8591d",
        "ON_HEADER": "#fffdf6",
        "GOLD": "#f4c84a",
        "YELLOW": "#fbe58a",
        "ON_GOLD": "#2b2b33",
        "ON_ACCENT": "#fffdf6",
        "ON_DANGER": "#fffdf6",
        "GREEN": "#4caf72",
        "GREEN_DARK": "#2f7d4f",
        "GREEN_LIGHT": "#e3f5e5",
        "RED": "#d94b47",
        "RED_DARK": "#9e2f31",
        "RED_LIGHT": "#fbe4e2",
        "PURPLE": "#b9b9f4",
        "BORDER": "#7b89ac",
        "BORDER_SOFT": "#c8bea3",
        "BORDER_STRONG": "#26345c",
        "HOVER": "#fff8d8",
        "HOVER_BORDER": "#e9822e",
        "PRESSED": "#f0e6c9",
        "DISABLED_BG": "#e5dfd1",
        "DISABLED_FG": "#96938a",
        "DISABLED_BORDER": "#b8b2a3",
        "SCROLL_BG": "#e7dfca",
        "SCROLL_HANDLE": "#8fa3cc",
        "SCROLL_HANDLE_HOVER": "#f4c84a",
        "APP_BG_TOP": "#e9e1cd",
        "APP_BG_BOTTOM": "#f6f0df",
        "TOPBAR_BG": "#fffdf6",
        "TAB_BG": "#ded5bd",
        "TAB_SELECTED_BG": "#fbf5df",
        "SUMMARY_BG_1": "#d3d1f8",
        "SUMMARY_BG_2": "#b9b9f4",
        "SUMMARY_BG_3": "#aabcea",
        "SUMMARY_BORDER": "#7a7cc0",
        "SUMMARY_CARD": "#fdfbe6",
        "SUMMARY_STAT_BG": "#6f83bb",
        "SUMMARY_STAT_TEXT": "#ffffff",
        "SUMMARY_MEMO_BG": "#fdfbe6",
        "SUMMARY_MEMO_BORDER": "#e8a878",
        "SUMMARY_RULE": "#f4c84a",
        "SUMMARY_TITLE": "#26345c",
        "MENU_SKY_TOP": "#bfe6f7",
        "MENU_SKY_MID": "#dcf1f4",
        "MENU_SKY_LOW": "#f7edcd",
        "MENU_SKY_BOTTOM": "#f3e3ba",
        "MENU_HILL_1": "#c4dab6",
        "MENU_HILL_2": "#9dc68f",
        "MENU_HILL_3": "#78ae6a",
        "MENU_PATH": "#f6e7ba",
        "MENU_CLOUD": "#ffffff",
        "MENU_INK": "#26345c",
        "MENU_FOOTER_BG": "#1d2b44",
        "MENU_FOOTER_FG": "#ffffff",
        "TRADE_BG_1": "#1a2c55",
        "TRADE_BG_2": "#27477c",
        "TRADE_BG_3": "#355f97",
        "TRADE_INK": "#fffdf6",
        "TRADE_PATTERN": "#ffffff",
        "BANNER_BG": "#26345c",
        "BANNER_TEXT": "#fffdf6",
        "SHADOW": "#30262d3e",
        "PANEL_RADIUS": "9",
        "CARD_RADIUS": "17",
        "CONTROL_RADIUS": "6",
    },
    "dark": {
        "LABEL": "DARK",
        "SHORT_LABEL": "DARK",
        "DESCRIPTION": "Graphite and indigo night with warm gold accents.",
        "MENU_STYLE": "night",
        "INK": "#f1ebdf",
        "INK_SOFT": "#b9c1d2",
        "INK_MUTED": "#8e97aa",
        "NAVY": "#91ace8",
        "NAVY_DARK": "#e4ecff",
        "BLUE": "#718fd8",
        "BLUE_LIGHT": "#33466e",
        "CREAM": "#1d2431",
        "CREAM_ALT": "#141a24",
        "PAPER": "#252d3b",
        "PANEL": "#202838",
        "PANEL_ALT": "#2a3344",
        "FIELD": "#19202c",
        "FIELD_ALT": "#202938",
        "READONLY": "#1a202b",
        "ORANGE": "#e9a14b",
        "ORANGE_DARK": "#ffd08a",
        "HEADER_LIGHT": "#f2b262",
        "HEADER": "#e9a14b",
        "HEADER_DARK": "#b9762c",
        "ON_HEADER": "#fff8eb",
        "GOLD": "#f0c75e",
        "YELLOW": "#5a4a22",
        "ON_GOLD": "#1b202a",
        "ON_ACCENT": "#fff8eb",
        "ON_DANGER": "#fff8eb",
        "GREEN": "#5fbf83",
        "GREEN_DARK": "#8ee0aa",
        "GREEN_LIGHT": "#244635",
        "RED": "#e06a64",
        "RED_DARK": "#ffaaa4",
        "RED_LIGHT": "#4a2627",
        "PURPLE": "#453c66",
        "BORDER": "#64718c",
        "BORDER_SOFT": "#404b5f",
        "BORDER_STRONG": "#91ace8",
        "HOVER": "#33405a",
        "HOVER_BORDER": "#f0c75e",
        "PRESSED": "#111722",
        "DISABLED_BG": "#252b36",
        "DISABLED_FG": "#858da0",
        "DISABLED_BORDER": "#3b4352",
        "SCROLL_BG": "#1a202b",
        "SCROLL_HANDLE": "#55688c",
        "SCROLL_HANDLE_HOVER": "#f0c75e",
        "APP_BG_TOP": "#10151d",
        "APP_BG_BOTTOM": "#1a2230",
        "TOPBAR_BG": "#232b39",
        "TAB_BG": "#2a3342",
        "TAB_SELECTED_BG": "#1a2230",
        "SUMMARY_BG_1": "#3a3760",
        "SUMMARY_BG_2": "#2c2b4a",
        "SUMMARY_BG_3": "#24243f",
        "SUMMARY_BORDER": "#8e8bd0",
        "SUMMARY_CARD": "#242236",
        "SUMMARY_STAT_BG": "#5468a0",
        "SUMMARY_STAT_TEXT": "#f6f2e7",
        "SUMMARY_MEMO_BG": "#2a2639",
        "SUMMARY_MEMO_BORDER": "#c28a55",
        "SUMMARY_RULE": "#f0c75e",
        "SUMMARY_TITLE": "#f4eddc",
        "MENU_SKY_TOP": "#080d18",
        "MENU_SKY_MID": "#111c2f",
        "MENU_SKY_LOW": "#1b293c",
        "MENU_SKY_BOTTOM": "#293445",
        "MENU_HILL_1": "#1b2d35",
        "MENU_HILL_2": "#173126",
        "MENU_HILL_3": "#10241d",
        "MENU_PATH": "#594e3d",
        "MENU_CLOUD": "#b9c6dc",
        "MENU_INK": "#f2ecdf",
        "MENU_FOOTER_BG": "#080d16",
        "MENU_FOOTER_FG": "#d6deee",
        "TRADE_BG_1": "#0d1524",
        "TRADE_BG_2": "#162540",
        "TRADE_BG_3": "#1f3554",
        "TRADE_INK": "#f2ecdf",
        "TRADE_PATTERN": "#9fb4d6",
        "BANNER_BG": "#2a3a5c",
        "BANNER_TEXT": "#f8efe0",
        "SHADOW": "#70100c14",
        "PANEL_RADIUS": "9",
        "CARD_RADIUS": "17",
        "CONTROL_RADIUS": "6",
    },
    "frlg": {
        "LABEL": "FRLG",
        "SHORT_LABEL": "FRLG",
        "DESCRIPTION": "FireRed and LeafGreen cobalt, cream and orange.",
        "MENU_STYLE": "gba",
        "INK": "#202020",
        "INK_SOFT": "#4a4a4a",
        "INK_MUTED": "#6e6e6e",
        "NAVY": "#2b4f9a",
        "NAVY_DARK": "#172c56",
        "BLUE": "#3b6fbf",
        "BLUE_LIGHT": "#a8c6e8",
        "CREAM": "#fff8e2",
        "CREAM_ALT": "#dbe7f7",
        "PAPER": "#fffdf4",
        "PANEL": "#fff9e8",
        "PANEL_ALT": "#f3e7c8",
        "FIELD": "#fffdf4",
        "FIELD_ALT": "#f7eccf",
        "READONLY": "#f4e6c2",
        "ORANGE": "#e07828",
        "ORANGE_DARK": "#a34e12",
        "HEADER_LIGHT": "#f09246",
        "HEADER": "#e07828",
        "HEADER_DARK": "#a34e12",
        "ON_HEADER": "#fffdf4",
        "GOLD": "#f8d030",
        "YELLOW": "#fbe58a",
        "ON_GOLD": "#202020",
        "ON_ACCENT": "#fffdf4",
        "ON_DANGER": "#fffdf4",
        "GREEN": "#4ca85c",
        "GREEN_DARK": "#236b34",
        "GREEN_LIGHT": "#c8e8b8",
        "RED": "#d03028",
        "RED_DARK": "#8a1a18",
        "RED_LIGHT": "#f5c8c0",
        "PURPLE": "#c8d8e8",
        "BORDER": "#6b86b8",
        "BORDER_SOFT": "#c8b890",
        "BORDER_STRONG": "#172c56",
        "HOVER": "#fff4c8",
        "HOVER_BORDER": "#e07828",
        "PRESSED": "#e8d8b0",
        "DISABLED_BG": "#d8cba8",
        "DISABLED_FG": "#807860",
        "DISABLED_BORDER": "#aa9c80",
        "SCROLL_BG": "#c8d8ec",
        "SCROLL_HANDLE": "#5b78b8",
        "SCROLL_HANDLE_HOVER": "#e07828",
        "APP_BG_TOP": "#c8dbf1",
        "APP_BG_BOTTOM": "#eaf2fc",
        "TOPBAR_BG": "#fffdf4",
        "TAB_BG": "#b8cce8",
        "TAB_SELECTED_BG": "#eef5ff",
        "SUMMARY_BG_1": "#f8d890",
        "SUMMARY_BG_2": "#f0b860",
        "SUMMARY_BG_3": "#e8a850",
        "SUMMARY_BORDER": "#2b4f9a",
        "SUMMARY_CARD": "#fffdf4",
        "SUMMARY_STAT_BG": "#3b6fbf",
        "SUMMARY_STAT_TEXT": "#fffdf4",
        "SUMMARY_MEMO_BG": "#fffdf4",
        "SUMMARY_MEMO_BORDER": "#e07828",
        "SUMMARY_RULE": "#e07828",
        "SUMMARY_TITLE": "#172c56",
        "MENU_SKY_TOP": "#bfe4f8",
        "MENU_SKY_MID": "#e8f4f8",
        "MENU_SKY_LOW": "#f8f0d8",
        "MENU_SKY_BOTTOM": "#f8d890",
        "MENU_HILL_1": "#98c878",
        "MENU_HILL_2": "#78b868",
        "MENU_HILL_3": "#5a9a50",
        "MENU_PATH": "#f0d8a0",
        "MENU_CLOUD": "#ffffff",
        "MENU_INK": "#172c56",
        "MENU_FOOTER_BG": "#172c56",
        "MENU_FOOTER_FG": "#fffdf4",
        "TRADE_BG_1": "#1e3868",
        "TRADE_BG_2": "#2c4f8e",
        "TRADE_BG_3": "#3f68a8",
        "TRADE_INK": "#fffdf4",
        "TRADE_PATTERN": "#a8c6e8",
        "BANNER_BG": "#2b4f9a",
        "BANNER_TEXT": "#fffdf4",
        "SHADOW": "#40141c2c",
        "PANEL_RADIUS": "5",
        "CARD_RADIUS": "8",
        "CONTROL_RADIUS": "3",
    },
    "unova": {
        "LABEL": "UNOVA",
        "SHORT_LABEL": "UNOVA",
        "DESCRIPTION": "Deep Unova black with cyan PC-box and summary light.",
        "MENU_STYLE": "city",
        "INK": "#edf6f9",
        "INK_SOFT": "#b4c8d2",
        "INK_MUTED": "#869da8",
        "NAVY": "#6fc9e6",
        "NAVY_DARK": "#eaf8fc",
        "BLUE": "#45a8d6",
        "BLUE_LIGHT": "#24495a",
        "CREAM": "#101a20",
        "CREAM_ALT": "#0a1116",
        "PAPER": "#17242c",
        "PANEL": "#17232b",
        "PANEL_ALT": "#20313c",
        "FIELD": "#0d171d",
        "FIELD_ALT": "#15232b",
        "READONLY": "#1a2932",
        "ORANGE": "#f0744f",
        "ORANGE_DARK": "#ffb49a",
        "HEADER_LIGHT": "#3d7d9c",
        "HEADER": "#2b6684",
        "HEADER_DARK": "#173f52",
        "ON_HEADER": "#f4fcff",
        "GOLD": "#57d2ea",
        "YELLOW": "#1d4350",
        "ON_GOLD": "#052029",
        "ON_ACCENT": "#f4fcff",
        "ON_DANGER": "#fff6f4",
        "GREEN": "#4fbf82",
        "GREEN_DARK": "#93e7b6",
        "GREEN_LIGHT": "#16382a",
        "RED": "#d95b5b",
        "RED_DARK": "#ff9d9d",
        "RED_LIGHT": "#3b1d21",
        "PURPLE": "#36566a",
        "BORDER": "#3c5968",
        "BORDER_SOFT": "#2a3e49",
        "BORDER_STRONG": "#6fc9e6",
        "HOVER": "#1b303b",
        "HOVER_BORDER": "#57d2ea",
        "PRESSED": "#0b1318",
        "DISABLED_BG": "#1c282f",
        "DISABLED_FG": "#6f838e",
        "DISABLED_BORDER": "#2f444f",
        "SCROLL_BG": "#0c151a",
        "SCROLL_HANDLE": "#376273",
        "SCROLL_HANDLE_HOVER": "#57d2ea",
        "APP_BG_TOP": "#070d11",
        "APP_BG_BOTTOM": "#101c23",
        "TOPBAR_BG": "#121f27",
        "TAB_BG": "#15232c",
        "TAB_SELECTED_BG": "#1c2e38",
        "SUMMARY_BG_1": "#1a2f3a",
        "SUMMARY_BG_2": "#142630",
        "SUMMARY_BG_3": "#0e1d25",
        "SUMMARY_BORDER": "#57d2ea",
        "SUMMARY_CARD": "#0d1a21",
        "SUMMARY_STAT_BG": "#245c72",
        "SUMMARY_STAT_TEXT": "#f2fcff",
        "SUMMARY_MEMO_BG": "#111e25",
        "SUMMARY_MEMO_BORDER": "#3d8196",
        "SUMMARY_RULE": "#57d2ea",
        "SUMMARY_TITLE": "#eaf8fc",
        "MENU_SKY_TOP": "#04080b",
        "MENU_SKY_MID": "#08131a",
        "MENU_SKY_LOW": "#0d2029",
        "MENU_SKY_BOTTOM": "#12303c",
        "MENU_HILL_1": "#0c1b22",
        "MENU_HILL_2": "#09151b",
        "MENU_HILL_3": "#061014",
        "MENU_PATH": "#2a4a57",
        "MENU_CLOUD": "#5d7f8d",
        "MENU_INK": "#eaf8fc",
        "MENU_FOOTER_BG": "#04090c",
        "MENU_FOOTER_FG": "#b9e9f5",
        "TRADE_BG_1": "#0a141a",
        "TRADE_BG_2": "#122630",
        "TRADE_BG_3": "#1b3b48",
        "TRADE_INK": "#eaf8fc",
        "TRADE_PATTERN": "#5d9db0",
        "BANNER_BG": "#17323d",
        "BANNER_TEXT": "#eaf8fc",
        "SHADOW": "#70000609",
        "PANEL_RADIUS": "4",
        "CARD_RADIUS": "6",
        "CONTROL_RADIUS": "3",
    },
}

# The original G4 Light mixed DPPt lavender with FRLG cobalt and cream, which
# made it read as a second FireRed skin at a glance.  Retune it to the warmer
# HeartGold/SoulSilver language: ivory, soft gold, Johto teal and dark cocoa.
PALETTES["hgss"].update({
    "LABEL": "HGSS",
    "SHORT_LABEL": "HGSS",
    "DESCRIPTION": "HeartGold and SoulSilver ivory, warm gold and soft Johto teal.",
    "MENU_STYLE": "hgss",
    "MENU_OVERLINE": "POKéMON HEARTGOLD  •  SOULSILVER",
    "MENU_FOOTER_TAG": "JOHTO  •  HEARTGOLD  •  SOULSILVER",
    "INK": "#3d3428",
    "INK_SOFT": "#6b5d4b",
    "INK_MUTED": "#8a7b66",
    "NAVY": "#6c5a3e",
    "NAVY_DARK": "#423522",
    "BLUE": "#6f8fa6",
    "BLUE_LIGHT": "#d6e6ee",
    "CREAM": "#f7f0df",
    "CREAM_ALT": "#efe4cf",
    "PAPER": "#fffdf4",
    "PANEL": "#fbf6e8",
    "PANEL_ALT": "#f1e6d0",
    "FIELD": "#fffdf7",
    "FIELD_ALT": "#f6eeda",
    "READONLY": "#eadfc8",
    "ORANGE": "#c9782e",
    "ORANGE_DARK": "#8b4a1e",
    "HEADER_LIGHT": "#e9cc8c",
    "HEADER": "#dbb56e",
    "HEADER_DARK": "#a97b3d",
    "ON_HEADER": "#423522",
    "GOLD": "#e8c45a",
    "YELLOW": "#f8e7ad",
    "ON_GOLD": "#3d3428",
    "GREEN": "#7aa05a",
    "GREEN_DARK": "#4f7038",
    "GREEN_LIGHT": "#e3edd2",
    "RED": "#c9564a",
    "RED_DARK": "#8a2e26",
    "RED_LIGHT": "#f3d8d2",
    "PURPLE": "#cbbfd8",
    "BORDER": "#b7a482",
    "BORDER_SOFT": "#d9caad",
    "BORDER_STRONG": "#423522",
    "HOVER": "#f6ecd4",
    "HOVER_BORDER": "#c9782e",
    "PRESSED": "#e9d9bb",
    "DISABLED_BG": "#e6dccb",
    "DISABLED_FG": "#948873",
    "DISABLED_BORDER": "#bfb19a",
    "SCROLL_BG": "#e8ddc7",
    "SCROLL_HANDLE": "#a3916f",
    "SCROLL_HANDLE_HOVER": "#c9782e",
    "APP_BG_TOP": "#e9dfc9",
    "APP_BG_BOTTOM": "#f8f2e5",
    "TOPBAR_BG": "#fffdf4",
    "TAB_BG": "#d9ccb1",
    "TAB_SELECTED_BG": "#f7f0df",
    "SUMMARY_BG_1": "#d3e6ed",
    "SUMMARY_BG_2": "#bcd6e2",
    "SUMMARY_BG_3": "#a9c8d8",
    "SUMMARY_BORDER": "#6f8fa6",
    "SUMMARY_CARD": "#fffdf4",
    "SUMMARY_STAT_BG": "#6f8fa6",
    "SUMMARY_STAT_TEXT": "#ffffff",
    "SUMMARY_MEMO_BG": "#fffdf4",
    "SUMMARY_MEMO_BORDER": "#cf9a5a",
    "SUMMARY_RULE": "#e8c45a",
    "SUMMARY_TITLE": "#423522",
    "MENU_SKY_TOP": "#bfe0ef",
    "MENU_SKY_MID": "#dff0ec",
    "MENU_SKY_LOW": "#f7edcf",
    "MENU_SKY_BOTTOM": "#f2dfae",
    "MENU_HILL_1": "#c6d7b1",
    "MENU_HILL_2": "#a6c18e",
    "MENU_HILL_3": "#84a96c",
    "MENU_PATH": "#f5e6b8",
    "MENU_CLOUD": "#ffffff",
    "MENU_INK": "#423522",
    "MENU_FOOTER_BG": "#4a3824",
    "MENU_FOOTER_FG": "#fffdf4",
    "TRADE_BG_1": "#2f4a43",
    "TRADE_BG_2": "#45695e",
    "TRADE_BG_3": "#5c8474",
    "TRADE_INK": "#fffdf4",
    "TRADE_PATTERN": "#cfe2d6",
    "BANNER_BG": "#4a3824",
    "BANNER_TEXT": "#fffdf4",
})

# A genuinely bright fifth option, separate from both FRLG cream and HGSS ivory.
# Its trade room is light too, so the whole application reads as a light mode.
PALETTES["light"] = {
    **PALETTES["hgss"],
    "LABEL": "LIGHT",
    "SHORT_LABEL": "LIGHT",
    "DESCRIPTION": "Bright white light mode with sky-blue PC and trade windows.",
    "MENU_STYLE": "light",
    "MENU_OVERLINE": "POKéMON  •  WIRELESS LINK",
    "MENU_FOOTER_TAG": "WIRELESS TRADE  •  STORAGE  •  LOCAL LINK",
    "INK": "#1f2d36",
    "INK_SOFT": "#526775",
    "INK_MUTED": "#7d919d",
    "NAVY": "#2f6f9e",
    "NAVY_DARK": "#133f5b",
    "BLUE": "#2f8fd8",
    "BLUE_LIGHT": "#bfe3f5",
    "CREAM": "#f2f8fc",
    "CREAM_ALT": "#e6eff6",
    "PAPER": "#ffffff",
    "PANEL": "#ffffff",
    "PANEL_ALT": "#edf5fa",
    "FIELD": "#ffffff",
    "FIELD_ALT": "#f3f8fb",
    "READONLY": "#e9f1f6",
    "ORANGE": "#ff7a3d",
    "ORANGE_DARK": "#b8431c",
    "HEADER_LIGHT": "#7ec8ee",
    "HEADER": "#3f9fd4",
    "HEADER_DARK": "#1f6e9c",
    "ON_HEADER": "#ffffff",
    "GOLD": "#ffcf4a",
    "YELLOW": "#fff0b8",
    "ON_GOLD": "#20303a",
    "GREEN": "#37a867",
    "GREEN_DARK": "#1f7647",
    "GREEN_LIGHT": "#dff5e8",
    "RED": "#d94b47",
    "RED_DARK": "#992a28",
    "RED_LIGHT": "#fde4e2",
    "PURPLE": "#b9c9f4",
    "BORDER": "#8fb3c8",
    "BORDER_SOFT": "#cfe0ea",
    "BORDER_STRONG": "#133f5b",
    "HOVER": "#e6f6ff",
    "HOVER_BORDER": "#2f8fd8",
    "PRESSED": "#d6ecf7",
    "DISABLED_BG": "#e3edf3",
    "DISABLED_FG": "#8ba0ac",
    "DISABLED_BORDER": "#b9cdd8",
    "SCROLL_BG": "#e2eef5",
    "SCROLL_HANDLE": "#8fc0da",
    "SCROLL_HANDLE_HOVER": "#2f8fd8",
    "APP_BG_TOP": "#dff1fb",
    "APP_BG_BOTTOM": "#f8fdff",
    "TOPBAR_BG": "#ffffff",
    "TAB_BG": "#d4e7f2",
    "TAB_SELECTED_BG": "#ffffff",
    "SUMMARY_BG_1": "#ffffff",
    "SUMMARY_BG_2": "#eaf7ff",
    "SUMMARY_BG_3": "#d8effa",
    "SUMMARY_BORDER": "#7fb8d6",
    "SUMMARY_CARD": "#ffffff",
    "SUMMARY_STAT_BG": "#2f8fd8",
    "SUMMARY_STAT_TEXT": "#ffffff",
    "SUMMARY_MEMO_BG": "#f7fcff",
    "SUMMARY_MEMO_BORDER": "#ffb08a",
    "SUMMARY_RULE": "#ffcf4a",
    "SUMMARY_TITLE": "#133f5b",
    "MENU_SKY_TOP": "#bfe9ff",
    "MENU_SKY_MID": "#e6f8ff",
    "MENU_SKY_LOW": "#f5fcff",
    "MENU_SKY_BOTTOM": "#e8f4e6",
    "MENU_HILL_1": "#c9e7c1",
    "MENU_HILL_2": "#a9d6a0",
    "MENU_HILL_3": "#84bf7a",
    "MENU_PATH": "#fff4c9",
    "MENU_CLOUD": "#ffffff",
    "MENU_INK": "#133f5b",
    "MENU_FOOTER_BG": "#133f5b",
    "MENU_FOOTER_FG": "#ffffff",
    "TRADE_BG_1": "#dff2fc",
    "TRADE_BG_2": "#c8e8f7",
    "TRADE_BG_3": "#aedcf2",
    "TRADE_INK": "#133f5b",
    "TRADE_PATTERN": "#ffffff",
    "BANNER_BG": "#2f6f9e",
    "BANNER_TEXT": "#ffffff",
    "SHADOW": "#30102030",
}

# Hoenn is the exception that gets to be loud: Rayquaza jade and gold carry
# the chrome, Kyogre blue handles links and secondary actions, and Groudon
# crimson is reserved for destructive actions and warnings.  The result is a
# tropical emerald UI rather than another blue Kanto skin.
PALETTES["hoenn"] = {
    **PALETTES["hgss"],
    "LABEL": "HOENN",
    "SHORT_LABEL": "HOENN",
    "DESCRIPTION": "Emerald jade and Rayquaza gold with Groudon red and Kyogre blue.",
    "MENU_STYLE": "hoenn",
    "MENU_OVERLINE": "POKéMON RUBY  •  SAPPHIRE  •  EMERALD",
    "MENU_FOOTER_TAG": "HOENN  •  RUBY  •  SAPPHIRE  •  EMERALD",
    "INK": "#12332e",
    "INK_SOFT": "#41675f",
    "INK_MUTED": "#728d83",
    "NAVY": "#0a6f57",
    "NAVY_DARK": "#043a30",
    "BLUE": "#1b6fbe",
    "BLUE_LIGHT": "#d7ecff",
    "CREAM": "#e7f5df",
    "CREAM_ALT": "#d8edd1",
    "PAPER": "#f7fef1",
    "PANEL": "#ecf8e5",
    "PANEL_ALT": "#d9edcf",
    "FIELD": "#f8fff3",
    "FIELD_ALT": "#e5f3dc",
    "READONLY": "#d8e8d2",
    "ORANGE": "#c9462f",
    "ORANGE_DARK": "#7e2618",
    "HEADER_LIGHT": "#66d9a3",
    "HEADER": "#0d8a63",
    "HEADER_DARK": "#07523f",
    "ON_HEADER": "#f8fff8",
    "GOLD": "#f0cc55",
    "YELLOW": "#f7e9aa",
    "ON_GOLD": "#17372e",
    "GREEN": "#0f7a4e",
    "GREEN_DARK": "#0a4f36",
    "GREEN_LIGHT": "#d8f2e0",
    "RED": "#b9373a",
    "RED_DARK": "#7a1f23",
    "RED_LIGHT": "#f8d7d6",
    "PURPLE": "#bfe0d2",
    "BORDER": "#4f8f77",
    "BORDER_SOFT": "#b2d4be",
    "BORDER_STRONG": "#073f36",
    "HOVER": "#fff3c8",
    "HOVER_BORDER": "#d45a40",
    "PRESSED": "#d6e8cd",
    "DISABLED_BG": "#dde8d7",
    "DISABLED_FG": "#87917f",
    "DISABLED_BORDER": "#b3c8b0",
    "SCROLL_BG": "#d6eadb",
    "SCROLL_HANDLE": "#6ba990",
    "SCROLL_HANDLE_HOVER": "#d45a40",
    "APP_BG_TOP": "#cbe8d8",
    "APP_BG_BOTTOM": "#f1fbed",
    "TOPBAR_BG": "#f5fdef",
    "TAB_BG": "#b4e0c6",
    "TAB_SELECTED_BG": "#f5efc4",
    "SUMMARY_BG_1": "#a8e8bd",
    "SUMMARY_BG_2": "#4db88a",
    "SUMMARY_BG_3": "#0e7a5e",
    "SUMMARY_BORDER": "#0a5f50",
    "SUMMARY_CARD": "#effbea",
    "SUMMARY_STAT_BG": "#1b6fbe",
    "SUMMARY_STAT_TEXT": "#f8fff8",
    "SUMMARY_MEMO_BG": "#effbea",
    "SUMMARY_MEMO_BORDER": "#c9462f",
    "SUMMARY_RULE": "#e6c34c",
    "SUMMARY_TITLE": "#073f36",
    "MENU_SKY_TOP": "#083d5a",
    "MENU_SKY_MID": "#0e716c",
    "MENU_SKY_LOW": "#69c38a",
    "MENU_SKY_BOTTOM": "#f1d179",
    "MENU_HILL_1": "#80c88d",
    "MENU_HILL_2": "#4aa574",
    "MENU_HILL_3": "#277551",
    "MENU_PATH": "#f2dd9d",
    "MENU_CLOUD": "#f8fff8",
    "MENU_INK": "#073f36",
    "MENU_FOOTER_BG": "#063a32",
    "MENU_FOOTER_FG": "#eaf7d9",
    "TRADE_BG_1": "#053b37",
    "TRADE_BG_2": "#07665f",
    "TRADE_BG_3": "#13897a",
    "TRADE_INK": "#f8fff0",
    "TRADE_PATTERN": "#a9ead0",
    "BANNER_BG": "#075044",
    "BANNER_TEXT": "#f4fff5",
    "SHADOW": "#40102c27",
    "PANEL_RADIUS": "6",
    "CARD_RADIUS": "10",
    "CONTROL_RADIUS": "4",
    "BOX_FRAME": "#1b6fbe",
    "BOX_FRAME_INNER": "#f0cc55",
}

# Platinum's PC box is not a grey room: it is lake cyan, periwinkle casing,
# lime gridwork and coral buttons.  Keep the night-time contrast of the app,
# but let those four colour families show up consistently in the chrome.
PALETTES["sinnoh"] = {
    **PALETTES["dark"],
    "LABEL": "SINNOH",
    "SHORT_LABEL": "SINNOH",
    "DESCRIPTION": "Platinum lake cyan, periwinkle, lime and coral under a cold night.",
    "MENU_STYLE": "platinum",
    "MENU_OVERLINE": "POKéMON DIAMOND  •  PEARL  •  PLATINUM",
    "MENU_FOOTER_TAG": "SINNOH  •  DIAMOND  •  PEARL  •  PLATINUM",
    "INK": "#f2fbfa",
    "INK_SOFT": "#b6d6d4",
    "INK_MUTED": "#84a6a6",
    "NAVY": "#a5a3ea",
    "NAVY_DARK": "#f0fbff",
    "BLUE": "#5db9e4",
    "BLUE_LIGHT": "#15414b",
    "CREAM": "#0d2a2d",
    "CREAM_ALT": "#0a2327",
    "PAPER": "#173f43",
    "PANEL": "#153b40",
    "PANEL_ALT": "#1e5056",
    "FIELD": "#0b282e",
    "FIELD_ALT": "#15393f",
    "READONLY": "#11343a",
    "ORANGE": "#f2968c",
    "ORANGE_DARK": "#ffc7bd",
    "HEADER_LIGHT": "#b5aef5",
    "HEADER": "#7576cf",
    "HEADER_DARK": "#464b9c",
    "ON_HEADER": "#fbfbff",
    "GOLD": "#f4d98a",
    "YELLOW": "#f8eab4",
    "ON_GOLD": "#14212b",
    "ON_ACCENT": "#05212a",
    "ON_DANGER": "#2b0d12",
    "GREEN": "#c6d96c",
    "GREEN_DARK": "#eef7b7",
    "GREEN_LIGHT": "#24402f",
    "RED": "#f0938e",
    "RED_DARK": "#ffd2cc",
    "RED_LIGHT": "#3d2428",
    "PURPLE": "#c9c4fb",
    "BORDER": "#679aa4",
    "BORDER_SOFT": "#38636b",
    "BORDER_STRONG": "#c9f2e6",
    "HOVER": "#2a5b60",
    "HOVER_BORDER": "#f4d98a",
    "PRESSED": "#123438",
    "DISABLED_BG": "#1b2f33",
    "DISABLED_FG": "#769193",
    "DISABLED_BORDER": "#3a5a5f",
    "SCROLL_BG": "#0a2428",
    "SCROLL_HANDLE": "#5b959b",
    "SCROLL_HANDLE_HOVER": "#f4d98a",
    "APP_BG_TOP": "#071b21",
    "APP_BG_BOTTOM": "#143b40",
    "TOPBAR_BG": "#143b3e",
    "TAB_BG": "#1d4d50",
    "TAB_SELECTED_BG": "#2d6368",
    "SUMMARY_BG_1": "#8a7fd6",
    "SUMMARY_BG_2": "#5a9fc0",
    "SUMMARY_BG_3": "#3d6e93",
    "SUMMARY_BORDER": "#c9c4fb",
    "SUMMARY_CARD": "#14363b",
    "SUMMARY_STAT_BG": "#505fa8",
    "SUMMARY_STAT_TEXT": "#f5fdff",
    "SUMMARY_MEMO_BG": "#14363b",
    "SUMMARY_MEMO_BORDER": "#f0b79c",
    "SUMMARY_RULE": "#f4d98a",
    "SUMMARY_TITLE": "#f5fffe",
    "MENU_SKY_TOP": "#06121b",
    "MENU_SKY_MID": "#0b2a35",
    "MENU_SKY_LOW": "#1c525b",
    "MENU_SKY_BOTTOM": "#497c74",
    "MENU_HILL_1": "#2a5d5b",
    "MENU_HILL_2": "#1b4246",
    "MENU_HILL_3": "#102e33",
    "MENU_PATH": "#e7cf8a",
    "MENU_CLOUD": "#bcd8dd",
    "MENU_INK": "#f5fffe",
    "MENU_FOOTER_BG": "#061a20",
    "MENU_FOOTER_FG": "#d9fbef",
    "TRADE_BG_1": "#061e23",
    "TRADE_BG_2": "#0a3a3f",
    "TRADE_BG_3": "#12636a",
    "TRADE_INK": "#f2fffb",
    "TRADE_PATTERN": "#a5efdc",
    "BANNER_BG": "#c7ead9",
    "BANNER_TEXT": "#173a34",
    "SHADOW": "#70040f15",
    "PANEL_RADIUS": "4",
    "CARD_RADIUS": "7",
    "CONTROL_RADIUS": "3",
    "BOX_FRAME": "#b9b3f0",
    "BOX_FRAME_INNER": "#b3d36a",
}

# Give every skin a PC-box frame pair.  Region themes can override these to
# carry a second accent (Hoenn gets Kyogre blue + Rayquaza gold; Sinnoh gets
# periwinkle + lake cyan) without changing the storage layout itself.
for _palette in PALETTES.values():
    _palette.setdefault("BOX_FRAME", _palette["NAVY_DARK"])
    _palette.setdefault("BOX_FRAME_INNER", _palette["PANEL"])

# Platinum's in-game PC is a bright mint / steel-blue / coral / olive
# composition, not a dark room.  Keep the title scene night-time (the MENU_*
# keys below stay dark), but let the application chrome use the box's actual
# colour families so the theme finally has the DS game's personality.
PALETTES["sinnoh"].update({
    "DESCRIPTION": "Platinum box mint, steel blue, coral and olive under a night sky.",
    "INK": "#253d45",
    "INK_SOFT": "#4d6b74",
    "INK_MUTED": "#78939a",
    "NAVY": "#4f7385",
    "NAVY_DARK": "#1f3b47",
    "BLUE": "#3e93bc",
    "BLUE_LIGHT": "#cfeaf4",
    "CREAM": "#fff8e8",
    "CREAM_ALT": "#f2ead8",
    "PAPER": "#fffdf6",
    "PANEL": "#f7fdfa",
    "PANEL_ALT": "#d7eee7",
    "FIELD": "#ffffff",
    "FIELD_ALT": "#edf7f2",
    "READONLY": "#d9eae4",
    "ORANGE": "#e78b8b",
    "ORANGE_DARK": "#a95358",
    "HEADER_LIGHT": "#6f9fa2",
    "HEADER": "#477585",
    "HEADER_DARK": "#2b5260",
    "ON_HEADER": "#ffffff",
    "GOLD": "#e7cd76",
    "YELLOW": "#faf0c2",
    "ON_GOLD": "#26343a",
    "ON_ACCENT": "#173039",
    "ON_DANGER": "#2c1114",
    "GREEN": "#8fb75e",
    "GREEN_DARK": "#597a3d",
    "GREEN_LIGHT": "#e9f3d4",
    "RED": "#d9777a",
    "RED_DARK": "#983e46",
    "RED_LIGHT": "#fae3e3",
    "PURPLE": "#cbbfee",
    "BORDER": "#7aa6b0",
    "BORDER_SOFT": "#b6d3d3",
    "BORDER_STRONG": "#274753",
    "HOVER": "#eefaf6",
    "HOVER_BORDER": "#e28a86",
    "PRESSED": "#d7ebe4",
    "DISABLED_BG": "#e5efeb",
    "DISABLED_FG": "#8ca09f",
    "DISABLED_BORDER": "#c1d5d1",
    "SCROLL_BG": "#e1f0ea",
    "SCROLL_HANDLE": "#8a86c9",
    "SCROLL_HANDLE_HOVER": "#e28a86",
    "APP_BG_TOP": "#c8f0e6",
    "APP_BG_BOTTOM": "#f7fdf8",
    "TOPBAR_BG": "#fbfffd",
    "TAB_BG": "#d8d4f3",
    "TAB_SELECTED_BG": "#fff3dc",
    "SUMMARY_BG_1": "#6f9cab",
    "SUMMARY_BG_2": "#4f7f8f",
    "SUMMARY_BG_3": "#315a6b",
    "SUMMARY_BORDER": "#294c59",
    "SUMMARY_CARD": "#fffaf0",
    "SUMMARY_STAT_BG": "#537e8e",
    "SUMMARY_STAT_TEXT": "#ffffff",
    "SUMMARY_MEMO_BG": "#fffaf0",
    "SUMMARY_MEMO_BORDER": "#e28a86",
    "SUMMARY_RULE": "#b4c96b",
    "SUMMARY_TITLE": "#1f3942",
    "TRADE_BG_1": "#cfe8e2",
    "TRADE_BG_2": "#a9d5d0",
    "TRADE_BG_3": "#7fbab4",
    "TRADE_INK": "#1d3942",
    "TRADE_PATTERN": "#ffffff",
    "BANNER_BG": "#4e8b70",
    "BANNER_TEXT": "#f8fff9",
    "BOX_FRAME": "#5a6f9e",
    "BOX_FRAME_INNER": "#b4c96b",
    "SHADOW": "#30102028",
})

# Emerald's chrome was reading as pale cream with green trim.  Push Rayquaza
# jade and gold through the panels and controls, keep Kyogre blue for links and
# Groudon crimson for warnings, and leave the text dark enough to stay crisp.
PALETTES["hoenn"].update({
    "APP_BG_TOP": "#6fce9f",
    "APP_BG_BOTTOM": "#e7f8dc",
    "TOPBAR_BG": "#f1fbe7",
    "TAB_BG": "#79c99f",
    "TAB_SELECTED_BG": "#ffe58a",
    "PANEL": "#fbfff3",
    "PANEL_ALT": "#d3ebc6",
    "FIELD": "#fcfff5",
    "FIELD_ALT": "#e1f2d8",
    "READONLY": "#d9edcf",
    "NAVY": "#075c45",
    "NAVY_DARK": "#032d24",
    "BLUE": "#176cc0",
    "BLUE_LIGHT": "#d4ebff",
    "HEADER_LIGHT": "#3ed49a",
    "HEADER": "#078b60",
    "HEADER_DARK": "#04503b",
    "BORDER": "#267d60",
    "BORDER_SOFT": "#a6cfb6",
    "BORDER_STRONG": "#032f27",
    "GOLD": "#f6d24f",
    "ORANGE": "#c9472f",
    "ORANGE_DARK": "#7e2618",
    "RED": "#b52f33",
    "RED_DARK": "#7a1f23",
    "SUMMARY_BG_1": "#83e0ae",
    "SUMMARY_BG_2": "#2aaf7a",
    "SUMMARY_BG_3": "#066147",
    "SUMMARY_BORDER": "#054b3b",
    "SUMMARY_CARD": "#fbfff3",
    "SUMMARY_STAT_BG": "#176cc0",
    "SUMMARY_STAT_TEXT": "#f8fff8",
    "SUMMARY_MEMO_BG": "#fbfff3",
    "SUMMARY_MEMO_BORDER": "#c9472f",
    "SUMMARY_RULE": "#f6d24f",
    "SCROLL_BG": "#d4ead0",
    "SCROLL_HANDLE": "#3c9975",
    "MENU_SKY_TOP": "#073f5d",
    "MENU_SKY_MID": "#0b756c",
    "MENU_SKY_LOW": "#63c58c",
    "MENU_SKY_BOTTOM": "#f0cf76",
    "MENU_HILL_1": "#76c78e",
    "MENU_HILL_2": "#43a372",
    "MENU_HILL_3": "#256d4d",
    "MENU_PATH": "#f3dc9c",
    "MENU_FOOTER_BG": "#043a32",
    "MENU_FOOTER_FG": "#eaf7d9",
    "TRADE_BG_1": "#043b34",
    "TRADE_BG_2": "#066458",
    "TRADE_BG_3": "#0e8a74",
    "BANNER_BG": "#075a47",
    "BANNER_TEXT": "#f4fff5",
    "BOX_FRAME": "#176cc0",
    "BOX_FRAME_INNER": "#f6d24f",
})

# The title screen is a visual skin, not a claim of connectivity to a
# particular game.  Keep its copy game-agnostic on every theme; the palette
# still supplies all of the colour and scene identity.
for _palette in PALETTES.values():
    _palette["MENU_OVERLINE"] = "POKéMON  •  WIRELESS LINK"
    _palette["MENU_FOOTER_TAG"] = "WIRELESS TRADE  •  STORAGE  •  LOCAL LINK"

# Title-screen copy sits on painted skylines, not on the application chrome.
# Give every skin an explicit muted ink so a previous theme's colour can never
# leak through a theme switch, then brighten the two night scenes and Hoenn's
# deep-teal overline where the default app ink would disappear.
for _palette in PALETTES.values():
    _palette.setdefault("MENU_TITLE_INK", _palette["MENU_INK"])
    _palette.setdefault("MENU_TITLE_INK_ALT", _palette["MENU_TITLE_INK"])
    _palette.setdefault("MENU_OVERLINE_INK", _palette["INK_SOFT"])
    _palette.setdefault("MENU_OVERLINE_INK_ALT", _palette["MENU_OVERLINE_INK"])
    _palette.setdefault("MENU_SUBTITLE_INK", _palette["INK_SOFT"])
    _palette.setdefault("MENU_SUBTITLE_INK_ALT", _palette["MENU_SUBTITLE_INK"])
PALETTES["hoenn"]["MENU_OVERLINE_INK"] = "#f2ead2"
PALETTES["hoenn"]["MENU_OVERLINE_INK_ALT"] = "#f2ead2"
PALETTES["sinnoh"]["MENU_OVERLINE_INK"] = "#cfe8e4"
PALETTES["sinnoh"]["MENU_OVERLINE_INK_ALT"] = "#cfe8e4"
PALETTES["sinnoh"]["MENU_SUBTITLE_INK"] = "#d9f0eb"
PALETTES["sinnoh"]["MENU_SUBTITLE_INK_ALT"] = "#d9f0eb"
PALETTES["unova"]["MENU_OVERLINE_INK"] = "#d6edf4"
PALETTES["unova"]["MENU_SUBTITLE_INK"] = "#d6edf4"
# HGSS and Hoenn also have a light half and a dark half behind the title,
# even though their scenery is not a hard split.  Give the right-hand copy
# the opposite ink so neither side is lost.
PALETTES["hgss"]["MENU_TITLE_INK"] = "#26345c"
PALETTES["hgss"]["MENU_TITLE_INK_ALT"] = "#26345c"
PALETTES["hgss"]["MENU_OVERLINE_INK"] = "#5c6172"
PALETTES["hgss"]["MENU_OVERLINE_INK_ALT"] = "#5c6172"
PALETTES["hgss"]["MENU_SUBTITLE_INK"] = "#5c6172"
PALETTES["hgss"]["MENU_SUBTITLE_INK_ALT"] = "#5c6172"
PALETTES["hoenn"]["MENU_TITLE_INK"] = "#f2ead2"
PALETTES["hoenn"]["MENU_TITLE_INK_ALT"] = "#073f36"
PALETTES["hoenn"]["MENU_OVERLINE_INK"] = "#f2ead2"
PALETTES["hoenn"]["MENU_OVERLINE_INK_ALT"] = "#073f36"
PALETTES["hoenn"]["MENU_SUBTITLE_INK"] = "#f2ead2"
PALETTES["hoenn"]["MENU_SUBTITLE_INK_ALT"] = "#073f36"

# Unova is split down the middle, so its title lock-up is the inverse of
# itself too: light ink on Reshiram's black half, dark ink on Zekrom's
# White Forest half.
PALETTES["unova"]["MENU_TITLE_INK"] = "#f2fbfd"
PALETTES["unova"]["MENU_TITLE_INK_ALT"] = "#0b2731"
PALETTES["unova"]["MENU_OVERLINE_INK"] = "#d6edf4"
PALETTES["unova"]["MENU_OVERLINE_INK_ALT"] = "#36525c"
PALETTES["unova"]["MENU_SUBTITLE_INK"] = "#d6edf4"
PALETTES["unova"]["MENU_SUBTITLE_INK_ALT"] = "#27434c"
# The FRLG title scene is now the red/green box-art vortex instead of a pale
# Kanto sky, so its title lock-up uses warm cream rather than dark navy.
PALETTES["frlg"]["MENU_TITLE_INK"] = "#fff8e2"
PALETTES["frlg"]["MENU_TITLE_INK_ALT"] = "#fff8e2"
PALETTES["frlg"]["MENU_OVERLINE_INK"] = "#ffeccb"
PALETTES["frlg"]["MENU_OVERLINE_INK_ALT"] = "#ffeccb"
PALETTES["frlg"]["MENU_SUBTITLE_INK"] = "#fff3d8"
PALETTES["frlg"]["MENU_SUBTITLE_INK_ALT"] = "#fff3d8"

THEME_ORDER = ["frlg", "hoenn", "hgss", "sinnoh", "unova", "light", "dark"]
THEME_CHOICES = [(key, PALETTES[key]["LABEL"]) for key in THEME_ORDER]

# Older builds stored generation numbers in assets/ui/theme.txt.  Keep those
# settings valid so an upgrade never drops the user back to the default skin.
LEGACY_THEME_ALIASES = {
    "gen3": "frlg",
    "gen4_light": "hgss",
    "gen4_dark": "dark",
    "gen5": "unova",
}


def canonical_theme_id(theme_id: str) -> str:
    """Translate a legacy saved id to its region-named equivalent."""
    return LEGACY_THEME_ALIASES.get(theme_id, theme_id)


# Active theme metadata (filled by _activate()).
THEME_ID = "hgss"
THEME_LABEL = PALETTES[THEME_ID]["LABEL"]
THEME_SHORT_LABEL = PALETTES[THEME_ID]["SHORT_LABEL"]
THEME_MENU_STYLE = PALETTES[THEME_ID]["MENU_STYLE"]

# ---------------------------------------------------------------------------
# Active palette aliases
# ---------------------------------------------------------------------------
# These names are read directly by the tab modules; set_theme() replaces them
# in place, which is why custom paintEvent() methods always use fresh colours.
INK = "#2b2b33"
INK_SOFT = "#5c6172"
INK_MUTED = "#7c8090"
NAVY = "#34477c"
NAVY_DARK = "#26345c"
BLUE = "#5b78c7"
BLUE_LIGHT = "#a9c1ef"
CREAM = "#fbf5df"
CREAM_ALT = "#f0e6c9"
PAPER = "#fffdf6"
PANEL = "#fffdf6"
PANEL_ALT = "#f8f1dc"
FIELD = "#fffdf6"
FIELD_ALT = "#f7f0dd"
READONLY = "#f3ead2"
ORANGE = "#e9822e"
ORANGE_DARK = "#b8591d"
HEADER_LIGHT = "#f09a4e"
HEADER = "#e9822e"
HEADER_DARK = "#b8591d"
ON_HEADER = "#fffdf6"
GOLD = "#f4c84a"
YELLOW = "#fbe58a"
ON_GOLD = "#2b2b33"
ON_ACCENT = "#fffdf6"
ON_DANGER = "#fffdf6"
GREEN = "#4caf72"
GREEN_DARK = "#2f7d4f"
GREEN_LIGHT = "#e3f5e5"
RED = "#d94b47"
RED_DARK = "#9e2f31"
RED_LIGHT = "#fbe4e2"
PURPLE = "#b9b9f4"
BORDER = "#7b89ac"
BORDER_SOFT = "#c8bea3"
BORDER_STRONG = "#26345c"
HOVER = "#fff8d8"
HOVER_BORDER = "#e9822e"
PRESSED = "#f0e6c9"
DISABLED_BG = "#e5dfd1"
DISABLED_FG = "#96938a"
DISABLED_BORDER = "#b8b2a3"
SCROLL_BG = "#e7dfca"
SCROLL_HANDLE = "#8fa3cc"
SCROLL_HANDLE_HOVER = "#f4c84a"
APP_BG_TOP = "#e9e1cd"
APP_BG_BOTTOM = "#f6f0df"
TOPBAR_BG = "#fffdf6"
TAB_BG = "#ded5bd"
TAB_SELECTED_BG = "#fbf5df"
SUMMARY_BG_1 = "#d3d1f8"
SUMMARY_BG_2 = "#b9b9f4"
SUMMARY_BG_3 = "#aabcea"
SUMMARY_BORDER = "#7a7cc0"
SUMMARY_CARD = "#fdfbe6"
SUMMARY_STAT_BG = "#6f83bb"
SUMMARY_STAT_TEXT = "#ffffff"
SUMMARY_MEMO_BG = "#fdfbe6"
SUMMARY_MEMO_BORDER = "#e8a878"
SUMMARY_RULE = "#f4c84a"
SUMMARY_TITLE = "#26345c"
MENU_SKY_TOP = "#bfe6f7"
MENU_SKY_MID = "#dcf1f4"
MENU_SKY_LOW = "#f7edcd"
MENU_SKY_BOTTOM = "#f3e3ba"
MENU_HILL_1 = "#c4dab6"
MENU_HILL_2 = "#9dc68f"
MENU_HILL_3 = "#78ae6a"
MENU_PATH = "#f6e7ba"
MENU_CLOUD = "#ffffff"
MENU_INK = "#26345c"
MENU_TITLE_INK = "#26345c"
MENU_TITLE_INK_ALT = "#26345c"
MENU_FOOTER_BG = "#1d2b44"
MENU_FOOTER_FG = "#ffffff"
MENU_OVERLINE = "POKéMON  •  WIRELESS LINK"
MENU_FOOTER_TAG = "WIRELESS TRADE  •  STORAGE  •  LOCAL LINK"
TRADE_BG_1 = "#1a2c55"
TRADE_BG_2 = "#27477c"
TRADE_BG_3 = "#355f97"
TRADE_INK = "#fffdf6"
TRADE_PATTERN = "#ffffff"
BANNER_BG = "#26345c"
BANNER_TEXT = "#fffdf6"
PANEL_RADIUS = "9"
CARD_RADIUS = "17"
CONTROL_RADIUS = "6"

SHADOW = QColor("#30262d3e")

# Fonts loaded by init_app(); the fallbacks keep headless harnesses working.
FONT_DS = "DejaVu Sans"
FONT_GBA = "DejaVu Sans"
FONT_SIZE = 15
BODY_FAMILY = FONT_DS

# UI size choices, in the spirit of Minecraft's GUI scale.  These are applied
# as Qt's global scale factor before the QApplication exists, so a change takes
# effect on the next launch.  100% follows the desktop's own Qt scaling.
SCALE_CHOICES: tuple[float, ...] = (0.90, 1.00, 1.25, 1.50, 2.00)
SCALE_DEFAULT = 1.00
SCALE_DESCRIPTIONS = {
    0.90: "Compact",
    1.00: "Desktop",
    1.25: "Comfortable",
    1.50: "Large",
    2.00: "Maximum",
}
_ACTIVE_SCALE = SCALE_DEFAULT
_BASE_SCALE = 1.0

_loaded_fonts: set[str] = set()
_initialised = False
_BASE_DS = "DejaVu Sans"
_BASE_GBA = "DejaVu Sans"
_assets_ready: set[str] = set()


def _activate(theme_id: str) -> None:
    """Copy a palette into the module-level names used by the UI."""
    global THEME_ID, THEME_LABEL, THEME_SHORT_LABEL, THEME_MENU_STYLE
    global SHADOW, UI_DIR, BODY_FAMILY

    theme_id = canonical_theme_id(str(theme_id))
    spec = PALETTES.get(theme_id) or PALETTES["hgss"]
    THEME_ID = theme_id if theme_id in PALETTES else "hgss"
    THEME_LABEL = spec["LABEL"]
    THEME_SHORT_LABEL = spec["SHORT_LABEL"]
    THEME_MENU_STYLE = spec["MENU_STYLE"]

    for key, value in spec.items():
        if key.startswith("_") or key in ("LABEL", "SHORT_LABEL", "DESCRIPTION", "MENU_STYLE"):
            continue
        globals()[key] = value

    SHADOW = QColor(spec["SHADOW"])
    UI_DIR = UI_ROOT / THEME_ID
    # Dense form text always uses the narrower DS face.  Gen 3 still carries
    # its GBA identity through every header, plate and button, but using the
    # wider pixel face for body copy inflated the forms past 1180 px.
    BODY_FAMILY = FONT_DS


def _read_saved_theme() -> str:
    for source in (SETTINGS_FILE, UI_ROOT / "theme.txt"):
        try:
            value = canonical_theme_id(source.read_text(encoding="utf-8").strip())
            if value in PALETTES:
                return value
        except OSError:
            continue
    return "hgss"


def _save_theme(theme_id: str) -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(canonical_theme_id(theme_id) + "\n", encoding="utf-8")
    except OSError:
        pass


def _as_scale(value) -> float | None:
    """Return the nearest supported scale, or None if the value is unusable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    for choice in SCALE_CHOICES:
        if abs(choice - number) < 0.001:
            return choice
    return None


def read_saved_scale() -> float:
    for source in (SCALE_FILE, UI_ROOT / "ui_scale.txt"):
        try:
            saved = _as_scale(source.read_text(encoding="utf-8").strip())
            if saved is not None:
                return saved
        except OSError:
            continue
    return SCALE_DEFAULT


def save_scale(scale: float) -> bool:
    choice = _as_scale(scale)
    if choice is None:
        return False
    try:
        SCALE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCALE_FILE.write_text(f"{choice:g}\n", encoding="utf-8")
        return True
    except OSError:
        return False


def apply_scale_environment() -> float:
    """Install the saved UI scale before QApplication is constructed.

    Qt reads QT_SCALE_FACTOR once, at startup.  The app's 100% is layered on
    top of whatever Qt scaling the desktop already uses; otherwise choosing
    "100%" would silently undo a system accessibility scale.  The base is
    carried across a restart in FRLG_BASE_QT_SCALE so it is never applied
    twice.
    """
    global _ACTIVE_SCALE, _BASE_SCALE
    _ACTIVE_SCALE = read_saved_scale()
    raw_base = os.environ.get("FRLG_BASE_QT_SCALE")
    if raw_base is None:
        raw_base = os.environ.get("QT_SCALE_FACTOR", "1")
    try:
        _BASE_SCALE = float(raw_base)
    except (TypeError, ValueError):
        _BASE_SCALE = 1.0
    os.environ["FRLG_BASE_QT_SCALE"] = f"{_BASE_SCALE:g}"
    os.environ["QT_SCALE_FACTOR"] = f"{_BASE_SCALE * _ACTIVE_SCALE:g}"
    return _ACTIVE_SCALE


def active_scale() -> float:
    return _ACTIVE_SCALE


def base_scale() -> float:
    """The desktop's Qt scale, before the app's own UI-size multiplier."""
    return _BASE_SCALE


def scale_label(scale: float) -> str:
    return f"{round(scale * 100):d}%"


def scale_description(scale: float) -> str:
    return SCALE_DESCRIPTIONS.get(_as_scale(scale) or SCALE_DEFAULT, "Desktop")


def scale_fits_screen(screen, scale: float) -> bool:
    """Whether the app's 1180x820 working minimum fits after scaling.

    QScreen geometry is already expressed in device-independent pixels for the
    current factor, so convert through the current factor before applying the
    candidate.  The 24/48 px allowance leaves room for window decorations.
    """
    if screen is None:
        return True
    candidate = _as_scale(scale)
    if candidate is None:
        return False
    geometry = screen.availableGeometry()
    current = _ACTIVE_SCALE or SCALE_DEFAULT
    width = geometry.width() * current / candidate
    height = geometry.height() * current / candidate
    return width >= 1180 + 24 and height >= 820 + 32


# ---------------------------------------------------------------------------
# Fonts and application setup
# ---------------------------------------------------------------------------
def _load_font(path: Path) -> str | None:
    if not path.exists():
        return None
    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id < 0:
        return None
    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else None


def ui_font(size: int = FONT_SIZE, *, gba: bool = False, bold: bool = False) -> QFont:
    font = QFont(FONT_GBA if gba else FONT_DS)
    font.setPixelSize(size)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return font


def _apply_app_palette(app: QApplication) -> None:
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(CREAM_ALT))
    pal.setColor(QPalette.ColorRole.Base, QColor(FIELD))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_ALT))
    pal.setColor(QPalette.ColorRole.Text, QColor(INK))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(INK))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(INK))
    pal.setColor(QPalette.ColorRole.Button, QColor(PANEL))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(GOLD))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(ON_GOLD))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(INK))
    app.setPalette(pal)


def _hover_fill() -> str:
    """The theme's own row-highlight colour for dropdown hover.

    Lightening GOLD by 55% produced an almost-white row in dark palettes
    (Unova's cyan became #d0f4fb) while the row text stayed near-white, so
    the hovered option was unreadable.  Every palette already defines HOVER
    as a subtle tint that its own INK is legible on, so use that instead of
    deriving a lighter accent.
    """
    return HOVER


class _ComboListPopup(QFrame):
    """The dropdown list, drawn inside the app window instead of by the OS.

    Qt hands a combo's list to the compositor as a separate popup window.  On
    Wayland the compositor owns that window's position, and Qt reports the
    anchor in the window's unscaled coordinates, so the list could land at
    two thirds of the field's position or, when the popup grab was refused,
    in the middle of the screen.  Moving that native window afterwards cannot
    fix it reliably: the app is not the one placing it.

    This widget is an ordinary child of the window that owns the combo.  Its
    geometry is in the same coordinate system as the field, so it opens flush
    under (or above) the field at 90%, 100%, 125%, 150% and 200%, on Wayland,
    X11 or a nested compositor.  It shows the combo's own model, so item text,
    item data and the current selection are the same objects the native list
    displayed.
    """

    MARGIN = 6
    ROW_MIN = 18
    BORDER = 4

    def __init__(self, combo: "AppComboBox"):
        super().__init__(combo.window())
        self.combo = combo
        self._committed = False
        self._filtered = False
        # Typed searches reuse this frame: the proxy narrows the combo's own
        # model, so the matches are drawn and clicked exactly like the list
        # that opens from the arrow.
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(0)
        self._proxy.setDynamicSortFilter(True)
        self.setObjectName("frlgComboPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view = QListView(self)
        self.view.setObjectName("frlgComboList")
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.viewport().setMouseTracking(True)
        self.view.installEventFilter(self)
        self.view.clicked.connect(self._commit)
        self.view.activated.connect(self._commit)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view)
        self.hide()

    # -- theming ----------------------------------------------------------
    def apply_theme(self) -> None:
        # The list lives inside the main window, so it inherits the app
        # stylesheet, but the colours are restated from the active palette in
        # case a theme switch happened since the last time it opened.
        self.setStyleSheet(
            # padding: 0 is load-bearing: the app stylesheet gives
            # #frlgComboPopup 12 px of vertical padding for Qt's native
            # combo popup, which would shrink this frame's list viewport by
            # 24 px and clip the last visible row.
            "QFrame#frlgComboPopup { background-color: %s;"
            " border: 2px solid %s; border-radius: 3px; padding: 0px; }"
            "QListView#frlgComboList { background-color: transparent;"
            " color: %s; border: none; outline: none; }"
            "QListView#frlgComboList::item { padding: 4px 8px; }"
            "QListView#frlgComboList::item:hover { background-color: %s;"
            " color: %s; }"
            "QListView#frlgComboList::item:selected { background-color: %s;"
            " color: %s; }"
            % (PANEL, NAVY, INK, _hover_fill(), INK, GOLD, ON_GOLD)
        )

    # -- placement --------------------------------------------------------
    def open_at_combo(self, focus: bool = True) -> None:
        combo = self.combo
        window = combo.window()
        if window is None or not window.isVisible() or not combo.isVisible():
            return
        model = combo.model()
        total = combo.count()
        if model is None or total <= 0:
            return
        self._committed = False
        self._open_list(model, total, combo.currentIndex(), focus=focus)

    def open_filtered(self, text: str) -> None:
        """Open the same in-window list, narrowed to the typed text.

        Typed searches used to hand the list to Qt's own completer window,
        which the compositor then placed independently of the app (the list
        could land on the wallpaper).  Filtering the combo's own model through
        this frame keeps the matches in the window, under the field, drawn and
        clicked exactly like the arrow list.
        """
        combo = self.combo
        window = combo.window()
        if window is None or not window.isVisible() or not combo.isVisible():
            return
        source = combo.model()
        if source is None or combo.count() <= 0:
            return
        if self._proxy.sourceModel() is not source:
            self._proxy.setSourceModel(source)
        self._proxy.setFilterFixedString(text)
        total = self._proxy.rowCount()
        if total <= 0:
            self.close_popup(restore_focus=True)
            return
        self._committed = False
        best = self._best_match_row(text)
        self._open_list(self._proxy, total, best, focus=False)
        # A filtered list starts at the top, but the best match can be lower
        # down a broad search (for example "water").  Keep the highlighted
        # row visible so Enter/Tab accept the row the player can see.
        index = self.view.model().index(best, 0)
        if index.isValid():
            self.view.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)

    def _best_match_row(self, text: str) -> int:
        """Pick the row a typed search should highlight first.

        The list is ordered by the combo's own model, so a `contains` filter
        can put an incidental early hit above the option the player meant.
        Prefer an exact label, then a label whose name part starts with the
        typed text, then the first filtered row.
        """
        needle = (text or "").strip().casefold()
        if not needle or self._proxy.rowCount() <= 0:
            return 0
        prefix = None
        for row in range(self._proxy.rowCount()):
            label = str(self._proxy.index(row, 0).data() or "").casefold()
            if label == needle:
                return row
            name = label.split(" ", 1)[1] if " " in label else label
            if prefix is None and (label.startswith(needle)
                                   or name.startswith(needle)):
                prefix = row
        return 0 if prefix is None else prefix

    def _open_list(self, model, total: int, current: int,
                   *, focus: bool) -> None:
        combo = self.combo
        window = combo.window()
        if window is None:
            return
        self.apply_theme()
        self.view.setModel(model)
        self.view.setRootIndex(
            combo.rootModelIndex() if model is combo.model()
            else QModelIndex())
        self.view.ensurePolished()

        nominal = self.view.sizeHintForRow(0)
        if nominal <= 0:
            nominal = combo.fontMetrics().height() + 12
        row_h = max(self.ROW_MIN, nominal)

        content_w = self.view.sizeHintForColumn(0)
        scroll_w = 0
        rows = max(1, min(total, combo.MAX_VISIBLE))
        if total > rows:
            scroll_w = self.view.verticalScrollBar().sizeHint().width()
        width = max(combo.width(), content_w + scroll_w + 12)
        width = min(width, max(combo.MAX_WIDTH, combo.width()))
        width = max(120, min(width, window.width() - 2 * self.MARGIN))

        origin = combo.mapTo(window, QPoint(0, 0))
        bottom = origin.y() + combo.height()
        left = origin.x()
        left = max(self.MARGIN, min(left, window.width() - self.MARGIN - width))

        # Lay the list out at its final width before measuring it.  The
        # stylesheet's item padding only reaches the delegate once the view
        # has a real viewport, so sizeHintForRow() alone under-reports the row
        # height on Wayland (22 px planned against 29 px painted).  The popup
        # then showed two and a half rows of a three-row list, and clicking
        # the third row landed outside the list.
        self.setGeometry(left, min(bottom, window.height() - self.MARGIN - 1),
                         width, row_h + self.BORDER)
        self.view.doItemsLayout()
        row_h = self._painted_row_height(model)
        self.setGeometry(*self._place(
            origin.y(), bottom, left, width, row_h, total))
        self.view.doItemsLayout()

        if 0 <= current < total:
            index = model.index(current, 0)
            self.view.setCurrentIndex(index)
            # EnsureVisible instead of PositionAtCenter: centring a short
            # list scrolls even when every row already fits, which hid the
            # top rows behind the frame edge.  This only scrolls when the
            # current item is actually outside the viewport.
            if focus:
                self.view.scrollTo(
                    index, QAbstractItemView.ScrollHint.EnsureVisible)
            else:
                self.view.scrollToTop()
        else:
            self.view.clearSelection()

        self._install_filters()
        self.show()
        self.raise_()
        self.view.doItemsLayout()
        settled = self._painted_row_height(model)
        if abs(settled - row_h) > 1:
            # The first paint settled on a different row height; re-fit so
            # every shown row stays clickable.
            self.setGeometry(*self._place(
                origin.y(), bottom, left, width, settled, total))
            self.view.doItemsLayout()
        if focus:
            self.view.setFocus(Qt.FocusReason.PopupFocusReason)
        # Some layouts shift by a few pixels when the list takes focus.
        # Re-anchor from the field's final position so the gap stays zero.
        final = combo.mapTo(window, QPoint(0, 0))
        final_bottom = final.y() + combo.height()
        if final != origin:
            final_left = max(self.MARGIN, min(
                final.x(), window.width() - self.MARGIN - width))
            self.setGeometry(*self._place(
                final.y(), final_bottom, final_left, width, settled, total))
            self.view.doItemsLayout()
        # A layout can also settle one event-loop turn later; re-anchor then
        # so the list never keeps the few-pixel gap from the pre-layout field.
        QTimer.singleShot(0, self._reanchor)

    def _reanchor(self) -> None:
        """Re-place a visible list after its field has finished moving."""
        try:
            if not self.isVisible():
                return
            combo = self.combo
        except RuntimeError:
            # The window was closed before the deferred re-anchor ran.
            return
        window = combo.window()
        if window is None or not window.isVisible() or not combo.isVisible():
            return
        model = self.view.model()
        if model is None or model.rowCount() <= 0:
            return
        origin = combo.mapTo(window, QPoint(0, 0))
        left = max(self.MARGIN, min(
            origin.x(), window.width() - self.MARGIN - self.width()))
        row_h = self._painted_row_height(model)
        self.setGeometry(*self._place(
            origin.y(), origin.y() + combo.height(), left, self.width(),
            row_h, model.rowCount()))
        self.view.doItemsLayout()

    def _painted_row_height(self, model) -> int:
        """The height the delegate actually paints a row with right now."""
        height = self.view.visualRect(model.index(0, 0)).height()
        if height <= 0:
            height = self.view.sizeHintForRow(0)
        if height <= 0:
            height = self.combo.fontMetrics().height() + 12
        return max(self.ROW_MIN, height)

    def _place(self, field_top: int, field_bottom: int, left: int,
               width: int, row_h: int,
               total: int) -> tuple[int, int, int, int]:
        """Place whole rows under the field, or above it when space is short."""
        combo = self.combo
        window = combo.window()
        rows = max(1, min(total, combo.MAX_VISIBLE))
        rows = min(rows, max(1, (combo.MAX_HEIGHT - self.BORDER) // row_h))
        full_h = rows * row_h + self.BORDER
        below = window.height() - self.MARGIN - field_bottom
        above = field_top - self.MARGIN
        if full_h <= below:
            return left, field_bottom, width, full_h
        if full_h <= above:
            return left, field_top - full_h, width, full_h
        if below >= above:
            return left, field_bottom, width, self._fit(below, row_h)
        height = self._fit(above, row_h)
        return left, field_top - height, width, height

    def _fit(self, space: int, row_h: int) -> int:
        rows = max(1, int((space - self.BORDER) // row_h))
        return min(space, rows * row_h + self.BORDER)

    # -- lifetime ---------------------------------------------------------
    def _install_filters(self) -> None:
        if self._filtered:
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.combo.installEventFilter(self)
        window = self.combo.window()
        if window is not None:
            window.installEventFilter(self)
        line = self.combo.lineEdit() if self.combo.isEditable() else None
        if line is not None:
            line.installEventFilter(self)
        self._filtered = True

    def _remove_filters(self) -> None:
        if not self._filtered:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        try:
            self.combo.removeEventFilter(self)
            window = self.combo.window()
            if window is not None:
                window.removeEventFilter(self)
            line = self.combo.lineEdit() if self.combo.isEditable() else None
            if line is not None:
                line.removeEventFilter(self)
        except RuntimeError:
            pass
        self._filtered = False

    def close_popup(self, *, restore_focus: bool = False) -> None:
        self._remove_filters()
        if self.isVisible():
            self.hide()
        if restore_focus:
            try:
                line = self.combo.lineEdit()
                target = line if line is not None else self.combo
                if target.isVisible():
                    target.setFocus(Qt.FocusReason.OtherFocusReason)
            except RuntimeError:
                pass

    def _commit(self, index) -> None:
        if not index.isValid() or self._committed:
            return
        self._committed = True
        combo = self.combo
        model = self.view.model()
        source = model.mapToSource(index) if model is self._proxy else index
        row = source.row()
        if row < 0 or row >= combo.count():
            self.close_popup(restore_focus=True)
            return
        combo.setCurrentIndex(row)
        # Match a real selection in Qt's own list: the combo and every
        # currentIndexChanged/activated handler see the new row.
        combo.activated[int].emit(row)
        self.close_popup(restore_focus=True)

    def _current_or_first(self):
        """The highlighted row, or the first row when nothing is highlighted."""
        model = self.view.model()
        if model is None or model.rowCount() <= 0:
            return None
        index = self.view.currentIndex()
        if not index.isValid() or not (0 <= index.row() < model.rowCount()):
            index = model.index(0, 0)
            self.view.setCurrentIndex(index)
            self.view.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)
        return index

    def _move_current(self, delta: int) -> None:
        """Move the highlighted row while the line edit keeps the keyboard."""
        model = self.view.model()
        if model is None or model.rowCount() == 0:
            return
        row = self.view.currentIndex().row()
        if row < 0:
            row = 0 if delta > 0 else model.rowCount() - 1
        else:
            row = max(0, min(model.rowCount() - 1, row + delta))
        index = model.index(row, 0)
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)

    def _line_edit(self):
        """The editable field, or None when this combo is read-only."""
        try:
            return self.combo.lineEdit() if self.combo.isEditable() else None
        except RuntimeError:
            return None

    def handle_key(self, key: int) -> bool:
        """Handle the search field's keyboard contract for any event target.

        Qt delivers keys to the focused QComboBox while the line edit is its
        focus proxy.  Filtering only the line edit therefore worked when a
        test addressed the line directly but not for a real keypress.  This
        method is shared by the line, the combo and the list so Enter and the
        arrow keys behave the same however focus reached the field.
        """
        line = self._line_edit()
        popup_open = self.isVisible()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            if popup_open:
                self._move_current(1 if key == Qt.Key.Key_Down else -1)
            else:
                # Down/Up opens the list for an editable field too: with
                # typed text it shows only the matches, otherwise the full
                # list.  A click selects the entire existing value, so treat
                # that selected value as "no query" and show every choice,
                # just like a native combo arrow.
                text = line.text().strip() if line is not None else ""
                if (line is not None and text and line.hasSelectedText()
                        and line.selectedText() == line.text()):
                    text = ""
                if text:
                    self.open_filtered(text)
                else:
                    self.open_at_combo(focus=False)
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if popup_open:
                index = self._current_or_first()
                if index is not None:
                    self._commit(index)
                else:
                    self.close_popup(restore_focus=True)
                return True
            # A real Enter arrives at the combo, not the line.  If the list
            # was closed by a transient filter update, resolve the typed text
            # against a fresh filtered list instead of letting QComboBox pick
            # an unrelated first item from its own native search.
            text = line.text().strip() if line is not None else ""
            if text:
                self.open_filtered(text)
                if self.isVisible():
                    index = self._current_or_first()
                    if index is not None:
                        self._commit(index)
                        return True
                # Keep a no-match query intact.  Falling through to Qt's own
                # QComboBox search here selected an unrelated first item.
                self.close_popup(restore_focus=True)
                return True
            return False
        if key == Qt.Key.Key_Escape:
            if popup_open:
                self.close_popup(restore_focus=True)
                return True
            return False
        if key == Qt.Key.Key_Tab:
            # Tab accepts the highlighted match, like a shell completion.
            # It only does so while the list is open, so a later Tab still
            # moves focus instead of reopening this field forever.
            if popup_open:
                index = self._current_or_first()
                if index is not None:
                    self._commit(index)
                    return True
                self.close_popup(restore_focus=True)
            return False
        if key == Qt.Key.Key_Backtab:
            if popup_open:
                self.close_popup()
            return False
        if popup_open and key in (Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
            step = self.combo.MAX_VISIBLE if key == Qt.Key.Key_PageDown else -self.combo.MAX_VISIBLE
            self._move_current(step)
            return True
        return False

    def eventFilter(self, obj, event) -> bool:
        kind = event.type()
        line = self._line_edit()
        if kind == QEvent.Type.KeyPress and line is not None and obj is line:
            if self.handle_key(event.key()):
                return True
        if kind == QEvent.Type.KeyPress and obj is self.combo and self.isVisible():
            if self.handle_key(event.key()):
                return True
        if kind == QEvent.Type.KeyPress and obj is self.view:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close_popup(restore_focus=True)
                return True
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                # Some focus paths hand the list itself the keyboard (for
                # example a click on the popup before it settles).  Keep the
                # same arrow/Enter contract as the line-edit path instead of
                # falling back to Qt's default list handling.
                self._move_current(1 if key == Qt.Key.Key_Down else -1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                index = self._current_or_first()
                if index is not None:
                    self._commit(index)
                else:
                    self.close_popup(restore_focus=True)
                return True
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                self.close_popup()
                return False
        if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
            # Qt delivers a press twice to an application filter: once for
            # the top-level QWindow and once for the widget under the
            # pointer.  QWindow is not a QWidget, so the first pass used to
            # fall through to the close below and hid the list before the
            # row could take the click.  Only widget targets can mean
            # "clicked somewhere else".
            if not isinstance(obj, QWidget):
                return False
            if obj is self or self.isAncestorOf(obj):
                return False
            combo = self.combo
            if obj is combo or combo.isAncestorOf(obj):
                return False
            if kind == QEvent.Type.Wheel:
                # Scrolling past the first or last row can bounce the wheel
                # event to a widget behind the list; the pointer is still
                # over the list, so that is not an outside click.
                try:
                    point = event.globalPosition().toPoint()
                except (AttributeError, TypeError):
                    point = None
                if point is not None and (
                        self.rect().contains(self.mapFromGlobal(point))
                        or combo.rect().contains(combo.mapFromGlobal(point))):
                    return False
            self.close_popup()
            return False
        if isinstance(obj, QWidget) and kind in (
                QEvent.Type.Hide, QEvent.Type.Resize, QEvent.Type.Move,
                QEvent.Type.WindowDeactivate):
            try:
                combo = self.combo
                window = combo.window()
            except RuntimeError:
                self.close_popup()
                return False
            if obj is combo and kind == QEvent.Type.Move and self.isVisible():
                # The field moved under the open list (layout still settling
                # after a tab switch, for example); stay glued to it.
                self._reanchor()
            elif obj is combo and kind == QEvent.Type.Hide:
                self.close_popup()
            elif obj is window and kind in (
                    QEvent.Type.Resize, QEvent.Type.Move,
                    QEvent.Type.WindowDeactivate, QEvent.Type.Hide):
                self.close_popup()
        return False


class AppComboBox(QComboBox):
    """A combo box whose list opens under the field, inside the app window.

    Qt sizes a combo popup from the view's content and the current scale;
    long Gen 3 item, species and location lists can therefore cover most of
    the window.  This subclass caps the visible rows and the pixel height and
    opens the list as a child of the window, flush with the field, so the
    result is identical at every UI scale and does not depend on how the
    compositor places native popup windows.
    """

    MAX_VISIBLE = 8
    MAX_HEIGHT = 300
    MAX_WIDTH = 520
    # View border (2+2) plus the 12 px top/bottom QSS padding.  Subtracting
    # this from the popup height leaves exactly one row per visible item.
    POPUP_CHROME = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaxVisibleItems(self.MAX_VISIBLE)
        self._search_hook_installed = False
        self._line_filter_widget = None
        self._limit_view()

    def _limit_view(self) -> None:
        view = self.view()
        view.setObjectName("frlgComboPopup")
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setMouseTracking(True)
        view.viewport().setMouseTracking(True)
        completer = self.completer()
        if completer is not None:
            completer.setMaxVisibleItems(self.MAX_VISIBLE)
            # Typed matches are drawn by _ComboListPopup inside the window.
            # An empty completer model stops Qt from creating its own
            # top-level completion window, which the compositor could place
            # anywhere (on Wayland it landed on the wallpaper at 150%).
            # QComboBox does not refill this model when items are added.
            completer.setModel(QStringListModel([]))
            line = self.lineEdit()
            if line is not None and not self._search_hook_installed:
                line.textEdited.connect(self._on_search_text)
                self._search_hook_installed = True
            if line is not None and line is not self._line_filter_widget:
                if self._line_filter_widget is not None:
                    try:
                        self._line_filter_widget.removeEventFilter(self)
                    except RuntimeError:
                        pass
                line.installEventFilter(self)
                self._line_filter_widget = line

    def _on_search_text(self, text: str) -> None:
        """Show typed matches in the same in-window list as the arrow."""
        popup = self._popup_overlay()
        text = (text or "").strip()
        if not text:
            if popup.isVisible():
                popup.close_popup(restore_focus=True)
            return
        popup.open_filtered(text)

    def _select_all_search_text(self) -> None:
        """Make a click or focus start a fresh query, not append to the old one.

        Without this, clicking a populated editable field put the caret at the
        end.  Typing `rai` after `#001 Bulbasaur` produced
        `#001 Bulbasaurrai`, no row matched, and Enter had nothing to commit.
        """
        try:
            line = self.lineEdit()
        except RuntimeError:
            return
        if line is not None and line.isVisible():
            line.selectAll()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._line_filter_widget:
            if event.type() in (
                QEvent.Type.FocusIn,
                QEvent.Type.MouseButtonPress,
            ):
                # Run after the field has placed its caret.
                QTimer.singleShot(0, self._select_all_search_text)
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        # QComboBox is the real focus widget; its line edit is only the focus
        # proxy.  Let the in-window list handle Enter and the arrow keys here
        # as well, otherwise a normal keypress bypasses the line-edit filter.
        if self.isEditable():
            popup = self._popup_overlay()
            if popup.handle_key(event.key()):
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        # Clicking the field again after a selection must start a fresh query.
        # The line edit only receives clicks inside its text area; a click on
        # the combo's padding or arrow lands on the combo itself and used to
        # leave the old value selected no more, so typing appended to it and
        # the filtered list found nothing.
        if self.isEditable() and event.button() == Qt.MouseButton.LeftButton:
            try:
                line = self.lineEdit()
            except RuntimeError:
                line = None
            if line is not None:
                line.setFocus(Qt.FocusReason.MouseFocusReason)
                QTimer.singleShot(0, self._select_all_search_text)
        super().mousePressEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().focusInEvent(event)
        if self.isEditable():
            QTimer.singleShot(0, self._select_all_search_text)

    def _popup_overlay(self) -> _ComboListPopup:
        popup = getattr(self, "_list_popup", None)
        if not isinstance(popup, _ComboListPopup):
            popup = _ComboListPopup(self)
            self._list_popup = popup
        return popup


    def setEditable(self, editable: bool) -> None:
        super().setEditable(editable)
        self._limit_view()

    def showPopup(self) -> None:
        """Open the in-window list under this field.

        The list is an ordinary child widget, so this app decides its
        position in the window's own coordinates instead of asking a
        compositor to place a native popup window.  That is what keeps it
        flush with the field at every UI scale, on every session type.
        """
        self.setMaxVisibleItems(self.MAX_VISIBLE)
        popup = self._popup_overlay()
        if popup.isVisible():
            popup.close_popup(restore_focus=True)
            return
        # Editable fields keep the keyboard in the line edit, exactly like
        # Qt's native list, so typing right after clicking the arrow still
        # narrows the list instead of typing into nothing.  Select the
        # existing value so the next keypress starts a search rather than
        # appending to the previous species or move.
        if self.isEditable():
            QTimer.singleShot(0, self._select_all_search_text)
        popup.open_at_combo(focus=not self.isEditable())

    def hidePopup(self) -> None:
        popup = getattr(self, "_list_popup", None)
        if popup is not None and popup.isVisible():
            popup.close_popup()
        super().hidePopup()


class _WidgetTooltip(QFrame):
    """A themed tooltip bubble that is positioned from scratch every time.

    Qt's built-in tooltip label is reused across hovers.  Re-showing the same
    text keeps the previous window geometry, which is why a tooltip could
    appear at a stale mouse position or near the centre of the window.  Owning
    the bubble lets us place it beside the current hover and clamp it to the
    active screen at every UI scale.
    """

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip |
                         Qt.WindowType.FramelessWindowHint)
        self.setObjectName("frlgTooltip")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.label = QLabel(self)
        self.label.setTextFormat(Qt.TextFormat.AutoText)
        self.label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.addWidget(self.label)
        self.apply_theme()

    def apply_theme(self) -> None:
        self.setStyleSheet(
            "QFrame#frlgTooltip { background-color: %s; border: 2px solid %s;"
            " border-radius: 5px; }"
            "QLabel { color: %s; background: transparent;"
            " font-family: '%s'; font-size: 13px; }"
            % (PANEL, NAVY, INK, FONT_DS)
        )

    def show_for(self, text: str, pos: QPoint) -> None:
        self.apply_theme()
        self.label.setText(text)
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        self.label.setMaximumWidth(max(160, min(480, avail.width() - 40)))
        self.adjustSize()
        w, h = self.width(), self.height()
        x = pos.x() + 12
        y = pos.y() + 18
        if x + w > avail.right() - 4:
            x = avail.right() - w - 4
        if y + h > avail.bottom() - 4:
            y = pos.y() - h - 8
        self.move(max(avail.left() + 4, x), max(avail.top() + 4, y))
        self.show()
        self.raise_()


class _AnchoredTooltipFilter(QObject):
    """Show every widget tooltip beside the current pointer position."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._tip = _WidgetTooltip()
        # The bubble is a top-level widget with no parent.  Qt destroys it
        # while the application is shutting down, which invalidates the
        # Python wrapper; later events would then raise RuntimeError during
        # teardown.  Drop the reference before that happens.
        app.aboutToQuit.connect(self._release_tip)

    def _release_tip(self) -> None:
        # Stop filtering before Qt starts destroying widgets.  The filter is
        # global to the application, so it would otherwise receive teardown
        # events for objects that are already partly gone.
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        tip = self._tip
        self._tip = None
        if tip is not None:
            tip.hide()
            tip.deleteLater()

    def eventFilter(self, obj, event) -> bool:
        tip = self._tip
        if tip is None:
            return False
        kind = event.type()
        if kind == QEvent.Type.ToolTip:
            if not isinstance(obj, QWidget) or obj.window() is tip:
                return False
            text = obj.toolTip()
            if not text:
                tip.hide()
                return True
            tip.show_for(text, event.globalPos())
            return True
        if kind in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress,
                    QEvent.Type.Wheel, QEvent.Type.KeyPress,
                    QEvent.Type.WindowDeactivate):
            try:
                if tip.isVisible():
                    tip.hide()
            except RuntimeError:
                # Qt already destroyed the bubble during teardown.
                self._tip = None
        return False


class AppStyle(QProxyStyle):
    """Fusion styling with list-style combo popups.

    QStyle::SH_ComboBox_Popup makes Qt use a menu-like popup for non-editable
    combos.  Fusion reports it as available, and in that mode QComboBox maps
    a full-screen popup and ignores ``maxVisibleItems`` for long lists.  The
    popup window then covers the whole screen and the list appears near the
    middle instead of under its field.  Reporting no popup mode keeps the
    same Fusion painting but gives every combo the normal, anchored list.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None) -> int:
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, option, widget, returnData)


def init_app(app: QApplication) -> None:
    """Load fonts, restore the saved theme and install the global stylesheet."""
    global FONT_DS, FONT_GBA, _loaded_fonts, _initialised, _BASE_DS, _BASE_GBA

    # Fusion answers SH_ComboBox_Popup with 1.  That turns every non-editable
    # combo into a menu-style popup which ignores maxVisibleItems and maps a
    # screen-height window; Qt then parks the visible list in the middle of
    # it.  Answering 0 keeps all of Fusion's painting while letting QComboBox
    # honour the eight-row cap and anchor the list to its field.
    if not isinstance(app.style(), AppStyle):
        app.setStyle(AppStyle("Fusion"))

    ds = _load_font(FONT_DIR / "PokemonDS.ttf")
    gba = _load_font(FONT_DIR / "PokePixelGBA.ttf")
    FONT_DS = ds or "DejaVu Sans"
    FONT_GBA = gba or FONT_DS
    _BASE_DS, _BASE_GBA = FONT_DS, FONT_GBA
    _loaded_fonts = {f for f in (ds, gba) if f}

    _activate(_read_saved_theme())

    app.setFont(ui_font(FONT_SIZE))
    app.setApplicationName("FRLG Studio")
    app.setApplicationDisplayName("FRLG Studio")

    icon = ASSET_DIR / "branding" / "frlg_studio_icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    _apply_app_palette(app)
    _ensure_ui_assets()
    app.setStyleSheet(build_stylesheet())
    if getattr(app, "_frlg_tooltip_filter", None) is None:
        app._frlg_tooltip_filter = _AnchoredTooltipFilter(app)
        app.installEventFilter(app._frlg_tooltip_filter)
    _initialised = True


def set_theme(
    theme_id: str,
    *,
    persist: bool = True,
    target: QWidget | None = None,
) -> bool:
    """Switch every palette token and refresh the Qt stylesheet.

    ``target`` lets the main window own the theme stylesheet.  Applying a
    10 KB stylesheet to one window is roughly six times faster than asking
    QApplication to repolish every top-level widget.  Dialogs created with the
    main window as their parent inherit it normally.
    """
    theme_id = canonical_theme_id(str(theme_id))
    if theme_id not in PALETTES or theme_id == THEME_ID:
        return False

    _activate(theme_id)
    _ensure_ui_assets()

    app = QApplication.instance()
    if isinstance(app, QApplication):
        _apply_app_palette(app)
        qss = build_stylesheet()
        if target is not None:
            target.setStyleSheet(qss)
        else:
            app.setStyleSheet(qss)

    if persist:
        _save_theme(theme_id)
    return True


def fonts_available() -> bool:
    return bool(_loaded_fonts)


def lighten(color: str | QColor, amount: int = 115) -> QColor:
    return QColor(color).lighter(amount)


def darken(color: str | QColor, amount: int = 120) -> QColor:
    return QColor(color).darker(amount)


# ---------------------------------------------------------------------------
# Small generated UI assets (arrows, checkbox ticks) - no binary dependencies
# ---------------------------------------------------------------------------
def _pixel_icon(path: Path, size: tuple[int, int], painter_fn) -> None:
    img = QPixmap(*size)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter_fn(painter)
    painter.end()
    img.save(str(path))


def _ensure_ui_assets() -> None:
    UI_DIR.mkdir(parents=True, exist_ok=True)
    required = (
        UI_DIR / "chevron_down.png",
        UI_DIR / "chevron_up.png",
        UI_DIR / "check.png",
    )
    if THEME_ID in _assets_ready and all(p.exists() for p in required):
        return

    def down_arrow(p: QPainter):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(NAVY_DARK))
        p.drawRect(2, 2, 8, 2)
        p.drawRect(3, 4, 6, 2)
        p.drawRect(4, 6, 4, 2)
        p.drawRect(5, 8, 2, 2)

    def up_arrow(p: QPainter):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(NAVY_DARK))
        p.drawRect(5, 1, 2, 2)
        p.drawRect(4, 3, 4, 2)
        p.drawRect(3, 5, 6, 2)
        p.drawRect(2, 7, 8, 2)

    def check(p: QPainter):
        pen = QPen(QColor(ON_GOLD), 3)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        p.setPen(pen)
        p.drawLine(2, 7, 5, 10)
        p.drawLine(5, 10, 11, 2)

    _pixel_icon(UI_DIR / "chevron_down.png", (12, 10), down_arrow)
    _pixel_icon(UI_DIR / "chevron_up.png", (12, 10), up_arrow)
    _pixel_icon(UI_DIR / "check.png", (14, 14), check)
    _assets_ready.add(THEME_ID)


# ---------------------------------------------------------------------------
# Global stylesheet
# ---------------------------------------------------------------------------
_QSS = Template(r"""
QWidget {
    color: ${INK};
    font-family: "${BODY_FAMILY}";
    font-size: ${FONT_SIZE}px;
}
QMainWindow, QDialog {
    background-color: ${CREAM_ALT};
}
QToolTip {
    background-color: ${PANEL};
    color: ${INK};
    border: 2px solid ${NAVY};
    border-radius: 5px;
    padding: 6px 8px;
    font-family: "${FONT_DS}";
    font-size: 13px;
}
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 ${PANEL}, stop:0.55 ${CREAM}, stop:1 ${CREAM_ALT});
    color: ${NAVY_DARK};
    border: 2px solid ${NAVY};
    border-bottom: 3px solid ${NAVY_DARK};
    border-radius: ${CONTROL_RADIUS}px;
    padding: 5px 11px;
    min-height: 22px;
    font-family: "${FONT_GBA}";
    font-size: 13px;
}
QPushButton:hover {
    background-color: ${HOVER};
    border-color: ${HOVER_BORDER};
    color: ${INK};
}
QPushButton:pressed {
    background-color: ${PRESSED};
    border: 2px solid ${ORANGE_DARK};
    padding-top: 6px;
    padding-bottom: 4px;
}
QPushButton:disabled {
    background-color: ${DISABLED_BG};
    color: ${DISABLED_FG};
    border-color: ${DISABLED_BORDER};
}
QPushButton:focus {
    border-color: ${ORANGE};
}
QPushButton[role="primary"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 ${GREEN}, stop:0.55 ${GREEN}, stop:1 ${GREEN_DARK});
    color: ${ON_ACCENT};
    border: 2px solid ${GREEN_DARK};
    border-bottom: 4px solid ${GREEN_DARK};
    font-size: 14px;
}
QPushButton[role="primary"]:hover { background-color: ${GREEN_DARK}; }
QPushButton[role="primary"]:pressed { background-color: ${GREEN}; }
QPushButton[role="primary"]:disabled,
QPushButton[role="danger"]:disabled,
QPushButton[role="accent"]:disabled,
QPushButton[role="blue"]:disabled {
    background-color: ${DISABLED_BG};
    border-color: ${DISABLED_BORDER};
    color: ${DISABLED_FG};
}
QPushButton[role="danger"] {
    background-color: ${RED};
    color: ${ON_DANGER};
    border: 2px solid ${RED_DARK};
    border-bottom: 4px solid ${RED_DARK};
    font-size: 14px;
}
QPushButton[role="danger"]:hover { background-color: ${RED_DARK}; }
QPushButton[role="danger"]:pressed { background-color: ${RED}; }
QPushButton[role="accent"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 ${YELLOW}, stop:0.55 ${GOLD}, stop:1 ${ORANGE});
    color: ${ON_GOLD};
    border: 2px solid ${ORANGE_DARK};
    border-bottom: 4px solid ${ORANGE_DARK};
    font-size: 14px;
}
QPushButton[role="accent"]:hover { background-color: ${GOLD}; }
QPushButton[role="blue"] {
    background-color: ${BLUE};
    color: ${ON_ACCENT};
    border: 2px solid ${NAVY};
    border-bottom: 4px solid ${NAVY_DARK};
    font-size: 14px;
}
QPushButton[role="blue"]:hover { background-color: ${NAVY}; }
QPushButton[role="ghost"] {
    background: transparent;
    border: 2px solid transparent;
    border-bottom: 3px solid transparent;
    color: ${INK_SOFT};
    padding: 5px 9px;
}
QPushButton[role="ghost"]:hover {
    background-color: ${HOVER};
    border-color: ${HOVER_BORDER};
    color: ${INK};
}
QPushButton[role="menu"] { text-align: left; padding: 7px 13px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: ${FIELD};
    color: ${INK};
    border: 2px solid ${BORDER};
    border-radius: ${CONTROL_RADIUS}px;
    padding: 2px 7px;
    min-height: 21px;
    selection-background-color: ${GOLD};
    selection-color: ${ON_GOLD};
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: ${ORANGE};
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    background-color: ${DISABLED_BG};
    color: ${DISABLED_FG};
    border-color: ${DISABLED_BORDER};
}
QLineEdit[readOnly="true"] { background-color: ${READONLY}; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 2px solid ${BORDER};
    background-color: ${PANEL_ALT};
    border-top-right-radius: ${CONTROL_RADIUS}px;
    border-bottom-right-radius: ${CONTROL_RADIUS}px;
}
QComboBox::down-arrow {
    image: url("${UI_DIR}/chevron_down.png");
    width: 12px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background-color: ${PANEL};
    color: ${INK};
    border: 2px solid ${NAVY};
    outline: none;
    selection-background-color: ${GOLD};
    selection-color: ${ON_GOLD};
    /* QComboBox overlays its little scroll-arrow bars on the view edge.  The
       extra top/bottom padding keeps those bars off the first and last row. */
    padding: 12px 3px;
}
QComboBox QAbstractItemView::item {
    padding: 4px 8px;
}
#frlgComboPopup {
    background-color: ${PANEL};
    color: ${INK};
    border: 2px solid ${NAVY};
    outline: none;
    selection-background-color: ${GOLD};
    selection-color: ${ON_GOLD};
    padding: 12px 3px;
}
#frlgComboPopup::item {
    padding: 4px 8px;
}
QAbstractItemView {
    background-color: ${PANEL};
    color: ${INK};
    selection-background-color: ${GOLD};
    selection-color: ${ON_GOLD};
    border: 2px solid ${BORDER};
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    margin: 1px;
    border-left: 2px solid ${BORDER};
    background-color: ${PANEL_ALT};
    border-top-right-radius: ${CONTROL_RADIUS}px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    margin: 1px;
    border-left: 2px solid ${BORDER};
    background-color: ${PANEL_ALT};
    border-bottom-right-radius: ${CONTROL_RADIUS}px;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("${UI_DIR}/chevron_up.png");
    width: 12px; height: 10px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("${UI_DIR}/chevron_down.png");
    width: 12px; height: 10px;
}
QGroupBox {
    background-color: ${PANEL};
    border: 2px solid ${BORDER};
    border-radius: ${PANEL_RADIUS}px;
    margin-top: 12px;
    padding-top: 4px;
    font-family: "${FONT_DS}";
    font-size: 14px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 2px 10px;
    background-color: ${GOLD};
    color: ${ON_GOLD};
    border: 2px solid ${ORANGE_DARK};
    border-radius: ${CONTROL_RADIUS}px;
}
QTabWidget::pane {
    border: 2px solid ${NAVY};
    background-color: ${CREAM};
    border-radius: ${PANEL_RADIUS}px;
    top: -2px;
}
QTabBar::tab {
    background-color: ${TAB_BG};
    color: ${INK_SOFT};
    border: 2px solid ${BORDER};
    border-bottom: none;
    border-top-left-radius: ${PANEL_RADIUS}px;
    border-top-right-radius: ${PANEL_RADIUS}px;
    padding: 6px 14px;
    margin-right: 3px;
    min-width: 76px;
    font-family: "${FONT_GBA}";
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: ${TAB_SELECTED_BG};
    color: ${NAVY_DARK};
    border-color: ${NAVY};
    border-bottom: 2px solid ${TAB_SELECTED_BG};
}
QTabBar::tab:hover:!selected {
    background-color: ${HOVER};
    color: ${INK};
}
QTabWidget#MainTabs > QTabBar::tab {
    padding: 8px 20px;
    min-width: 112px;
    font-size: 15px;
}
QCheckBox, QRadioButton {
    spacing: 8px;
    color: ${INK};
    min-height: 22px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 17px;
    height: 17px;
    border: 2px solid ${BORDER};
    background-color: ${FIELD};
}
QCheckBox::indicator { border-radius: 3px; }
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator:checked {
    image: url("${UI_DIR}/check.png");
    background-color: ${GOLD};
    border-color: ${ORANGE_DARK};
}
QRadioButton::indicator:checked {
    background-color: ${GOLD};
    border: 4px solid ${NAVY};
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background-color: ${DISABLED_BG};
    border-color: ${DISABLED_BORDER};
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background-color: ${SCROLL_BG};
    width: 13px;
    margin: 0;
    border-left: 1px solid ${BORDER_SOFT};
}
QScrollBar::handle:vertical {
    background-color: ${SCROLL_HANDLE};
    border: 2px solid ${NAVY};
    border-radius: 3px;
    min-height: 32px;
    margin: 1px;
}
QScrollBar::handle:vertical:hover {
    background-color: ${SCROLL_HANDLE_HOVER};
    border-color: ${ORANGE_DARK};
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    width: 0; height: 0; background: none;
}
QScrollBar:horizontal {
    background-color: ${SCROLL_BG};
    height: 13px;
    margin: 0;
    border-top: 1px solid ${BORDER_SOFT};
}
QScrollBar::handle:horizontal {
    background-color: ${SCROLL_HANDLE};
    border: 2px solid ${NAVY};
    border-radius: 3px;
    min-width: 32px;
    margin: 1px;
}
QScrollBar::handle:horizontal:hover {
    background-color: ${SCROLL_HANDLE_HOVER};
    border-color: ${ORANGE_DARK};
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0; height: 0; background: none;
}
QTextEdit, QPlainTextEdit {
    background-color: ${FIELD};
    color: ${INK};
    border: 3px solid ${NAVY};
    border-radius: ${PANEL_RADIUS}px;
    padding: 8px;
    selection-background-color: ${GOLD};
    selection-color: ${ON_GOLD};
    font-family: "${BODY_FAMILY}";
    font-size: 13px;
}
QMenu {
    background-color: ${PANEL};
    color: ${INK};
    border: 2px solid ${NAVY};
    padding: 4px;
}
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: ${GOLD}; color: ${ON_GOLD}; }
QSplitter::handle { background-color: transparent; }
QSplitter::handle:horizontal { width: 9px; }
QProgressBar {
    background-color: ${CREAM_ALT};
    border: 2px solid ${NAVY};
    border-radius: ${CONTROL_RADIUS}px;
    text-align: center;
    color: ${INK};
    font-size: 12px;
}
QProgressBar::chunk {
    background-color: ${GOLD};
    border-radius: 2px;
}
QMessageBox { background-color: ${CREAM_ALT}; }
QMessageBox QLabel { color: ${INK}; }
QFileDialog { background-color: ${CREAM_ALT}; }
QLabel { background: transparent; }
QWidget#AppEngine {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 ${APP_BG_TOP}, stop:1 ${APP_BG_BOTTOM});
}
QFrame#TopBar {
    background-color: ${TOPBAR_BG};
    border: 2px solid ${NAVY};
    border-radius: ${PANEL_RADIUS}px;
}
QFrame#TopBar QLabel { background: transparent; border: none; color: ${INK}; }
QComboBox[role="theme"] {
    background-color: ${PANEL_ALT};
    color: ${INK};
    border: 2px solid ${BORDER};
    border-radius: ${CONTROL_RADIUS}px;
    padding: 2px 5px;
    min-height: 22px;
    font-family: "${FONT_GBA}";
    font-size: 12px;
}
QComboBox[role="theme"]:hover { border-color: ${ORANGE}; }
""")


def build_stylesheet() -> str:
    return _QSS.safe_substitute(
        INK=INK, INK_SOFT=INK_SOFT, INK_MUTED=INK_MUTED,
        NAVY=NAVY, NAVY_DARK=NAVY_DARK, BLUE=BLUE,
        CREAM=CREAM, CREAM_ALT=CREAM_ALT, PAPER=PAPER,
        PANEL=PANEL, PANEL_ALT=PANEL_ALT, FIELD=FIELD,
        READONLY=READONLY,
        ORANGE=ORANGE, ORANGE_DARK=ORANGE_DARK, GOLD=GOLD, YELLOW=YELLOW,
        ON_GOLD=ON_GOLD, ON_ACCENT=ON_ACCENT, ON_DANGER=ON_DANGER,
        GREEN=GREEN, GREEN_DARK=GREEN_DARK,
        RED=RED, RED_DARK=RED_DARK,
        BORDER=BORDER, BORDER_SOFT=BORDER_SOFT,
        HOVER=HOVER, HOVER_BORDER=HOVER_BORDER, PRESSED=PRESSED,
        DISABLED_BG=DISABLED_BG, DISABLED_FG=DISABLED_FG,
        DISABLED_BORDER=DISABLED_BORDER,
        SCROLL_BG=SCROLL_BG, SCROLL_HANDLE=SCROLL_HANDLE,
        SCROLL_HANDLE_HOVER=SCROLL_HANDLE_HOVER,
        APP_BG_TOP=APP_BG_TOP, APP_BG_BOTTOM=APP_BG_BOTTOM,
        TOPBAR_BG=TOPBAR_BG, TAB_BG=TAB_BG, TAB_SELECTED_BG=TAB_SELECTED_BG,
        PANEL_RADIUS=PANEL_RADIUS, CONTROL_RADIUS=CONTROL_RADIUS,
        BODY_FAMILY=BODY_FAMILY,
        FONT_DS=FONT_DS, FONT_GBA=FONT_GBA, FONT_SIZE=FONT_SIZE,
        UI_DIR=UI_DIR.as_posix(),
    )


# ---------------------------------------------------------------------------
# Shared paint helpers
# ---------------------------------------------------------------------------
def rounded_frame(
    painter: QPainter,
    rect: QRectF,
    *,
    fill: str | QColor = PAPER,
    border: str | QColor = NAVY,
    radius: float = 10.0,
    width: float = 2.0,
    shadow: bool = True,
    highlight: bool = True,
) -> None:
    """Draw a GBA-style double-edged window with a soft drop shadow."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if shadow:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(SHADOW)
        painter.drawRoundedRect(rect.translated(0, 3), radius, radius)
    painter.setPen(QPen(QColor(border), width))
    painter.setBrush(QColor(fill) if isinstance(fill, str) else fill)
    painter.drawRoundedRect(rect, radius, radius)
    if highlight:
        inner = rect.adjusted(width + 1.5, width + 1.5, -width - 1.5, -width - 1.5)
        painter.setPen(QPen(QColor(255, 255, 255, 90 if THEME_ID in ("dark", "sinnoh") else 150), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(inner, max(1.0, radius - 2), max(1.0, radius - 2))
    painter.restore()


def draw_pokeball(
    painter: QPainter,
    cx: float,
    cy: float,
    radius: float,
    *,
    top: str = "#e0524b",
    bottom: str = "#fdfbf4",
    outline: str = INK,
    angle: float = 0.0,
    outline_width: float = 2.0,
) -> None:
    """A crisp Poké Ball that scales cleanly at desktop resolutions."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(cx, cy)
    painter.rotate(angle)
    painter.setPen(QPen(QColor(outline), outline_width))
    painter.setBrush(QColor(bottom))
    painter.drawEllipse(QPointF(0, 0), radius, radius)
    painter.setBrush(QColor(top))
    painter.drawChord(
        QRectF(-radius, -radius, radius * 2, radius * 2), 0, 180 * 16
    )
    painter.setPen(QPen(QColor(outline), max(1.5, radius * 0.16)))
    painter.drawLine(QPointF(-radius, 0), QPointF(radius, 0))
    painter.setPen(QPen(QColor(outline), outline_width))
    painter.setBrush(QColor("#f8f6ec"))
    painter.drawEllipse(QPointF(0, 0), radius * 0.33, radius * 0.33)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(outline), max(1.0, radius * 0.09)))
    painter.drawEllipse(QPointF(0, 0), radius * 0.20, radius * 0.20)
    painter.restore()


def draw_cloud(painter: QPainter, x: float, y: float, scale: float = 1.0, alpha: int = 210) -> None:
    """Chunky 8px-step cloud, deliberately closer to GBA tiles than vector art."""
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    cloud = QColor(MENU_CLOUD)
    cloud.setAlpha(alpha)
    painter.setBrush(cloud)
    s = max(1.0, scale)
    blocks = [
        (0, 3, 10, 3), (1, 2, 8, 1), (2, 1, 5, 1), (3, 0, 3, 1),
        (11, 4, 5, 2), (12, 3, 3, 1), (13, 5, 4, 1), (4, 5, 9, 1),
    ]
    for bx, by, bw, bh in blocks:
        painter.drawRect(QRectF(x + bx * 8 * s, y + by * 8 * s, bw * 8 * s, bh * 8 * s))
    painter.restore()


def draw_stat_bar(
    painter: QPainter,
    rect: QRectF,
    value: int,
    maximum: int,
    *,
    color: str = GOLD,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(NAVY), 1.5))
    painter.setBrush(QColor(PANEL_ALT))
    painter.drawRoundedRect(rect, 3, 3)
    frac = max(0.0, min(1.0, value / maximum if maximum else 0.0))
    if frac > 0:
        fill = QRectF(rect.left() + 2, rect.top() + 2, (rect.width() - 4) * frac, rect.height() - 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(fill, 2, 2)
    painter.restore()


# The storage hand is copied pixel-for-pixel from the FireRed/LeafGreen PC
# cursor (pret/pokefirered graphics/pokemon_storage/cursor.png, pointing
# frame): a white glove with the index finger extended down-left and the thumb
# raised at the top right.  These are the game's own 17x20 pixels and palette;
# nothing here is synthesised, which is why it needs no extra outline.
HAND_CURSOR_W = 17
HAND_CURSOR_H = 20
HAND_CURSOR_PIXELS = (
    "............s....",
    "..........ssos...",
    ".......sssoo#os..",
    ".....ssooo##l#os.",
    "....soo######l#os",
    "...so########los.",
    "..so########llos.",
    ".so#########los..",
    ".so#########los..",
    ".so###l#####los..",
    "sol##lll###llos..",
    "so###ltolllltos..",
    "so###ltotlllos...",
    "so##ltototttos...",
    "so##ltoooooos....",
    "so##lossssss.....",
    "so##los..........",
    "solltos..........",
    ".sooos...........",
    "..sss............",
)
# The four greys of the GBA cursor palette.
HAND_CURSOR_COLORS = {
    "#": "#ffffff",
    "l": "#dedef6",
    "s": "#9494ac",
    "t": "#a4a4b4",
    "o": "#52525a",
}
# Multi-move mode recolours the same glove rather than drawing a second
# cursor.  FireRed/LeafGreen use the alternate storage palette here; this
# green variant follows the Poké Bank multi-select cue the desktop UI is
# modelling and reads clearly against every box wallpaper.
HAND_CURSOR_MULTI_COLORS = {
    "#": "#d9f5c8",
    "l": "#a8e08a",
    "s": "#4d8b3b",
    "t": "#7fbf63",
    "o": "#24501a",
}


def draw_hand_cursor(
    painter: QPainter,
    x: float,
    y: float,
    *,
    scale: float = 1.0,
    multi: bool = False,
) -> None:
    """Paint the exact FireRed/LeafGreen storage glove.

    ``x`` and ``y`` are the top-left of the 17x20 logical sprite.  The sprite
    is drawn with square pixels and no smoothing, so integer scales look
    exactly like the in-game cursor.  The normal cursor is the game's white
    cloth glove; ``multi`` swaps in the green multi-select palette without
    changing a single pixel of its shape.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    painter.translate(x, y)
    painter.scale(scale, scale)
    painter.setPen(Qt.PenStyle.NoPen)
    colors = HAND_CURSOR_MULTI_COLORS if multi else HAND_CURSOR_COLORS

    for cy, row in enumerate(HAND_CURSOR_PIXELS):
        run_start = 0
        run_char = row[0]
        for cx in range(1, len(row) + 1):
            ch = row[cx] if cx < len(row) else None
            if ch == run_char:
                continue
            if run_char != ".":
                painter.setBrush(QColor(colors[run_char]))
                painter.drawRect(QRectF(run_start, cy, cx - run_start, 1))
            run_start = cx
            run_char = ch
    painter.restore()


def soft_shadow(widget: QWidget, blur: int = 18, dy: int = 4, alpha: int = 55) -> None:
    """Attach a gentle drop shadow. Callers keep a reference via Qt ownership."""
    from PyQt6.QtGui import QColor as _QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(_QColor(30, 36, 52, alpha))
    widget.setGraphicsEffect(effect)
