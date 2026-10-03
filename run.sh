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
# 3. Środowisko interaktywnego shella potrafi zepsuć ładowanie wtyczek Qt:
#    - LD_LIBRARY_PATH (np. pod CUDA/conda/SDK) przesłania systemowe
#      biblioteki, których wayland/xcb wymagają przy dlopen,
#    - PYTHONPATH/PYTHONHOME mogą wcisnąć INNĄ kopię PySide6/Qt (np.
#      systemową) zamiast tej z .venv - objaw: wtyczki "znalezione, ale
#      nie do załadowania". PySide6 ma Qt w pakiecie, main.py sam dodaje
#      src/ do sys.path - aplikacja nie potrzebuje żadnego z nich.
#      (Ten sam mechanizm co _clean_subprocess_env() starego projektu.)
unset QT_PLUGIN_PATH
unset QT_QPA_PLATFORM_PLUGIN_PATH
unset LD_LIBRARY_PATH
unset PYTHONPATH
unset PYTHONHOME

VENV_PY="$PROJECT_DIR/.venv/bin/python"

exec "$VENV_PY" "$PROJECT_DIR/src/main.py" "$@"
