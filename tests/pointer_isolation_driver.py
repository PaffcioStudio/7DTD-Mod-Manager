"""Kliknięcie kontrolki i zamykanie modala nie mogą uruchamiać tła."""
import os
import sys
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QUrl, QPoint, QPointF, Qt, QObject, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression, QQmlEngine
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
engine = QQmlApplicationEngine()
class Icons(QObject):
    @Slot(str, str, result=str)
    def url(self, name, tint):
        return ''
icons = Icons()
engine.rootContext().setContextProperty('Icons', icons)
engine.loadData(f'''
import QtQuick
import QtQuick.Controls.Basic
import "{ROOT.as_uri()}/qml/components" as C
ApplicationWindow {{
    id: win; width: 1100; height: 700; visible: true
    property int backgroundHits: 0
    property int foregroundHits: 0
    Rectangle {{
        anchors.fill: parent; color: "#151820"
        TapHandler {{ onTapped: win.backgroundHits++ }}
    }}
    C.PrimaryButton {{ objectName: "primary"; x: 30; y: 70; text: "Primary"; onClicked: win.foregroundHits++ }}
    C.SecondaryButton {{ objectName: "secondary"; x: 200; y: 70; text: "Secondary"; onClicked: win.foregroundHits++ }}
    C.FilterChip {{ objectName: "chip"; x: 390; y: 70; label: "Chip"; onClicked: win.foregroundHits++ }}
    C.ToggleSwitch {{ objectName: "toggle"; x: 510; y: 70; onToggled: win.foregroundHits++ }}
    C.DropdownButton {{
        id: dropdown; objectName: "dropdown"; x: 630; y: 70
        value: "a"; options: [{{value: "a", label: "Option A"}}, {{value: "b", label: "Option B"}}]
        onPicked: (value) => {{ dropdown.value = value; win.foregroundHits++ }}
    }}
    C.ConfirmModal {{ id: modal; onConfirmed: win.foregroundHits++ }}
    function showModal() {{ modal.ask("Pointer test", "Only the foreground can react", "Confirm", false) }}
}}
'''.encode(), QUrl.fromLocalFile('/tmp/PointerIsolation.qml'))
assert engine.rootObjects()
window = engine.rootObjects()[0]


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def center(item):
    p = item.mapToScene(QPointF(item.width()/2, item.height()/2))
    return QPoint(int(p.x()), int(p.y()))


def click(item):
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, center(item))
    QTest.qWait(60)


QTest.qWait(300)
for name in ['primary', 'secondary', 'chip', 'toggle']:
    control = next(i for i in walk(window.contentItem()) if i.objectName() == name)
    click(control)
    assert window.property('backgroundHits') == 0, name
assert window.property('foregroundHits') == 4
control = next(i for i in walk(window.contentItem()) if i.objectName() == 'dropdown')
click(control)
QTest.qWait(200)
option = next(i for i in walk(window.contentItem()) if i.isVisible() and i.property('text') == 'Option B')
click(option)
assert control.property('value') == 'b'
assert window.property('backgroundHits') == 0, 'dropdown'
expr = QQmlExpression(QQmlEngine.contextForObject(window), window, 'showModal()')
expr.evaluate()
assert not expr.hasError()
QTest.qWait(800)
QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(10, 10))
assert window.property('backgroundHits') == 0, 'modal scrim'
confirm = next(i for i in walk(window.contentItem()) if i.isVisible() and i.property('text') == 'Confirm')
point = center(confirm)
click(confirm)
QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(50)
assert window.property('backgroundHits') == 0, 'closing modal'
assert window.property('foregroundHits') == 6
QTest.qWait(600)
QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
assert window.property('backgroundHits') == 1, 'background did not unlock'
print('PASS: controls, dropdown, modal scrim and closing guard')
