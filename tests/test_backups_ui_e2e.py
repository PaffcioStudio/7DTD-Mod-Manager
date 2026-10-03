"""Backups page, end to end in the real app (offscreen, throw-away HOME).

Regression: clicking the trash icon did nothing (QML assigned a property that
does not exist on the confirmation modal, which aborted the click handler).
Also covers Restore and the startup migration of modpacks/ -> backups/.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_delete_and_restore_through_the_ui(tmp_path):
    pytest.importorskip("PySide6.QtTest")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
    res = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "e2e_backups_driver.py"), str(tmp_path / "home")],
        env=env, capture_output=True, text=True, timeout=120)
    lines = [ln for ln in res.stdout.splitlines() if ln.startswith(("PASS", "FAIL", "ALL", "SOME"))]
    assert res.returncode == 0, "\n".join(lines) + "\n" + res.stderr[-2000:]
    assert any(ln.startswith("ALL PASS") for ln in lines)
    assert "Cannot assign to non-existent property" not in res.stdout + res.stderr
