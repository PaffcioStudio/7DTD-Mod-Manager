import QtQuick
import "../theme"

// Page container with enter/exit animation managed by PageStack.
// The page fills the stack; the inner container carries the animation so
// anchors and motion never fight each other.
Item {
    id: page

    anchors.fill: parent

    property string pageName: ""
    property bool active: false
    property real maxWidth: Dimensions.maxContentW

    // helper width for inner content columns (centered, capped)
    readonly property real contentWidth: Math.min(width - 2 * Dimensions.pagePad, maxWidth)

    visible: false

    default property alias content: container.data

    Item {
        id: container
        anchors.fill: parent

        opacity: page.active ? 1 : 0
        y: page.active ? 0 : 16

        Behavior on opacity { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
        Behavior on y { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
    }

    onActiveChanged: {
        if (active) visible = true
        else hideTimer.restart()
    }

    Timer {
        id: hideTimer
        interval: 380
        onTriggered: if (!page.active) page.visible = false
    }
}
