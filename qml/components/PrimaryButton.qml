import QtQuick
import "../theme"

// Filled accent button - primary call to action.
Item {
    id: root

    signal clicked()

    property string text: ""
    property string icon: ""
    property bool large: false
    property bool danger: false
    property bool disabled: false
    property bool busy: false          // kręcąca się ikonka + blokada klikania

    readonly property color base: danger ? Theme.danger : Theme.accent
    readonly property real h: large ? Dimensions.controlHLg : Dimensions.controlH
    property real spin: 0

    onBusyChanged: if (!busy) spin = 0

    SequentialAnimation on spin {
        running: root.busy && root.visible
        loops: Animation.Infinite
        NumberAnimation { from: 0; to: 360; duration: 900; easing.type: Easing.Linear }
    }

    implicitWidth: content.implicitWidth + (large ? 44 : 32)
    implicitHeight: h

    scale: tap.pressed ? 0.98 : 1.0
    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: 10
        color: root.disabled ? Theme.bg3
             : tap.pressed ? Qt.darker(root.base, 1.12)
             : hover.hovered ? Qt.lighter(root.base, 1.10)
             : root.base
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }

    Row {
        id: content
        anchors.centerIn: parent
        spacing: 9

        Icon {
            name: root.icon
            size: root.large ? 18 : 16
            tint: root.disabled ? Theme.textMuted : Theme.accentForeground
            visible: root.icon !== ""
            rotation: root.spin
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.text
            color: root.disabled ? Theme.textMuted : Theme.accentForeground
            font.pixelSize: root.large ? Typography.body + 1 : Typography.body
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    HoverHandler { id: hover }
    TapHandler { id: tap; enabled: !root.disabled && !root.busy; onTapped: root.clicked() }
}
