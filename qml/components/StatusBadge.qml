import QtQuick
import "../theme"
import "../i18n"

// Soft tinted status badge:  ● Enabled   ↑ Update   ⚠ Conflict
Item {
    id: root

    property string key: "enabled"          // see Theme.statusColor()
    property string label: ""               // overrides the default label

    readonly property color c: Theme.statusColor(key)
    readonly property string text: label !== "" ? label : I18n.t("status." + key)


    readonly property string glyph: ({
        "update": "arrow-up",
        "conflict": "alert-triangle",
        "warning": "alert-triangle",
        "error": "x",
        "failed": "x",
        "success": "check",
        "completed": "check",
        "downloading": "download",
        "info": "info"
    })[key] || ""

    implicitHeight: 24
    implicitWidth: contentRow.implicitWidth + 20

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: Theme.rgba(root.c, 0.12)
        border.width: 1
        border.color: Theme.rgba(root.c, 0.32)
    }

    Row {
        id: contentRow
        anchors.centerIn: parent
        spacing: 6

        Item {
            width: root.glyph !== "" ? 13 : 7
            height: 13
            anchors.verticalCenter: parent.verticalCenter

            Rectangle {
                anchors.centerIn: parent
                width: 7
                height: 7
                radius: 4
                color: root.c
                visible: root.glyph === ""
            }

            Icon {
                anchors.centerIn: parent
                name: root.glyph
                tint: root.c
                size: 13
                visible: root.glyph !== ""
            }
        }

        Text {
            text: root.text
            color: root.c
            font.pixelSize: Typography.caption + 0.5
            font.weight: Font.Medium
            font.family: Theme.fontFamily
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
