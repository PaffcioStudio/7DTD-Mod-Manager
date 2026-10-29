"""Przewijanie kółkiem ma być szybkie, a przeciąganie listy LPM wyłączone."""
import os
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QCoreApplication, QUrl, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
engine = QQmlApplicationEngine()
engine.loadData(f'''
import QtQuick
import QtQuick.Controls.Basic
import "{ROOT.as_uri()}/qml/components" as C
ApplicationWindow {{
    width: 800; height: 600; visible: true
    C.AppScrollView {{
        objectName: "scroll"; anchors.fill: parent; contentHeight: 3000
        Column {{
            Repeater {{ model: 30; Rectangle {{ width: 760; height: 100; color: index % 2 ? "#26313a" : "#182127" }} }}
        }}
    }}
}}
'''.encode(), QUrl.fromLocalFile('/tmp/DesktopScroll.qml'))
window = engine.rootObjects()[0]


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


QTest.qWait(300)
view = next(i for i in walk(window.contentItem()) if i.objectName() == 'scroll')
QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, QPoint(300, 400))
for y in range(380, 179, -20):
    QTest.mouseMove(window, QPoint(300, y), 20)
QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(300, 180))
QTest.qWait(150)
assert view.property('contentY') == 0, 'Przeciągnięcie LPM przewinęło widok'


def wheel(angle, pixel=0):
    point = QPoint(300, 300)
    event = QWheelEvent(QPointF(point), QPointF(window.mapToGlobal(point)),
                        QPoint(0, pixel), QPoint(0, angle), Qt.NoButton, Qt.NoModifier,
                        Qt.NoScrollPhase, False)
    QCoreApplication.sendEvent(window, event)
    QTest.qWait(30)


wheel(-120, -5)
assert view.property('contentY') == 360, view.property('contentY')
for _ in range(3):
    wheel(-120)
assert view.property('contentY') == 1440
wheel(0, -12)
assert view.property('contentY') == 1452
wheel(-15, -1)
assert view.property('contentY') == 1497
bar = next(i for i in walk(view) if i.metaObject().className().startswith('AppScrollBar_'))
y = (bar.property('position') + bar.property('size')/2) * bar.height()
start = bar.mapToScene(QPointF(bar.width()/2, y))
start = QPoint(int(start.x()), int(start.y()))
QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
for offset in range(10, 101, 10):
    QTest.mouseMove(window, QPoint(start.x(), start.y()+offset), 20)
QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(start.x(), start.y()+100))
QTest.qWait(100)
assert view.property('contentY') > 1700, 'Pasek przewijania nie daje się przeciągać'
print('PASS: brak przewijania LPM, szybkie kółko, drobny ruch pikselowy i pasek przewijania')
