import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Custom dropdown (button + styled Popup) - used for sorting & settings.
// options: [{ value, label, icon(optional) }]
//
// Popup parent = Overlay.overlay: menu zawsze renderuje się NAD scrimem
// modala (ModalBase Item z: 500) i pozycjonowane jest we współrzędnych
// okna (mapToItem z Overlay.overlay). Bez tego menu wewnątrz modala
// lądowało POD scrimem - przyciemnione i nieklikalne.
Item {
    id: root

    signal picked(string value)

    property var options: []
    property string value: ""
    property string caption: ""        // small label above the button (optional)
    property bool compact: false
    property bool disabled: false
    readonly property int optionHeight: 36
    readonly property bool menuOpened: menu.opened

    readonly property string currentLabel: {
        for (let i = 0; i < options.length; i++) {
            if (options[i].value === value) return options[i].label !== undefined ? I18n.resolveMessage(String(options[i].label)) : ""
        }
        return ""
    }

    implicitHeight: compact ? Dimensions.controlHSm : Dimensions.controlH
    implicitWidth: buttonRow.implicitWidth + (compact ? 24 : 34)

    Rectangle {
        anchors.fill: parent
        radius: 9
        color: menu.opened ? Theme.bg3 : (hover.hovered ? Theme.bg3 : Theme.bg2)
        border.width: 1
        border.color: root.disabled ? Theme.border
                     : menu.opened ? Theme.rgba(Theme.accent, 0.5) : Theme.border
        opacity: root.disabled ? 0.55 : 1
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }

    RowLayout {
        id: buttonRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 8

        Text {
            text: root.caption !== "" ? root.caption + ": " : ""
            color: Theme.textMuted
            font.pixelSize: root.compact ? Typography.small : Typography.body
            font.family: Theme.fontFamily
            visible: root.caption !== ""
        }

        Text {
            text: root.currentLabel
            color: Theme.text
            font.pixelSize: root.compact ? Typography.small : Typography.body
            font.weight: Font.Medium
            font.family: Theme.fontFamily
            elide: Text.ElideRight
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
        }

        Icon {
            name: "chevron-down"
            size: 14
            tint: Theme.textMuted
            rotation: menu.opened ? 180 : 0
            Layout.alignment: Qt.AlignVCenter
            Behavior on rotation { NumberAnimation { duration: Theme.fast } }
        }
    }

    HoverHandler { id: hover }

    function closeMenu() { menu.close() }

    // Popup ma CloseOnPressOutside: klik w przycisk przy otwartej liście zamyka
    // ją już przy NACIŚNIĘCIU (to "outside" względem popupu), a TapHandler
    // odpala się dopiero przy puszczeniu - wcześniej to ponownie otwierało
    // listę. Zapamiętujemy moment naciśnięcia i zamknięcia: jeśli zamknięcie
    // nastąpiło przy tym samym kliknięciu, tap ma tylko zostawić listę zamkniętą.
    property double _pressAt: 0
    property double _closedAt: -10000

    TapHandler {
        enabled: !root.disabled
        onPressedChanged: if (pressed) root._pressAt = Date.now()
        onTapped: {
            if (menu.opened)
                menu.close()
            else if (Math.abs(root._closedAt - root._pressAt) > 200)
                root.openMenu()
        }
    }

    function openMenu() {
        const overlay = Overlay.overlay
        if (!overlay)
            return

        menu.parent = overlay
        menu.width = Math.max(root.width, 226)
        // sufit wysokości: widoczne ~6 pozycji jednocześnie, dłuższa lista
        // scrolluje się w środku zamiast wychodzić poza ekran
        menu.maxMenuHeight = Math.min(
            Math.max(200, overlay.height - 32),
            root.optionHeight * 6 + menu.topPadding + menu.bottomPadding + 2)

        const margin = 8
        const below = root.mapToItem(overlay, 0, root.height)
        const top = root.mapToItem(overlay, 0, 0)
        const popupH = menu.implicitHeight
        const belowY = below.y + 6
        const aboveY = top.y - popupH - 6

        menu.x = Math.max(margin, Math.min(below.x, overlay.width - menu.width - margin))
        menu.y = belowY + popupH <= overlay.height - margin || aboveY < margin
                 ? belowY
                 : Math.max(margin, aboveY)
        menu.open()
        menu.forceActiveFocus()
    }

    Popup {
        id: menu
        parent: Overlay.overlay
        z: 10000
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onAboutToHide: root._closedAt = Date.now()
        padding: 6
        property real maxMenuHeight: 400   // nadpisywane w openMenu() wg okna
        implicitWidth: Math.max(root.width, 226)
        implicitHeight: Math.min(contentCol.implicitHeight + topPadding + bottomPadding,
                                 menu.maxMenuHeight)

        background: Rectangle {
            radius: 11
            color: Theme.bg2
            border.color: Theme.borderHover
        }

        contentItem: Item {
            implicitWidth: contentCol.implicitWidth
            implicitHeight: Math.min(contentCol.implicitHeight,
                                     menu.maxMenuHeight - menu.topPadding - menu.bottomPadding)

            Flickable {
                id: flick
                anchors.fill: parent
                contentHeight: contentCol.implicitHeight
                contentWidth: width
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickDeceleration: 5200
                maximumFlickVelocity: 1800

                Column {
                    id: contentCol
                    width: flick.width

                    Repeater {
                        model: root.options

                        delegate: Item {
                            id: item
                            required property var modelData

                            width: menu.width - menu.leftPadding - menu.rightPadding
                            height: root.optionHeight
                            readonly property bool selected: item.modelData.value === root.value

                            Rectangle {
                                anchors.fill: parent
                                radius: 8
                                color: rowMouse.containsMouse ? Theme.bg3 : "transparent"
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8

                                Icon {
                                    name: "check"
                                    size: 15
                                    tint: Theme.accent
                                    visible: item.selected
                                    Layout.preferredWidth: 15
                                }
                                Item { Layout.preferredWidth: item.selected ? 0 : 15 }

                                Text {
                                    text: I18n.resolveMessage(item.modelData.label)
                                    color: rowMouse.containsMouse ? Theme.text : Theme.textSecondary
                                    font.pixelSize: Typography.small + 0.5
                                    font.weight: item.selected ? Font.DemiBold : Font.Medium
                                    font.family: Theme.fontFamily
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                Icon {
                                    name: item.modelData.icon || ""
                                    size: 15
                                    tint: Theme.textMuted
                                    visible: (item.modelData.icon || "") !== ""
                                    Layout.preferredWidth: visible ? 15 : 0
                                }
                            }

                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton
                                onClicked: {
                                    root.picked(item.modelData.value)
                                    menu.close()
                                }
                            }
                        }
                    }
                }

                // widoczny pasek gdy lista się mieści w sufit
                ScrollBar.vertical: AppScrollBar {
                    policy: flick.contentHeight > flick.height
                            ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
                }

                // scroll myszki po opcjach (krótszy krok - wiersz ma 36 px)
                WheelHandler {
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: (event) => {
                        const maxY = Math.max(0, flick.contentHeight - flick.height)
                        if (maxY <= 0) { event.accepted = false; return }
                        const step = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                        flick.contentY = Math.max(0, Math.min(maxY, flick.contentY - step))
                        event.accepted = true
                    }
                }
            }
        }
    }
}
