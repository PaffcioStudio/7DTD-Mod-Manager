#!/usr/bin/env bash
# ============================================================================
#  7 Days to Die - Mod Manager :: environment setup
#  Creates a local virtual environment (.venv) and installs all dependencies.
# ============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[i]${NC} $1"; }
ok()      { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
fail()    { echo -e "${RED}[✗]${NC} $1"; }

echo ""
echo -e "${BOLD}==============================================${NC}"
echo -e "${BOLD}  7 Days to Die - Mod Manager :: setup${NC}"
echo -e "${BOLD}==============================================${NC}"
echo ""

# ----------------------------------------------------------------------------
# 1. Check that Python 3 is available
# ----------------------------------------------------------------------------
info "Checking for Python 3..."

if ! command -v python3 >/dev/null 2>&1; then
    fail "Python 3 was not found on this system."
    fail "Please install Python 3 (>= 3.9) first, for example:"
    echo ""
    echo "    Debian/Ubuntu:  sudo apt install python3 python3-venv"
    echo "    Fedora:         sudo dnf install python3"
    echo "    Arch:           sudo pacman -S python"
    echo ""
    exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))')"
ok "Found Python $PY_VERSION ($(command -v python3))"

# ----------------------------------------------------------------------------
# 2. Create the virtual environment
# ----------------------------------------------------------------------------
if [ -d ".venv" ] && [ -x ".venv/bin/python" ]; then
    warn "Virtual environment already exists at .venv/ - reusing it."
else
    info "Creating virtual environment in .venv/ ..."
    if ! python3 -m venv .venv; then
        fail "Could not create the virtual environment."
        fail "On Debian/Ubuntu you may need:  sudo apt install python3-venv"
        exit 1
    fi
    ok "Virtual environment created."
fi

VENV_PY="$PROJECT_DIR/.venv/bin/python"

# ----------------------------------------------------------------------------
# 3. Upgrade pip
# ----------------------------------------------------------------------------
info "Upgrading pip..."
if ! "$VENV_PY" -m pip install --upgrade pip --quiet; then
    fail "Could not upgrade pip inside the virtual environment."
    exit 1
fi
ok "pip is up to date."

# ----------------------------------------------------------------------------
# 4. Install dependencies from requirements.txt
# ----------------------------------------------------------------------------
if [ ! -f "requirements.txt" ]; then
    fail "requirements.txt not found in $PROJECT_DIR"
    exit 1
fi

info "Installing dependencies from requirements.txt (this may take a while)..."
if ! "$VENV_PY" -m pip install -r requirements.txt; then
    echo ""
    fail "Dependency installation failed."
    fail "Check your internet connection and try again with:"
    echo ""
    echo "    ./venv.sh"
    echo ""
    exit 1
fi

echo ""
ok "All dependencies installed successfully."
echo ""
echo -e "You can now start the application with:"
echo ""
echo -e "    ${BOLD}./run.sh${NC}"
echo ""
