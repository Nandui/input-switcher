#!/usr/bin/env bash
# build_mac.sh — Build InputSwitcher.app and package it into a distributable .dmg
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="InputSwitcher"
VERSION="1.0.0"
DMG_NAME="${APP_NAME}-${VERSION}-macOS"

echo "Input Switcher — macOS package builder"
echo "----------------------------------------"

# ── 1. Find Python 3.9+ ──────────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" -c "import sys; print(sys.version_info >= (3,9))" 2>/dev/null)
    if [ "$ver" = "True" ]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.9 or newer not found."
  echo "Install from https://www.python.org  or:  brew install python3"
  exit 1
fi
echo "Python: $($PYTHON --version)"

# ── 2. Check for m1ddc (runtime dep, not bundled) ────────────────────────────
if ! command -v m1ddc &>/dev/null; then
  echo ""
  echo "WARNING: m1ddc not found — the packaged app will require it at runtime."
  echo "Users can install it with:  brew install m1ddc"
  echo ""
fi

# ── 3. Set up isolated build venv ────────────────────────────────────────────
BUILD_VENV="$DIR/.build-venv"
if [ ! -d "$BUILD_VENV" ]; then
  echo "Creating build environment…"
  "$PYTHON" -m venv "$BUILD_VENV"
fi
PY="$BUILD_VENV/bin/python"
PIP="$BUILD_VENV/bin/pip"
PYINSTALLER="$BUILD_VENV/bin/pyinstaller"

echo "Installing build dependencies…"
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet pyinstaller rumps

# ── 4. Build the .app ────────────────────────────────────────────────────────
echo "Building ${APP_NAME}.app with PyInstaller…"
"$PYINSTALLER" --clean --noconfirm "$DIR/InputSwitcher.spec"
echo "App built → dist/${APP_NAME}.app"

# ── 5. Package into a .dmg ───────────────────────────────────────────────────
echo "Creating ${DMG_NAME}.dmg…"

STAGING="$DIR/dist/.dmg-staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"

cp -r "$DIR/dist/${APP_NAME}.app" "$STAGING/"
# Applications symlink lets users drag-and-drop to install
ln -s /Applications "$STAGING/Applications"

DMG_PATH="$DIR/dist/${DMG_NAME}.dmg"
rm -f "$DMG_PATH"

hdiutil create \
  -volname "Input Switcher" \
  -srcfolder "$STAGING" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

rm -rf "$STAGING"

echo ""
echo "Done!"
echo "  App:      dist/${APP_NAME}.app"
echo "  Installer: dist/${DMG_NAME}.dmg"
echo ""
echo "NOTE: m1ddc must be installed on the target Mac (brew install m1ddc)."
echo "      The .app is unsigned; users may need to right-click → Open on first launch."
