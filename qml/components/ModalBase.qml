import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "../theme"
import "../i18n"

// Base for modal dialogs: scrim + animated centered card, hosted in the
// window overlay so it covers the entire window (sidebar included).
//
// The card renders its own chrome (title row, divider, footer) and hosts
// custom rows in the middle column:
//     * default property `content`  -> rows placed between title and footer
//     * `footer`                     -> row of buttons (aligned right)
//
// The card height follows the content's implicitHeight - no childrenRect
// and no fill-anchored children, so no binding loops.
Item {
    id: root

    default property alias content: contentCol.data
    property alias footer: footerRow.data
    property string title: ""
    property string iconName: ""
    property color iconTint: Theme.accent
    property real cardWidth: 470
    property bool opened: false

    signal closeRequested()

    function beginCloseGuard() {
        closeGuard = true
        guardTimer.restart()
    }
    Timer {
        id: guardTimer
        interval: 500
        onTriggered: root.closeGuard = false
    }

    Keys.onEscapePressed: closeRequested()

    parent: Overlay.overlay
    anchors.fill: parent
    z: 500
    // closeGuard: po zamknieciu scrim zostaje (niewidoczny) jeszcze na
    // GUARD_MS - doklikniecie w oknie fade-out (np. podwojne klikniecie
    // w przycisk Potwierdz) nie moze trafic w karte strony pod spodem
    property bool closeGuard: false
    visible: opened || closeGuard || opacity > 0.001
    opacity: opened ? 1 : 0
    // enabled trzyma blokadę takze w trakcie fade-out - klik 'przelatujący'
    // do strony w trakcie zanikania otwierał modal pod spodem
    enabled: opened || closeGuard || opacity > 0.01

    // zamkniecie modala domyka tez Menu/Popup otwarte w jego tresci
    // (bez tego lista dropdownu zostawala 'sierota' nad strona)

    function closePopupsIn(item) {
        // Popup (Menu) NIE jest Itemem - siedzi w Item.data (obok children),
        // wiec obchodzimy cala liste zasobow, nie tylko children
        for (let i = 0; i < item.data.length; i++) {
            const obj = item.data[i]
            if (obj.close !== undefined && typeof obj.close === "function") {
                obj.close()
                continue
            }
            if (obj.children !== undefined)
                closePopupsIn(obj)
        }
    }

    Behavior on opacity { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
    onOpenedChanged: {
        if (opened)
            beginCloseGuard()
        else
            closePopupsIn(contentCol)
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.scrimColor
        opacity: root.opened ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.normal } }

        // Blokuje WSZYSTKIE interakcje z tym, co pod scrimem. Celowo NIE zamyka
        // modala kliknieciem w tlo - zamykanie: X, Anuluj, Esc.
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.AllButtons
        }
    }


    Item {
        id: center
        anchors.centerIn: parent
        width: Math.min(root.cardWidth, root.width - 48)
        height: cardLayout.implicitHeight + 48

        Behavior on height { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

        scale: root.opened ? 1 : 0.95
        opacity: root.opened ? 1 : 0

        Behavior on scale { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutBack; easing.overshoot: 1.05 } }
        Behavior on opacity { NumberAnimation { duration: Theme.normal } }

        SoftShadow { source: card; elevation: 3 }

        Rectangle {
            id: card
            objectName: "modalCard"
            anchors.fill: parent
            radius: Dimensions.radiusLg
            color: Theme.bg2
            border.width: 1
            border.color: Theme.borderHover
            clip: true

            // Sam prostokąt karty nie przechwytuje kliknięć w puste miejsca.
            // Ten handler gwarantuje, że żaden klik z wnętrza modala nie
            // przejdzie do strony znajdującej się pod nim. Dzieci (przyciski,
            // pola tekstowe itd.) są wyżej w drzewie i nadal dostają zdarzenia.
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
                z: -1
            }
        }

        ColumnLayout {
            id: cardLayout
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            anchors.topMargin: 24
            spacing: 18

            // ---- title row -------------------------------------------------- #
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item {
                    width: 38
                    height: 38
                    Layout.alignment: Qt.AlignVCenter
                    visible: root.iconName !== ""

                    Rectangle {
                        anchors.fill: parent
                        radius: 11
                        color: Theme.rgba(root.iconTint, 0.14)
                        border.width: 1
                        border.color: Theme.rgba(root.iconTint, 0.3)
                    }

                    Icon {
                        anchors.centerIn: parent
                        name: root.iconName
                        tint: root.iconTint
                        size: 18
                    }
                }

                Text {
                    text: root.title
                    color: Theme.text
                    font.pixelSize: Typography.h2 + 1
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                IconButton {
                    icon: "x"
                    buttonSize: 30
                    iconSize: 15
                    tooltip: I18n.t("common.close")
                    onClicked: root.closeRequested()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Theme.border
            }

            // ---- custom content ---------------------------------------------- #
            ColumnLayout {
                id: contentCol
                Layout.fillWidth: true
                spacing: 12
                visible: contentCol.implicitHeight > 0
            }

            // ---- footer ------------------------------------------------------ #
            Row {
                id: footerRow
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignRight
                spacing: 10
                visible: footerRow.implicitHeight > 0
            }
        }
    }
}
