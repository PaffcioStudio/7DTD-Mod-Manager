import QtQuick
import "../theme"

// Rounded filter chip with count badge ("All 23", "Enabled 20", …).
Item {
    id: root

    signal clicked()

    property string label: ""
    property int count: -1
    property bool active: false

    implicitHeight: 32
    implicitWidth: contentRow.implicitWidth + 30

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.active ? Theme.accentSoft
             : (hover.hovered ? Theme.bg3 : Theme.bg2)
        border.width: 1
        border.color: root.active ? Theme.rgba(Theme.accent, 0.5) : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    Row {
        id: contentRow
        anchors.centerIn: parent
        spacing: 7

        Text {
            text: root.label
            color: root.active ? Theme.accent
                 : (hover.hovered ? Theme.text : Theme.textSecondary)
            font.pixelSize: Typography.small + 0.5
            font.weight: root.active ? Font.DemiBold : Font.Medium
            font.family: Theme.fontFamily
            anchors.verticalCenter: parent.verticalCenter

            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }

        Text {
            text: root.count >= 0 ? root.count : ""
            color: root.active ? Theme.rgba(Theme.accent, 0.85) : Theme.textMuted
            font.pixelSize: Typography.caption
            font.weight: Font.Medium
            font.family: Theme.fontFamily
            anchors.verticalCenter: parent.verticalCenter
            visible: root.count >= 0
        }
    }

    HoverHandler { id: hover }
    TapHandler { onTapped: root.clicked() }
}
