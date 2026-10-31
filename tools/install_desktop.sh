#!/usr/bin/env bash
# Install a per-user desktop entry for FRLG Studio.  Run this once after the
# venv and requirements are in place; re-run it after moving the project.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
ICON="$ROOT/assets/branding/frlg_studio_icon.png"
ENTRY="$DESKTOP_DIR/frlg-studio.desktop"

if [[ ! -x "$ROOT/frlg-studio" ]]; then
    chmod +x "$ROOT/frlg-studio"
fi
if [[ ! -x "$ROOT/venv/bin/python" ]]; then
    echo "No venv found at $ROOT/venv." >&2
    echo "Create it first: python3 -m venv venv && venv/bin/pip install -r requirements.txt PyQt6 pythonnet" >&2
    exit 1
fi

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"
if [[ -f "$ICON" ]]; then
    cp "$ICON" "$ICON_DIR/frlg-studio.png"
fi

cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=FRLG Studio
GenericName=Pokémon FireRed / LeafGreen Link Tool
Comment=Wireless trade, storage, editing and Wonder Cards for FRLG
Exec="$ROOT/frlg-studio" %f
Path=$ROOT
Icon=frlg-studio
Terminal=false
Categories=Utility;
Keywords=pokemon;firered;leafgreen;trade;pk3;
StartupWMClass=trade_gui.py
EOF

chmod 755 "$ENTRY"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Installed: $ENTRY"
echo "FRLG Studio should now appear in your application launcher."
echo "Re-run this script if you move the project folder."
