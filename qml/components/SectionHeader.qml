import QtQuick
import QtQuick.Layouts
import "../theme"

// Page section header: title + caption on the left, optional action on the right.
RowLayout {
    id: root

    property string title: ""
    property string caption: ""
    default property alias action: actionSlot.data

    spacing: 12
    layoutDirection: Qt.LeftToRight

    ColumnLayout {
        spacing: 2
        Layout.fillWidth: true

        Text {
            text: root.title
            color: Theme.text
            font.pixelSize: Typography.h2
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        Text {
            visible: root.caption !== ""
            text: root.caption
            color: Theme.textMuted
            font.pixelSize: Typography.caption + 0.5
            font.family: Theme.fontFamily
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
    }

    Item {
        id: actionSlot
        Layout.alignment: Qt.AlignVCenter
        implicitWidth: childrenRect.width
        implicitHeight: childrenRect.height
    }
}
