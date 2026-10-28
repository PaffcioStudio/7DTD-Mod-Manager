"""Wylogowanie z obu miejsc wymaga zgody, także po zmianie języka."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('language', ['pl', 'en'])
def test_steam_logout_requires_confirmation(tmp_path, language):
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tests/e2e_steam_logout_driver.py'), str(tmp_path), language],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software'),
        capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-4000:]
    assert 'PASS: page, header, cancel, Escape, confirm' in result.stdout
