import QtQuick
import "../theme"

// Crisp recolorable SVG icon (served as a data URL by the Python IconService).
Item {
    id: root

    property string name: ""
    property color tint: Theme.textSecondary
    property real size: 16

    implicitWidth: size
    implicitHeight: size

    Image {
        anchors.fill: parent
        fillMode: Image.PreserveAspectFit
        source: root.name !== "" && Icons !== null
                ? Icons.url(root.name, root.tint.toString())
                : ""
        sourceSize.width: Math.max(1, Math.ceil(root.size * 2))
        sourceSize.height: Math.max(1, Math.ceil(root.size * 2))
        smooth: true
        visible: root.name !== "" && source !== ""
    }
}
