import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Single toast notification (used as a Repeater delegate in ToastManager).
Item {
    id: root

    signal dismissed()

    property string message: ""
    property string level: "info"
    property string detail: ""

    readonly property color tint: Theme.statusColor(level)
    readonly property string glyph: ({
        "success": "check-circle",
        "warning": "alert-triangle",
        "error": "x-circle",
        "info": "info",
        "download": "download"
    })[level] || "info"

    width: 340
    height: Math.max(52, contentCol.implicitHeight + 22)

    opacity: 1
    readonly property int durationMs: 5800

    function dismiss() {
        if (!exitAnim.running) exitAnim.start()
    }

    Timer {
        interval: root.durationMs
        running: true
        onTriggered: root.dismiss()
    }

    SequentialAnimation {
        id: exitAnim

        ParallelAnimation {
            NumberAnimation { target: root; property: "opacity"; to: 0; duration: 180; easing.type: Easing.InQuad }
            NumberAnimation { target: root; property: "x"; to: 46; duration: 180; easing.type: Easing.InQuad }
        }

        ScriptAction { script: root.dismissed() }
    }

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: Theme.bg2
        border.width: 1
        border.color: Theme.rgba(root.tint, 0.38)
    }

    RowLayout {
        id: contentCol
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 14
        anchors.topMargin: 11
        anchors.bottomMargin: 11
        spacing: 11

        Item {
            Layout.preferredWidth: 28
            Layout.preferredHeight: 28
            Layout.alignment: Qt.AlignTop

            Rectangle {
                anchors.fill: parent
                radius: 9
                color: Theme.rgba(root.tint, 0.15)
            }

            Icon {
                anchors.centerIn: parent
                name: root.glyph
                tint: root.tint
                size: 16
            }
        }

        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true

            Text {
                text: root.message
                color: Theme.text
                font.pixelSize: Typography.small + 0.5
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                visible: root.detail !== ""
                text: root.detail
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                maximumLineCount: 2
            }
        }

        IconButton {
            Layout.alignment: Qt.AlignTop
            icon: "x"
            buttonSize: 22
            iconSize: 12
            radius: 6
            tint: Theme.textMuted
            tooltip: I18n.t("common.close")
            onClicked: root.dismiss()
        }
    }

    // Delikatny pasek odliczający czas życia toasta. Zmniejsza się od lewej
    // do prawej przez cały czas widoczności, dzięki czemu użytkownik od razu
    // widzi, ile czasu zostało.
    Rectangle {
        id: lifetimeTrack
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 2
        radius: 1
        color: Theme.rgba(root.tint, 0.72)
        clip: true

        Rectangle {
            id: lifetimeBar
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: parent.width
            radius: 1
            color: root.tint

            NumberAnimation on width {
                from: root.width
                to: 0
                duration: root.durationMs
                easing.type: Easing.Linear
                running: true
            }
        }
    }
}
