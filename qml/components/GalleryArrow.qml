import QtQuick
import "../theme"

// Okrągły przycisk-strzałka na zdjęciu (karuzela i pełnoekranowy podgląd).
// direction: -1 = w lewo, 1 = w prawo. Półprzezroczysty, żeby czytał się
// zarówno na jasnych, jak i ciemnych zrzutach.
Item {
    id: root

    signal clicked()

    property int direction: 1
    property real size: 36

    implicitWidth: size
    implicitHeight: size
    width: size
    height: size

    readonly property bool hovered: hover.hovered

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: root.hovered ? "#B3000000" : "#80000000"
        border.width: 1
        border.color: root.hovered ? "#4DFFFFFF" : "#26FFFFFF"
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }

    Icon {
        anchors.centerIn: parent
        name: "chevron-right"
        rotation: root.direction < 0 ? 180 : 0
        tint: root.hovered ? "#FFFFFF" : "#E6FFFFFF"
        size: Math.round(root.size * 0.5)
    }

    HoverHandler { id: hover }

    MouseArea {
        id: tap
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    scale: tap.containsPress ? 0.92 : 1.0
    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
}
