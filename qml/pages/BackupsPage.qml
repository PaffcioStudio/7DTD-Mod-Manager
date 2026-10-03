import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "modpacks"
    maxWidth: 1080

    // ------------------------------------------------------------------ #
    // modpack operations (migration stage 7)
    // ------------------------------------------------------------------ #
    readonly property bool anyModalOpen: createModal.opened || restoreModal.opened || deleteModal.opened
    readonly property bool contentLocked: anyModalOpen || unlockTimer.running
    onAnyModalOpenChanged: if (!anyModalOpen) unlockTimer.restart()
    Timer {
        id: unlockTimer
        interval: 600
    }

    function instanceOptions() {
        // instancje z katalogiem danych (domyslna jest pomijana)
        return Profiles.instanceOptions()
    }

    function openCreate() {
        createModal.instanceId = page.instanceOptions().length > 0
                                 ? page.instanceOptions()[0].value : ""
        createModal.open()
    }

    function openRestore(packName, instanceId, createdText, count) {
        restoreModal.packName = packName
        restoreModal.instanceId = instanceId
        restoreModal.createdText = createdText
        restoreModal.modCount = count
        restoreModal.open()
    }

    // ------------------------------------------------------------------ #
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingXl
        // modale są poza tym layoutem - blokada nie dotyka ich samych
        enabled: !contentLocked

        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            PrimaryButton {
                text: I18n.t("backups.create")
                icon: "plus"
                onClicked: page.openCreate()
            }
        }

        // ---- pack list --------------------------------------------------- #
        AppScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
                contentHeight: modpacksColumn.implicitHeight

            ColumnLayout {
                id: modpacksColumn
                width: Math.min(parent.width, page.contentWidth)
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Dimensions.spacingLg

                Repeater {
                    model: Modpacks.model

                    Item {
                        id: packDelegate
                        required property string packName
                    required property string instanceId
                        required property string packPath
                        required property string packSizeText
                        required property int packItemCount
                        required property string packCreatedText
                        required property string packUpdatedText

                        Layout.fillWidth: true
                        implicitHeight: 132

                        Rectangle {
                            anchors.fill: parent
                            radius: Dimensions.radiusLg
                            color: packHover.hovered ? Theme.bg3 : Theme.bg2
                            border.width: 1
                            border.color: packHover.hovered ? Theme.borderHover : Theme.border
                            Behavior on color { ColorAnimation { duration: Theme.fast } }
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.margins: 14
                            width: 3
                            radius: 2
                            color: Theme.accent
                            opacity: 0.85
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 32
                            anchors.rightMargin: 18
                            anchors.topMargin: 16
                            anchors.bottomMargin: 14
                            spacing: 6

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Text {
                                    text: packDelegate.packName
                                    color: Theme.text
                                    font.pixelSize: Typography.h2
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: I18n.format("backups.items", {count: packDelegate.packItemCount})
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.small
                                    font.family: Theme.fontFamily
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                Icon {
                                    name: "folder"
                                    size: 12
                                    tint: Theme.textSecondary
                                    Layout.alignment: Qt.AlignVCenter
                                }

                                Text {
                                    text: packDelegate.packPath
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                            }

                            Item { Layout.fillHeight: true }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: packDelegate.packSizeText
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.small
                                    font.weight: Font.Medium
                                    font.family: Theme.fontFamily
                                }

                                Text {
                                    text: "·  " + I18n.format("backups.created", {date: packDelegate.packCreatedText})
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                }

                                Text {
                                    visible: packDelegate.packUpdatedText !== packDelegate.packCreatedText
                                    text: "·  " + I18n.format("backups.updated", {date: packDelegate.packUpdatedText})
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                }

                                Item { Layout.fillWidth: true }

                                SecondaryButton {
                                    text: I18n.t("backups.update")
                                    icon: "refresh-cw"
                                    compact: true
                                    enabled: !Game.isRunning
                                    onClicked: Modpacks.updateBackup(packDelegate.instanceId)
                                }

                                SecondaryButton {
                                    text: I18n.t("backups.restore")
                                    icon: "play"
                                    compact: true
                                    onClicked: page.openRestore(packDelegate.packName, packDelegate.instanceId, packDelegate.packCreatedText, packDelegate.packItemCount)
                                }

                                IconButton {
                                    icon: "trash"
                                    tooltip: I18n.t("backups.delete.tooltip")
                                    buttonSize: 30
                                    iconSize: 14
                                    danger: true
                                    onClicked: {
                                        deleteModal.packToDelete = packDelegate.instanceId
                                        deleteModal.ask(
                                            I18n.t("backups.delete.title"),
                                            I18n.format("backups.delete.message", {name: packDelegate.packName}),
                                            I18n.t("backups.delete.confirm"), true)
                                    }
                                }
                            }
                        }

                        HoverHandler { id: packHover }
                    }
                }

                // empty state
                EmptyState {
                    visible: Modpacks.count === 0
                    Layout.fillWidth: true
                    icon: "package"
                    title: I18n.t("backups.empty.title")
                    subtitle: I18n.t("backups.empty.subtitle")
                    actionText: I18n.t("backups.empty.create")
                    onActionTriggered: page.openCreate()
                }
            }
        }
    }

    // ---- create modal ------------------------------------------------------ #
    Modal {
        id: createModal
        title: I18n.t("backups.create.title")
        iconName: "package"

        property string instanceId: ""

        ColumnLayout {
            spacing: 12
            Layout.fillWidth: true

            Text {
                color: Theme.textSecondary
                font.pixelSize: Typography.small
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                text: I18n.t("backups.create.description")
            }

            ColumnLayout {
                spacing: 6
                Layout.fillWidth: true
                Text { text: I18n.t("backups.instance"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                DropdownButton {
                    id: createInstanceDropdown
                    Layout.fillWidth: true
                    options: page.instanceOptions().length > 0
                             ? page.instanceOptions()
                             : [{ value: "", label: I18n.t("backups.noInstance") }]
                    value: createModal.instanceId
                    onPicked: (value) => {
                        if (value !== "") {
                            createModal.instanceId = value
                            createInstanceDropdown.value = value
                        }
                    }
                }
                Text {
                    visible: page.instanceOptions().length === 0
                    color: Theme.danger
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    text: I18n.t("backups.noInstance.message")
                }
                SecondaryButton {
                    visible: page.instanceOptions().length === 0
                    text: I18n.t("backups.goInstances")
                    icon: "layers"
                    onClicked: {
                        createModal.close()
                        Bus.goTo("profiles")
                    }
                }
            }
        }

        footer: [
            PrimaryButton {
                text: I18n.t("backups.create")
                icon: "check"
                disabled: createModal.instanceId === "" || Game.isRunning
                onClicked: {
                    if (Modpacks.createBackup(createModal.instanceId))
                        createModal.close()
                }
            }
        ]
    }

    // ---- restore modal ------------------------------------------------------ #
    Modal {
        id: restoreModal
        title: I18n.t("backups.restore.title")
        iconName: "alert-triangle"

        property string packName: ""
        property string instanceId: ""
        property string createdText: ""
        property int modCount: 0

        ColumnLayout {
            spacing: 12
            Layout.fillWidth: true

            Text {
                color: Theme.text
                font.pixelSize: Typography.body
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                text: I18n.format("backups.restore.instance", {name: restoreModal.packName})
                      + (restoreModal.createdText !== "" ? I18n.format("backups.restore.created", {date: restoreModal.createdText}) : "")
            }

            Text {
                color: Theme.danger
                font.pixelSize: Typography.small
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                text: I18n.t("backups.restore.warning")
            }
        }

        footer: [
            SecondaryButton { text: I18n.t("backups.cancel"); onClicked: restoreModal.close() },
            PrimaryButton {
                text: I18n.t("backups.restore.action")
                icon: "check"
                disabled: restoreModal.instanceId === "" || Game.isRunning
                onClicked: {
                    Modpacks.restoreBackup(restoreModal.instanceId)
                    restoreModal.close()
                }
            }
        ]
    }

    // ---- delete confirm ------------------------------------------------------ #
    ConfirmModal {
        id: deleteModal
        property string packToDelete: ""
        onConfirmed: Modpacks.deleteBackup(packToDelete)
    }
}
