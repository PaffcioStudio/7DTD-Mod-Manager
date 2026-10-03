import QtQuick
import "../theme"

// Surface panel (card) with default content slot.
Item {
    id: root

    default property alias content: inner.data
    property real pad: 20
    property color background: Theme.bg2
    property color borderColor: Theme.border

    implicitHeight: inner.childrenRect.height + pad * 2
    implicitWidth: inner.childrenRect.width + pad * 2

    Rectangle {
        anchors.fill: parent
        radius: Dimensions.radiusLg
        color: root.background
        border.width: 1
        border.color: root.borderColor
    }

    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: root.pad
    }
}
