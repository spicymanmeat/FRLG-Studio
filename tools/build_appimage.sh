#!/usr/bin/env bash
# Build a self-contained, release-ready FRLG Studio AppImage.
#
# Usage:
#   ./tools/build_appimage.sh
#   ./tools/build_appimage.sh --skip-build
#
# The first run downloads PyInstaller's dependencies into build/, the .NET 10
# runtime and appimagetool 1.9.1 into build/tools/.  The resulting AppImage
# contains the application, Python, Qt, frlgsim, PKHeX.Core.dll, the Wonder
# Card host and the .NET runtime.  User data, saves, prefs and prod.keys are
# never included; at runtime they live under the XDG data/config directories.
#
# Set FRLG_SIGN_KEY to a GPG key id to sign the AppImage and SHA256SUMS.
# Set FRLG_UPDATE_INFO to override the embedded AppImageUpdate URL.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/venv"
BUILD="$ROOT/build/appimage"
PYI_DIST="$ROOT/build/pyinstaller/dist"
PYI_WORK="$ROOT/build/pyinstaller/work"
APPDIR="$BUILD/FRLG_Studio.AppDir"
TOOLS="$ROOT/build/tools"
RELEASE_DIR="$ROOT/release"
APPIMAGETOOL="$TOOLS/appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"

DOTNET_RUNTIME_VERSION="${DOTNET_RUNTIME_VERSION:-10.0.13}"
DOTNET_RUNTIME_SHA256="${DOTNET_RUNTIME_SHA256:-958c952691d2c3f8ce21f717f4e911c02b5da0e21ead21bd576368c454b79c77}"
DOTNET_RUNTIME_URL="${DOTNET_RUNTIME_URL:-https://dotnetcli.azureedge.net/dotnet/Runtime/${DOTNET_RUNTIME_VERSION}/dotnet-runtime-${DOTNET_RUNTIME_VERSION}-linux-x64.tar.gz}"
DOTNET_CACHE="$ROOT/build/dotnet-runtime"
DOTNET_TARBALL="$DOTNET_CACHE/dotnet-runtime-${DOTNET_RUNTIME_VERSION}-linux-x64.tar.gz"
DOTNET_TREE="$DOTNET_CACHE/dotnet-runtime-${DOTNET_RUNTIME_VERSION}"

UPDATE_INFO="${FRLG_UPDATE_INFO:-gh-releases-zsync|tornadus|frlg-ldn-trade|latest|FRLG_Studio-x86_64.AppImage.zsync}"
# The AppImage desktop id is the AppStream component id, so appimagetool
# finds usr/share/metainfo/$APP_ID.appdata.xml.  The executable keeps the
# short frlg-studio name used by the bundle and the AppRun.
APP_ID="io.github.tornadus.frlg_studio"
APP_EXEC="frlg-studio"
METAINFO_ID="$APP_ID"
METAINFO="$ROOT/assets/branding/$METAINFO_ID.metainfo.xml"
STABLE_NAME="FRLG_Studio-x86_64.AppImage"

PYTHON="${FRLG_BUILD_PYTHON:-$VENV/bin/python}"
PYINSTALLER="${FRLG_BUILD_PYINSTALLER:-$VENV/bin/pyinstaller}"

SKIP_BUILD=0
if [[ "${1:-}" == "--skip-build" ]]; then
    SKIP_BUILD=1
elif [[ -n "${1:-}" ]]; then
    echo "Unknown option: $1" >&2
    echo "Usage: $0 [--skip-build]" >&2
    exit 2
fi

