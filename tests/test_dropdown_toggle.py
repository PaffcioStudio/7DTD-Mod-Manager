"""DropdownButton: a second click on the button must close the open list.

Regression: the popup closed on press-outside and the tap handler reopened it
on release, so the list could only be closed by clicking elsewhere.
Runs a real QML window offscreen with synthetic mouse events.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

QML = """
import QtQuick
import QtQuick.Controls.Basic
import "%(components)s"
ApplicationWindow {
    width: 600; height: 400; visible: true
    property bool open: dd.menuOpened
    DropdownButton {
        id: dd; x: 50; y: 50; width: 200; value: "a"
        options: [{ value: "a", label: "Alpha" }, { value: "b", label: "Beta" }]
    }
}
"""

RUNNER = """
import sys
from PySide6.QtCore import Qt, QPoint, QTimer, QEventLoop
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
app = QGuiApplication(sys.argv)
e = QQmlApplicationEngine(); e.load(sys.argv[1])
w = e.rootObjects()[0]
def wait(ms):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()
def click(delay=40):
    p = QPoint(120, 70)
    QTest.mousePress(w, Qt.LeftButton, Qt.NoModifier, p); wait(delay)
    QTest.mouseRelease(w, Qt.LeftButton, Qt.NoModifier, p); wait(350)
wait(400)
seq = []
for delay in (40, 40, 40, 400):
    click(delay); seq.append(bool(w.property("open")))
print(seq)
sys.exit(0 if seq == [True, False, True, False] else 1)
"""


def test_second_click_closes_dropdown(tmp_path):
    pytest.importorskip("PySide6.QtTest")
    qml = tmp_path / "T.qml"
    qml.write_text(QML % {"components": (ROOT / "qml" / "components").as_uri()})
    runner = tmp_path / "run.py"
    runner.write_text(textwrap.dedent(RUNNER))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=str(tmp_path))
    res = subprocess.run([sys.executable, str(runner), str(qml)], env=env,
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
