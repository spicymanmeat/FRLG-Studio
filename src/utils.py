import getpass
import os
import shutil
import struct
import subprocess
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QApplication, QMessageBox

import paths
from core_data import NATURES, STAT_MOD_NAMES, SUBSTRUCT_ORDER, HOENN_INTERNAL_TO_NAT, get_item_info
from pkmds_editor import GEN3_EN_TABLE, calc_gen3_party_stats, infer_level_and_rate
from sprite_paths import animated_sprite_path, icon_path, unown_form_from_pid

BASE_DIR = paths.APP_DIR
DATA_DIR = paths.DATA_DIR
SLOT1_DIR = paths.SLOT1_DIR
RECEIVED_DIR = paths.RECEIVED_DIR

# The AppImage is mounted from a root-owned squashfs, so the old
# ``BASE_DIR.owner()`` fallback would return ``root``.  Use the actual login
# name instead; sudo's SUDO_USER still wins when present.
USER_NAME = (
    os.environ.get("SUDO_USER")
    or getpass.getuser()
)

# ---------------------------------------------------------------------------
# SUDO KEEPALIVE & SECURE ASKPASS AUTHENTICATION
# ---------------------------------------------------------------------------
class SudoKeepAlive(QThread):
    def run(self):
        while True:
            # Sleep for 60 seconds (broken into 1s chunks to allow clean exits)
            for _ in range(60):
                time.sleep(1)
                if self.isInterruptionRequested():
                    return

            # Non-interactive background check to keep the sudo timestamp alive.
            # If the timestamp has expired, this will gracefully fail (returncode != 0)
            # instead of asking for a password or hammering faillock.
            res = subprocess.run(["sudo", "-v", "-n"], capture_output=True)
            if res.returncode != 0:
                # TRIPWIRE TRIGGERED: Ticket expired. Kill the background loop so
                # we don't trigger the Arch/CachyOS faillock security measure.
                return

_sudo_keepalive_worker: SudoKeepAlive | None = None

def acquire_admin() -> bool:
    """
    Prompts for the user's password and utilizes the official sudo ASKPASS (-A)
    mechanism. This securely caches the ticket for the current user without
    triggering standard-input piping bugs or pkexec root-context mismatches.
    """
    global _sudo_keepalive_worker

    def start_keepalive():
        global _sudo_keepalive_worker
        if _sudo_keepalive_worker is None or not _sudo_keepalive_worker.isRunning():
            _sudo_keepalive_worker = SudoKeepAlive()
            _sudo_keepalive_worker.start()

    if os.geteuid() == 0:
        return True

    # If the user already has a valid cached sudo ticket, just start the loop
    if subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0:
        start_keepalive()
        return True

    app = QApplication.instance()
    parent = app.activeWindow() if app else None

    pwd, ok = QInputDialog.getText(parent, "Admin Required", "Enter your Linux password to unlock Wi-Fi:", QLineEdit.EchoMode.Password)
    if not ok or not pwd:
        return False

    # Create a temporary secure executable script to pass the password to sudo
    askpass_path = Path("/tmp/frlg_askpass.sh")

    # Safely escape single quotes just in case they exist in the password
    safe_pwd = pwd.replace("'", "'\\''")
    askpass_path.write_text(f"#!/bin/bash\necho '{safe_pwd}'\n")
    askpass_path.chmod(0o700)

    env = os.environ.copy()
    env["SUDO_ASKPASS"] = str(askpass_path)

    # Run sudo -A to securely absorb the password from the script and validate (-v)
    res = subprocess.run(["sudo", "-A", "-v"], env=env, capture_output=True)

    # Immediately wipe the temporary password script
    askpass_path.unlink(missing_ok=True)

    if res.returncode == 0:
        start_keepalive()
        return True

    QMessageBox.critical(parent, "Authentication Failed", "Incorrect password. Sudo authorization failed.")
    return False

def decode_gen3_text(raw: bytes) -> str:
    out = []
    for b in raw:
        if b == 0xFF:
            break
        ch = GEN3_EN_TABLE[b] if 0 <= b < 256 else None
        if ch is not None:
            out.append(ch)
    return "".join(out).strip() or "PKMN"

