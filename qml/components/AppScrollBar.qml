import QtQuick
import QtQuick.Controls.Basic
import "../theme"

// Minimal dark scrollbar.
ScrollBar {
    id: control

    implicitWidth: 10
    implicitHeight: 10

    contentItem: Rectangle {
        implicitWidth: 7
        implicitHeight: 7
        radius: 4
        color: control.pressed ? Theme.borderStrong
             : (control.hovered ? Theme.borderHover : Theme.textFaint)
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }

    background: Rectangle {
        implicitWidth: 7
        implicitHeight: 7
        radius: 4
        color: "transparent"
    }
}
