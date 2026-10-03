import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Conflict pair card for the Conflicts page.
Item {
    id: root

    signal viewModRequested(string modId)
    signal resolveRequested(string keepId, string disableId)

    property string modAId: ""
    property string modAName: ""
    property string modBId: ""
    property string modBName: ""
    property string fileText: ""
    property string reasonText: ""

    implicitHeight: content.implicitHeight + 48

    // ---- card background -------------------------------------------------- #
    Rectangle {
        anchors.fill: parent
        radius: Dimensions.radiusLg
        color: Theme.bg2
        border.width: 1
        border.color: Theme.rgba(Theme.warning, 0.3)
    }

    // warning ribbon
    Rectangle {
        anchors.top: parent.top
        anchors.topMargin: 1
        anchors.left: parent.left
        anchors.leftMargin: 20
        anchors.right: parent.right
        anchors.rightMargin: 20
        height: 3
        radius: 2
        opacity: 0.7

        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Theme.warning }
            GradientStop { position: 1; color: Theme.rgba(Theme.warning, 0.05) }
        }
    }

    // ---- content (sizes the card) ------------------------------------------ #
    ColumnLayout {
        id: content
        x: 22
        y: 24
        width: root.width - 44
        spacing: 14

        // pair row
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ConflictModPill {
                modId: root.modAId
                name: root.modAName
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                onClicked: root.viewModRequested(root.modAId)
            }

            ColumnLayout {
                spacing: 3
                Layout.alignment: Qt.AlignHCenter

                Icon {
                    name: "shield-alert"
                    tint: Theme.warning
                    size: 18
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: I18n.t("conflicts.card.inConflictWith")
                    color: Theme.textMuted
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                    Layout.alignment: Qt.AlignHCenter
                }
            }

            ConflictModPill {
                modId: root.modBId
                name: root.modBName
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                onClicked: root.viewModRequested(root.modBId)
            }
        }

        // reason
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: reasonText.implicitHeight + reasonText2.implicitHeight + 34
            radius: Dimensions.radiusMd
            color: Theme.rgba(Theme.warning, 0.07)
            border.width: 1
            border.color: Theme.rgba(Theme.warning, 0.22)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 4

                Text {
                    id: reasonText
                    Layout.fillWidth: true
                    text: I18n.format("conflicts.card.reason", {file: root.fileText})
                    color: Theme.warning
                    font.pixelSize: Typography.small
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                }

                Text {
                    id: reasonText2
                    Layout.fillWidth: true
                    text: I18n.resolveMessage(root.reasonText)
                    color: Theme.textSecondary
                    font.pixelSize: Typography.small
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                    lineHeight: 1.4
                }
            }
        }

        // quick resolve
        Row {
            spacing: 10

            SecondaryButton {
                text: I18n.format("conflicts.card.keepA", {name: root.modAName.split(" ")[0]})
                icon: "check"
                compact: true
                onClicked: root.resolveRequested(root.modAId, root.modBId)
            }

            SecondaryButton {
                text: I18n.format("conflicts.card.keepB", {name: root.modBName.split(" ")[0]})
                icon: "check"
                compact: true
                onClicked: root.resolveRequested(root.modBId, root.modAId)
            }

            SecondaryButton {
                text: I18n.t("conflicts.card.details")
                icon: "chevron-right"
                compact: true
                ghost: true
                onClicked: root.viewModRequested(root.modAId)
            }
        }
    }

    component ConflictModPill: Item {
        id: pill

        signal clicked()
        property string modId: ""
        property string name: ""

        implicitHeight: 54

        Rectangle {
            anchors.fill: parent
            radius: Dimensions.radiusMd
            color: hover.hovered ? Theme.bg3 : Theme.bg2
            border.width: 1
            border.color: hover.hovered ? Theme.borderHover : Theme.border

            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10

            Item {
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredWidth: 34
                Layout.preferredHeight: 34

                Rectangle {
                    anchors.fill: parent
                    radius: 10
                    color: Theme.rgba(Theme.warning, 0.12)
                    border.width: 1
                    border.color: Theme.rgba(Theme.warning, 0.3)
                }

                Icon {
                    anchors.centerIn: parent
                    name: "package"
                    tint: Theme.warning
                    size: 15
                }
            }

            Text {
                text: pill.name
                color: Theme.text
                font.pixelSize: Typography.small + 0.5
                font.weight: Font.Medium
                font.family: Theme.fontFamily
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        HoverHandler { id: hover }
        TapHandler { onTapped: pill.clicked() }
    }
}
