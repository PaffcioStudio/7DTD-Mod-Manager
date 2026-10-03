import QtQuick
import QtQuick.Layouts
import "../theme"

// Dashboard metric card: icon, big number, label. Hover lifts the card,
// entrance animation is staggered through the `shown` property.
Item {
    id: root

    signal clicked()

    property string title: ""
    property string value: "0"
    property string icon: "grid"
    property color tint: Theme.accent
    property bool shown: false
    property bool clickable: true

    implicitWidth: 200
    // Give the metric stack enough vertical breathing room so the large number
    // and label never collide with the card edge, especially in scaled themes.
    implicitHeight: 144 * Dimensions.scale
    Layout.minimumHeight: implicitHeight

    opacity: shown ? 1 : 0
    y: shown ? 0 : 14

    Behavior on opacity { NumberAnimation { duration: 420; easing.type: Easing.OutCubic } }
    Behavior on y { NumberAnimation { duration: 460; easing.type: Easing.OutCubic } }

    scale: tap.pressed ? 0.985 : 1.0
    Behavior on scale { NumberAnimation { duration: 90 } }

    SoftShadow {
        source: cardRect
        elevation: hover.hovered && root.clickable ? 2 : 1
        Behavior on elevation { NumberAnimation { duration: Theme.normal } }
    }

    Rectangle {
        id: cardRect
        anchors.fill: parent
        radius: Dimensions.radiusLg
        color: hover.hovered && root.clickable ? Theme.bg3 : Theme.bg2
        border.width: 1
        border.color: hover.hovered && root.clickable
             ? Theme.rgba(root.tint, 0.4)
             : Theme.border

        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 18
        anchors.rightMargin: 18
        anchors.topMargin: 16
        anchors.bottomMargin: 16
        spacing: 7

        Item {
            Layout.preferredWidth: 40
            Layout.preferredHeight: 40
            Layout.alignment: Qt.AlignTop | Qt.AlignLeft

            Rectangle {
                anchors.fill: parent
                radius: 12
                color: Theme.rgba(root.tint, 0.13)
                border.width: 1
                border.color: Theme.rgba(root.tint, 0.28)
            }

            Icon {
                anchors.centerIn: parent
                name: root.icon
                tint: root.tint
                size: 19
            }
        }

        Text {
            text: root.value
            color: Theme.text
            font.pixelSize: Typography.statBig
            font.weight: Font.Black
            font.family: Theme.fontFamily
            Layout.fillWidth: true
            Layout.preferredHeight: Math.ceil(Typography.statBig * 1.18)
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        Text {
            text: root.title
            color: Theme.textMuted
            font.pixelSize: Typography.caption
            font.letterSpacing: Typography.trackingCaps
            font.family: Theme.fontFamily
            Layout.fillWidth: true
            Layout.preferredHeight: Math.ceil(Typography.caption * 1.35)
            verticalAlignment: Text.AlignVCenter
        }

        Item { Layout.fillHeight: true; Layout.minimumHeight: 1 }
    }

    HoverHandler { id: hover; enabled: root.clickable }
    TapHandler { id: tap; enabled: root.clickable; onTapped: root.clicked() }
}
