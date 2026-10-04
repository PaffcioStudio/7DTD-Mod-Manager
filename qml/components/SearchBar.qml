import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Pill search field with animated focus ring and clear button.
// State is owned by the caller:
//     searchText       -> bind to the shared search property (one-way in)
//     searchEdited(t)  -> caller writes it back to the backend
Item {
    id: root

    property string placeholder: I18n.t("globalSearch.placeholder")
    property string searchText: ""
    property real preferredWidth: 280
    property alias searchFocused: input.activeFocus

    // Non-text focus sink: clicking outside the search field must remove the
    // visual focus ring and keyboard focus from the TextInput completely.
    focus: false
    activeFocusOnTab: false
    signal searchEdited(string text)
    signal accepted()

    function forceFocusInput() {
        input.forceActiveFocus()
    }

    function clearFocus() {
        input.deselect()
        input.focus = false
        root.forceActiveFocus()
    }

    implicitHeight: 38
    implicitWidth: preferredWidth

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: 11
        color: input.activeFocus ? Theme.bg3 : Theme.bg2
        border.width: 1
        border.color: input.activeFocus ? Theme.rgba(Theme.accent, 0.6)
                    : hover.hovered ? Theme.borderHover
                    : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 13
        anchors.rightMargin: 8
        spacing: 9

        Icon {
            name: "search"
            size: 16
            Layout.alignment: Qt.AlignVCenter
            tint: input.activeFocus ? Theme.accent : Theme.textMuted
            Behavior on tint { ColorAnimation { duration: Theme.fast } }
        }

        TextInput {
            id: input
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            text: root.searchText
            color: Theme.text
            selectionColor: Theme.accentSoftUp
            selectedTextColor: Theme.text
            font.pixelSize: Typography.body
            font.family: Theme.fontFamily
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            activeFocusOnPress: true

            onTextEdited: root.searchEdited(input.text)
            onAccepted: root.accepted()
            Keys.onEscapePressed: {
                if (input.text !== "") root.searchEdited("")
                else input.focus = false
            }

            Text {
                anchors.fill: parent
                verticalAlignment: Text.AlignVCenter
                visible: input.text === ""
                text: root.placeholder
                color: Theme.textMuted
                font.pixelSize: Typography.body
                font.family: Theme.fontFamily
            }
        }

        IconButton {
            id: clearBtn
            icon: "x"
            buttonSize: 24
            iconSize: 13
            radius: 12
            tint: Theme.textMuted
            hoverTint: Theme.text
            visible: input.text !== ""
            opacity: visible ? 1 : 0
            Layout.alignment: Qt.AlignVCenter
            Behavior on opacity { NumberAnimation { duration: 120 } }
            onClicked: {
                input.text = ""
                root.searchEdited("")
            }
        }
    }

    HoverHandler { id: hover }
}