[[ "$(uname -s)" == "Linux" ]] || {
    echo "AppImage builds require Linux." >&2
    exit 1
}
[[ "$(uname -m)" == "x86_64" ]] || {
    echo "This recipe currently builds x86_64 only." >&2
    exit 1
}
[[ -x "$PYTHON" ]] || {
    echo "Missing Python: $PYTHON" >&2
    echo "Set FRLG_BUILD_PYTHON or create the venv, then install requirements-build.txt." >&2
    exit 1
}
[[ -x "$PYINSTALLER" ]] || {
    echo "Missing PyInstaller: $PYINSTALLER" >&2
    echo "Install the build tool with: venv/bin/pip install -r requirements-build.txt" >&2
    exit 1
}
"$PYTHON" -c 'import PyQt6, pythonnet' >/dev/null 2>&1 || {
    echo "The build Python is missing PyQt6 or pythonnet." >&2
    exit 1
}

VERSION="$("$PYTHON" - <<'PY'
import sys
sys.path.insert(0, "src")
from version import APP_VERSION
print(APP_VERSION)
PY
)"
OUTPUT="$BUILD/$STABLE_NAME"
VERSIONED_OUTPUT="$BUILD/FRLG_Studio-${VERSION}-x86_64.AppImage"

echo "==> Building the PyInstaller onedir bundle"
if [[ "$SKIP_BUILD" -eq 0 ]]; then
    rm -rf "$PYI_DIST" "$PYI_WORK"
    FRLG_STUDIO_ROOT="$ROOT" "$PYINSTALLER" \
        --noconfirm --clean \
        --distpath "$PYI_DIST" \
        --workpath "$PYI_WORK" \
        "$ROOT/tools/frlg_studio.spec"
else
    [[ -x "$PYI_DIST/frlg-studio/frlg-studio" ]] || {
        echo "No bundle at $PYI_DIST; run without --skip-build first." >&2
        exit 1
    }
fi

# A release must never contain the user's keys, boxes, saves or preferences.
if find "$PYI_DIST/frlg-studio" -type f \
    \( -name 'prod.keys' -o -name '*.pk3' -o -name '*.ek3' -o -name 'prefs.json' \) \
    -print -quit | grep -q .; then
    echo "Refusing to package user data found in the PyInstaller bundle." >&2
    find "$PYI_DIST/frlg-studio" -type f \
        \( -name 'prod.keys' -o -name '*.pk3' -o -name '*.ek3' -o -name 'prefs.json' \) \
        -print >&2
    exit 1
fi

echo "==> Preparing the .NET ${DOTNET_RUNTIME_VERSION} runtime"
mkdir -p "$DOTNET_CACHE"
if [[ ! -f "$DOTNET_TARBALL" ]]; then
    echo "    downloading $DOTNET_RUNTIME_URL"
    curl -fL --retry 3 --retry-delay 2 -o "$DOTNET_TARBALL.part" "$DOTNET_RUNTIME_URL"
    echo "$DOTNET_RUNTIME_SHA256  $DOTNET_TARBALL.part" | sha256sum -c -
    mv "$DOTNET_TARBALL.part" "$DOTNET_TARBALL"
else
    echo "$DOTNET_RUNTIME_SHA256  $DOTNET_TARBALL" | sha256sum -c -
fi
rm -rf "$DOTNET_TREE"
mkdir -p "$DOTNET_TREE"
tar -xzf "$DOTNET_TARBALL" -C "$DOTNET_TREE"
"$DOTNET_TREE/dotnet" --info >/dev/null

echo "==> Assembling the AppDir"
rm -rf "$APPDIR" "$OUTPUT" "$VERSIONED_OUTPUT" "$OUTPUT.zsync"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/metainfo" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/doc/frlg-studio"
cp -a "$PYI_DIST/frlg-studio" "$APPDIR/usr/lib/frlg-studio"
cp -a "$DOTNET_TREE" "$APPDIR/usr/lib/frlg-studio/dotnet"
cp "$ROOT/assets/branding/frlg_studio_icon.png" \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
cp "$ROOT/assets/branding/frlg_studio_icon.png" "$APPDIR/$APP_ID.png"
# AppStream requires the installed filename to match the component id.
# appimagetool 1.9.1 only discovers the legacy .appdata.xml spelling, so the
# single metadata file is installed under that name; AppStream 1.x still
# accepts it and there is no duplicate component in the AppImage.
cp "$METAINFO" "$APPDIR/usr/share/metainfo/$APP_ID.appdata.xml"
cp "$ROOT/LICENSE" "$APPDIR/usr/share/doc/frlg-studio/LICENSE"

