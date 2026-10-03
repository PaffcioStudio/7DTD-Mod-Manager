import QtQuick
import "../theme"

// Slim animated progress bar.
Item {
    id: root

    property real value: 0.0        // 0..1
    property color barColor: Theme.accent
    property real barHeight: 6
    property bool animated: true
    property bool indeterminate: false   // nieznany rozmiar - przesuwający się segment

    // segment indeterminate startuje z ujemnym x - bez clipu wystaje poza
    // prowadnicę (na screenie wyjeżdżał nawet na sidebar)
    clip: true

    implicitHeight: barHeight

    Rectangle {
        anchors.fill: parent
        radius: barHeight / 2
        color: Theme.bg4
        opacity: 0.65
    }

    Rectangle {
        id: fill
        visible: !root.indeterminate
        height: parent.height
        radius: barHeight / 2
        color: root.barColor
        width: Math.max(0, Math.min(1.0, root.value)) * parent.width

        Behavior on width {
            enabled: root.animated
            NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
        }

        // subtle highlight line
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 1.5
            radius: 1
            color: Qt.lighter(root.barColor, 1.35)
            opacity: 0.7
            visible: root.value > 0.02
        }
    }

    // segment przesuwany tam i z powrotem, gdy nie znamy rozmiaru
    Rectangle {
        id: pulseFill
        visible: root.indeterminate
        height: parent.height
        radius: barHeight / 2
        color: root.barColor
        width: parent.width * 0.28
        x: -width + (parent.width + width) * travel

        property real travel: 0

        SequentialAnimation on travel {
            running: root.indeterminate && root.visible
            loops: Animation.Infinite
            NumberAnimation { from: 0; to: 1; duration: 1150; easing.type: Easing.InOutSine }
        }
        SequentialAnimation on opacity {
            running: root.indeterminate && root.visible
            loops: Animation.Infinite
            NumberAnimation { from: 0.55; to: 0.95; duration: 575; easing.type: Easing.InOutSine }
        }
    }
}
