import QtQuick
import "../theme"

// Dark text field with animated focus ring.
Item {
    id: root

    property alias text: input.text
    property alias inputItem: input
    property string placeholder: ""
    property bool multiline: false
    signal editingFinished()
    signal accepted()   // Enter pressed (forwarded from the inner TextInput)

    implicitHeight: 38

    Rectangle {
        anchors.fill: parent
        radius: 9
        color: input.activeFocus ? Theme.bg3 : Theme.bg2
        border.width: 1
        border.color: input.activeFocus ? Theme.rgba(Theme.accent, 0.55)
                    : hover.hovered ? Theme.borderHover
                    : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    TextInput {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: root.multiline ? 9 : 0
        anchors.bottomMargin: root.multiline ? 9 : 0
        verticalAlignment: TextInput.AlignVCenter
        color: Theme.text
        selectionColor: Theme.accentSoftUp
        selectedTextColor: Theme.text
        font.pixelSize: Typography.body
        font.family: Theme.fontFamily
        clip: true
        wrapMode: root.multiline ? TextInput.Wrap : TextInput.NoWrap
        activeFocusOnPress: true
        onEditingFinished: root.editingFinished()
        onAccepted: root.accepted()

        Text {
            anchors.fill: parent
            verticalAlignment: root.multiline ? Text.AlignTop : Text.AlignVCenter
            visible: input.text === "" && !input.activeFocus
            text: root.placeholder
            color: Theme.textMuted
            font.pixelSize: Typography.body
            font.family: Theme.fontFamily
        }
    }

    HoverHandler { id: hover }
}
