#!/usr/bin/env bash
# Build the release AppImage on the oldest supported glibc baseline.
#
# The host build is convenient for development, but it inherits the host
# Python/Qt and therefore the host glibc.  This script builds inside Debian 11
# (glibc 2.31) and writes the same build/ and release/ directories as
# tools/build_appimage.sh.  It uses podman or docker, whichever is available.
#
# Usage:
#   ./tools/build_release.sh
#   CONTAINER_ENGINE=docker ./tools/build_release.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${FRLG_BUILD_IMAGE:-python:3.12-slim-bullseye}"

if [[ -n "${CONTAINER_ENGINE:-}" ]]; then
    ENGINE="$CONTAINER_ENGINE"
elif command -v podman >/dev/null 2>&1; then
    ENGINE=podman
elif command -v docker >/dev/null 2>&1; then
    ENGINE=docker
else
    echo "Missing podman or docker; install one to build the release baseline." >&2
    exit 1
fi

if [[ ! -f "$ROOT/requirements.txt" ]]; then
    echo "Run this from the FRLG Studio checkout." >&2
    exit 1
fi

echo "==> Building in $IMAGE with $ENGINE"
echo "    The first run installs Qt, pythonnet, PyInstaller and zsync in the container."

"$ENGINE" run --rm \
    -v "$ROOT:/work:Z" \
    -w /work \
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
    -e QT_QPA_PLATFORM=offscreen \
    "$IMAGE" bash -lc '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Debian 11 reached end of LTS on 2026-08-31.  The security archive index is
# still served, but its per-package .deb files now return 404, so any apt
# install that resolves a package from bullseye-security fails.  Dropping
# that one line lets apt use the still-available bullseye main/updates pool;
# the glibc baseline stays 2.31.  A pinned snapshot would also work, but it
# is far slower and the archive keeps the same package versions.
if [[ -f /etc/apt/sources.list ]]; then
    sed -i "/debian-security/d" /etc/apt/sources.list
fi
if grep -Rqs "debian-security" /etc/apt/sources.list /etc/apt/sources.list.d/; then
    echo "A debian-security apt source is still configured; its packages are gone." >&2
    exit 1
fi

apt-get update
apt-get install -y --no-install-recommends \
    wget file ca-certificates binutils patchelf \
    zsync appstream desktop-file-utils \
    libgl1 libegl1 libglib2.0-0 libgomp1 \
    libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 \
    libfontconfig1 libxrender1 libxi6 libxtst6 \
    libsm6 libice6 libxfixes3 libxext6 libx11-6 \
    libxcb1 libxcb-util1 libxcb-cursor0 libxcb-icccm4 \
    libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-shm0 \
    libxcb-sync1 libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 \
    libpulse0 libasound2 libicu67 libssl1.1

GLIBC_VERSION="$(ldd --version | sed -n "1p" | awk "{print \$NF}")"
if [[ "$GLIBC_VERSION" != "2.31"* ]]; then
    echo "Expected the glibc 2.31 baseline, found $GLIBC_VERSION." >&2
    exit 1
fi
python - <<"PY"
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"Expected Python 3.12, found {sys.version.split()[0]}")
PY
if ! command -v zsyncmake >/dev/null 2>&1; then
    echo "zsyncmake is missing; the AppImageUpdate metadata would be skipped." >&2
    exit 1
fi

echo "    glibc $GLIBC_VERSION, $(python --version), $(zsyncmake -V 2>&1 | sed -n "1p")"

python -m venv /tmp/frlg-build-venv
. /tmp/frlg-build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-build.txt

export FRLG_BUILD_PYTHON=/tmp/frlg-build-venv/bin/python
export FRLG_BUILD_PYINSTALLER=/tmp/frlg-build-venv/bin/pyinstaller
./tools/build_appimage.sh
'

echo
echo "Release build finished.  Check release/SHA256SUMS and release/*.AppImage."
