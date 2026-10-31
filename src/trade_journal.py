"""Persistent record of every trade attempt.

The link log is useful while the app is open and gone when it closes.  This
module writes one folder per attempt under ``journal/`` with both Pokémon
copied byte-for-byte, a JSON record and the session log, plus an append-only
index for the browser.  Nothing here is required for trading; a journal error
must never stop a trade.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import paths
from utils import parse_pk3_file

JOURNAL_DIR = paths.JOURNAL_DIR
INDEX_PATH = JOURNAL_DIR / "index.jsonl"

_SPECIES: dict[int, str] = {}
try:
    _SPECIES = {
        int(key): str(value)
        for key, value in json.loads(
            (paths.ASSETS_DIR / "data" / "species.json").read_text(
                encoding="utf-8"
            )
        ).items()
    }
except (OSError, ValueError, json.JSONDecodeError):
    _SPECIES = {}


def _summarise(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        return {"file": p.name, "missing": True}
    info = parse_pk3_file(str(p)) or {}
    dex = int(info.get("nat_dex") or 0)
    return {
        "file": p.name,
        "nickname": info.get("nickname") or "PKMN",
        "species": dex,
        "species_name": _SPECIES.get(dex, f"#{dex}"),
        "level": int(info.get("level") or 0),
        "shiny": bool(info.get("is_shiny")),
        "ot": info.get("ot_name") or "",
        "tid": int(info.get("tid") or 0),
        "sid": int(info.get("sid") or 0),
        "ivs": list(info.get("ivs") or ()),
    }


def _copy(source: str | Path | None, folder: Path, prefix: str) -> str:
    if not source:
        return ""
    src = Path(source)
    if not src.is_file():
        return ""
    name = f"{prefix}-{src.name}"
    try:
        shutil.copy2(src, folder / name)
    except OSError:
        return ""
    return name


class TradeSession:
    """A journal entry that exists before the trade finishes."""

    def __init__(self, mode: str, game: str, traded_path: str, dummy_path: str):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.entry_id = f"{stamp}-{uuid.uuid4().hex[:4]}"
        self.folder = JOURNAL_DIR / self.entry_id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.mode = str(mode)
        self.game = str(game)
        self.traded = _summarise(traded_path)
        self.dummy = _summarise(dummy_path)
        self.traded_copy = _copy(traded_path, self.folder, "traded")
        self.dummy_copy = _copy(dummy_path, self.folder, "dummy")
        self.received: dict = {}
        self.received_copy = ""
        self.finished = False
        self.entry = {
            "id": self.entry_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "mode": self.mode,
            "game": self.game,
            "status": "running",
            "success": False,
            "traded": self.traded,
            "dummy": self.dummy,
            "received": {},
            "files": {
                "traded": self.traded_copy,
                "dummy": self.dummy_copy,
                "received": "",
                "log": "",
            },
        }
        self._write_entry()

    def _write_entry(self) -> None:
        try:
            (self.folder / "entry.json").write_text(
                json.dumps(self.entry, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def finish(self, received_path: str | None, success: bool, log_text: str) -> dict:
        if self.finished:
            return self.entry
        self.finished = True
        self.received = _summarise(received_path)
        self.received_copy = _copy(received_path, self.folder, "received")
        try:
            (self.folder / "session.log").write_text(
                (log_text or "")[:200_000], encoding="utf-8"
            )
            log_name = "session.log"
        except OSError:
            log_name = ""
        self.entry.update(
            {
                "finished": datetime.now().isoformat(timespec="seconds"),
                "status": "complete" if success else "failed",
                "success": bool(success),
                "received": self.received,
                "files": {
                    "traded": self.traded_copy,
                    "dummy": self.dummy_copy,
                    "received": self.received_copy,
                    "log": log_name,
                },
            }
        )
        self._write_entry()
        try:
            JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
            with INDEX_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(self.entry) + "\n")
        except OSError:
            pass
        return self.entry


def load_entries() -> list[dict]:
    """Load the index newest-first, falling back to scanning folders."""
    entries: list[dict] = []
    if INDEX_PATH.is_file():
        try:
            for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict) and value.get("id"):
                    entries.append(value)
        except OSError:
            pass
    # Always merge the per-entry folders, not just when the index is missing.
    # A trade that is interrupted before finish() never reaches index.jsonl;
    # its running entry should still appear in the journal instead of being
    # invisible until the next successful trade rewrites the index.
    unique: dict[str, dict] = {}
    for entry in entries:
        unique[str(entry.get("id"))] = entry
    if JOURNAL_DIR.is_dir():
        for entry_file in JOURNAL_DIR.glob("*/entry.json"):
            try:
                value = json.loads(entry_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict) or not value.get("id"):
                continue
            unique.setdefault(str(value["id"]), value)
    return sorted(
        unique.values(), key=lambda item: str(item.get("timestamp", "")), reverse=True
    )


def export_markdown(entries: list[dict]) -> str:
    lines = [
        "# FRLG Studio — Trade Journal",
        "",
        f"Exported: {datetime.now().isoformat(timespec='seconds')}",
        f"Trades: {len(entries)}",
        "",
        "| When | Mode | Result | Sent | Received |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        sent = entry.get("traded") or {}
        got = entry.get("received") or {}
        sent_label = (
            f"{sent.get('nickname', '—')} (Lv.{sent.get('level', '?')})"
            if sent else "—"
        )
        got_label = (
            f"{got.get('nickname', '—')} (Lv.{got.get('level', '?')})"
            if got else "—"
        )
        result = "Complete" if entry.get("success") else "Failed"
        lines.append(
            f"| {entry.get('timestamp', '—')} | {str(entry.get('mode', '—')).title()} | "
            f"{result} | {sent_label} | {got_label} |"
        )
    lines.append("")
    for entry in entries:
        sent = entry.get("traded") or {}
        got = entry.get("received") or {}
        lines.extend(
            [
                f"## {entry.get('timestamp', entry.get('id', 'Trade'))}",
                "",
                f"- Mode: {str(entry.get('mode', '—')).title()}",
                f"- Result: {'complete' if entry.get('success') else 'failed'}",
                f"- Game: {entry.get('game', '—')}",
                f"- Sent: {sent.get('nickname', '—')} · "
                f"{sent.get('species_name', '')} Lv.{sent.get('level', '?')} · "
                f"OT {sent.get('ot', '—')} ({sent.get('tid', '?')}/{sent.get('sid', '?')})",
                f"- Received: {got.get('nickname', '—')} · "
                f"{got.get('species_name', '')} Lv.{got.get('level', '?')} · "
                f"OT {got.get('ot', '—')} ({got.get('tid', '?')}/{got.get('sid', '?')})",
                f"- Entry: `journal/{entry.get('id', '')}`",
                "",
            ]
        )
    return "\n".join(lines)


def export_json(entries: list[dict]) -> str:
    return json.dumps(entries, indent=2)

