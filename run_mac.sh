#!/usr/bin/env bash
# Input Switcher — macOS launcher (menu bar widget)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Input Switcher — MSI 321URX"
echo "----------------------------"

# ── 1. Find Python 3.9+ ───────────────────────────────────────────────────────
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

# ── 2. Check for m1ddc ────────────────────────────────────────────────────────
if ! command -v m1ddc &>/dev/null; then
  echo ""
  echo "m1ddc not found — required for DDC/CI on Apple Silicon."
  if command -v brew &>/dev/null; then
    echo "Installing via Homebrew…"
    brew install m1ddc
  else
    echo "ERROR: Install Homebrew first (https://brew.sh), then:"
    echo "  brew install m1ddc"
    exit 1
  fi
fi

# ── 3. Set up a local venv and install rumps ─────────────────────────────────
VENV="$DIR/.venv"
if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment…"
  $PYTHON -m venv "$VENV"
fi
PY="$VENV/bin/python"

if ! "$PY" -c "import rumps" &>/dev/null; then
  echo "Installing rumps…"
  "$PY" -m pip install --quiet rumps
fi

# ── 4. Launch detached (terminal can be closed immediately) ──────────────────
echo "Launching menu bar widget…"
nohup "$PY" "$DIR/input_switcher.py" > /tmp/msi-input-switcher.log 2>&1 &
disown
echo "Done — you can close this terminal. Logs: /tmp/msi-input-switcher.log"
