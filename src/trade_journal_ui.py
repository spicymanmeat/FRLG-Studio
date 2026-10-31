"""Trade journal browser."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout,
)

import app_prefs
import theme
import trade_journal


class TradeJournalDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FRLG Studio — Trade Journal")
        self.setMinimumSize(860, 560)
        self.resize(960, 660)
        self.entries: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(7)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_lbl = QLabel("TRADE JOURNAL")
        self.summary_lbl = QLabel("Every completed and failed link attempt.")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.summary_lbl)
        header.addLayout(title_box, stretch=1)
        self.count_lbl = QLabel("")
        header.addWidget(self.count_lbl)
        root.addLayout(header)

        self.rule = QFrame()
        self.rule.setFixedHeight(3)
        root.addWidget(self.rule)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["WHEN", "MODE", "RESULT", "RECEIVED"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._show_detail)
        root.addWidget(self.table, stretch=3)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(180)
        self.detail.setPlaceholderText(
            "Select a trade to see both Pokémon, trainer IDs and saved files."
        )
        root.addWidget(self.detail, stretch=2)

        buttons = QHBoxLayout()
        buttons.setSpacing(7)
        self.btn_refresh = QPushButton("REFRESH")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_markdown = QPushButton("EXPORT MARKDOWN…")
        self.btn_markdown.clicked.connect(lambda: self._export("md"))
        self.btn_json = QPushButton("EXPORT JSON…")
        self.btn_json.clicked.connect(lambda: self._export("json"))
        self.btn_folder = QPushButton("OPEN FOLDER")
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_close = QPushButton("CLOSE")
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_refresh)
        buttons.addWidget(self.btn_markdown)
        buttons.addWidget(self.btn_json)
        buttons.addWidget(self.btn_folder)
        buttons.addStretch()
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

        self.apply_theme()
        self.refresh()

    def apply_theme(self):
        self.setStyleSheet("QDialog { background-color: %s; }" % theme.APP_BG_BOTTOM)
        self.title_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 19px; letter-spacing: 3px;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.summary_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.count_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px; font-weight: bold;"
            % (theme.INK, theme.FONT_DS)
        )
        self.rule.setStyleSheet("background-color: %s; border: none;" % theme.GOLD)
        self.table.setStyleSheet(
            "QTableWidget { background-color: %s; color: %s;"
            " alternate-background-color: %s; gridline-color: %s;"
            " border: 2px solid %s; border-radius: 7px;"
            " font-family: '%s'; font-size: 12px; }"
            "QHeaderView::section { background-color: %s; color: %s;"
            " border: none; border-bottom: 2px solid %s;"
            " padding: 5px; font-family: '%s'; font-size: 11px; }"
            % (theme.PANEL, theme.INK, theme.PANEL_ALT, theme.BORDER_SOFT,
               theme.BORDER_SOFT, theme.FONT_DS, theme.HEADER, theme.ON_HEADER,
               theme.GOLD, theme.FONT_DS)
        )
        self.detail.setStyleSheet(
            "QTextEdit { background-color: %s; color: %s;"
            " border: 2px solid %s; border-radius: 7px; padding: 7px;"
            " font-family: '%s'; font-size: 12px; }"
            % (theme.FIELD, theme.INK, theme.BORDER_SOFT, theme.FONT_GBA)
        )
        for button in (
            self.btn_refresh, self.btn_markdown, self.btn_json,
            self.btn_folder, self.btn_close,
        ):
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-bottom: 3px solid %s;"
                " border-radius: 5px; padding: 5px 11px; min-height: 24px;"
                " font-family: '%s'; font-size: 12px; }"
                "QPushButton:hover { background-color: %s; border-color: %s; }"
                % (theme.PANEL_ALT, theme.INK, theme.BORDER, theme.BORDER_SOFT,
                   theme.FONT_GBA, theme.HOVER, theme.HOVER_BORDER)
            )

    def refresh(self):
        self.entries = trade_journal.load_entries()
        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            received = entry.get("received") or {}
            when = str(entry.get("timestamp", "")).replace("T", " ")[:19]
            mode = str(entry.get("mode", "live")).title()
            if str(entry.get("status", "")) == "running":
                result = "RUNNING"
            else:
                result = "COMPLETE" if entry.get("success") else "FAILED"
            got = (
                f"{received.get('nickname', '—')} Lv.{received.get('level', '?')}"
                if received else "—"
            )
            values = (when, mode, result, got)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row)
                if column == 2:
                    if result == "RUNNING":
                        color = Qt.GlobalColor.darkYellow
                    elif entry.get("success"):
                        color = Qt.GlobalColor.darkGreen
                    else:
                        color = Qt.GlobalColor.darkRed
                    item.setForeground(color)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        self.count_lbl.setText(
            f"{len(self.entries)} ENTR{'Y' if len(self.entries) == 1 else 'IES'}"
        )
        has_entries = bool(self.entries)
        for button in (self.btn_markdown, self.btn_json, self.btn_folder):
            button.setEnabled(has_entries)
        if has_entries and self.table.currentRow() < 0:
            self.table.selectRow(0)
        if not has_entries:
            self.detail.setPlainText(
                "No trades recorded yet.\n\n"
                "Complete or attempt a live trade, or run a rehearsal, and it "
                "will appear here with both Pokémon and the session log."
            )

    def _entry(self) -> dict | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None

    def _show_detail(self):
        entry = self._entry()
        if entry is None:
            return
        sent = entry.get("traded") or {}
        got = entry.get("received") or {}
        files = entry.get("files") or {}

        def mon_block(label: str, mon: dict, file_key: str) -> list[str]:
            if not mon:
                return [f"{label}: —"]
            sats = "/".join(str(value) for value in (mon.get("ivs") or []))
            return [
                f"{label}: {mon.get('nickname', '—')} · "
                f"{mon.get('species_name', '')} Lv.{mon.get('level', '?')}"
                f"{' ★' if mon.get('shiny') else ''}",
                f"   OT {mon.get('ot', '—')} · TID {mon.get('tid', '?')} / "
                f"SID {mon.get('sid', '?')} · IVs {sats or '—'}",
                f"   Saved as {files.get(file_key) or mon.get('file', '—')}",
            ]

        status = str(entry.get("status", ""))
        result = "RUNNING" if status == "running" else (
            "COMPLETE" if entry.get("success") else "FAILED"
        )
        lines = [
            f"{entry.get('timestamp', '—')}  ·  {str(entry.get('mode', '—')).title()}"
            f"  ·  {result}",
            f"Game version: {entry.get('game', '—')}",
            f"Journal folder: journal/{entry.get('id', '')}",
            "",
        ]
        lines.extend(mon_block("Sent", sent, "traded"))
        lines.append("")
        lines.extend(mon_block("Received", got, "received"))
        log_name = files.get("log")
        if log_name:
            lines.extend(["", f"Session log: journal/{entry.get('id')}/{log_name}"])
        self.detail.setPlainText("\n".join(lines))

    def _export(self, kind: str) -> None:
        if not self.entries:
            return
        export_dir = Path(str(app_prefs.get("journal_export_dir", "")))
        if not export_dir.is_dir():
            export_dir = Path.home()
        suffix = "md" if kind == "md" else "json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export trade journal",
            str(export_dir / f"frlg-trade-journal.{suffix}"),
            "Markdown (*.md)" if kind == "md" else "JSON (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        if not path.lower().endswith(f".{suffix}"):
            path += f".{suffix}"
        target = Path(path)
        try:
            if kind == "md":
                target.write_text(
                    trade_journal.export_markdown(self.entries), encoding="utf-8"
                )
            else:
                target.write_text(
                    trade_journal.export_json(self.entries), encoding="utf-8"
                )
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        app_prefs.update(journal_export_dir=str(target.parent))
        QMessageBox.information(self, "Journal exported", str(target))

    def _open_folder(self) -> None:
        entry = self._entry()
        folder = (
            trade_journal.JOURNAL_DIR / str(entry.get("id"))
            if entry is not None else trade_journal.JOURNAL_DIR
        )
        if not folder.is_dir():
            folder = trade_journal.JOURNAL_DIR
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
