import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import "../theme"

// Compact square icon button with hover state, press feedback and tooltip.
Item {
    id: root

    signal clicked()

    property string icon: ""
    property real iconRotation: 0
    property color tint: Theme.textSecondary
    property color hoverTint: Theme.text
    property real iconSize: 16
    property real buttonSize: 34
    property real radius: 8
    property string tooltip: ""
    property bool danger: false
    property bool checked: false
    property color checkedTint: Theme.accent
    property bool disabled: false

    implicitWidth: buttonSize
    implicitHeight: buttonSize

    readonly property bool hovered: hover.hovered && !root.disabled
    readonly property color effectiveTint: root.disabled ? Theme.textMuted
        : checked ? checkedTint
        : (hovered ? (danger ? Theme.danger : hoverTint)
                   : (danger ? Theme.danger : tint))

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: root.radius
        color: root.checked ? Theme.accentSoft
             : (root.hovered ? Theme.bg3 : "transparent")
        border.width: root.hovered || root.checked ? 1 : 0
        border.color: root.checked ? Theme.rgba(root.checkedTint, 0.4) : Theme.borderHover
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }

    Icon {
        anchors.centerIn: parent
        name: root.icon
        rotation: root.iconRotation
        tint: root.effectiveTint
        size: root.iconSize
    }

    HoverHandler { id: hover }

    // MouseArea (nie TapHandler): przejmuje klik wylacznie - pasywny
    // TapHandler byl anulowany przez blokujacy scrim modala pod spodem
    MouseArea {
        id: tap
        anchors.fill: parent
        enabled: !root.disabled
        hoverEnabled: true
        cursorShape: root.disabled ? Qt.ArrowCursor : Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    scale: tap.containsPress ? 0.92 : 1.0
    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }

    // Tooltip renderujemy w warstwie Overlay okna. Dzięki temu może wyjść
    // poza rodzica z clip: true (np. kartę modala) i zawsze pojawia się
    // nad całą aplikacją.
    readonly property var tipHost: Overlay.overlay
        ? Overlay.overlay
        : (Window.window ? Window.window.contentItem : root)
    readonly property point tipOrigin: root.mapToItem(root.tipHost, 0, 0)

    readonly property bool tipBelow: {
        if (!hover.hovered || !Window.window)
            return false
        return root.tipOrigin.y < 42
    }

    // keep the tooltip inside the window horizontally (clamp around the button)
    readonly property real tipGlobalX: {
        const host = root.tipHost
        const maxX = Math.max(8, host.width - tip.width - 8)
        const centered = root.tipOrigin.x + (root.width - tip.width) / 2
        return Math.max(8, Math.min(maxX, centered))
    }

    // ---- tooltip -------------------------------------------------------- #
    Item {
        id: tip
        parent: root.tipHost
        opacity: 0
        visible: opacity > 0.01
        width: tipText.implicitWidth + 18
        height: 26
        x: root.tipGlobalX
        y: root.tipBelow
           ? root.tipOrigin.y + root.height + 8
           : root.tipOrigin.y - height - 8
        z: 10000

        Rectangle {
            anchors.fill: parent
            radius: 7
            color: Theme.bg2
            border.width: 1
            border.color: Theme.borderHover
        }

        Text {
            id: tipText
            anchors.centerIn: parent
            text: root.tooltip
            color: Theme.textSecondary
            font.pixelSize: Typography.small
            font.family: Theme.fontFamily
        }

        Behavior on opacity { NumberAnimation { duration: 160 } }

        Timer {
            interval: 550
            running: root.hovered && root.tooltip !== ""
            onTriggered: tip.opacity = 1
        }
        Connections {
            target: hover
            function onHoveredChanged() {
                if (!hover.hovered) tip.opacity = 0
            }
        }
    }
}
