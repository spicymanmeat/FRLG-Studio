"""About window and on-demand update check."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

import theme
from utils import BASE_DIR, DATA_DIR
from version import (
    APP_NAME, APP_TAGLINE, APP_VERSION, DISCORD_URL, PROJECT_URL,
    RELEASES_API, RELEASES_URL,
)


class UpdateWorker(QThread):
    checked = pyqtSignal(bool, str)

    def run(self):
        request = urllib.request.Request(
            RELEASES_API,
            headers={
                "User-Agent": f"{APP_NAME}/{APP_VERSION}",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latest = str(payload.get("tag_name") or "").lstrip("v")
            url = str(payload.get("html_url") or RELEASES_URL)
            if not latest:
                self.checked.emit(False, "The release has no version tag yet.")
                return
            if self._newer(latest, APP_VERSION):
                self.checked.emit(
                    True,
                    f"Version {latest} is available.\n\n{url}",
                )
            else:
                self.checked.emit(
                    True,
                    f"You are on {APP_VERSION}, the newest published release.",
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                self.checked.emit(
                    False,
                    "No published GitHub releases yet.\n\n"
                    f"{RELEASES_URL}",
                )
            else:
                self.checked.emit(False, f"Update check failed (HTTP {exc.code}).")
        except Exception as exc:
            self.checked.emit(False, f"Could not reach GitHub: {exc}")

    @staticmethod
    def _newer(candidate: str, current: str) -> bool:
        def parts(value: str) -> tuple[int, ...]:
            return tuple(int(item) for item in re.findall(r"\d+", value))
        left, right = parts(candidate), parts(current)
        length = max(len(left), len(right))
        left += (0,) * (length - len(left))
        right += (0,) * (length - len(right))
        return left > right


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(560)
        self._worker = None
        self.setStyleSheet("QDialog { background-color: %s; }" % theme.APP_BG_BOTTOM)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(9)

        header = QHBoxLayout()
        self.icon_lbl = QLabel()
        icon_path = BASE_DIR / "assets" / "branding" / "frlg_studio_icon.png"
        pix = QPixmap(str(icon_path))
        if not pix.isNull():
            self.icon_lbl.setPixmap(
                pix.scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            )
        self.icon_lbl.setFixedSize(64, 64)
        header.addWidget(self.icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_lbl = QLabel(APP_NAME.upper())
        self.version_lbl = QLabel(f"Version {APP_VERSION}")
        self.tagline_lbl = QLabel(APP_TAGLINE)
        self.tagline_lbl.setWordWrap(True)
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.version_lbl)
        title_box.addWidget(self.tagline_lbl)
        header.addLayout(title_box, stretch=1)
        root.addLayout(header)

        self.rule = QFrame()
        self.rule.setFixedHeight(3)
        root.addWidget(self.rule)

        self.body_lbl = QLabel(
            "A desktop front end for the FRLG wireless link: trade, storage, "
            "a PKHeX-backed editor and a Wonder Card studio.\n\n"
            "Built on Tornadus11's frlg-ldn-trade, PKHeX, pythonnet, PyQt6, "
            "kinnay's LDN library, the pret/pokefirered decompilation and a "
            "heavily stripped-down pokeldn subset. This is a fan project; "
            "Pokémon and related marks belong to Nintendo, Creatures and "
            "Game Freak."
        )
        self.body_lbl.setWordWrap(True)
        root.addWidget(self.body_lbl)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setMinimumHeight(30)
        root.addWidget(self.status_lbl)

        links = QHBoxLayout()
        links.setSpacing(7)
        self.btn_project = QPushButton("PROJECT PAGE")
        self.btn_project.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PROJECT_URL)))
        self.btn_discord = QPushButton("DISCORD")
        self.btn_discord.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL)))
        links.addWidget(self.btn_project)
        links.addWidget(self.btn_discord)
        links.addStretch()
        root.addLayout(links)

        buttons = QHBoxLayout()
        buttons.setSpacing(7)
        self.btn_update = QPushButton("CHECK FOR UPDATES")
        self.btn_update.clicked.connect(self.check_updates)
        self.btn_data = QPushButton("OPEN DATA FOLDER")
        self.btn_data.clicked.connect(self._open_data_folder)
        self.btn_copy = QPushButton("COPY DIAGNOSTICS")
        self.btn_copy.clicked.connect(self._copy_diagnostics)
        self.btn_close = QPushButton("CLOSE")
        self.btn_close.setProperty("role", "primary")
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_update)
        buttons.addWidget(self.btn_data)
        buttons.addWidget(self.btn_copy)
        buttons.addStretch()
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

        self.apply_theme()

    def apply_theme(self):
        self.title_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 25px; letter-spacing: 4px;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.version_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px; font-weight: bold;"
            % (theme.ORANGE_DARK, theme.FONT_DS)
        )
        self.tagline_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.rule.setStyleSheet("background-color: %s; border: none;" % theme.GOLD)
        self.body_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px;"
            % (theme.INK, theme.FONT_DS)
        )
        self.status_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        for button in (
            self.btn_project, self.btn_discord, self.btn_update,
            self.btn_data, self.btn_copy, self.btn_close,
        ):
            primary = button is self.btn_close
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-bottom: 3px solid %s;"
                " border-radius: 5px; padding: 5px 10px; min-height: 24px;"
                " font-family: '%s'; font-size: 11px; }"
                "QPushButton:hover { background-color: %s; }"
                "QPushButton:disabled { background-color: %s; color: %s;"
                " border-color: %s; }"
                % (
                    theme.GREEN if primary else theme.PANEL_ALT,
                    theme.ON_ACCENT if primary else theme.INK,
                    theme.GREEN_DARK if primary else theme.BORDER,
                    theme.GREEN_DARK if primary else theme.BORDER_SOFT,
                    theme.FONT_GBA,
                    theme.GREEN_DARK if primary else theme.HOVER,
                    theme.DISABLED_BG, theme.DISABLED_FG, theme.DISABLED_BORDER,
                )
            )

    def check_updates(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self.btn_update.setEnabled(False)
        self.btn_update.setText("CHECKING…")
        self.status_lbl.setText("Asking GitHub for the newest published release…")
        self._worker = UpdateWorker(self)
        self._worker.checked.connect(self._on_checked)
        self._worker.start()

    def _on_checked(self, reachable: bool, message: str):
        self.btn_update.setEnabled(True)
        self.btn_update.setText("CHECK FOR UPDATES")
        self.status_lbl.setText(message)
        self.status_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px;"
            % (theme.GREEN_DARK if reachable else theme.ORANGE_DARK, theme.FONT_DS)
        )

    def _open_data_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR)))

    def _copy_diagnostics(self):
        try:
            import readiness
            checks = readiness.collect_checks(self.parent() or self)
            text = readiness.diagnostics_text(self.parent() or self, checks)
        except Exception as exc:
            text = f"{APP_NAME} {APP_VERSION}\nDiagnostics failed: {exc}"
        QApplication.clipboard().setText(text)
        self.btn_copy.setText("COPIED ✓")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(
            1400, lambda: self.btn_copy.setText("COPY DIAGNOSTICS")
        )
