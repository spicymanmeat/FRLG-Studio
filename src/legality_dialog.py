"""Legality audit window for Bill's PC."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout,
)

import app_prefs
import legality_audit
import theme
import user_data


class LegalityAuditDialog(QDialog):
    data_changed = pyqtSignal(object)

    def __init__(self, parent, box_name: str, items: list[tuple[int, str]], pc_tab=None):
        super().__init__(parent)
        self.setWindowTitle(f"FRLG Studio — Legality Audit — {box_name}")
        self.box_name = box_name
        self.items = list(items)
        self.pc_tab = pc_tab
        self.findings: list[legality_audit.Finding] = []
        self.setMinimumSize(820, 560)
        self.resize(920, 650)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(7)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_lbl = QLabel(f"LEGALITY AUDIT — {box_name.upper()}")
        self.summary_lbl = QLabel("Checking every record with PKHeX…")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.summary_lbl)
        header.addLayout(title_box, stretch=1)
        self.state_lbl = QLabel("")
        header.addWidget(self.state_lbl)
        root.addLayout(header)

        self.rule = QFrame()
        self.rule.setFixedHeight(3)
        root.addWidget(self.rule)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["STATUS", "POKéMON", "LV.", "PKHEX FINDINGS"])
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
        self.detail.setPlaceholderText(
            "Select a record to see PKHeX's complete finding list."
        )
        self.detail.setMaximumHeight(110)
        root.addWidget(self.detail, stretch=1)

        buttons = QHBoxLayout()
        buttons.setSpacing(7)
        self.btn_reaudit = QPushButton("RE-AUDIT")
        self.btn_reaudit.clicked.connect(self.run_audit)
        self.btn_legalize = QPushButton("LEGALIZE ILLEGAL")
        self.btn_legalize.setProperty("role", "primary")
        self.btn_legalize.clicked.connect(self.legalize_illegal)
        self.btn_legalize.setEnabled(False)
        self.btn_export = QPushButton("EXPORT REPORT…")
        self.btn_export.clicked.connect(self.export_report)
        self.btn_close = QPushButton("CLOSE")
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_reaudit)
        buttons.addWidget(self.btn_export)
        buttons.addStretch()
        buttons.addWidget(self.btn_legalize)
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(
            "QDialog { background-color: %s; }" % theme.APP_BG_BOTTOM
        )
        self.title_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 18px; letter-spacing: 2px;"
            % (theme.NAVY_DARK, theme.FONT_GBA)
        )
        self.summary_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px;"
            % (theme.INK_SOFT, theme.FONT_DS)
        )
        self.state_lbl.setStyleSheet(
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
            " border: 2px solid %s; border-radius: 7px; padding: 6px;"
            " font-family: '%s'; font-size: 12px; }"
            % (theme.FIELD, theme.INK, theme.BORDER_SOFT, theme.FONT_GBA)
        )
        for button in (
            self.btn_reaudit, self.btn_export, self.btn_legalize, self.btn_close
        ):
            is_primary = button is self.btn_legalize
            is_close = button is self.btn_close
            bg = theme.GREEN if is_primary else (
                theme.PANEL_ALT if not is_close else theme.PANEL
            )
            fg = theme.ON_ACCENT if is_primary else theme.INK
            border = theme.GREEN_DARK if is_primary else theme.BORDER
            hover = theme.GREEN_DARK if is_primary else theme.HOVER
            button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s;"
                " border: 2px solid %s; border-bottom: 3px solid %s;"
                " border-radius: 5px; padding: 5px 12px; min-height: 24px;"
                " font-family: '%s'; font-size: 12px; }"
                "QPushButton:hover { background-color: %s; }"
                "QPushButton:disabled { background-color: %s; color: %s;"
                " border-color: %s; }"
                % (bg, fg, border, border, theme.FONT_GBA, hover,
                   theme.DISABLED_BG, theme.DISABLED_FG, theme.DISABLED_BORDER)
            )

    def run_audit(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            self.findings = legality_audit.audit_paths(self.items)
        finally:
            QApplication.restoreOverrideCursor()
        self._fill_table()
        self.data_changed.emit(self.findings)

    def _fill_table(self):
        self.table.setRowCount(len(self.findings))
        for row, finding in enumerate(self.findings):
            status = QTableWidgetItem("LEGAL" if finding.valid else "ILLEGAL")
            status.setForeground(
                Qt.GlobalColor.darkGreen if finding.valid else Qt.GlobalColor.darkRed
            )
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name = QTableWidgetItem(
                f"{finding.nickname}{' ★' if finding.shiny else ''}"
            )
            level = QTableWidgetItem(str(finding.level))
            level.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            detail = QTableWidgetItem(
                "—" if finding.valid else "; ".join(finding.messages) or "Illegal"
            )
            if not finding.valid:
                detail.setForeground(Qt.GlobalColor.darkRed)
            for column, item in enumerate((status, name, level, detail)):
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.table.setItem(row, column, item)
        legal = sum(1 for finding in self.findings if finding.valid)
        illegal = len(self.findings) - legal
        self.summary_lbl.setText(
            f"{len(self.findings)} records · {legal} legal · {illegal} illegal"
        )
        self.state_lbl.setText(
            "ALL LEGAL" if illegal == 0 else f"{illegal} NEED ATTENTION"
        )
        self.state_lbl.setStyleSheet(
            "color: %s; font-family: '%s'; font-size: 12px; font-weight: bold;"
            % (theme.GREEN_DARK if illegal == 0 else theme.RED_DARK, theme.FONT_DS)
        )
        self.btn_legalize.setEnabled(illegal > 0)
        if self.findings and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def _show_detail(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.findings):
            self.detail.clear()
            return
        finding = self.findings[row]
        lines = [
            finding.path,
            "",
            "Legal" if finding.valid else "Illegal",
        ]
        if finding.messages:
            lines.append("")
            lines.extend(f"• {message}" for message in finding.messages)
        if finding.changes:
            lines.extend(["", "Last repair:"])
            lines.extend(f"• {change}" for change in finding.changes)
        self.detail.setPlainText("\n".join(lines))

    def legalize_illegal(self):
        invalid = [finding for finding in self.findings if not finding.valid]
        if not invalid:
            return
        reply = QMessageBox.question(
            self,
            "Legalize Box",
            f"Ask PKHeX to repair {len(invalid)} illegal record"
            f"{'s' if len(invalid) != 1 else ''}?\n\n"
            "Legal records are left untouched. The whole user-data folder is "
            "snapshotted first, so this can be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        user_data.snapshot(f"Legalize {self.box_name}")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        repaired = 0
        failed = 0
        try:
            for finding in invalid:
                result = legality_audit.legalize_file(finding.path)
                if result.valid:
                    repaired += 1
                else:
                    failed += 1
                QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()

        self.findings = [
            legality_audit.audit_file(finding.path, finding.slot)
            for finding in self.findings
        ]
        self._fill_table()
        self.data_changed.emit(self.findings)
        QMessageBox.information(
            self,
            "Legalize Box",
            f"Repaired {repaired} record{'s' if repaired != 1 else ''}."
            + (f"\n{failed} could not be repaired; their findings are shown." if failed else ""),
        )

    def export_report(self):
        export_dir = Path(str(app_prefs.get("journal_export_dir", "")))
        if not export_dir.is_dir():
            export_dir = Path.home()
        safe_name = self.box_name.lower().replace(" ", "-")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export legality report",
            str(export_dir / f"{safe_name}-legality.md"),
            "Markdown (*.md);;JSON (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        if not path.lower().endswith((".md", ".json")):
            path += ".md"
        target = Path(path)
        try:
            if target.suffix.lower() == ".json":
                import json
                target.write_text(
                    json.dumps(
                        [
                            {
                                "path": finding.path,
                                "slot": finding.slot + 1 if finding.slot >= 0 else None,
                                "nickname": finding.nickname,
                                "species": finding.species,
                                "level": finding.level,
                                "shiny": finding.shiny,
                                "legal": finding.valid,
                                "messages": list(finding.messages),
                            }
                            for finding in self.findings
                        ],
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            else:
                target.write_text(
                    legality_audit.report_markdown(self.box_name, self.findings),
                    encoding="utf-8",
                )
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        app_prefs.update(journal_export_dir=str(target.parent))
        QMessageBox.information(self, "Report saved", str(target))
