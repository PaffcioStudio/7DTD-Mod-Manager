import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

Modal {
    id: root
    title: I18n.t("logs.title") + " · " + Logs.instanceName
    cardWidth: 1000
    function showFor(instanceId) { Logs.select(instanceId); open() }
    ColumnLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(580, root.height - 180)
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Text { Layout.fillWidth: true; text: I18n.t("logs.help"); color: Theme.textMuted; wrapMode: Text.Wrap; font.family: Theme.fontFamily }
            SecondaryButton { text: I18n.t("protons.refresh"); onClicked: Logs.refresh() }
        }
        AppScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 220
            contentHeight: files.implicitHeight
            ColumnLayout {
                id: files
                width: parent.width
                Repeater {
                    model: Logs.files
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: modelData.date + " · " + I18n.t("logs.kind." + modelData.kind) + " · " + modelData.name; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Typography.small }
                            Text { Layout.fillWidth: true; text: modelData.path; color: Theme.textMuted; font.pixelSize: Typography.micro; elide: Text.ElideMiddle }
                        }
                        SecondaryButton { text: I18n.t("logs.preview"); visible: modelData.text; compact: true; onClicked: Logs.preview(modelData.path) }
                        IconButton { icon: "file-text"; tooltip: I18n.t("logs.openFile"); onClicked: Logs.openFile(modelData.path) }
                        IconButton { icon: "folder"; tooltip: I18n.t("logs.openFolder"); onClicked: Logs.openFolder(modelData.path) }
                    }
                }
                Text { visible: Logs.files.length === 0; text: I18n.t("logs.empty"); color: Theme.textMuted }
            }
        }
        Text { text: I18n.t("logs.tail"); color: Theme.textMuted; font.pixelSize: Typography.micro }
        Text { Layout.fillWidth: true; text: Logs.selectedPath; elide: Text.ElideMiddle; color: Theme.textSecondary; font.pixelSize: Typography.micro }
        ScrollView {
            Component.onCompleted: contentItem.acceptedButtons = Qt.NoButton
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            TextArea {
                text: Logs.previewText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: Theme.text
                font.family: "monospace"
                font.pixelSize: 12
                background: Rectangle { color: Theme.bg2; radius: 6 }
            }
        }
    }
}