def parse_pk3_file(filepath: str) -> dict | None:
    if not str(filepath or "").strip():
        return None
    p = Path(filepath)
    if not p.is_file() or p.stat().st_size < 80:
        return None
    data = p.read_bytes()
    pid, otid = struct.unpack("<II", data[0:8])
    tid = otid & 0xFFFF
    sid = (otid >> 16) & 0xFFFF
    is_shiny = ((tid ^ sid ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8)
    nat_idx = pid % 25
    nature = NATURES[nat_idx]
    inc, dec_s = nat_idx // 5, nat_idx % 5
    nature_full = f"{nature} (+{STAT_MOD_NAMES[inc]} / -{STAT_MOD_NAMES[dec_s]})" if inc != dec_s else f"{nature} (Neutral)"

    nickname = decode_gen3_text(data[0x08:0x12])
    ot_name = decode_gen3_text(data[0x14:0x1B])
    checksum = struct.unpack("<H", data[0x1C:0x1E])[0]

    sub_raw = data[0x20:0x50]
    raw_sum = sum(struct.unpack("<24H", sub_raw)) & 0xFFFF
    g_idx, a_idx, e_idx, m_idx = SUBSTRUCT_ORDER[pid % 24]

    if raw_sum == checksum:
        dec = sub_raw
        sp0, it0, _ = struct.unpack("<HHI", dec[0:8])
        orig3 = struct.unpack("<H", dec[36 + 2 : 36 + 4])[0]
        unshuf_ok = (1 <= sp0 <= 411) and (it0 <= 376) and (1 <= ((orig3 >> 11) & 0xF) <= 12)
        if unshuf_ok:
            g_offset, e_offset, m_offset = 0, 24, 36
        else:
            g_offset, e_offset, m_offset = g_idx * 12, e_idx * 12, m_idx * 12
    else:
        key = pid ^ otid
        words = struct.unpack("<12I", sub_raw)
        dec = b"".join(struct.pack("<I", w ^ key) for w in words)
        g_offset, e_offset, m_offset = g_idx * 12, e_idx * 12, m_idx * 12

    internal_sp, item_id, exp = struct.unpack("<HHI", dec[g_offset:g_offset + 8])
    nat_dex = internal_sp if 1 <= internal_sp <= 251 else HOENN_INTERNAL_TO_NAT.get(internal_sp, 1)
    item_name, item_slug = get_item_info(item_id)

    ev_hp, ev_atk, ev_def, ev_spe, ev_spa, ev_spd = struct.unpack("<6B", dec[e_offset:e_offset + 6])
    evs = (ev_hp, ev_atk, ev_def, ev_spa, ev_spd, ev_spe)

    iv_word = struct.unpack("<I", dec[m_offset + 4:m_offset + 8])[0]
    ivs = (
        iv_word & 31, (iv_word >> 5) & 31, (iv_word >> 10) & 31,
        (iv_word >> 20) & 31, (iv_word >> 25) & 31, (iv_word >> 15) & 31,
    )

    inferred_lvl, _ = infer_level_and_rate(exp)
    if len(data) >= 100 and 1 <= data[0x54] <= 100:
        level = data[0x54]
        cur_hp, max_hp, atk, dfn, spe, spa, spd = struct.unpack("<7H", data[0x56:0x64])
        if max_hp == 0:
            iv_d = {"HP": ivs[0], "Atk": ivs[1], "Def": ivs[2], "SpA": ivs[3], "SpD": ivs[4], "Spe": ivs[5]}
            ev_d = {"HP": evs[0], "Atk": evs[1], "Def": evs[2], "SpA": evs[3], "SpD": evs[4], "Spe": evs[5]}
            max_hp, atk, dfn, spe, spa, spd = calc_gen3_party_stats(nat_dex, level, pid, iv_d, ev_d)
            cur_hp = max_hp
    else:
        level = inferred_lvl
        iv_d = {"HP": ivs[0], "Atk": ivs[1], "Def": ivs[2], "SpA": ivs[3], "SpD": ivs[4], "Spe": ivs[5]}
        ev_d = {"HP": evs[0], "Atk": evs[1], "Def": evs[2], "SpA": evs[3], "SpD": evs[4], "Spe": evs[5]}
        max_hp, atk, dfn, spe, spa, spd = calc_gen3_party_stats(nat_dex, level, pid, iv_d, ev_d)
        cur_hp = max_hp

    return {
        "pid": pid, "tid": tid, "sid": sid, "is_shiny": is_shiny,
        "nature": nature, "nature_full": nature_full, "nickname": nickname, "ot_name": ot_name,
        "nat_dex": nat_dex, "level": level, "ivs": ivs, "evs": evs,
        "stats": (cur_hp, max_hp, atk, dfn, spa, spd, spe),
        "item_id": item_id, "item_name": item_name, "item_slug": item_slug
    }

def find_prod_keys() -> Path:
    """Prefer the writable data folder, then the CLI's ~/.switch default."""
    for candidate in (
        DATA_DIR / "prod.keys",
        paths.CONFIG_DIR / "prod.keys",
        Path.home() / ".switch" / "prod.keys",
    ):
        try:
            if candidate.is_file() and candidate.stat().st_size > 64:
                return candidate
        except OSError:
            continue
    return DATA_DIR / "prod.keys"


def ensure_slot1_dummy() -> str:
    existing = sorted(SLOT1_DIR.glob("*.pk3"))
    if existing:
        return str(existing[0])
    legacy_magikarp = DATA_DIR / "Magikarp_5606AEA5.pk3"
    if legacy_magikarp.exists():
        dest = SLOT1_DIR / legacy_magikarp.name
        shutil.copy2(str(legacy_magikarp), str(dest))
        return str(dest)
    any_pk3 = sorted(DATA_DIR.glob("*.pk3"))
    if any_pk3:
        dest = SLOT1_DIR / any_pk3[0].name
        shutil.copy2(str(any_pk3[0]), str(dest))
        return str(dest)
    return ""

def finalize_received_pk3(staging_file: Path) -> Path | None:
    if not staging_file.exists() or staging_file.stat().st_size < 80:
        return None
    info = parse_pk3_file(str(staging_file))
    if not info:
        return staging_file

    dex = info["nat_dex"]
    clean_name = "".join(c for c in info["nickname"] if c.isalnum() or c in ("-", "_")).upper() or "PKMN"
    pid_hex = f"{info['pid']:08X}"
    shiny_tag = "_SHINY" if info["is_shiny"] else ""

    base_stem = f"{dex:03d}_{clean_name}_{pid_hex}{shiny_tag}"
    target = RECEIVED_DIR / f"{base_stem}.pk3"

    counter = 2
    while target.exists():
        target = RECEIVED_DIR / f"{base_stem}_{counter}.pk3"
        counter += 1

    shutil.move(str(staging_file), str(target))
    return target

def network_manager_active() -> bool:
    """Whether NetworkManager is active, without requiring systemd.

    Minimal containers and non-systemd distributions have no ``systemctl``.
    Status checks must still work there, and must never stop the UI from
    opening or closing; an absent service manager means "not active".
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "NetworkManager"],
            capture_output=True,
            text=True,
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip() == "active"


def detect_wiphy(bring_up: bool = True) -> str:
    """Return the first wireless phy, or ``phy0`` when none is present.

    ``bring_up`` keeps the old behaviour of loading the MediaTek module and
    unblocking Wi-Fi when no phy exists.  That asks for the root password, so
    labels that merely report status pass ``False``: drawing the window must
    never open an admin prompt before the window itself is on screen.
    """
    ieee_dir = Path("/sys/class/ieee80211")
    phys = sorted(p.name for p in ieee_dir.iterdir()) if ieee_dir.exists() else []
    if not phys and bring_up:
        if acquire_admin():
            subprocess.run(["sudo", "modprobe", "mt7921e"])
            subprocess.run(["sudo", "rfkill", "unblock", "wifi"])
        phys = sorted(p.name for p in ieee_dir.iterdir()) if ieee_dir.exists() else []
    return phys[0] if phys else "phy0"

class SpriteDownloadWorker(QThread):
    loaded = pyqtSignal(str, str, str)

    def __init__(self, dex_id: int, is_shiny: bool, item_slug: str = "", form: int = 0):
        super().__init__()
        self.dex_id = dex_id
        self.is_shiny = is_shiny
        self.item_slug = item_slug
        self.form = form

    def run(self):
        if self.dex_id <= 0: return

        main_path = animated_sprite_path(self.dex_id, self.form, self.is_shiny)

        if not main_path.exists():
            tag = "shiny" if self.is_shiny else "normal"
            main_path = BASE_DIR / "assets" / "sprites" / tag / f"{self.dex_id}.png"

        sprite_icon = icon_path(self.dex_id, self.form)
        item_path = "" # Item sprites disabled locally to keep assets lean

        self.loaded.emit(str(main_path), str(sprite_icon), str(item_path))
