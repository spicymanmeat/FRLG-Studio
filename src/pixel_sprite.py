"""Crisp high-DPI rendering for the game's pixel-art sprites.

A plain QLabel/QMovie pair hands the GIF frame to Qt at its native pixmap
resolution.  When the application is scaled to 125-200%, Qt then stretches
that frame by a fractional factor and the pixel edges land between device
pixels, which reads as jagged or smeared on a sprite.

This label keeps the source frame, rescales it in whole logical pixels with
FastTransformation, and tags the result with the screen's device-pixel ratio.
Qt can then blit it 1:1, so every source pixel still occupies a square block
of screen pixels.

It also preserves the animated sprite's native footprint.  The Gen 3/4/5
GIFs are drawn on canvases proportional to the creature, so stretching each
one to fill a fixed portrait plate made a Rattata as tall as a Venusaur.
Small species now stay small, while the plate's reference box still gives
large species room to grow.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QMovie, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QLabel

# Space for the label's stylesheet border/padding so the sprite never draws
# over the frame.  Kept in logical pixels.  Four px clears the two-pixel
# frame while leaving the sprite enough room for whole-pixel blits.
_INSET = 4


def _widget_dpr(widget=None) -> float:
    """Return the real device scale, including fractional Qt factors."""
    if widget is not None:
        try:
            dpr = float(widget.devicePixelRatioF())
            if dpr > 0:
                return dpr
        except (AttributeError, RuntimeError):
            pass
    app = QApplication.instance()
    screen = app.primaryScreen() if app is not None else None
    try:
        dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
    except (AttributeError, RuntimeError):
        dpr = 1.0
    return dpr if dpr > 0 else 1.0


def integer_device_scale(dpr: float | None = None) -> int:
    """The whole device-pixel multiplier closest to the window scale.

    A sprite cannot be drawn at 1.5 device pixels per source pixel without
    either blurring or dropping rows.  Rounding the multiplier to 2 gives
    every source pixel a 2x2 device block while Qt still lays the pixmap out
    at its correct device-independent size.
    """
    if dpr is None:
        dpr = _widget_dpr()
    return max(1, int(math.floor(float(dpr) + 0.5)))


def sprite_plate_extent(base: int) -> int:
    """Grow a portrait frame when the next whole pixel block is larger.

    At 150% on a 1x desktop the closest whole device multiplier is 2x, not
    1.5x.  Enlarging the plate by 2 / 1.5 keeps the sprite-to-frame
    composition identical to 100% while allowing the sprite itself to stay
    perfectly square-pixeled.  At 125% the closest multiplier is 1x, so the
    frame keeps its existing size.
    """
    dpr = max(0.1, float(_widget_dpr()))
    k = integer_device_scale(dpr)
    factor = max(1.0, k / dpr)
    return max(1, int(round(base * factor)))


def integer_scaled_pixmap(
    source: QPixmap,
    max_logical_w: float,
    max_logical_h: float,
    dpr: float | None = None,
) -> QPixmap:
    """Fit a static pixmap at the largest whole device-pixel multiplier.

    Used for the small 40x30 box icons that are not large enough to justify a
    full portrait plate.  The returned pixmap is already tagged with the real
    DPR, so Qt's final blit is 1:1.
    """
    if source is None or source.isNull():
        return QPixmap()
    if dpr is None:
        dpr = _widget_dpr()
    dpr = max(0.1, float(dpr))
    avail_phys_w = max(1.0, float(max_logical_w) * dpr)
    avail_phys_h = max(1.0, float(max_logical_h) * dpr)
    step = max(
        1,
        int(math.floor(min(
            avail_phys_w / max(1, source.width()),
            avail_phys_h / max(1, source.height()),
        ) + 1e-6)),
    )
    scaled = source.scaled(
        source.width() * step,
        source.height() * step,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
    scaled.setDevicePixelRatio(dpr)
    return scaled


class CrispSpriteLabel(QLabel):
    """A QLabel that displays animated or static sprites without resampling.

    The source is never resampled to a fractional destination size.  The
    label picks the closest whole device-pixel multiplier, builds the frame
    at exactly ``source_size * multiplier``, tags it with the real DPR, and
    lets Qt blit it 1:1.  At 150% that means a 2x2 device block per source
    pixel, with the label occupying 1.333 logical pixels per source pixel.
    """

    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._crisp_movie = None
        self._crisp_source = QPixmap()
        self._plate_base: int | None = None
        self._resizing_plate = False
        self._clickable = False

    def set_clickable(self, enabled: bool = True) -> None:
        """Make the plate a cry target without changing every other label."""
        self._clickable = bool(enabled)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if self._clickable
            else Qt.CursorShape.ArrowCursor
        )

    def mouseReleaseEvent(self, event):
        if (
            self._clickable
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_plate_base(self, extent: int) -> None:
        """Record the normal plate size so oversized sprites can expand it.

        Most species fit the normal 104/112 px case.  A few animated sources
        (Lugia, Ho-oh, some flying frames) have canvases wider than that; the
        plate grows to the next whole block size instead of clipping them or
        fractionally shrinking the artwork.
        """
        self._plate_base = max(1, int(extent))

    def _reset_plate_extent(self) -> None:
        if self._plate_base is None or self._resizing_plate:
            return
        if (self.width(), self.height()) == (self._plate_base, self._plate_base):
            return
        self._resizing_plate = True
        try:
            self.setFixedSize(self._plate_base, self._plate_base)
        finally:
            self._resizing_plate = False

    def _sync_plate_extent(self, source: QPixmap) -> bool:
        if self._plate_base is None or source.isNull() or self._resizing_plate:
            return False
        dpr = _widget_dpr(self)
        step = integer_device_scale(dpr)
        # Stylesheet borders/padding (the summary plates use a 2-3 px frame)
        # reduce QLabel's contentsRect.  Account for that chrome when sizing
        # the grown plate, otherwise a Large sprite can request 2x but still
        # be forced back to 1x by a few pixels of border.
        extra_x = max(0, self.width() - self.contentsRect().width())
        extra_y = max(0, self.height() - self.contentsRect().height())
        needed_w = int(math.ceil(source.width() * step / dpr)) + 2 * _INSET + extra_x
        needed_h = int(math.ceil(source.height() * step / dpr)) + 2 * _INSET + extra_y
        needed = max(self._plate_base, needed_w, needed_h)
        if (self.width(), self.height()) == (needed, needed):
            return False
        self._resizing_plate = True
        try:
            self.setFixedSize(needed, needed)
        finally:
            self._resizing_plate = False
        # The resize event can observe the old contentsRect; rebuild once the
        # new geometry has been committed so the larger plate selects 2x (or
        # 3x) instead of sticking with the 1x frame chosen before it grew.
        QTimer.singleShot(0, self._apply_crisp_source)
        return True

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------
    def movie(self):
        """Return the GIF currently playing, if any.

        QLabel's own movie is deliberately unused; this shadow keeps the
        existing ``label.movie().stop()`` / ``setMovie(None)`` call sites
        working while the label paints a crisp pixmap itself.
        """
        return self._crisp_movie

    def setMovie(self, movie):  # noqa: N802 - Qt naming
        if movie is not None:
            # QMovie's default speed is already 100%, but be explicit: every
            # summary/trade/editor GIF must play on its native delay table.
            # Caching decoded frames also removes decode hitches when a long
            # 60 ms Gen 5 cycle loops.
            movie.setSpeed(100)
            movie.setCacheMode(QMovie.CacheMode.CacheAll)
        if self._crisp_movie is not None:
            try:
                self._crisp_movie.frameChanged.disconnect(self._refresh_frame)
            except (TypeError, RuntimeError):
                pass
        self._crisp_movie = movie
        if movie is None:
            self._crisp_source = QPixmap()
            super().setPixmap(QPixmap())
            self._reset_plate_extent()
            return
        movie.frameChanged.connect(self._refresh_frame)
        self._refresh_frame()

    def setPixmap(self, pixmap):  # noqa: N802 - Qt naming
        if self._crisp_movie is not None:
            try:
                self._crisp_movie.frameChanged.disconnect(self._refresh_frame)
            except (TypeError, RuntimeError):
                pass
            self._crisp_movie = None
        self._crisp_source = QPixmap(pixmap) if pixmap is not None else QPixmap()
        self._apply_crisp_source()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _refresh_frame(self, *_args):
        if self._crisp_movie is None:
            return
        self._crisp_source = self._crisp_movie.currentPixmap()
        if self._sync_plate_extent(self._crisp_source):
            return
        self._apply_crisp_source()

    def _apply_crisp_source(self):
        source = self._crisp_source
        if source is None or source.isNull() or source.width() <= 0:
            super().setPixmap(QPixmap())
            self._reset_plate_extent()
            return

        if self._sync_plate_extent(source):
            return

        dpr = _widget_dpr(self)
        rect = self.contentsRect().adjusted(_INSET, _INSET, -_INSET, -_INSET)
        avail_phys_w = max(1, int(math.floor(max(1, rect.width()) * dpr)))
        avail_phys_h = max(1, int(math.floor(max(1, rect.height()) * dpr)))

        # Pick one whole multiplier per frame.  The preferred value is the
        # window's integer device scale (2 at 150%, 3 at 250%, 1 at 125%).
        # A sprite that would overflow is stepped down rather than squeezed:
        # it is always source_width * k or nothing.
        step = integer_device_scale(dpr)
        while step > 1 and (
            source.width() * step > avail_phys_w
            or source.height() * step > avail_phys_h
        ):
            step -= 1

        phys_w = max(1, source.width() * step)
        phys_h = max(1, source.height() * step)

        # FastTransformation is nearest-neighbour, and the exact integer
        # target means no row or column is ever dropped or blended.
        scaled = source.scaled(
            phys_w,
            phys_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        # Tagging the real DPR is what makes Qt paint the physical image 1:1
        # instead of applying the window scale a second time.
        scaled.setDevicePixelRatio(dpr)
        super().setPixmap(scaled)

    def paintEvent(self, event):
        """Paint the finished pixmap at an exact device-pixel offset.

        QLabel's own pixmap painting rounds the pixmap's device-independent
        size to whole logical pixels.  At 150% that turns the 74x76 physical
        Bulbasaur frame into a 49x51 logical target, which Qt then resamples
        back across the 1.5x transform: every edge blends and the block
        structure disappears.  Drawing the already-scaled pixmap at a
        physical integer offset avoids that second scale entirely.

        The frame/background still comes from QFrame/QSS.  When there is no
        source (the "Sprite" / "STANDBY" placeholder state), QLabel paints
        normally so the text is preserved.
        """
        source_pixmap = self.pixmap()
        if source_pixmap is None or source_pixmap.isNull():
            super().paintEvent(event)
            return

        QFrame.paintEvent(self, event)

        dpr = max(0.1, float(self.devicePixelRatioF()))
        contents = self.contentsRect()
        avail_w = max(1.0, contents.width() * dpr)
        avail_h = max(1.0, contents.height() * dpr)
        alignment = self.alignment()
        if alignment & Qt.AlignmentFlag.AlignRight:
            dx = avail_w - source_pixmap.width()
        elif alignment & Qt.AlignmentFlag.AlignHCenter:
            dx = (avail_w - source_pixmap.width()) / 2.0
        else:
            dx = 0.0
        if alignment & Qt.AlignmentFlag.AlignBottom:
            dy = avail_h - source_pixmap.height()
        elif alignment & Qt.AlignmentFlag.AlignVCenter:
            dy = (avail_h - source_pixmap.height()) / 2.0
        else:
            dy = 0.0
        x_phys = round(contents.x() * dpr) + max(0, round(dx))
        y_phys = round(contents.y() * dpr) + max(0, round(dy))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setClipRect(contents)
        painter.drawPixmap(QPointF(x_phys / dpr, y_phys / dpr), source_pixmap)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._crisp_source.isNull():
            self._apply_crisp_source()
