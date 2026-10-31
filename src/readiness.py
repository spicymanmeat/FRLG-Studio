"""First-run setup check.

The app needs a few things that a fresh checkout cannot discover by itself:
Switch keys, a wireless phy, a working adapter/driver, PKHeX, and two staged
Pokémon.  This dialog turns those into one checklist with one-click fixes and
a diagnostics block that can be pasted into Discord.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import app_prefs
import paths
import theme
from utils import BASE_DIR, acquire_admin, detect_wiphy

KNOWN_WEAK_DRIVERS = {
    "iwlwifi": "Intel AX200-class cards usually cannot be assigned an IP.",
    "ath9k_htc": "Atheros AR9271-class cards often fail to be assigned an IP.",
}


@dataclass
class Check:
    key: str
    title: str
    detail: str
    ok: bool
    fix_label: str = ""
    fix: Callable[[], None] | None = None
    blocking: bool = True


def _phy_names() -> list[str]:
    root = Path("/sys/class/ieee80211")
    try:
        return sorted(item.name for item in root.iterdir())
    except OSError:
        return []


def _driver_name(phy: str) -> str:
    link = Path("/sys/class/ieee80211") / phy / "device" / "driver"
    try:
        return link.resolve().name
    except OSError:
        return ""


def _network_manager_active() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "NetworkManager"],
            capture_output=True, text=True, timeout=4,
        )
        return result.stdout.strip() == "active"
    except (OSError, subprocess.SubprocessError):
        return False


def _has_cached_admin() -> bool:
    if os.geteuid() == 0:
        return True
    try:
        return subprocess.run(
            ["sudo", "-n", "true"], capture_output=True, timeout=4
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_keys_path(current: str | Path | None = None) -> Path | None:
    candidates = []
    if current:
        candidates.append(Path(current).expanduser())
    candidates.extend([
        paths.DATA_DIR / "prod.keys",
        paths.CONFIG_DIR / "prod.keys",
        Path.home() / ".switch" / "prod.keys",
    ])
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size > 64:
                return candidate
        except OSError:
            continue
    return None


def collect_checks(win) -> list[Check]:
    checks: list[Check] = []

    keys = find_keys_path(getattr(win, "keys_path", ""))
    if keys is not None and hasattr(win, "keys_path"):
        if str(win.keys_path) != str(keys):
            win.keys_path = keys
            if hasattr(win, "update_keys_badge"):
                win.update_keys_badge()
    checks.append(Check(
        "keys",
        "Switch keys",
        (f"Using {keys}" if keys else
         "Place prod.keys in the data folder, or use the CLI default ~/.switch/prod.keys."),
        keys is not None,
        "FIND KEYS",
        getattr(win, "browse_keys_file", None),
    ))

    phys = _phy_names()
    phy = detect_wiphy(bring_up=False) if phys else "phy0"
    driver = _driver_name(phy) if phys else ""
    checks.append(Check(
        "phy",
        "Wireless interface",
        (f"{phy} found" + (f" · driver {driver}" if driver else "")
         if phys else "No /sys/class/ieee80211 interface is visible."),
        bool(phys),
        "ATTACH",
        getattr(win, "enable_trade_wifi", None),
    ))

    weak = driver in KNOWN_WEAK_DRIVERS
    checks.append(Check(
        "driver",
        "Adapter driver",
        (f"{driver}: {KNOWN_WEAK_DRIVERS[driver]}" if weak else
         (f"{driver} is loaded." if driver else
          "Driver name unavailable. The app will still try the selected phy.")),
        not weak,
        "" if weak else "OK",
        None,
        blocking=False,
    ))

    nm_active = _network_manager_active()
    checks.append(Check(
        "network",
        "NetworkManager",
        ("Normal Wi-Fi is up. Starting a live trade will detach it temporarily."
         if nm_active else
         "NetworkManager is stopped. Normal Wi-Fi is currently detached."),
        True,
        "",
        None,
        blocking=False,
    ))

    admin = _has_cached_admin()
    checks.append(Check(
        "admin",
        "Admin access",
        ("A cached sudo ticket is available." if admin else
         "A password will be requested when attaching the adapter or starting a live trade."),
        admin,
        "UNLOCK",
        acquire_admin if not admin else None,
        blocking=False,
    ))

    dll = BASE_DIR / "src" / "PKHeX.Core.dll"
    pkhex_loaded = "PKHeX.Core" in sys.modules
    dotnet = ""
    try:
        if "System" in sys.modules:
            import System  # noqa: F401
            dotnet = str(System.Environment.Version)
    except Exception:
        dotnet = ""
    checks.append(Check(
        "pkhex",
        "PKHeX / .NET",
        (f"PKHeX.Core.dll loaded" + (f" · .NET {dotnet}" if dotnet else "")
         if dll.exists() and pkhex_loaded else
         f"Missing or not loaded: {dll}"),
        dll.exists() and pkhex_loaded,
        "",
        None,
    ))

    dummy = Path(str(getattr(getattr(win, "dummy_badge", None), "filepath", "")))
    checks.append(Check(
        "slot1",
        "Slot 1 lead",
        (f"{dummy.name} is staged." if dummy.is_file() else
         "No lead Pokémon is staged in slot1/. This is the Pokémon the Switch sees first."),
        dummy.is_file(),
        "CHOOSE .PK3",
        getattr(getattr(win, "dummy_badge", None), "swap_dummy", None),
    ))

    slot2 = Path(str(getattr(win, "slot2_path", "")))
    checks.append(Check(
        "slot2",
        "Trade offer",
        (f"{slot2.name} is ready to offer." if slot2.is_file() else
         "Send a Pokémon from Bill's PC to Trade Slot 2 before starting a trade."),
        slot2.is_file(),
        "OPEN BILL'S PC",
        (lambda: getattr(win, "_open_tab", lambda _index: None)(1)) if hasattr(win, "_open_tab") else None,
    ))

    try:
        pc_count = sum(1 for _ in paths.PC_DIR.rglob("*.pk3"))
    except OSError:
        pc_count = 0
    checks.append(Check(
        "storage",
        "Bill's PC",
        f"{pc_count} Pokémon stored in PCstorage/.",
        True,
        "",
        None,
        blocking=False,
    ))

    capture = Path(str(app_prefs.get("rehearsal_capture", "")))
    checks.append(Check(
        "capture",
        "Rehearsal capture",
        (f"{capture.name} is available for offline practice." if capture.is_file() else
         "No capture yet. Record one during a live attempt, or select a .jsonl capture."),
        capture.is_file(),
        "",
        None,
        blocking=False,
    ))

    writable = os.access(paths.DATA_DIR, os.W_OK) and os.access(paths.PC_DIR, os.W_OK)
    checks.append(Check(
        "writable",
        "Data folder",
        (f"{paths.DATA_DIR} is writable." if writable else
         "The app cannot write to its data folder. Check ownership/permissions."),
        writable,
        "OPEN FOLDER",
        _open_data_folder,
    ))

    return checks


def _open_data_folder() -> None:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.DATA_DIR)))


def summarize(checks: list[Check]) -> tuple[bool, str]:
    blocking = [check for check in checks if check.blocking]
    failed = [check for check in blocking if not check.ok]
    if not failed:
        return True, "LIVE TRADE READY"
    if len(failed) == 1:
        return False, f"1 ITEM NEEDS ATTENTION"
    return False, f"{len(failed)} ITEMS NEED ATTENTION"


def diagnostics_text(win, checks: list[Check]) -> str:
    from version import APP_NAME, APP_VERSION
    try:
        import PyQt6.QtCore as QtCore
        qt_version = QtCore.QT_VERSION_STR
    except Exception:
        qt_version = "?"
    lines = [
        f"{APP_NAME} {APP_VERSION} diagnostics",
        f"Time: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}",
        f"Platform: {platform.platform()}",
        f"Python: {sys.version.split()[0]} · Qt {qt_version}",
        f"Theme: {theme.THEME_ID} · UI scale: {theme.active_scale():.2f}",
        f"Program: {BASE_DIR}",
        f"Data: {paths.DATA_DIR}",
        "",
    ]
    for check in checks:
        lines.append(
            f"[{'OK' if check.ok else '!!'}] {check.title}: {check.detail}"
        )
    return "\n".join(lines)


class ReadinessDialog(QDialog):
    """Non-modal checklist so the rest of the app stays usable."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("FRLG Studio — Setup Check")
        self.setModal(False)
        self.setMinimumSize(720, 560)
        self.resize(820, 680)
        self._checks: list[Check] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_lbl = QLabel("SETUP CHECK")
        self.subtitle_lbl = QLabel(
            "Everything the app needs for a live trade, in one place."
        )
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.subtitle_lbl)
        header.addLayout(title_box, stretch=1)
        self.state_lbl = QLabel("CHECKING…")
        header.addWidget(self.state_lbl)
        root.addLayout(header)

        self.rule = QFrame()
        self.rule.setFixedHeight(3)
        root.addWidget(self.rule)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rows_host = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 2, 4, 2)
        self.rows_layout.setSpacing(6)
        self.rows_layout.addStretch()
        self.scroll.setWidget(self.rows_host)
        root.addWidget(self.scroll, stretch=1)

        buttons = QHBoxLayout()
        buttons.setSpacing(7)
        self.btn_recheck = QPushButton("RE-CHECK")
        self.btn_recheck.clicked.connect(self.rebuild)
        self.btn_copy = QPushButton("COPY DIAGNOSTICS")
        self.btn_copy.clicked.connect(self.copy_diagnostics)
        self.btn_close = QPushButton("CLOSE")
        self.btn_close.setProperty("role", "primary")
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_recheck)
        buttons.addWidget(self.btn_copy)
        buttons.addStretch()
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

        self.apply_theme()
        self.rebuild()

    # -- theme -------------------------------------------------------------
    def apply_theme(self):
        self.setStyleSheet(
            "QDialog { background-color: %s; }" % theme.APP_BG_BOTTOM
        )
        self.title_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 20px; letter-spacing: 3px;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.subtitle_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.state_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px; font-weight: bold;"
            % (theme.INK, theme.FONT_DS)
        )
        self.rule.setStyleSheet(
            "background-color: %s; border: none;" % theme.GOLD
        )
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QWidget#readinessRows { background: transparent; }"
        )
        self.rows_host.setObjectName("readinessRows")
        for button in (self.btn_recheck, self.btn_copy, self.btn_close):
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-bottom: 3px solid %s;"
                " border-radius: 6px; padding: 5px 12px; min-height: 24px;"
                " font-family: '%s'; font-size: 12px; }"
                "QPushButton:hover { background-color: %s; border-color: %s; }"
                % (
                    theme.PANEL_ALT if button is not self.btn_close else theme.GREEN,
                    theme.INK if button is not self.btn_close else theme.ON_ACCENT,
                    theme.BORDER if button is not self.btn_close else theme.GREEN_DARK,
                    theme.BORDER_SOFT if button is not self.btn_close else theme.GREEN_DARK,
                    theme.FONT_GBA,
                    theme.HOVER if button is not self.btn_close else theme.GREEN_DARK,
                    theme.HOVER_BORDER if button is not self.btn_close else theme.GREEN_DARK,
                )
            )

    # -- rows --------------------------------------------------------------
    def _clear_rows(self):
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def rebuild(self):
        self._checks = collect_checks(self.win)
        self._clear_rows()
        for check in self._checks:
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, self._row(check))
        ok, summary = summarize(self._checks)
        self.state_lbl.setText(summary)
        self.state_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px; font-weight: bold;"
            % (theme.GREEN_DARK if ok else theme.ORANGE_DARK, theme.FONT_DS)
        )

    def _row(self, check: Check) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ReadinessRow")
        frame.setStyleSheet(
            "#ReadinessRow { background-color: %s; border: 2px solid %s;"
            " border-radius: 8px; }"
            % (theme.PANEL, theme.BORDER_SOFT if check.ok else theme.RED)
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 7, 9, 7)
        layout.setSpacing(9)

        mark = QLabel("✓" if check.ok else "!")
        mark.setFixedSize(24, 24)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet(
            "background-color: %s; color: %s; border-radius: 12px;"
            " font-family: '%s'; font-size: 14px; font-weight: bold;"
            % (
                theme.GREEN if check.ok else theme.RED,
                theme.ON_ACCENT if check.ok else theme.PANEL,
                theme.FONT_GBA,
            )
        )
        layout.addWidget(mark)

        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        title = QLabel(check.title)
        title.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 13px; font-weight: bold;"
            " border: none; background: transparent;"
            % (theme.INK, theme.FONT_DS)
        )
        detail = QLabel(check.detail)
        detail.setWordWrap(True)
        detail.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 11px;"
            " border: none; background: transparent;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        text_box.addWidget(title)
        text_box.addWidget(detail)
        layout.addLayout(text_box, stretch=1)

        if check.fix is not None and check.fix_label:
            button = QPushButton(check.fix_label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-radius: 5px;"
                " padding: 3px 9px; min-height: 22px;"
                " font-family: '%s'; font-size: 11px; }"
                "QPushButton:hover { background-color: %s; }"
                % (theme.PANEL_ALT, theme.ORANGE_DARK, theme.ORANGE,
                   theme.FONT_GBA, theme.HOVER)
            )
            button.clicked.connect(lambda _checked=False, c=check: self._run_fix(c))
            layout.addWidget(button)

        return frame

    def _run_fix(self, check: Check):
        if check.fix is None:
            return
        try:
            check.fix()
        except Exception as exc:
            check.detail = f"Fix failed: {exc}"
            check.ok = False
        QTimer.singleShot(350, self.rebuild)

    def copy_diagnostics(self):
        text = diagnostics_text(self.win, self._checks)
        QApplication.clipboard().setText(text)
        self.btn_copy.setText("COPIED ✓")
        QTimer.singleShot(1400, lambda: self.btn_copy.setText("COPY DIAGNOSTICS"))

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen()
        parent = self.parentWidget()
        if screen is not None and parent is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
        self.raise_()
        self.activateWindow()


def open_readiness(win) -> ReadinessDialog:
    dialog = ReadinessDialog(win)
    win._readiness_dialog = dialog
    dialog.show()
    return dialog
