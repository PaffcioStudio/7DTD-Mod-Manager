#!/usr/bin/env bash
# ============================================================================
#  7 Days to Die - Mod Manager :: launcher
#  Runs the application using the interpreter from the local .venv.
#  It does NOT rely on activating the environment via .venv/bin/activate.
# ============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# ----------------------------------------------------------------------------
# 1. The virtual environment must already exist
# ----------------------------------------------------------------------------
if [ ! -d ".venv" ] || [ ! -x ".venv/bin/python" ]; then
    echo ""
    echo -e "${RED}Virtual environment not found.${NC}"
    echo ""
    echo "Run:"
    echo ""
    echo -e "    ${BOLD}./venv.sh${NC}"
    echo ""
    exit 1
fi

# ----------------------------------------------------------------------------
# 2. Launch the app with the venv interpreter
# ----------------------------------------------------------------------------
# An interactive shell environment can break Qt plugin loading:
#   - LD_LIBRARY_PATH (e.g. for CUDA/conda/an SDK) overrides the system
#     libraries that wayland/xcb need at dlopen time,
#   - PYTHONPATH/PYTHONHOME can force a DIFFERENT copy of PySide6/Qt (e.g. the
#     system one) instead of the one from .venv - symptom: plugins "found, but
#     could not be loaded". PySide6 ships its own Qt and main.py adds src/ to
#     sys.path itself - the app needs none of these variables.
#     (Same mechanism as _clean_subprocess_env() in the old project.)
unset QT_PLUGIN_PATH
unset QT_QPA_PLATFORM_PLUGIN_PATH
unset LD_LIBRARY_PATH
unset PYTHONPATH
unset PYTHONHOME

VENV_PY="$PROJECT_DIR/.venv/bin/python"

exec "$VENV_PY" "$PROJECT_DIR/src/main.py" "$@"
