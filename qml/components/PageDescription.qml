import QtQuick
import QtQuick.Layouts
import "../theme"

// Compact page description kept inside the content area, so long copy never
// pushes global header controls out of view.
Item {
    id: root

    property string text: ""
    property real maxTextWidth: 760

    implicitHeight: description.implicitHeight
    Layout.fillWidth: true
    visible: root.text.trim() !== ""

    Text {
        id: description
        width: Math.min(root.width, root.maxTextWidth)
        text: root.text
        color: Theme.textMuted
        font.pixelSize: Typography.caption + 0.5
        font.family: Theme.fontFamily
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        elide: Text.ElideRight
    }
}
