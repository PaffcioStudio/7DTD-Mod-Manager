import QtQuick
import "../theme"

// Animated toggle switch.
Item {
    id: root

    signal toggled(bool checked)

    property bool checked: false

    implicitWidth: 46
    implicitHeight: 25

    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.accent
             : (hover.hovered ? Theme.bg4 : Theme.bg3)
        border.width: root.checked ? 0 : 1
        border.color: Theme.borderHover
        Behavior on color { ColorAnimation { duration: Theme.normal } }
        Behavior on border.color { ColorAnimation { duration: Theme.normal } }
    }

    Rectangle {
        id: knob
        width: 19
        height: 19
        radius: 10
        anchors.verticalCenter: parent.verticalCenter
        x: root.checked ? parent.width - width - 3 : 3
        color: root.checked ? Theme.accentForeground : "#C6CFDF"
        scale: tap.pressed ? 0.9 : 1.0

        Behavior on x { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: 90 } }
    }

    HoverHandler { id: hover }
    TapHandler {
        id: tap
        onTapped: root.toggled(!root.checked)
    }
}
