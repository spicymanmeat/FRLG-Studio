import math
import shutil
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QFont, QFontMetrics, QMovie,
    QPainterPath,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFileDialog, QFrame, QSizePolicy,
    QCheckBox, QSlider,
)

import paths
import sound
import theme
from utils import SLOT1_DIR, parse_pk3_file, SpriteDownloadWorker
from sprite_paths import animated_sprite_path, unown_form_from_pid
from pixel_sprite import (
    CrispSpriteLabel, integer_scaled_pixmap, sprite_plate_extent,
)
from summary_sprites import SummaryIconSlot


class ThemeSwatch(QPushButton):
    """A small palette card in the settings popup.

    Each card paints its own palette, not the active one, so five themes can be
    compared at a glance while the rest of the window previews the selection.
    """

    def __init__(self, theme_id: str, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self._hover = False
        spec = theme.PALETTES[theme_id]
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(104, 72)
        # The global QPushButton rule has its own min-height; pin the card so a
        # tight popup layout cannot squeeze the palette label out of existence.
        self.setStyleSheet(
            "QPushButton { min-height: 72px; max-height: 72px; padding: 0;"
            " border: none; background: transparent; }"
        )
        self.setToolTip(f"{spec['LABEL']}\n{spec['DESCRIPTION']}")
        self.setAccessibleName(spec["LABEL"])

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        spec = theme.PALETTES[self.theme_id]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        card = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        selected = self.isChecked()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(spec["SHADOW"]) if "SHADOW" in spec else QColor(0, 0, 0, 38))
        p.drawRoundedRect(card.translated(0, 2), 8, 8)

        p.setPen(QPen(QColor(spec["ORANGE"] if selected else
                             spec["ORANGE_DARK"] if self._hover else spec["BORDER"]),
                      3 if selected else 2))
        p.setBrush(QColor(spec["PAPER"]))
        p.drawRoundedRect(card, 8, 8)

        # The little palette strip: header, body and accent, clipped to the card.
        strip = QRectF(card.left() + 5, card.top() + 5, card.width() - 10, 24)
        clip = QPainterPath()
        clip.addRoundedRect(strip, 5, 5)
        p.save()
        p.setClipPath(clip)
        band_w = strip.width() / 3.0
        p.fillRect(QRectF(strip.left(), strip.top(), band_w + 1, strip.height()),
                   QColor(spec["NAVY"]))
        p.fillRect(QRectF(strip.left() + band_w, strip.top(), band_w + 1, strip.height()),
                   QColor(spec["HEADER"]))
        p.fillRect(QRectF(strip.left() + band_w * 2, strip.top(), band_w + 1, strip.height()),
                   QColor(spec["GOLD"]))
        p.setPen(QPen(QColor(spec["PAPER"]), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(strip, 5, 5)
        p.restore()

        label = spec["SHORT_LABEL"]
        p.setFont(theme.ui_font(10, gba=True, bold=selected))
        p.setPen(QColor(spec["INK"] if selected else spec["INK_SOFT"]))
        metrics = QFontMetrics(theme.ui_font(10, gba=True, bold=selected))
        label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(card.width()) - 8)
        p.drawText(QRectF(card.left() + 3, strip.bottom() + 1, card.width() - 6, 27),
                   Qt.AlignmentFlag.AlignCenter, label)

        if selected:
            badge = QRectF(card.right() - 17, card.top() + 11, 13, 13)
            p.setPen(QPen(QColor(spec["PAPER"]), 2))
            p.setBrush(QColor(spec["GREEN_DARK"]))
            p.drawEllipse(badge)
            p.setPen(QPen(QColor(spec["PAPER"]), 2))
            p.drawLine(QPointF(badge.left() + 3, badge.center().y()),
                       QPointF(badge.center().x(), badge.bottom() - 3))
            p.drawLine(QPointF(badge.center().x(), badge.bottom() - 3),
                       QPointF(badge.right() - 2, badge.top() + 3))
        p.end()


class ScaleSlider(QWidget):
    """Discrete, Minecraft-style UI scale slider with five labelled detents."""

    value_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._choices = theme.SCALE_CHOICES
        self._index = self._index_for(theme.active_scale())
        self.setFixedHeight(55)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("UI size")
        self.setToolTip("Choose how large the entire interface is drawn")

    def _index_for(self, scale: float) -> int:
        return min(range(len(self._choices)),
                   key=lambda i: abs(self._choices[i] - scale))

    def index(self) -> int:
        return self._index

    def set_index(self, index: int, *, emit: bool = False):
        index = max(0, min(len(self._choices) - 1, int(index)))
        changed = index != self._index
        self._index = index
        if changed:
            self.update()
            if emit:
                self.value_changed.emit(index)

    def _x_for(self, index: int) -> float:
        left, right = 16.0, self.width() - 16.0
        if len(self._choices) <= 1:
            return left
        return left + (right - left) * index / (len(self._choices) - 1)

    def _set_from_x(self, x: float):
        if len(self._choices) <= 1:
            self.set_index(0, emit=True)
            return
        step = (self.width() - 32.0) / (len(self._choices) - 1)
        self.set_index(round((x - 16.0) / step), emit=True)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        track = QRectF(16, 13, w - 32, 9)

        p.setPen(QPen(QColor(theme.BORDER_SOFT), 2))
        p.setBrush(QColor(theme.FIELD_ALT))
        p.drawRoundedRect(track, 4.5, 4.5)

        selected_x = self._x_for(self._index)
        if selected_x > track.left() + 1:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.GOLD))
            p.drawRoundedRect(QRectF(track.left() + 2, track.top() + 2,
                                      selected_x - track.left() - 2,
                                      track.height() - 4), 3, 3)

        for i, scale in enumerate(self._choices):
            x = self._x_for(i)
            active = i == self._index
            p.setPen(QPen(QColor(theme.NAVY_DARK if active else theme.BORDER), 2))
            p.setBrush(QColor(theme.PANEL if active else theme.FIELD))
            radius = 6.0 if active else 4.4
            p.drawEllipse(QPointF(x, track.center().y()), radius, radius)
            p.setFont(theme.ui_font(9, gba=True, bold=active))
            p.setPen(QColor(theme.INK if active else theme.INK_SOFT))
            p.drawText(QRectF(x - 25, 29, 50, 20),
                       Qt.AlignmentFlag.AlignCenter, theme.scale_label(scale))

        # Hand-like knob: a small cream plate with a strong navy edge.
        knob = QRectF(selected_x - 8, 5, 16, 25)
        p.setPen(QPen(QColor(theme.ORANGE if self.hasFocus() else theme.NAVY), 3))
        p.setBrush(QColor(theme.PANEL))
        p.drawRoundedRect(knob, 5, 5)
        p.setPen(QPen(QColor(theme.GOLD), 2))
        p.drawLine(QPointF(knob.left() + 4, knob.center().y()),
                   QPointF(knob.right() - 4, knob.center().y()))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._set_from_x(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._set_from_x(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.set_index(self._index - 1, emit=True)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.set_index(self._index + 1, emit=True)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Home:
            self.set_index(0, emit=True)
            event.accept()
            return
        if event.key() == Qt.Key.Key_End:
            self.set_index(len(self._choices) - 1, emit=True)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)


class SettingsPopup(QFrame):
    """Small themed popup for live theme switching and restart-applied UI size."""

    theme_selected = pyqtSignal(str)
    restart_requested = pyqtSignal(float)
    readiness_requested = pyqtSignal()
    about_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    open_data_requested = pyqtSignal()
    sound_enabled_changed = pyqtSignal(bool)
    sound_volume_changed = pyqtSignal(float)
    sound_preview_requested = pyqtSignal()
    sound_settings_requested = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("SettingsPopup")
        self.setFixedWidth(480)
        self._active_scale = theme.active_scale()
        self._pending_scale = self._active_scale
        self._sound_volume_timer = QTimer(self)
        self._sound_volume_timer.setSingleShot(True)
        self._sound_volume_timer.setInterval(140)
        self._sound_volume_timer.timeout.connect(self._emit_sound_volume)
        self._audio_available: bool | None = None
        self._pack_summary = "NO OEM SOUND PACK"
        self._master_muted = False

        root = QVBoxLayout(self)
        root.setContentsMargins(17, 14, 17, 14)
        root.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.title_lbl = QLabel("SETTINGS")
        header.addWidget(self.title_lbl)
        header.addStretch()
        self.btn_close_x = QPushButton("✕")
        self.btn_close_x.setFixedSize(26, 26)
        self.btn_close_x.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_x.setToolTip("Close settings")
        self.btn_close_x.clicked.connect(self._dismiss)
        header.addWidget(self.btn_close_x)
        root.addLayout(header)

        self.rule = QFrame()
        self.rule.setFixedHeight(2)
        root.addWidget(self.rule)

        # Link status and the game selector now live here instead of
        # cluttering the working top bar.  The widgets are reparented in by
        # the main window once it has built them.
        self.link_lbl = QLabel("LINK")
        root.addWidget(self.link_lbl)
        self.link_host = QFrame()
        self.link_host.setObjectName("SettingsLink")
        self.link_host_layout = QVBoxLayout(self.link_host)
        self.link_host_layout.setContentsMargins(0, 0, 0, 0)
        self.link_host_layout.setSpacing(5)
        self.link_status_row = QHBoxLayout()
        self.link_status_row.setContentsMargins(0, 0, 0, 0)
        self.link_status_row.setSpacing(6)
        self.link_status_row.addStretch(1)
        self.link_control_row = QHBoxLayout()
        self.link_control_row.setContentsMargins(0, 0, 0, 0)
        self.link_control_row.setSpacing(6)
        self.link_control_row.addStretch(1)
        self.link_host_layout.addLayout(self.link_status_row)
        self.link_host_layout.addLayout(self.link_control_row)
        root.addWidget(self.link_host)
        self.link_lbl.hide()
        self.link_host.hide()

        self.theme_lbl = QLabel("THEME")
        root.addWidget(self.theme_lbl)

        swatch_rows = QVBoxLayout()
        swatch_rows.setSpacing(6)
        swatch_rows.setContentsMargins(0, 0, 0, 0)
        self.swatches = {}
        for row_index in range(2):
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)
            row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            row_items = theme.THEME_CHOICES[row_index * 4:(row_index + 1) * 4]
            for key, _label in row_items:
                swatch = ThemeSwatch(key)
                swatch.clicked.connect(lambda _checked=False, k=key: self._choose_theme(k))
                self.swatches[key] = swatch
                row.addWidget(swatch)
            swatch_rows.addLayout(row)
        root.addLayout(swatch_rows)

        size_header = QHBoxLayout()
        size_header.setSpacing(6)
        self.size_lbl = QLabel("UI SIZE")
        size_header.addWidget(self.size_lbl)
        size_header.addStretch()
        self.size_value_lbl = QLabel("")
        size_header.addWidget(self.size_value_lbl)
        root.addLayout(size_header)

        self.slider = ScaleSlider()
        self.slider.set_index(self.slider._index_for(self._active_scale))
        self.slider.value_changed.connect(self._on_slider)
        root.addWidget(self.slider)

        self.fit_lbl = QLabel("")
        self.fit_lbl.setWordWrap(True)
        self.fit_lbl.setMinimumHeight(30)
        root.addWidget(self.fit_lbl)

        sound_header = QHBoxLayout()
        sound_header.setSpacing(6)
        self.sound_lbl = QLabel("SOUND")
        sound_header.addWidget(self.sound_lbl)
        sound_header.addStretch()
        self.btn_sound_preview = QPushButton("PREVIEW")
        self.btn_sound_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sound_preview.setToolTip("Play the confirmation cue")
        self.btn_sound_preview.clicked.connect(self.sound_preview_requested.emit)
        sound_header.addWidget(self.btn_sound_preview)
        root.addLayout(sound_header)

        sound_toggle = QHBoxLayout()
        sound_toggle.setSpacing(6)
        self.chk_sound = QCheckBox("SOUND EFFECTS")
        self.chk_sound.setToolTip(
            "OEM pack cues for menus, Bill's PC, dialogs and trades.  "
            "Ctrl+M mutes every bus."
        )
        self.chk_sound.toggled.connect(self._on_sound_toggled)
        sound_toggle.addWidget(self.chk_sound)
        sound_toggle.addStretch()
        self.sound_state_lbl = QLabel("")
        sound_toggle.addWidget(self.sound_state_lbl)
        root.addLayout(sound_toggle)

        sound_volume = QHBoxLayout()
        sound_volume.setSpacing(6)
        self.sound_volume_lbl = QLabel("VOLUME")
        sound_volume.addWidget(self.sound_volume_lbl)
        self.sld_sound = QSlider(Qt.Orientation.Horizontal)
        self.sld_sound.setRange(0, 100)
        self.sld_sound.setFixedWidth(150)
        self.sld_sound.setToolTip("UI sound volume")
        self.sld_sound.valueChanged.connect(self._on_sound_volume)
        sound_volume.addWidget(self.sld_sound)
        self.sound_value_lbl = QLabel("55%")
        self.sound_value_lbl.setMinimumWidth(36)
        sound_volume.addWidget(self.sound_value_lbl)
        sound_volume.addStretch()
        root.addLayout(sound_volume)

        self.audio_status_lbl = QLabel("")
        self.audio_status_lbl.setWordWrap(True)
        root.addWidget(self.audio_status_lbl)

        self.btn_sound_settings = QPushButton("SOUND SETTINGS…")
        self.btn_sound_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sound_settings.setToolTip(
            "Independent music, sound-effect and cry levels; reload the OEM pack"
        )
        self.btn_sound_settings.clicked.connect(self.sound_settings_requested.emit)
        root.addWidget(self.btn_sound_settings)

        self.system_lbl = QLabel("SYSTEM")
        root.addWidget(self.system_lbl)
        system_grid = QGridLayout()
        system_grid.setContentsMargins(0, 0, 0, 0)
        system_grid.setHorizontalSpacing(7)
        system_grid.setVerticalSpacing(6)
        self.btn_setup = QPushButton("SETUP CHECK")
        self.btn_undo = QPushButton("UNDO LAST CHANGE")
        self.btn_data = QPushButton("OPEN DATA FOLDER")
        self.btn_about = QPushButton("ABOUT FRLG STUDIO")
        self.system_buttons = (
            self.btn_setup, self.btn_undo, self.btn_data, self.btn_about
        )
        self.btn_setup.clicked.connect(self.readiness_requested.emit)
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        self.btn_data.clicked.connect(self.open_data_requested.emit)
        self.btn_about.clicked.connect(self.about_requested.emit)
        system_grid.addWidget(self.btn_setup, 0, 0)
        system_grid.addWidget(self.btn_undo, 0, 1)
        system_grid.addWidget(self.btn_data, 1, 0)
        system_grid.addWidget(self.btn_about, 1, 1)
        root.addLayout(system_grid)

        buttons = QHBoxLayout()
        buttons.setSpacing(7)
        buttons.addStretch()
        self.btn_cancel = QPushButton("CLOSE")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._dismiss)
        buttons.addWidget(self.btn_cancel)
        self.btn_apply = QPushButton("APPLY && RESTART")
        self.btn_apply.setProperty("role", "primary")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setToolTip("Restart FRLG Studio at the selected UI size")
        self.btn_apply.clicked.connect(self._apply)
        buttons.addWidget(self.btn_apply)
        root.addLayout(buttons)

        self.apply_theme()
        self._sync_controls()
        self._fit_height()

    def _fit_height(self):
        """Keep the layout from squeezing the palette cards when the popup opens."""
        layout = self.layout()
        if layout is not None:
            layout.activate()
            self.setFixedHeight(layout.minimumSize().height())

    def attach_link_controls(self, wifi_status, phy_label, keys_button,
                             game_label, game_combo) -> None:
        """Move the top-bar link controls into the settings popup."""
        self.link_status_row.addWidget(wifi_status)
        self.link_status_row.addWidget(phy_label)
        self.link_status_row.addStretch(1)
        self.link_control_row.addWidget(keys_button)
        self.link_control_row.addWidget(game_label)
        self.link_control_row.addWidget(game_combo)
        self.link_control_row.addStretch(1)
        for widget in (wifi_status, phy_label, keys_button, game_label,
                       game_combo):
            widget.setParent(self.link_host)
            widget.show()
        self.link_lbl.show()
        self.link_host.show()
        self._fit_height()

    # -- theme and readout -------------------------------------------------
    def _choose_theme(self, key: str):
        sound.play("ui_toggle")
        self.theme_selected.emit(key)
        self._sync_swatches()

    def _sync_swatches(self):
        for key, swatch in self.swatches.items():
            swatch.setChecked(key == theme.THEME_ID)
            swatch.update()

    def _sync_controls(self):
        self._active_scale = theme.active_scale()
        self._pending_scale = self._active_scale
        self.slider.set_index(self.slider._index_for(self._active_scale))
        self._sync_swatches()
        self._update_readout()

    def _on_slider(self, index: int):
        self._pending_scale = theme.SCALE_CHOICES[index]
        self._update_readout()

    # -- sound -------------------------------------------------------------
    def set_sound_state(self, enabled: bool, volume: float,
                        available: bool | None = None,
                        summary: str | None = None,
                        muted: bool = False) -> None:
        if available is not None:
            self._audio_available = bool(available)
        if summary is not None:
            self._pack_summary = str(summary)
        self._master_muted = bool(muted)
        self._sync_audio_label()
        self.chk_sound.blockSignals(True)
        self.chk_sound.setChecked(bool(enabled))
        self.chk_sound.blockSignals(False)
        self.sld_sound.blockSignals(True)
        self.sld_sound.setValue(max(0, min(100, int(round(float(volume) * 100)))))
        self.sld_sound.blockSignals(False)
        self._sync_sound_enabled()

    def _sync_sound_enabled(self) -> None:
        enabled = self.chk_sound.isChecked()
        muted = bool(self._master_muted)
        self.chk_sound.setEnabled(not muted)
        self.sld_sound.setEnabled(enabled and not muted)
        self.btn_sound_preview.setEnabled(enabled and not muted)
        self.sound_state_lbl.setText(
            "MUTED" if muted else ("ON" if enabled else "OFF")
        )

    def _sync_audio_label(self) -> None:
        if self._audio_available is None:
            audio = "AUDIO CHECKING…"
            colour = theme.INK_SOFT
        elif self._audio_available:
            audio = "AUDIO READY"
            colour = theme.INK_SOFT
        else:
            audio = "NO AUDIO DEVICE — AUDIO STAYS SILENT"
            colour = theme.RED_DARK
        if self._master_muted:
            audio = "MUTED — CTRL+M TO RESTORE"
            colour = theme.ORANGE_DARK
        text = f"{self._pack_summary}\n{audio}"
        self.audio_status_lbl.setText(text)
        self.audio_status_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px; letter-spacing: 1px;"
            % (colour, theme.FONT_DS)
        )

    def _on_sound_toggled(self, checked: bool) -> None:
        self._sync_sound_enabled()
        self.sound_enabled_changed.emit(bool(checked))

    def _on_sound_volume(self, value: int) -> None:
        self.sound_value_lbl.setText(f"{value}%")
        self._sound_volume_timer.start()

    def _emit_sound_volume(self) -> None:
        self.sound_volume_changed.emit(self.sld_sound.value() / 100.0)

    def _update_readout(self):
        scale = self._pending_scale
        self.size_value_lbl.setText(
            f"{theme.scale_label(scale)} · {theme.scale_description(scale).upper()}"
        )
        fits = theme.scale_fits_screen(self.screen(), scale)
        if fits:
            detail = "Fits this screen with room for the 1180 × 820 working window."
        elif scale <= theme.SCALE_CHOICES[0]:
            detail = ("This screen is smaller than the app's working minimum, even at "
                      + theme.scale_label(scale) + ".")
        else:
            detail = ("This screen is tight for " + theme.scale_label(scale) +
                      "; a smaller size keeps the whole window on-screen.")
        if fits and abs(scale - self._active_scale) > 0.001:
            detail += "  A restart is needed to apply it."
        self.fit_lbl.setText(detail)
        self.fit_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px;"
            % (theme.INK_SOFT if fits else theme.RED_DARK, theme.FONT_DS)
        )
        changed = abs(scale - self._active_scale) > 0.001
        self.btn_apply.setEnabled(changed and fits)
        self.btn_apply.setText("APPLY && RESTART")
        self.btn_apply.setToolTip(
            "Restart FRLG Studio at the selected UI size" if fits
            else "Choose a size that fits this screen"
        )
        self.slider.update()

    def _apply(self):
        if abs(self._pending_scale - self._active_scale) <= 0.001:
            return
        self.restart_requested.emit(self._pending_scale)

    # -- popup lifecycle ---------------------------------------------------
    def _dismiss(self):
        self.hide()

    def show_at(self, anchor: QWidget | None = None):
        self._sync_controls()
        self._fit_height()
        self.adjustSize()
        self.ensurePolished()
        screen = (anchor.screen() if anchor is not None else self.screen())
        if screen is None:
            screen = self.parentWidget().screen() if self.parentWidget() else None
        geo = screen.availableGeometry() if screen is not None else None

        anchor_top = None
        if anchor is not None and anchor.isVisible():
            point = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height()))
            anchor_top = anchor.mapToGlobal(QPoint(0, 0)).y()
            x = point.x() - self.width()
            y = point.y() + 6
        else:
            parent = self.parentWidget()
            point = (parent.mapToGlobal(QPoint(parent.width() // 2,
                                               max(40, parent.height() // 5)))
                     if parent is not None else QPoint(0, 0))
            x = point.x() - self.width() // 2
            y = point.y()

        if geo is not None:
            # A menu-button anchor sits near the bottom; open upward rather
            # than covering the button.  A tab-bar anchor opens downward.
            if anchor_top is not None and y + self.height() + 8 > geo.bottom():
                y = anchor_top - self.height() - 6
            x = max(geo.left() + 8, min(x, geo.right() - self.width() - 8))
            y = max(geo.top() + 8, min(y, geo.bottom() - self.height() - 8))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.slider.setFocus(Qt.FocusReason.PopupFocusReason)

    def hideEvent(self, event):
        self._sync_controls()
        self.closed.emit()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._apply()
            event.accept()
            return
        super().keyPressEvent(event)

    # -- appearance --------------------------------------------------------
    def apply_theme(self):
        self.title_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 17px; letter-spacing: 3px;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.theme_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px; letter-spacing: 2px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.system_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px; letter-spacing: 2px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        for button in self.system_buttons:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-bottom: 3px solid %s;"
                " border-radius: 5px; padding: 3px 8px; min-height: 22px;"
                " font-family: '%s'; font-size: 11px; }"
                "QPushButton:hover { background-color: %s;"
                " border-color: %s; }"
                % (theme.PANEL_ALT, theme.INK, theme.BORDER, theme.BORDER_SOFT,
                   theme.FONT_GBA, theme.HOVER, theme.HOVER_BORDER)
            )
        self.size_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px; letter-spacing: 2px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.link_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px; letter-spacing: 2px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.link_host.setStyleSheet(
            "QFrame#SettingsLink { background: transparent; border: none; }"
        )
        self.sound_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px; letter-spacing: 2px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.sound_volume_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px; letter-spacing: 1px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.sound_value_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px; font-weight: bold;"
            % (theme.ORANGE_DARK, theme.FONT_DS)
        )
        self.sound_state_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px; letter-spacing: 1px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self._sync_audio_label()
        self.chk_sound.setStyleSheet(
            "QCheckBox { color: %s; font-family: '%s'; font-size: 12px;"
            " letter-spacing: 1px; }" % (theme.INK, theme.FONT_DS)
        )
        self.sld_sound.setStyleSheet(
            "QSlider::groove:horizontal { height: 6px; background: %s;"
            " border: 1px solid %s; border-radius: 3px; }"
            "QSlider::sub-page:horizontal { background: %s; border-radius: 3px; }"
            "QSlider::handle:horizontal { width: 14px; margin: -5px 0;"
            " background: %s; border: 2px solid %s; border-radius: 7px; }"
            % (theme.PANEL_ALT, theme.BORDER, theme.GOLD,
               theme.ORANGE_DARK, theme.NAVY)
        )
        self.btn_sound_preview.setStyleSheet(
            "QPushButton { background-color: %s; color: %s;"
            " border: 2px solid %s; border-bottom: 3px solid %s;"
            " border-radius: 5px; padding: 2px 8px; min-height: 20px;"
            " font-family: '%s'; font-size: 10px; }"
            "QPushButton:hover { background-color: %s; border-color: %s; }"
            "QPushButton:disabled { background-color: %s; color: %s; }"
            % (theme.PANEL_ALT, theme.INK, theme.BORDER, theme.BORDER_SOFT,
               theme.FONT_GBA, theme.HOVER, theme.HOVER_BORDER,
               theme.DISABLED_BG, theme.DISABLED_FG)
        )
        self.btn_sound_settings.setStyleSheet(
            "QPushButton { background-color: %s; color: %s;"
            " border: 2px solid %s; border-bottom: 3px solid %s;"
            " border-radius: 5px; padding: 3px 9px; min-height: 22px;"
            " font-family: '%s'; font-size: 11px; }"
            "QPushButton:hover { background-color: %s; border-color: %s; }"
            % (theme.PANEL_ALT, theme.INK, theme.BORDER, theme.BORDER_SOFT,
               theme.FONT_GBA, theme.HOVER, theme.HOVER_BORDER)
        )
        self._sync_sound_enabled()
        self.size_value_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px; font-weight: bold;"
            % (theme.ORANGE_DARK, theme.FONT_DS)
        )
        self.fit_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.rule.setStyleSheet(
            "background-color: %s; border: none;" % theme.GOLD
        )
        self.btn_close_x.setStyleSheet(
            "QPushButton { background: transparent; color: %s; border: none;"
            " border-radius: 4px; font-family: '%s'; font-size: 15px; padding: 0; }"
            "QPushButton:hover { background-color: %s; color: %s; }"
            % (theme.INK_SOFT, theme.FONT_DS, theme.PANEL_ALT, theme.ORANGE_DARK)
        )
        self.btn_cancel.setStyleSheet(
            "QPushButton { background-color: %s; color: %s; border: 2px solid %s;"
            " border-bottom: 3px solid %s; border-radius: 5px; padding: 4px 13px;"
            " min-height: 24px; font-family: '%s'; font-size: 12px; }"
            "QPushButton:hover { background-color: %s; border-color: %s; }"
            % (theme.PANEL_ALT, theme.INK, theme.BORDER, theme.BORDER_SOFT,
               theme.FONT_GBA, theme.HOVER, theme.HOVER_BORDER)
        )
        self.btn_apply.setStyleSheet(
            "QPushButton { background-color: %s; color: %s; border: 2px solid %s;"
            " border-bottom: 3px solid %s; border-radius: 5px; padding: 4px 14px;"
            " min-height: 24px; font-family: '%s'; font-size: 12px; }"
            "QPushButton:hover { background-color: %s; }"
            "QPushButton:disabled { background-color: %s; color: %s; border-color: %s; }"
            % (theme.GREEN, theme.ON_ACCENT, theme.GREEN_DARK, theme.GREEN_DARK,
               theme.FONT_GBA, theme.GREEN_DARK, theme.DISABLED_BG,
               theme.DISABLED_FG, theme.DISABLED_BORDER)
        )
        self._sync_swatches()
        for swatch in self.swatches.values():
            swatch.update()
        self.slider.update()
        self._update_readout()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(QPen(QColor(theme.NAVY), 3))
        p.setBrush(QColor(theme.PANEL))
        p.drawRoundedRect(rect, 12, 12)
        p.setPen(QPen(QColor(theme.PANEL_ALT), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 9, 9)
        p.end()


class SpritePlate(CrispSpriteLabel):
    """Cream display case with a faint checkerboard behind the sprite."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        p.setClipPath(path)
        p.fillRect(rect, QColor(theme.FIELD_ALT))
        cell = 12
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.PANEL_ALT))
        for row, y in enumerate(range(int(rect.top()), int(rect.bottom()) + cell, cell)):
            for col, x in enumerate(range(int(rect.left()), int(rect.right()) + cell, cell)):
                if (row + col) % 2 == 0:
                    p.drawRect(x, y, cell, cell)
        p.setClipping(False)
        p.setPen(QPen(QColor(theme.NAVY), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 8, 8)
        highlight = QColor(theme.PANEL)
        highlight.setAlpha(70 if theme.THEME_ID in ("dark", "sinnoh") else 170)
        p.setPen(QPen(highlight, 1))
        p.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 6, 6)
        p.end()
        super().paintEvent(event)


class MiniDummyLeadBadge(QFrame):
    def __init__(self, initial_path: str):
        super().__init__()
        self.filepath = initial_path
        self._workers = []
        self._bounce = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(7, 3, 7, 3)
        lay.setSpacing(8)

        self.icon_lbl = QLabel()
        icon_extent = sprite_plate_extent(42)
        self.icon_lbl.setFixedSize(icon_extent, icon_extent)
        self.icon_lbl.setScaledContents(False)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet(
            "border: 1px solid %s; border-radius: 5px; background: %s;"
            % (theme.BORDER, theme.FIELD_ALT)
        )
        lay.addWidget(self.icon_lbl)

        self.text_lbl = QLabel("Slot 1: None")
        self.text_lbl.setMinimumWidth(130)
        lay.addWidget(self.text_lbl)

        self.btn_swap = QPushButton("Swap")
        self.btn_swap.setFixedWidth(56)
        self.btn_swap.setToolTip("Change the permanent Slot 1 Dummy Lead stored in slot1/")
        self.btn_swap.setStyleSheet(
            "QPushButton { font-size: 12px; padding: 3px 5px; min-height: 22px; }"
        )
        self.btn_swap.clicked.connect(self.swap_dummy)
        lay.addWidget(self.btn_swap)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(260)
        self.load_dummy(initial_path)
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(
            "MiniDummyLeadBadge { background-color: %s; border: 2px solid %s; border-radius: %spx; }"
            % (theme.PANEL, theme.NAVY, theme.CONTROL_RADIUS)
        )
        self.icon_lbl.setStyleSheet(
            "border: 1px solid %s; border-radius: 5px; background: %s;"
            % (theme.BORDER, theme.FIELD_ALT)
        )
        self.text_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 14px; border: none; background: transparent;"
            % (theme.INK, theme.FONT_DS)
        )
        self.btn_swap.setStyleSheet(
            "QPushButton { font-family: '%s'; font-size: 12px; padding: 3px 5px; min-height: 22px; }"
            % theme.FONT_GBA
        )
        # The sprite plate grows by a whole device-pixel block at 150%
        # (42 -> 56 px).  Pin the badge to that plate plus its margins and
        # frame, otherwise a layout under pressure shrinks the badge below
        # its content and clips the bottom of the icon.
        self.ensurePolished()
        self.setMinimumHeight(self.sizeHint().height())

    def _tick(self):
        self._bounce = not self._bounce
        self.icon_lbl.setContentsMargins(0, 2 if self._bounce else 0, 0, 0)

    def load_dummy(self, path: str):
        path = str(path or "").strip()
        self.filepath = path
        if not path:
            self.text_lbl.setText("Slot 1: Missing")
            self.text_lbl.setToolTip(
                "No lead Pokémon is staged yet. Use Swap to choose a .pk3."
            )
            return
        info = parse_pk3_file(path)
        if not info:
            self.text_lbl.setText("Slot 1: Missing")
            self.text_lbl.setToolTip(path)
            return
        self.text_lbl.setText(f"{info['nickname']}  Lv.{info['level']}")
        self.text_lbl.setToolTip(
            f"Link Cable Lead: {info['nickname']} (Lv.{info['level']}) — click Swap to change"
        )
        w = SpriteDownloadWorker(
            info["nat_dex"], info["is_shiny"], form=unown_form_from_pid(info["pid"])
        )
        w.loaded.connect(self._set_icon)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _set_icon(self, _main: str, icon_path: str, _item: str):
        if icon_path and Path(icon_path).exists():
            pm = QPixmap(icon_path)
            if not pm.isNull():
                self.icon_lbl.setPixmap(
                    integer_scaled_pixmap(
                        pm, self.icon_lbl.width(), self.icon_lbl.height()
                    )
                )

    def swap_dummy(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Slot 1 Dummy Lead (.pk3)", str(SLOT1_DIR), "Gen 3 Pokemon (*.pk3 *.ek3)"
        )
        if path:
            src = Path(path)
            dest = SLOT1_DIR / src.name
            if src.resolve() != dest.resolve():
                for old in SLOT1_DIR.glob("*.pk3"):
                    old.unlink()
                shutil.copy2(str(src), str(dest))
            self.load_dummy(str(dest))


class GBATradeCenterPanel(QFrame):
    """A FRLG trade-room window with a cream summary card inside."""

    def __init__(self, header_title: str, is_pc_side: bool = True):
        super().__init__()
        self.is_pc_side = is_pc_side
        self.current_path = ""
        self._workers = []
        self._bounce = False
        self._current_movie = None
        self._shiny = False
        self._has_item = False
        self._dex_state = ""
        self._waiting = True
        self._cry_dex = 0
        theme.soft_shadow(self, blur=22, dy=4, alpha=58)

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 9, 12, 11)
        main.setSpacing(8)

        top_plate_row = QHBoxLayout()
        top_plate_row.addStretch()
        self.header_plate = QLabel(header_title)
        self.header_plate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_plate.setFixedHeight(34)
        self.header_plate.setMinimumWidth(250)
        self.header_plate.setMaximumWidth(470)
        self.header_plate.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        top_plate_row.addWidget(self.header_plate)
        top_plate_row.addStretch()
        main.addLayout(top_plate_row)

        self.inner_card = QFrame()
        inner_card = self.inner_card
        card_lay = QVBoxLayout(inner_card)
        card_lay.setContentsMargins(12, 10, 12, 9)
        card_lay.setSpacing(7)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(11)
        self.sprite_lbl = SpritePlate("STANDBY")
        sprite_extent = sprite_plate_extent(104)
        self.sprite_lbl.set_plate_base(sprite_extent)
        self.sprite_lbl.setFixedSize(sprite_extent, sprite_extent)
        self.sprite_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_lbl.set_clickable(True)
        self.sprite_lbl.setToolTip("Click to hear this Pokémon's cry")
        self.sprite_lbl.clicked.connect(self._play_cry)
        hero_row.addWidget(self.sprite_lbl)

        ident_col = QVBoxLayout()
        ident_col.setSpacing(2)

        title_line = QHBoxLayout()
        self.name_lbl = QLabel("—")
        self.name_lbl.setMinimumWidth(0)
        self.name_lbl.setMinimumHeight(30)
        self.name_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # The standby messages are full sentences.  Wrapping them keeps the
        # heading readable in the 1180 px minimum window instead of slicing
        # the right edge off ("...FROM STORAG").
        self.name_lbl.setWordWrap(True)
        title_line.addWidget(self.name_lbl, stretch=1)
        self.dex_badge = QLabel("")
        title_line.addWidget(self.dex_badge)
        ident_col.addLayout(title_line)

        self.lvl_ot_lbl = QLabel("Lv. —   |   OT: —   |   TID: —")
        ident_col.addWidget(self.lvl_ot_lbl)

        self.nature_lbl = QLabel("Nature: —")
        ident_col.addWidget(self.nature_lbl)

        item_line = QHBoxLayout()
        item_line.setSpacing(5)
        # Kept as the worker's small icon target for compatibility, but the
        # visible held-item marker is the framed badge below.
        self.item_icon_lbl = QLabel()
        self.item_icon_lbl.setFixedSize(22, 22)
        self.item_icon_lbl.hide()
        self.item_text_lbl = QLabel("Held Item: None")
        item_line.addWidget(self.item_text_lbl)
        # Inline, like the text it belongs to: showing an item never changes
        # the card's height or pushes the stat rows around.
        self.item_badge = SummaryIconSlot(self, base=22)
        item_line.addWidget(self.item_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        item_line.addStretch()
        ident_col.addLayout(item_line)
        ident_col.addStretch()
        hero_row.addLayout(ident_col, stretch=1)
        card_lay.addLayout(hero_row)

        stats_grid = QGridLayout()
        stats_grid.setSpacing(4)
        self.stat_boxes = {}
        stat_keys = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
        for idx, sk in enumerate(stat_keys):
            lbl = QLabel(f"{sk}: —")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumHeight(25)
            self.stat_boxes[sk] = lbl
            stats_grid.addWidget(lbl, 0, idx)
        card_lay.addLayout(stats_grid)

        self.iv_ev_lbl = QLabel("IVs: — / — / — / — / — / —\nEVs: — / — / — / — / — / —")
        self.iv_ev_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        card_lay.addWidget(self.iv_ev_lbl)

        inner_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        main.addWidget(inner_card)
        main.addStretch(1)

        self.btn_row = QHBoxLayout()
        self.btn_row.setSpacing(6)
        main.addLayout(self.btn_row)

        self.bounce_timer = QTimer(self)
        self.bounce_timer.timeout.connect(self._animate_bounce)
        self.bounce_timer.start(240)
        self.apply_theme()
        self._sync_minimum_height()

    def _sync_minimum_height(self) -> None:
        """Keep the cream summary card from being squeezed by the link log.

        The trade tab shares its vertical space with an expanding log.  At
        150% the sprite plate grows by the whole-pixel factor, and the log's
        size hint used to win that fight: the last stat/EV rows were laid out
        below the card.  Give the card and the panel a layout floor so the
        log yields instead, at every UI scale.
        """
        card_h = int(self.inner_card.sizeHint().height())
        if card_h > 0 and self.inner_card.minimumHeight() != card_h:
            self.inner_card.setMinimumHeight(card_h)
        layout = self.layout()
        if layout is not None:
            panel_h = int(layout.sizeHint().height())
            if panel_h > 0 and self.minimumHeight() != panel_h:
                self.setMinimumHeight(panel_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_minimum_height()

    def paintEvent(self, event):
        super().paintEvent(event)
        # Quiet link-room motif behind the compact summary card.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(0.10)
        theme.draw_pokeball(
            painter, self.width() / 2, self.height() - 94, 55,
            top="#ffffff", bottom="#ffffff", outline="#ffffff",
            outline_width=2.4,
        )
        painter.end()

    def _animate_bounce(self):
        self._bounce = not self._bounce
        if hasattr(self, "icon_lbl"):
            self.icon_lbl.setContentsMargins(0, 0 if self._bounce else 6, 0, 0)

    def _stop_movie(self):
        if self._current_movie:
            self._current_movie.stop()
            self._current_movie = None
        if self.sprite_lbl.movie():
            self.sprite_lbl.movie().stop()
            self.sprite_lbl.setMovie(None)

    def apply_theme(self):
        """Repaint the link-room shell and every inline label in the panel."""
        normal_border = theme.BORDER if theme.THEME_ID in ("dark", "sinnoh", "light") else theme.PANEL
        border = theme.GOLD if self._shiny else normal_border
        self.setStyleSheet(
            "GBATradeCenterPanel {"
            " background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 %s, stop:1 %s);"
            " border: 3px solid %s; border-radius: 14px; }"
            % (theme.TRADE_BG_2, theme.TRADE_BG_1, border)
        )
        self.header_plate.setStyleSheet(
            "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 %s, stop:0.55 %s, stop:1 %s);"
            " color: %s; border: 2px solid %s;"
            " border-bottom: 3px solid %s; border-radius: 7px;"
            " font-family: '%s'; font-size: 14px; padding: 3px 12px;"
            % (theme.HEADER_LIGHT, theme.HEADER, theme.HEADER_DARK,
               theme.ON_HEADER, theme.GOLD, theme.HEADER_DARK, theme.FONT_GBA)
        )
        self.inner_card.setStyleSheet(
            "QFrame { background-color: %s; border: 2px solid %s;"
            " border-radius: %spx; }"
            % (theme.PANEL, theme.BORDER_SOFT, theme.PANEL_RADIUS)
        )
        self.sprite_lbl.setStyleSheet(
            "background: transparent; border: none; color: %s;"
            " font-family: '%s'; font-size: 12px;" % (theme.INK_MUTED, theme.FONT_GBA)
        )
        name_color = theme.ORANGE_DARK if (self._shiny or not self.current_path) else theme.NAVY_DARK
        # Loaded names stay large; standby sentences drop to 15 px so they
        # wrap cleanly above the stats instead of running past the card edge.
        name_size = 15 if self._waiting else 17
        self.name_lbl.setMinimumHeight(42 if self._waiting else 34)
        self.name_lbl.setStyleSheet(
            "font-size: %dpx; color: %s; font-family: '%s';"
            " border: none; background: transparent;" % (name_size, name_color, theme.FONT_GBA)
        )
        self.lvl_ot_lbl.setStyleSheet(
            "font-size: 13px; color: %s; font-family: '%s';"
            " border: none; background: transparent;" % (theme.INK, theme.FONT_DS)
        )
        self.nature_lbl.setStyleSheet(
            "font-size: 12px; color: %s; font-family: '%s';"
            " border: none; background: transparent;" % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.item_text_lbl.setStyleSheet(
            "font-size: 12px; color: %s; font-family: '%s';"
            " border: none; background: transparent;"
            % (theme.ORANGE_DARK if self._has_item else theme.INK_SOFT, theme.FONT_DS)
        )
        self.item_icon_lbl.setStyleSheet("border: none; background: transparent;")
        badge_color = theme.GREEN_DARK if self._dex_state == "ok" else theme.RED_DARK if self._dex_state == "bad" else theme.INK_SOFT
        self.dex_badge.setStyleSheet(
            "color: %s; font-size: 12px; font-family: '%s';"
            " border: none; background: transparent;" % (badge_color, theme.FONT_DS)
        )
        for box in self.stat_boxes.values():
            box.setStyleSheet(
                "background-color: %s; border: 2px solid %s; border-radius: 5px;"
                " color: %s; font-family: '%s'; font-size: 12px; padding: 4px 2px;"
                % (theme.PANEL_ALT, theme.BORDER, theme.INK, theme.FONT_DS)
            )
        self.iv_ev_lbl.setStyleSheet(
            "font-size: 12px; color: %s; font-family: '%s';"
            " border: none; background: transparent;" % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.update()

    def set_waiting_state(self, message: str = ""):
        if not message:
            message = "WAITING FOR SWITCH..." if not self.is_pc_side else "NO POKÉMON STAGED"

        self._cry_dex = 0
        self.current_path = ""
        self._shiny = False
        self._has_item = False
        self._dex_state = ""
        self._waiting = True
        self.apply_theme()
        self._stop_movie()
        self.sprite_lbl.setPixmap(QPixmap())
        self.sprite_lbl.setText("LINK\nWAIT" if not self.is_pc_side else "SLOT\nEMPTY")
        self.item_icon_lbl.setPixmap(QPixmap())
        self.item_badge.clear()
        self.name_lbl.setText(message)
        self.name_lbl.setToolTip(message)
        # Long status sentences must fit the summary column even in the
        # app's minimum-width window; loaded Pokémon names still use 17px.
        self.name_lbl.setStyleSheet(
            "font-size: 15px; color: %s; font-family: '%s'; border: none; background: transparent;"
            % (theme.ORANGE_DARK, theme.FONT_GBA)
        )

        if self.is_pc_side:
            self.lvl_ot_lbl.setText("Send a Pokémon from Bill's PC to trade...")
        else:
            self.lvl_ot_lbl.setText("Select a Pokémon on your Switch in the Trade Center...")

        self.nature_lbl.setText("Nature: —")
        self.item_text_lbl.setText("Held Item: —")
        self.dex_badge.setText("")
        for sk, box in self.stat_boxes.items():
            box.setText(f"{sk}: —")
        self.iv_ev_lbl.setText("IVs: — / — / — / — / — / —\nEVs: — / — / — / — / — / —")
        self.apply_theme()
        self._sync_minimum_height()

    def load_pk3(self, filepath: str, force_shiny: bool | None = None):
        self.current_path = filepath.strip() if filepath else ""
        info = parse_pk3_file(self.current_path)
        if not info:
            self.set_waiting_state("NO POKÉMON LOADED")
            return

        self._waiting = False
        shiny = force_shiny if force_shiny is not None else info["is_shiny"]
        self._shiny = bool(shiny)

        dex = info["nat_dex"]
        self._cry_dex = int(dex)
        star = " ★ SHINY" if shiny else ""
        self.name_lbl.setText(f"#{dex:03d} {info['nickname']}{star}")
        self.name_lbl.setToolTip(self.name_lbl.text())

        self.lvl_ot_lbl.setText(
            f"Lv. {info['level']}   |   OT: {info['ot_name']}   |   TID: {info['tid']:05d} / SID: {info['sid']:05d}"
        )
        self.nature_lbl.setText(f"Nature: {info['nature_full']}   |   PID: {info['pid']:08X}")

        self._has_item = info["item_id"] > 0
        self.item_badge.set_item(int(info["item_id"]))
        if self._has_item:
            self.item_text_lbl.setText(f"Held Item: {info['item_name']}")
        else:
            self.item_text_lbl.setText("Held Item: None")
            self.item_icon_lbl.setPixmap(QPixmap())

        if 1 <= dex <= 151:
            self._dex_state = "ok"
            self.dex_badge.setText("✓ KANTO OK")
        else:
            self._dex_state = "bad"
            self.dex_badge.setText("⚠ NAT DEX")

        cur_hp, max_hp, atk, dfn, spa, spd, spe = info["stats"]
        stat_vals = {
            "HP": f"{cur_hp}/{max_hp}", "Atk": str(atk), "Def": str(dfn),
            "SpA": str(spa), "SpD": str(spd), "Spe": str(spe),
        }
        for sk, val_str in stat_vals.items():
            self.stat_boxes[sk].setText(f"{sk}: {val_str}")

        ivs = info["ivs"]
        evs = info["evs"]
        self.iv_ev_lbl.setText(
            f"IVs: {ivs[0]:02d}/{ivs[1]:02d}/{ivs[2]:02d}/{ivs[3]:02d}/{ivs[4]:02d}/{ivs[5]:02d}\n"
            f"EVs: {evs[0]:03d}/{evs[1]:03d}/{evs[2]:03d}/{evs[3]:03d}/{evs[4]:03d}/{evs[5]:03d}"
        )
        self.apply_theme()
        self._sync_minimum_height()

        self._stop_movie()
        form = unown_form_from_pid(info["pid"])
        gif_path = animated_sprite_path(dex, form, shiny)
        if gif_path.exists():
            self.sprite_lbl.setText("")
            self._current_movie = QMovie(str(gif_path))
            self.sprite_lbl.setMovie(self._current_movie)
            self._current_movie.start()
        else:
            static_path = (
                paths.ASSETS_DIR / "sprites"
                / ("shiny" if shiny else "normal") / f"{dex}.png"
            )
            if static_path.exists():
                self.sprite_lbl.setPixmap(QPixmap(str(static_path)))
            else:
                self.sprite_lbl.setText("NO SPRITE")

        w = SpriteDownloadWorker(dex, shiny, info["item_slug"], form=form)
        w.loaded.connect(self._apply_sprites)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _play_cry(self):
        if self._cry_dex:
            sound.play_cry(self._cry_dex)

    def _apply_sprites(self, main_path: str, icon_path: str, item_path: str):
        if main_path and Path(main_path).exists() and not self.sprite_lbl.movie():
            if main_path.endswith(".gif"):
                self.sprite_lbl.setText("")
                self._current_movie = QMovie(main_path)
                self.sprite_lbl.setMovie(self._current_movie)
                self._current_movie.start()
            else:
                pm = QPixmap(main_path)
                self.sprite_lbl.setText("")
                self.sprite_lbl.setPixmap(pm)

        if icon_path and Path(icon_path).exists() and hasattr(self, "icon_lbl"):
            ic = QPixmap(icon_path)
            if not ic.isNull():
                self.icon_lbl.setPixmap(
                    ic.scaled(
                        38, 38,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                )

        if item_path and Path(item_path).exists():
            it = QPixmap(item_path)
            if not it.isNull():
                self.item_icon_lbl.setPixmap(
                    it.scaled(
                        20, 20,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                )


class TradeTunnelWidget(QWidget):
    """The link-room cable stage, driven by the live trade state.

    The old animation tossed two Poké Balls back and forth for the whole
    session, whether or not a trade was happening.  This version has distinct
    stages: a standby breath, an initialisation sweep while the link is being
    established, a held link while the player is choosing, a single charging
    core once the console reports that the trade animation started, and one
    final pass into the Switch screen when the received record is written.
    No ball crosses the cable until that arrival moment.
    """

    # The retail wireless trade animation is ~1935 frames at 59.727 Hz.  The
    # ring fills over this span so it tracks the console rather than a guessed
    # short loop.  The receive file remains the authority for the arrival.
    TRADE_SEQUENCE_SECONDS = 32.4
    ARRIVAL_SECONDS = 0.72

    def __init__(self):
        super().__init__()
        self.setFixedHeight(76)
        self.state = "IDLE"
        self.status_text = "GBA WIRELESS LINK STANDBY — READY TO TRADE"
        self.phase = 0.0
        self.progress = 0.0
        self._state_elapsed = 0.0
        self._last_tick = time.monotonic()
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start(33)

    # -- public state -----------------------------------------------------
    def set_state(self, state: str, text: str = ""):
        if state != self.state:
            self.state = state
            self._state_elapsed = 0.0
        if text:
            self.status_text = text
        self.update()

    def start_trade_sequence(self) -> None:
        """The console has entered its trade animation; start the charge."""
        self.progress = 0.0
        self.set_state(
            "TRADE",
            "TRADE IN PROGRESS — CONSOLE LINK SEQUENCE RUNNING...",
        )

    def set_finalizing(self) -> None:
        """The console has sent READY_FINISH and is committing the trade."""
        self.progress = max(self.progress, 0.94)
        self.set_state(
            "FINALIZING",
            "TRADE CONFIRMED — RECEIVING POKéMON FROM SWITCH...",
        )

    def begin_arrival(self) -> None:
        """The received .pk3 has appeared; make the one final transfer pass."""
        self.progress = 1.0
        self.set_state("ARRIVAL", "POKéMON ARRIVING FROM SWITCH...")

    def _tick(self):
        now = time.monotonic()
        dt = max(0.0, min(0.1, now - self._last_tick))
        self._last_tick = now
        active = self.state in (
            "IDLE", "SCANNING", "LINKED", "TRADE", "FINALIZING",
            "ARRIVAL", "DONE",
        )
        if not active:
            return
        self._state_elapsed += dt
        self.phase = (self.phase + dt * 0.72) % 1.0
        if self.state == "TRADE":
            self.progress = max(
                self.progress,
                min(0.93, self._state_elapsed / self.TRADE_SEQUENCE_SECONDS),
            )
        elif self.state == "ARRIVAL" and self._state_elapsed >= self.ARRIVAL_SECONDS:
            self.state = "DONE"
            self._state_elapsed = 0.0
            self.status_text = "TRADE COMPLETE — POKéMON RECEIVED"
        self.update()

    def _state_color(self) -> QColor:
        return {
            "LINKED": QColor(theme.BLUE),
            "SCANNING": QColor(theme.ORANGE_DARK),
            "TRADE": QColor(theme.ORANGE_DARK),
            "FINALIZING": QColor(theme.GOLD),
            "ARRIVAL": QColor(theme.BLUE),
            "DONE": QColor(theme.GREEN_DARK),
            "ERROR": QColor(theme.RED_DARK),
        }.get(self.state, QColor(theme.INK_SOFT))

    def _draw_handhelds(self, p: QPainter, w: int, h: int):
        # Left: GBA with a tiny screen.
        gba = QRectF(20, h - 48, 78, 32)
        p.setPen(QPen(QColor(theme.NAVY_DARK), 2))
        p.setBrush(QColor(theme.NAVY))
        p.drawRoundedRect(gba, 7, 7)
        screen = QRectF(gba.left() + 8, gba.top() + 5, 38, 22)
        p.setPen(QPen(QColor(theme.BORDER_STRONG), 1.5))
        p.setBrush(QColor(theme.FIELD))
        p.drawRoundedRect(screen, 2, 2)
        p.setPen(QColor(theme.INK))
        p.setFont(theme.ui_font(10, gba=True, bold=True))
        p.drawText(screen, Qt.AlignmentFlag.AlignCenter, "PC")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.GOLD))
        p.drawEllipse(QPointF(gba.right() - 17, gba.top() + 11), 3.3, 3.3)
        p.setBrush(QColor(theme.RED))
        p.drawEllipse(QPointF(gba.right() - 10, gba.top() + 16), 3.3, 3.3)

        # Right: Switch-style tablet.
        switch = QRectF(w - 106, h - 50, 86, 35)
        p.setPen(QPen(QColor(theme.BORDER_STRONG), 2))
        p.setBrush(QColor(theme.NAVY_DARK))
        p.drawRoundedRect(switch, 8, 8)
        screen = QRectF(switch.left() + 14, switch.top() + 5, 58, 25)
        p.setPen(QPen(QColor(theme.BORDER_STRONG), 1.5))
        p.setBrush(QColor(theme.PANEL))
        p.drawRoundedRect(screen, 3, 3)
        p.setPen(QColor(theme.INK))
        p.setFont(theme.ui_font(9, gba=True, bold=True))
        p.drawText(screen, Qt.AlignmentFlag.AlignCenter, "SWITCH")
        p.setBrush(QColor(theme.GREEN))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(switch.left() + 7, switch.top() + 9), 2.6, 2.6)
        p.drawEllipse(QPointF(switch.right() - 7, switch.top() + 9), 2.6, 2.6)

    def _draw_cable(self, p: QPainter, w: int, h: int, color: QColor) -> None:
        cable_y = h - 25
        if self.state in ("SCANNING", "IDLE", "ERROR"):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.BORDER))
            for x in range(98, w - 98, 9):
                p.drawRect(x, cable_y, 5, 3)
            p.setBrush(QColor(theme.PANEL_ALT))
            for x in range(98, w - 98, 9):
                p.drawRect(x + 5, cable_y + 1, 4, 1)
            return

        # Connected / trade states use a solid rail.  Thin inner lines give it
        # the same two-tone cable look as the rest of the UI without reading as
        # a bar graph.
        p.setPen(QPen(color, 4))
        p.drawLine(QPointF(98, cable_y + 1), QPointF(w - 98, cable_y + 1))
        p.setPen(QPen(QColor(theme.PANEL), 1))
        p.drawLine(QPointF(100, cable_y), QPointF(w - 100, cable_y))

    def _draw_travel_pip(
        self, p: QPainter, x: float, y: float, color: QColor, alpha: int
    ) -> None:
        glow = QColor(color)
        glow.setAlpha(max(0, min(255, alpha // 3)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(x, y), 5.0, 5.0)
        core = QColor(color)
        core.setAlpha(alpha)
        p.setBrush(core)
        p.drawEllipse(QPointF(x, y), 2.2, 2.2)

    def _draw_initialising(self, p: QPainter, w: int, h: int, color: QColor):
        """A start-up sweep, not a trade: packets seek the centre and fade."""
        cy = h - 24.0
        cx = w / 2.0
        for i in range(3):
            t = (self.phase + i / 3.0) % 1.0
            alpha = int(150 * (1.0 - t))
            left = 112.0 + (cx - 124.0) * t
            right = (w - 112.0) - (w / 2.0 - 12.0) * t
            self._draw_travel_pip(p, left, cy, color, alpha)
            self._draw_travel_pip(p, right, cy, color, alpha)
        p.setPen(QPen(color, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        pulse = 8.0 + 4.0 * (0.5 + 0.5 * math.sin(self.phase * 2 * math.pi))
        p.drawEllipse(QPointF(cx, cy), pulse, pulse)

    def _draw_trade_core(self, p: QPainter, w: int, h: int, color: QColor):
        """Two energy streams feed a single core.  Nothing travels past it."""
        cy = h - 24.0
        cx = w / 2.0
        # Incoming energy from both ends, deliberately short of the endpoints.
        for side in (-1, 1):
            for i in range(4):
                t = (self.phase * 1.7 + i / 4.0) % 1.0
                distance = 74.0 * (1.0 - t)
                x = cx + side * (34.0 + distance)
                alpha = int(190 * (1.0 - t) + 25)
                self._draw_travel_pip(p, x, cy, color, alpha)

        # Progress ring around the core.  It fills over the real animation and
        # sits full while the record is committing/arriving.
        p.setPen(QPen(QColor(theme.BORDER), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 14, 14)
        arc_pen = QPen(color, 2.6)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        span = int(-360 * 16 * max(0.02, min(1.0, self.progress)))
        p.drawArc(QRectF(cx - 14, cy - 14, 28, 28), 90 * 16, span)
        theme.draw_pokeball(
            p, cx, cy, 8.5,
            angle=self.phase * 360 if self.state != "FINALIZING" else self.phase * 1440,
            outline_width=1.5,
        )
        if self.state == "FINALIZING":
            pulse = 15.5 + 2.0 * (0.5 + 0.5 * math.sin(self.phase * 8 * math.pi))
            p.setPen(QPen(QColor(theme.GOLD), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), pulse, pulse)

    def _draw_link_badge(self, p: QPainter, w: int, h: int, color: QColor):
        cy = h - 24.0
        cx = w / 2.0
        breathe = 13.0 + 1.6 * (0.5 + 0.5 * math.sin(self.phase * 2 * math.pi))
        p.setPen(QPen(color, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), breathe, breathe)
        # Two small interlocking link rings; clearly "connected", not a ball.
        for dx in (-3.0, 3.0):
            p.drawEllipse(QRectF(cx + dx - 3.5, cy - 3.5, 7, 7))

    def _draw_arrival(self, p: QPainter, w: int, h: int, color: QColor):
        cy = h - 24.0
        cx = w / 2.0
        end_x = w - 112.0
        t = min(1.0, self._state_elapsed / self.ARRIVAL_SECONDS)
        eased = t * t * (3.0 - 2.0 * t)
        ball_x = cx + (end_x - cx) * eased
        # A short trail behind the single ball, never a round trip.
        for i in range(4):
            trail = max(0.0, eased - (i + 1) * 0.055)
            x = cx + (end_x - cx) * trail
            alpha = max(20, 150 - i * 36)
            p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), alpha), 2))
            p.drawLine(QPointF(x - 5, cy), QPointF(x + 5, cy))
        theme.draw_pokeball(
            p, ball_x, cy, 10, angle=self.phase * 540, outline_width=1.8
        )
        if t >= 0.72:
            burst = (t - 0.72) / 0.28
            p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), int(190 * (1 - burst))), 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            radius = 10 + burst * 22
            p.drawEllipse(QPointF(end_x, cy), radius, radius * 0.65)

    def _draw_done_badge(self, p: QPainter, w: int, h: int):
        cy = h - 24.0
        cx = w / 2.0
        mid = QRectF(cx - 12, cy - 12, 24, 24)
        p.setPen(QPen(QColor(theme.GREEN_DARK), 2))
        p.setBrush(QColor(theme.GREEN_LIGHT))
        p.drawEllipse(mid)
        p.setPen(QPen(QColor(theme.GREEN_DARK), 2.5))
        p.drawLine(QPointF(mid.left() + 6, mid.center().y()),
                   QPointF(mid.center().x() - 1, mid.bottom() - 7))
        p.drawLine(QPointF(mid.center().x() - 1, mid.bottom() - 7),
                   QPointF(mid.right() - 5, mid.top() + 7))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        rect = QRectF(1, 1, w - 2, h - 2)
        theme.rounded_frame(
            p, rect, fill=theme.PAPER, border=theme.NAVY, radius=9, width=2,
            shadow=True, highlight=True,
        )

        state_col = self._state_color()
        p.setFont(theme.ui_font(13, bold=True))
        p.setPen(state_col)
        p.drawText(
            QRectF(10, 2, w - 20, 20),
            Qt.AlignmentFlag.AlignCenter,
            self.status_text,
        )

        self._draw_cable(p, w, h, state_col)
        self._draw_handhelds(p, w, h)
        start_x, end_x = 100.0, w - 112.0
        cy = h - 25.0

        if self.state in ("IDLE", "ERROR"):
            dim = QColor(theme.INK_SOFT)
            dim.setAlpha(170)
            theme.draw_pokeball(p, start_x, cy, 8, outline_width=1.5)
            theme.draw_pokeball(p, end_x, cy, 8, top=theme.BLUE, outline_width=1.5)
        elif self.state == "SCANNING":
            self._draw_initialising(p, w, h, state_col)
            theme.draw_pokeball(
                p, start_x, cy, 8, angle=self.phase * 180, outline_width=1.5
            )
            theme.draw_pokeball(
                p, end_x, cy, 8, top=theme.BLUE,
                angle=-self.phase * 180, outline_width=1.5,
            )
        elif self.state == "LINKED":
            theme.draw_pokeball(p, start_x, cy, 8, outline_width=1.5)
            theme.draw_pokeball(p, end_x, cy, 8, top=theme.BLUE, outline_width=1.5)
            self._draw_link_badge(p, w, h, state_col)
        elif self.state in ("TRADE", "FINALIZING"):
            self._draw_trade_core(p, w, h, state_col)
        elif self.state == "ARRIVAL":
            self._draw_arrival(p, w, h, state_col)
        elif self.state == "DONE":
            theme.draw_pokeball(p, start_x, cy, 8, outline_width=1.5)
            theme.draw_pokeball(p, end_x, cy, 8, top=theme.BLUE, outline_width=1.5)
            self._draw_done_badge(p, w, h)

        if self.state == "ERROR":
            p.setPen(QPen(QColor(theme.RED_DARK), 2))
            p.setBrush(QColor(theme.RED_LIGHT))
            p.drawEllipse(QRectF(w / 2 - 10, cy - 10, 20, 20))
            p.setFont(theme.ui_font(13, gba=True, bold=True))
            p.setPen(QColor(theme.RED_DARK))
            p.drawText(QRectF(w / 2 - 10, cy - 10, 20, 20), Qt.AlignmentFlag.AlignCenter, "!")
