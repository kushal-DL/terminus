#!/usr/bin/env bash
set -e

echo ""
echo " =============================================="
echo "  TERMINUS - The Last Stand Begins Here"
echo " =============================================="
echo ""

# Resolve script directory so it works from anywhere
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo " [ERROR] python3 not found."
    echo ""
    echo " macOS:  brew install python"
    echo " Ubuntu: sudo apt install python3 python3-venv python3-pip"
    echo ""
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo " Python $PYVER found."

# Check version >= 3.11
PYMAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYMINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYMAJOR" -lt 3 ] || { [ "$PYMAJOR" -eq 3 ] && [ "$PYMINOR" -lt 11 ]; }; then
    echo " [ERROR] Python 3.11 or newer required (found $PYVER)."
    exit 1
fi

# Create venv if missing
if [ ! -d ".venv" ]; then
    echo " Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install / upgrade dependencies
echo " Checking dependencies..."
pip install -e . -q --disable-pip-version-check

# Launch
echo " Launching Terminus..."
echo ""
python -m terminus