cat > "$APPDIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=FRLG Studio
GenericName=Pokémon FireRed / LeafGreen Link Tool
Comment=Wireless trade, storage, editing and Wonder Cards for FRLG
Exec=$APP_EXEC
Icon=$APP_ID
Terminal=false
Categories=Utility;
Keywords=pokemon;firered;leafgreen;trade;pk3;
StartupWMClass=frlg-studio
X-AppImage-Version=$VERSION
EOF
cp "$APPDIR/$APP_ID.desktop" "$APPDIR/usr/share/applications/$APP_ID.desktop"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
# AppRun: keep writes out of the read-only AppImage mount and use the
# bundled .NET runtime instead of whatever the host happens to have.
set -euo pipefail

HERE="${APPDIR:-$(cd "$(dirname "$0")" && pwd)}"
BUNDLE_ROOT="$HERE/usr/lib/frlg-studio"
BIN="$BUNDLE_ROOT/frlg-studio"
APP_FILES="$BUNDLE_ROOT/_internal"
DOTNET_BUNDLE="$BUNDLE_ROOT/dotnet"

if [[ ! -x "$BIN" ]]; then
    echo "FRLG Studio binary is missing from this AppImage." >&2
    exit 1
fi

: "${HOME:?HOME must be set to run FRLG Studio}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export FRLG_STUDIO_DATA_DIR="${FRLG_STUDIO_DATA_DIR:-$DATA_HOME/frlg-studio}"
export FRLG_STUDIO_CONFIG_DIR="${FRLG_STUDIO_CONFIG_DIR:-$CONFIG_HOME/frlg-studio}"
export FRLG_STUDIO_APP_DIR="${FRLG_STUDIO_APP_DIR:-$APP_FILES}"

mkdir -p "$FRLG_STUDIO_DATA_DIR" "$FRLG_STUDIO_CONFIG_DIR"

# The runtime is shipped inside the AppImage.  A developer can still point at
# another installation with FRLG_STUDIO_DOTNET_ROOT for troubleshooting.
if [[ -n "${FRLG_STUDIO_DOTNET_ROOT:-}" ]]; then
    export DOTNET_ROOT="$FRLG_STUDIO_DOTNET_ROOT"
elif [[ -x "$DOTNET_BUNDLE/dotnet" ]]; then
    export DOTNET_ROOT="$DOTNET_BUNDLE"
else
    for candidate in /usr/share/dotnet /usr/lib/dotnet "$HOME/.dotnet"; do
        if [[ -x "$candidate/dotnet" ]]; then
            export DOTNET_ROOT="$candidate"
            break
        fi
    done
fi
export DOTNET_MULTILEVEL_LOOKUP=0
export DOTNET_CLI_TELEMETRY_OPTOUT=1

cd "$FRLG_STUDIO_DATA_DIR"
exec "$BIN" "$@"
EOF
chmod 755 "$APPDIR/AppRun" "$APPDIR/$APP_ID.desktop"

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$APPDIR/$APP_ID.desktop"
fi
if command -v appstreamcli >/dev/null 2>&1; then
    appstreamcli validate --no-net "$APPDIR/usr/share/metainfo/$APP_ID.appdata.xml"
fi

if [[ ! -x "$APPIMAGETOOL" ]]; then
    echo "==> Downloading appimagetool 1.9.1"
    mkdir -p "$TOOLS"
    wget -q -O "$APPIMAGETOOL.part" "$APPIMAGETOOL_URL"
    echo "$APPIMAGETOOL_SHA256  $APPIMAGETOOL.part" | sha256sum -c -
    mv "$APPIMAGETOOL.part" "$APPIMAGETOOL"
    chmod 755 "$APPIMAGETOOL"
