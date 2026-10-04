"""Tooltip IconButton ma byc przy przycisku nawet gdy ten przesunie sie po
utworzeniu (layout/animacja strony/scroll). Regresja: tooltip ladowal np.
przy zakladce sidebara, bo pozycja liczona byla raz bindingiem mapToItem."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_tooltip_follows_button_moved_after_creation():
    pytest.importorskip("PySide6.QtTest")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
    res = subprocess.run([sys.executable, str(ROOT / "tests" / "icon_button_tip_driver.py")],
                         env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout[-500:] + res.stderr[-1500:]
