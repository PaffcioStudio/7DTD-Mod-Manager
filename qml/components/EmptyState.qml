import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Friendly empty state (icon + title + subtitle + optional action).
Item {
    id: root

    property string icon: "package"
    property color tint: Theme.textMuted
    property string title: I18n.t("common.empty.defaultTitle")
    property string subtitle: ""
    property string actionText: ""
    signal actionTriggered()

    implicitHeight: column.implicitHeight
    implicitWidth: column.implicitWidth

    ColumnLayout {
        id: column
        width: root.width
        spacing: 10

        Item {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 26
            width: 84
            height: 84

            Rectangle {
                anchors.fill: parent
                radius: 26
                color: Theme.bg2
                border.width: 1
                border.color: Theme.border
            }

            Icon {
                anchors.centerIn: parent
                name: root.icon
                tint: root.tint
                size: 34
            }
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: root.title
            color: Theme.text
            font.pixelSize: Typography.h2
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: 26
            visible: root.subtitle !== ""
            text: root.subtitle
            color: Theme.textMuted
            font.pixelSize: Typography.body
            font.family: Theme.fontFamily
            horizontalAlignment: Text.AlignHCenter
        }

        SecondaryButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: 26
            visible: root.actionText !== ""
            text: root.actionText
            onClicked: root.actionTriggered()
        }
    }
}
