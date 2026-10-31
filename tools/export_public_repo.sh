#!/usr/bin/env bash
# Create a clean source tree for a public FRLG Studio repository.
#
# Usage:
#   ./tools/export_public_repo.sh
#   ./tools/export_public_repo.sh /path/to/FRLG-Studio-public
#   ./tools/export_public_repo.sh --force
#
# The export deliberately excludes runtime data (PC boxes, .pk3 files,
# captures, journal, trainer/card files, prod.keys, preferences) and build
# artifacts.  It includes source, tools, assets and the public documentation.
# The AppImage is a GitHub Release asset, not a repository file: GitHub rejects
# individual files over 100 MiB and the AppImage is currently ~106 MB.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=0
DEST=""

for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        -h|--help)
            sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        -*)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
        *)
            if [[ -n "$DEST" ]]; then
                echo "Only one destination path is accepted." >&2
                exit 2
            fi
            DEST="$arg"
            ;;
    esac
done

DEST="${DEST:-$ROOT/dist/FRLG-Studio-public}"
DEST="$(realpath -m "$DEST")"
if [[ "$DEST" == "$ROOT" || "$DEST" == "/" ]]; then
    echo "Refusing to export over the checkout root." >&2
    exit 1
fi
if [[ -e "$DEST" ]]; then
    if [[ "$FORCE" -ne 1 ]]; then
        echo "Destination already exists: $DEST" >&2
        echo "Re-run with --force to replace it." >&2
        exit 1
    fi
    rm -rf -- "$DEST"
fi

command -v rsync >/dev/null 2>&1 || {
    echo "rsync is required to build the public tree." >&2
    exit 1
}

mkdir -p "$DEST"
echo "==> Copying application source"
rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$ROOT/src/" "$DEST/src/"

echo "==> Copying simulator and tools"
rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$ROOT/frlgsim/" "$DEST/frlgsim/"
rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$ROOT/tools/" "$DEST/tools/"

echo "==> Copying assets"
rsync -a \
    --exclude 'ui/prefs.json' \
    --exclude 'ui/theme.txt' \
    --exclude 'ui/ui_scale.txt' \
    "$ROOT/assets/" "$DEST/assets/"

echo "==> Copying public files"
for relative in \
    frlg-studio \
    frlgtrade.py \
    gen3_offline_db.json \
    LICENSE \
    README.md \
    RELEASE_NOTES.md \
    SOUND_PLAN.md \
    requirements.txt \
    requirements-build.txt \
    requirements-tools.txt
do
    if [[ -f "$ROOT/$relative" ]]; then
        cp -p "$ROOT/$relative" "$DEST/$relative"
    fi
done

cat > "$DEST/.gitignore" <<'EOF'
# Runtime data.  These belong in ~/.local/share/frlg-studio, never in Git.
*.pk3
*.ek3
*.sav
*.dsv
*.srm
*.state
prod.keys
title.keys
my_trainer.json
custom_wondercard.json
PCstorage/
created/
received/
slot1/
slot2/
captures/
journal/
custom_cards/
custom gifts/
soundpack/
.backups/
.freebuff/

# Local UI state and generated preferences.
assets/ui/prefs.json
assets/ui/theme.txt
assets/ui/ui_scale.txt

# Build, release and virtual-environment output.
build/
release/
dist/
venv/
__pycache__/
*.pyc
*.pyo
EOF

echo "==> Checking the export for private files"
private_patterns=(
    'prod.keys'
    'title.keys'
    'my_trainer.json'
    'custom_wondercard.json'
    'prefs.json'
    '*.pk3'
    '*.ek3'
    '*.sav'
    '*.dsv'
    '*.srm'
    '*.state'
)
failed=0
for pattern in "${private_patterns[@]}"; do
    found="$(find "$DEST" -type f -name "$pattern" -print -quit)"
    if [[ -n "$found" ]]; then
        echo "  ERROR: private file in export: ${found#$DEST/}" >&2
        failed=1
    fi
done
if rg -l --hidden --glob '!*.png' --glob '!*.jpg' --glob '!*.gif' \
    --glob '!**/tools/export_public_repo.sh' \
    '/home/[A-Za-z0-9._-]+/FRLGSwitchTool' "$DEST" >/dev/null 2>&1; then
    echo "  ERROR: local absolute path found in the export:" >&2
    rg -n --hidden --glob '!*.png' --glob '!*.jpg' --glob '!*.gif' \
        --glob '!**/tools/export_public_repo.sh' \
        '/home/[A-Za-z0-9._-]+/FRLGSwitchTool' "$DEST" | sed -n '1,20p' >&2
    failed=1
fi
if find "$DEST" -type f \( -iname '*.pem' -o -iname '*.key' \) -print -quit | grep -q .; then
    echo "  ERROR: private key material found in the export." >&2
    failed=1
fi
if [[ "$failed" -ne 0 ]]; then
    echo "Export failed its privacy checks; remove the files above and retry." >&2
    exit 1
fi

echo
echo "Public tree: $DEST"
echo "Files:       $(find "$DEST" -type f | wc -l)"
echo "Size:        $(du -sh "$DEST" | cut -f1)"
echo "AppImage:    keep out of Git; upload release/*.AppImage to a GitHub Release."
echo
echo "Next:"
echo "  cd \"$DEST\""
echo "  git init -b main"
echo "  git add ."
echo "  git commit -m \"Publish FRLG Studio\""
