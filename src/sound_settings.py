"""The full sound mixer, separated from the compact Settings popup.

The popup keeps the quick SFX toggle and volume; this dialog owns the three
independent buses, the OEM pack status, and the folder/reload controls.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import paths
import sound
import theme


class _BusRow(QWidget):
    """One labelled bus: enable, level, value and a test button."""

    toggled = pyqtSignal(bool)
    volume_changed = pyqtSignal(float)
    test_requested = pyqtSignal()

    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(7)
        self.check = QCheckBox(title)
        self.check.toggled.connect(self.toggled.emit)
        top.addWidget(self.check)
        top.addStretch()
        self.value_lbl = QLabel("0%")
        self.value_lbl.setMinimumWidth(38)
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.value_lbl)
        self.test_btn = QPushButton("TEST")
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.clicked.connect(self.test_requested.emit)
        top.addWidget(self.test_btn)
        lay.addLayout(top)

        self.detail_lbl = QLabel(detail)
        self.detail_lbl.setWordWrap(True)
        lay.addWidget(self.detail_lbl)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.valueChanged.connect(self._on_value)
        row.addWidget(self.slider, 1)
        lay.addLayout(row)

    def _on_value(self, value: int) -> None:
        self.value_lbl.setText(f"{value}%")
        self.volume_changed.emit(value / 100.0)

    def set_state(self, enabled: bool, volume: float) -> None:
        self.check.blockSignals(True)
        self.check.setChecked(bool(enabled))
        self.check.blockSignals(False)
        self.slider.blockSignals(True)
        self.slider.setValue(max(0, min(100, int(round(float(volume) * 100)))))
        self.slider.blockSignals(False)
        self.value_lbl.setText(f"{self.slider.value()}%")
        self.slider.setEnabled(bool(enabled))
        self.test_btn.setEnabled(bool(enabled))

    def apply_theme(self) -> None:
        self.check.setStyleSheet(
            "QCheckBox { color: %s; font-family: '%s'; font-size: 13px;"
            " font-weight: bold; letter-spacing: 1px; }"
            % (theme.INK, theme.FONT_GBA)
        )
        self.detail_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.value_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px; font-weight: bold;"
            % (theme.ORANGE_DARK, theme.FONT_DS)
        )
        self.slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 7px; background: %s;"
            " border: 1px solid %s; border-radius: 3px; }"
            "QSlider::sub-page:horizontal { background: %s; border-radius: 3px; }"
            "QSlider::handle:horizontal { width: 15px; margin: -5px 0;"
            " background: %s; border: 2px solid %s; border-radius: 7px; }"
            "QSlider:disabled { background: transparent; }"
            % (theme.PANEL_ALT, theme.BORDER, theme.GOLD,
               theme.ORANGE_DARK, theme.NAVY)
        )
        self.test_btn.setStyleSheet(
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


class SoundSettingsDialog(QDialog):
    """Non-modal mixer for music, effects and cries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FRLG Studio — Sound")
        self.setObjectName("SoundSettingsDialog")
        self.setModal(False)
        self.setMinimumWidth(660)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self._manager = sound.manager()
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        self.title_lbl = QLabel("SOUND")
        header.addWidget(self.title_lbl)
        header.addStretch()
        self.mute_check = QCheckBox("MUTE ALL")
        self.mute_check.setToolTip("Mute every bus; Ctrl+M does the same from the studio")
        self.mute_check.toggled.connect(self._on_mute)
        header.addWidget(self.mute_check)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Close sound settings")
        self.close_btn.clicked.connect(self.close)
        header.addWidget(self.close_btn)
        root.addLayout(header)

        self.rule = QFrame()
        self.rule.setFixedHeight(2)
        root.addWidget(self.rule)

        self.pack_frame = QFrame()
        pack_lay = QVBoxLayout(self.pack_frame)
        pack_lay.setContentsMargins(12, 10, 12, 10)
        pack_lay.setSpacing(4)
        pack_top = QHBoxLayout()
        self.pack_title = QLabel("OEM SOUND PACK")
        pack_top.addWidget(self.pack_title)
        pack_top.addStretch()
        self.audio_lbl = QLabel("")
        pack_top.addWidget(self.audio_lbl)
        pack_lay.addLayout(pack_top)
        self.pack_summary_lbl = QLabel("")
        self.pack_summary_lbl.setWordWrap(True)
        pack_lay.addWidget(self.pack_summary_lbl)
        self.pack_path_lbl = QLabel("")
        self.pack_path_lbl.setWordWrap(True)
        pack_lay.addWidget(self.pack_path_lbl)
        self.pack_errors_lbl = QLabel("")
        self.pack_errors_lbl.setWordWrap(True)
        self.pack_errors_lbl.hide()
        pack_lay.addWidget(self.pack_errors_lbl)

        pack_buttons = QHBoxLayout()
        pack_buttons.setSpacing(7)
        self.open_pack_btn = QPushButton("OPEN PACK FOLDER")
        self.open_pack_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_pack_btn.clicked.connect(self._open_pack)
        pack_buttons.addWidget(self.open_pack_btn)
        self.reload_btn = QPushButton("RELOAD PACK")
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.clicked.connect(self._reload_pack)
        pack_buttons.addWidget(self.reload_btn)
        pack_buttons.addStretch()
        self.music_now_lbl = QLabel("")
        pack_buttons.addWidget(self.music_now_lbl)
        pack_lay.addLayout(pack_buttons)
        root.addWidget(self.pack_frame)

        self.music_row = _BusRow(
            "MUSIC",
            "Pokémon Center loop for the active theme. The Gen 3 trade theme "
            "takes over while a link trade is running.",
        )
        self.sfx_row = _BusRow(
            "SOUND EFFECTS",
            "Menus, PC box pick-up/drop, page turns, dialogs, link and trade cues.",
        )
        self.cry_row = _BusRow(
            "CRIES",
            "Click a summary portrait in Bill's PC, the editor or a trade card "
            "to play its cry.",
        )
        self._rows = (self.music_row, self.sfx_row, self.cry_row)
        for row in self._rows:
            root.addWidget(row)

        self.music_row.toggled.connect(self._on_music_toggle)
        self.music_row.volume_changed.connect(self._on_music_volume)
        self.music_row.test_requested.connect(self._test_music)
        self.sfx_row.toggled.connect(self._on_sfx_toggle)
        self.sfx_row.volume_changed.connect(self._on_sfx_volume)
        self.sfx_row.test_requested.connect(self._test_sfx)
        self.cry_row.toggled.connect(self._on_cry_toggle)
        self.cry_row.volume_changed.connect(self._on_cry_volume)
        self.cry_row.test_requested.connect(self._test_cry)

        footer = QHBoxLayout()
        self.hint_lbl = QLabel("Ctrl+M mutes all three buses.")
        footer.addWidget(self.hint_lbl)
        footer.addStretch()
        self.close_bottom_btn = QPushButton("CLOSE")
        self.close_bottom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_bottom_btn.clicked.connect(self.close)
        footer.addWidget(self.close_bottom_btn)
        root.addLayout(footer)

        self.apply_theme()
        self._connect_manager()
        self.refresh()

    def _connect_manager(self) -> None:
        manager = self._manager
        if manager is None:
            return
        try:
            manager.pack_changed.connect(self.refresh)
            manager.music_changed.connect(self._on_music_changed)
            manager.mute_changed.connect(self._on_mute_changed)
        except (TypeError, RuntimeError):
            pass

    def refresh(self) -> None:
        manager = self._manager
        if manager is None:
            return
        self._syncing = True
        self.mute_check.blockSignals(True)
        self.mute_check.setChecked(bool(manager.master_muted))
        self.mute_check.blockSignals(False)
        self.music_row.set_state(manager.music_enabled, manager.music_volume)
        self.sfx_row.set_state(manager.sfx_enabled, manager.sfx_volume)
        self.cry_row.set_state(manager.cries_enabled, manager.cries_volume)
        self._syncing = False
        self._update_status()
        self._update_mute_state()

    def _update_status(self) -> None:
        manager = self._manager
        if manager is None:
            return
        status = manager.status()
        self.pack_summary_lbl.setText(status["pack"])
        self.pack_path_lbl.setText(
            f"Pack folder: {paths.SOUNDPACK_DIR}\n"
            f"Cries: {paths.BUNDLED_CRIES_DIR}\n"
            f"Effects: {paths.BUNDLED_SFX_DIR}"
        )
        if status["errors"]:
            self.pack_errors_lbl.setText(
                "Ignored: " + " · ".join(status["errors"][:3])
            )
            self.pack_errors_lbl.show()
        else:
            self.pack_errors_lbl.hide()
        if not status["available"]:
            text = "NO AUDIO DEVICE — CONTROLS STAY QUIET"
            colour = theme.RED_DARK
        elif status["cries"] == 0 and status["sfx"] == 0 and status["music"] == 0:
            text = "PACK EMPTY — ADD FILES, THEN RELOAD"
            colour = theme.ORANGE_DARK
        else:
            text = "AUDIO READY"
            colour = theme.GREEN_DARK
        self.audio_lbl.setText(text)
        self.audio_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px; letter-spacing: 1px;"
            % (colour, theme.FONT_DS)
        )
        label = status["music_label"] or "—"
        self.music_now_lbl.setText(f"NOW: {label}")
        self.music_now_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px; letter-spacing: 1px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )

    def _update_mute_state(self) -> None:
        manager = self._manager
        muted = bool(manager and manager.master_muted)
        for row in self._rows:
            row.setEnabled(not muted)
        self.music_row.setEnabled(not muted)
        self.sfx_row.setEnabled(not muted)
        self.cry_row.setEnabled(not muted)

    def _on_mute(self, checked: bool) -> None:
        if self._syncing or self._manager is None:
            return
        self._manager.set_master_muted(bool(checked))
        self._update_mute_state()
        if not checked:
            self._manager.play("ui_toggle", force=True)

    def _on_mute_changed(self, muted: bool) -> None:
        self._syncing = True
        self.mute_check.setChecked(bool(muted))
        self._syncing = False
        self._update_mute_state()

    def _on_music_toggle(self, checked: bool) -> None:
        if self._syncing or self._manager is None:
            return
        self._manager.set_music_enabled(bool(checked))
        self.music_row.slider.setEnabled(bool(checked))
        self.music_row.test_btn.setEnabled(bool(checked))

    def _on_music_volume(self, value: float) -> None:
        if self._syncing or self._manager is None:
            return
        self._manager.set_music_volume(float(value))

    def _on_sfx_toggle(self, checked: bool) -> None:
        if self._syncing or self._manager is None:
            return
        self._manager.set_sfx_enabled(bool(checked))
        self.sfx_row.slider.setEnabled(bool(checked))
        self.sfx_row.test_btn.setEnabled(bool(checked))

    def _on_sfx_volume(self, value: float) -> None:
        if self._syncing or self._manager is None:
            return
        self._manager.set_sfx_volume(float(value))

    def _on_cry_toggle(self, checked: bool) -> None:
        if self._syncing or self._manager is None:
            return
        self._manager.set_cries_enabled(bool(checked))
        self.cry_row.slider.setEnabled(bool(checked))
        self.cry_row.test_btn.setEnabled(bool(checked))

    def _on_cry_volume(self, value: float) -> None:
        if self._syncing or self._manager is None:
            return
        self._manager.set_cries_volume(float(value))

    def _test_music(self) -> None:
        if self._manager is not None:
            self._manager.preview_music()

    def _test_sfx(self) -> None:
        if self._manager is not None:
            self._manager.play("ui_confirm", force=True)

    def _test_cry(self) -> None:
        if self._manager is not None:
            self._manager.preview_cry()

    def _open_pack(self) -> None:
        try:
            paths.SOUNDPACK_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if self._manager is not None:
            self._manager.play("ui_open")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.SOUNDPACK_DIR)))

    def _reload_pack(self) -> None:
        if self._manager is not None:
            self._manager.reload_pack()
            self._manager.play("ui_confirm", force=True)
        self.refresh()

    def _on_music_changed(self, _label: str) -> None:
        self._update_status()

    def apply_theme(self) -> None:
        self.setStyleSheet(
            "QDialog#SoundSettingsDialog { background-color: %s; }"
            % theme.PANEL
        )
        self.title_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 18px; letter-spacing: 3px;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.mute_check.setStyleSheet(
            "QCheckBox { color: %s; font-family: '%s'; font-size: 12px;"
            " font-weight: bold; letter-spacing: 1px; }"
            % (theme.RED_DARK if self._manager and self._manager.master_muted
               else theme.INK, theme.FONT_GBA)
        )
        self.rule.setStyleSheet("background-color: %s; border: none;" % theme.GOLD)
        self.pack_frame.setStyleSheet(
            "QFrame { background-color: %s; border: 2px solid %s;"
            " border-radius: 8px; }"
            % (theme.PANEL_ALT, theme.BORDER_SOFT)
        )
        self.pack_title.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px; letter-spacing: 2px;"
            " background: transparent; border: none;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.pack_summary_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 14px; font-weight: bold;"
            " background: transparent; border: none;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.pack_path_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px;"
            " background: transparent; border: none;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.pack_errors_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px;"
            " background: transparent; border: none;"
            % (theme.RED_DARK, theme.FONT_DS)
        )
        for button in (self.open_pack_btn, self.reload_btn):
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-bottom: 3px solid %s;"
                " border-radius: 5px; padding: 3px 9px; min-height: 22px;"
                " font-family: '%s'; font-size: 10px; }"
                "QPushButton:hover { background-color: %s; border-color: %s; }"
                % (theme.PANEL, theme.INK, theme.BORDER, theme.BORDER_SOFT,
                   theme.FONT_GBA, theme.HOVER, theme.HOVER_BORDER)
            )
        for row in self._rows:
            row.apply_theme()
        self.hint_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        for button in (self.close_btn, self.close_bottom_btn):
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-bottom: 3px solid %s;"
                " border-radius: 5px; padding: 3px 12px; min-height: 24px;"
                " font-family: '%s'; font-size: 11px; }"
                "QPushButton:hover { background-color: %s; border-color: %s; }"
                % (theme.PANEL_ALT, theme.INK, theme.BORDER, theme.BORDER_SOFT,
                   theme.FONT_GBA, theme.HOVER, theme.HOVER_BORDER)
            )
        self.close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: %s; border: none;"
            " border-radius: 4px; font-family: '%s'; font-size: 15px; padding: 0; }"
            "QPushButton:hover { background-color: %s; color: %s; }"
            % (theme.INK_SOFT, theme.FONT_DS, theme.PANEL_ALT, theme.ORANGE_DARK)
        )
        self.audio_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px; letter-spacing: 1px;"
            " background: transparent; border: none;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.music_now_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 10px; letter-spacing: 1px;"
            " background: transparent; border: none;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self._update_status()
