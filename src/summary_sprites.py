"""Pixel-perfect ball and held-item badges for the summary cards.

The sprites are 32x32 inventory icons from the PokéSprite project.  Each
badge keeps a fixed logical frame and re-renders the icon at a whole device
pixel multiplier, so the artwork never picks up a fractional resample at
125%, 150% or 200% UI scale.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel

import core_data
import paths
import theme
from pixel_sprite import integer_scaled_pixmap, sprite_plate_extent

BALL_DIR = paths.UI_ASSETS_DIR / "balls"
ITEM_DIR = paths.UI_ASSETS_DIR / "items"
ICON_BASE = 44


def ball_icon_path(ball_id: int) -> Path | None:
    """Return the Gen 3 ball icon, falling back to a Poké Ball."""
    _, slug = core_data.GEN3_ITEMS.get(
        int(ball_id or 0), ("Poké Ball", "poke-ball")
    )
    path = BALL_DIR / f"{slug}.png"
    if path.is_file():
        return path
    fallback = BALL_DIR / "poke-ball.png"
    return fallback if fallback.is_file() else None


def item_icon_path(item_id: int) -> Path | None:
    """Return the bag icon for a held item, or None for an empty slot."""
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return None
    if item_id <= 0:
        return None
    _, slug = core_data.GEN3_ITEMS.get(item_id, ("Item", ""))
    if slug:
        # A held Poké Ball is still a bag item, but its inventory art is the
        # ball set rather than the generic item set.  Without this lookup a
        # held Master Ball/Great Ball/etc. fell through to unknown.png.
        ball_path = BALL_DIR / f"{slug}.png"
        if ball_path.is_file():
            return ball_path
        path = ITEM_DIR / f"{slug}.png"
        if path.is_file():
            return path
    fallback = ITEM_DIR / "unknown.png"
    return fallback if fallback.is_file() else None


class SummaryIconSlot(QLabel):
    """A framed badge that draws one crisp inventory icon or stays hidden."""

    def __init__(self, parent=None, base: int = ICON_BASE, reserve: bool = False):
        super().__init__(parent)
        self._source = None
        self._path: Path | None = None
        self._base = max(1, int(base))
        # A reserved slot keeps its footprint in the layout even while empty.
        # The held-item badge uses this: adding or clearing an item must not
        # reflow the portrait row or the summary card beside it.
        self._reserve = bool(reserve)
        self.setObjectName("SummaryIconSlot")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        extent = sprite_plate_extent(self._base)
        self.setFixedSize(extent, extent)
        self._apply_slot_style(False)
        if self._reserve:
            self.show()
        else:
            self.hide()

    # -- sources ----------------------------------------------------------
    def set_ball(self, ball_id: int) -> None:
        path = ball_icon_path(ball_id)
        name = core_data.GEN3_ITEMS.get(
            int(ball_id or 0), ("Poké Ball", "poke-ball")
        )[0]
        self._set_path(path, name)

    def set_item(self, item_id: int) -> None:
        path = item_icon_path(item_id)
        if path is None:
            self.clear()
            return
        name = core_data.GEN3_ITEMS.get(
            int(item_id), (f"Item #{item_id}", "")
        )[0]
        self._set_path(path, f"Held item: {name}")

    def clear(self) -> None:
        self._path = None
        self._source = None
        self.setPixmap(QPixmap())
        self.setToolTip("")
        if self._reserve:
            self._apply_slot_style(False)
            self.show()
        else:
            self.hide()

    def _set_path(self, path: Path | None, tooltip: str) -> None:
        if path is None:
            self.clear()
            return
        source = QPixmap(str(path))
        if source.isNull():
            self.clear()
            return
        self._path = path
        self._source = source
        self.setToolTip(tooltip)
        self._apply_slot_style(True)
        self.show()
        self._apply_icon()

    def _apply_slot_style(self, filled: bool) -> None:
        """Draw the frame only while a badge is present."""
        background = theme.SUMMARY_MEMO_BG if filled else "transparent"
        border = theme.SUMMARY_BORDER if filled else "transparent"
        self.setStyleSheet(
            "QLabel#SummaryIconSlot { background-color: %s; border: 2px solid %s;"
            " border-radius: 6px; }"
            % (background, border)
        )

    # -- rendering --------------------------------------------------------
    def _apply_icon(self) -> None:
        if self._source is None or self._source.isNull():
            return
        inner_w = max(1, self.width() - 8)
        inner_h = max(1, self.height() - 8)
        dpr = max(0.1, float(self.devicePixelRatioF()))
        target_w = max(1, int(round(inner_w * dpr)))
        target_h = max(1, int(round(inner_h * dpr)))
        if self._source.width() > target_w or self._source.height() > target_h:
            # A half-size badge is smaller than the 32 px source.  Whole-pixel
            # upscaling cannot help here, so downsample to the physical target
            # and tag the result with the display's DPR.  This keeps the small
            # frame sharp instead of clipping the source at 100%.
            scaled = self._source.scaled(
                target_w,
                target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            self.setPixmap(scaled)
            return
        self.setPixmap(
            integer_scaled_pixmap(self._source, inner_w, inner_h, dpr=dpr)
        )

    def resizeEvent(self, event):  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._apply_icon()
