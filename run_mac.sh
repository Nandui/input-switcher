#!/usr/bin/env bash
# Input Switcher — macOS launcher
# Run once: bash run_mac.sh
# After that you can double-click it or keep using: bash run_mac.sh

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Input Switcher — MSI 321URX"
echo "----------------------------"

# ── 1. Find a usable Python 3.9+ ──────────────────────────────────────────
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
  echo ""
  echo "ERROR: Python 3.9 or newer not found."
  echo "Install it from https://www.python.org  or via Homebrew:"
  echo "  brew install python"
  exit 1
fi

echo "Python: $($PYTHON --version)"

# ── 2. Check tkinter (ships with python.org builds; missing on some Homebrew installs) ──
if ! $PYTHON -c "import tkinter" &>/dev/null; then
  echo ""
  echo "ERROR: tkinter not found."
  echo "Fix options:"
  echo "  • Homebrew Python:  brew install python-tk"
  echo "  • Or install Python from https://www.python.org (includes Tk)"
  exit 1
fi

# ── 3. Install / upgrade monitorcontrol ───────────────────────────────────
echo "Checking dependencies…"
$PYTHON -m pip install --quiet --upgrade monitorcontrol

# ── 4. Launch ─────────────────────────────────────────────────────────────
echo "Launching…"
$PYTHON "$DIR/input_switcher.py"
