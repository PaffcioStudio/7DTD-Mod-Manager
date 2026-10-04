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

    // Pozycję liczymy IMPERATYWNIE, w chwili pokazania i potem cyklicznie,
    // gdy tooltip jest widoczny. mapToItem() nie emituje zmian, więc binding
    // typu `readonly property point origin: mapToItem(...)` liczył się raz
    // (przy tworzeniu, gdy przycisk bywał jeszcze w (0,0) / na stronie
    // sprzed animacji przejścia / przed layoutem) i tooltip lądował w
    // przypadkowym miejscu, np. przy innym elemencie sidebara.
    function placeTip() {
        const host = root.tipHost
        if (!host || !root.visible)
            return
        const origin = root.mapToItem(host, 0, 0)
        // keep the tooltip inside the window horizontally (clamp around the button)
        const maxX = Math.max(8, host.width - tip.width - 8)
        const centered = origin.x + (root.width - tip.width) / 2
        tip.x = Math.max(8, Math.min(maxX, centered))
        // tuz przy gornej krawedzi okna tooltip idzie POD przycisk
        tip.y = origin.y < 42
            ? origin.y + root.height + 8
            : origin.y - tip.height - 8
    }

    // ---- tooltip -------------------------------------------------------- #
    Item {
        id: tip
        parent: root.tipHost
        opacity: 0
        visible: opacity > 0.01
        width: tipText.implicitWidth + 18
        height: 26
        objectName: "iconButtonTip"
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
            onTriggered: {
                root.placeTip()
                tip.opacity = 1
            }
        }
        // przycisk moze sie przesunac pod stojacym kursorem (scroll, layout,
        // animacja strony) - dopóki tooltip jest widoczny, trzymamy go przy nim
        Timer {
            interval: 50
            repeat: true
            running: tip.visible
            onTriggered: root.placeTip()
        }
        Connections {
            target: hover
            function onHoveredChanged() {
                if (!hover.hovered) tip.opacity = 0
            }
        }
    }
}