else
    echo "$APPIMAGETOOL_SHA256  $APPIMAGETOOL" | sha256sum -c -
fi

APPIMAGETOOL_ARGS=()
if [[ -n "${FRLG_SIGN_KEY:-}" ]]; then
    APPIMAGETOOL_ARGS+=(--sign --sign-key "$FRLG_SIGN_KEY")
fi
if command -v zsyncmake >/dev/null 2>&1; then
    APPIMAGETOOL_ARGS+=(-u "$UPDATE_INFO")
else
    echo "==> zsyncmake not found; building without AppImageUpdate metadata"
    echo "    Install the 'zsync' package (or use tools/build_release.sh) to enable it."
fi

echo "==> Creating $OUTPUT"
run_appimagetool() {
    if [[ -e /dev/fuse ]]; then
        "$APPIMAGETOOL" "$@"
    else
        APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$@"
    fi
}
run_appimagetool "${APPIMAGETOOL_ARGS[@]}" "$APPDIR" "$OUTPUT"

# appimagetool runs zsyncmake from the current directory, so the .zsync can
# land beside the checkout even though the AppImage path is absolute.  Move it
# next to the AppImage before the release directory is assembled.
if command -v zsyncmake >/dev/null 2>&1; then
    ZSYNC_PATH=""
    for candidate in \
        "$OUTPUT.zsync" \
        "$(pwd)/$(basename "$OUTPUT").zsync" \
        "$ROOT/$(basename "$OUTPUT").zsync"; do
        if [[ -f "$candidate" ]]; then
            ZSYNC_PATH="$candidate"
            break
        fi
    done
    if [[ -z "$ZSYNC_PATH" ]]; then
        echo "appimagetool did not produce a .zsync file." >&2
        exit 1
    fi
    if [[ "$ZSYNC_PATH" != "$OUTPUT.zsync" ]]; then
        mv -f "$ZSYNC_PATH" "$OUTPUT.zsync"
    fi
fi

cp -p "$OUTPUT" "$VERSIONED_OUTPUT"

echo "==> Preparing release directory"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
cp -p "$OUTPUT" "$RELEASE_DIR/$STABLE_NAME"
cp -p "$VERSIONED_OUTPUT" "$RELEASE_DIR/$(basename "$VERSIONED_OUTPUT")"
if [[ -f "$OUTPUT.zsync" ]]; then
    cp -p "$OUTPUT.zsync" "$RELEASE_DIR/$(basename "$OUTPUT.zsync")"
fi
if [[ -f "$ROOT/RELEASE_NOTES.md" ]]; then
    cp -p "$ROOT/RELEASE_NOTES.md" "$RELEASE_DIR/RELEASE_NOTES.md"
fi
release_files=()
for release_file in "$RELEASE_DIR"/*.AppImage "$RELEASE_DIR"/*.zsync; do
    [[ -f "$release_file" ]] && release_files+=("$(basename "$release_file")")
done
(
    cd "$RELEASE_DIR"
    sha256sum "${release_files[@]}" > SHA256SUMS
)
if [[ -n "${FRLG_SIGN_KEY:-}" ]]; then
    echo "==> Signing SHA256SUMS with $FRLG_SIGN_KEY"
    gpg --batch --yes --local-user "$FRLG_SIGN_KEY" \
        --armor --detach-sign "$RELEASE_DIR/SHA256SUMS"
fi

echo
echo "Built: $OUTPUT"
echo "Copy:  $VERSIONED_OUTPUT"
echo "Release directory: $RELEASE_DIR"
echo "Size:  $(du -h "$OUTPUT" | cut -f1)"
echo "Run:   chmod +x \"$OUTPUT\" && \"$OUTPUT\""
echo
echo "The first launch creates ~/.local/share/frlg-studio and"
echo "~/.config/frlg-studio.  The .NET ${DOTNET_RUNTIME_VERSION} runtime is inside"
echo "the AppImage; prod.keys stays outside it."
