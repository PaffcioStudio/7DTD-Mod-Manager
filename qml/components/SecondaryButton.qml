import QtQuick
import "../theme"

// Outlined / ghost button - secondary actions.
// variants: normal (border), ghost (no border), danger (red text).
Item {
    id: root

    signal clicked()

    property string text: ""
    property string icon: ""
    property bool large: false
    property bool ghost: false
    property bool danger: false
    property bool disabled: false
    property bool compact: false
    property bool busy: false

    readonly property real h: large ? Dimensions.controlHLg
                          : compact ? Dimensions.controlHSm
                          : Dimensions.controlH
    readonly property color textColor: danger ? Theme.danger
        : (hover.hovered ? Theme.text : Theme.textSecondary)

    implicitWidth: content.implicitWidth + (large ? 40 : 28)
    implicitHeight: h
    onBusyChanged: if (!busy) busyIcon.rotation = 0

    scale: tap.pressed ? 0.98 : 1.0
    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: hover.hovered ? Theme.bg3 : "transparent"
        border.width: ghost ? 0 : 1
        border.color: root.danger && hover.hovered ? Theme.rgba(Theme.danger, 0.55) : Theme.borderHover
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    Row {
        id: content
        anchors.centerIn: parent
        spacing: 8

        Icon {
            id: busyIcon
            name: root.icon
            size: root.compact ? 14 : 16
            tint: root.disabled ? Theme.textMuted : root.textColor
            visible: root.icon !== ""
            anchors.verticalCenter: parent.verticalCenter

            RotationAnimation on rotation {
                running: root.busy
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 900
            }
        }

        Text {
            text: root.text
            color: root.disabled ? Theme.textMuted : root.textColor
            font.pixelSize: root.compact ? Typography.small : Typography.body
            font.weight: Font.Medium
            font.family: Theme.fontFamily
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    HoverHandler { id: hover }
    TapHandler { id: tap; enabled: !root.disabled; onTapped: root.clicked() }
}
