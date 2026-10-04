import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "updates"
    maxWidth: 1000

    function updateAll() {
        const list = Mods.updatesList
        let started = 0
        for (let i = 0; i < list.length; i++) {
            if (Downloads.activeMap[list[i].id] === undefined) {
                Downloads.startModUpdate(list[i].id)
                started++
            }
        }
        if (started === 0) {
            Bus.toast(I18n.t("updates.noneToStart"), "info")
        } else {
            Bus.toast(I18n.format("updates.queuedToast", {count: started}), "info")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingXl

        PageDescription {
            text: Mods.updateCount > 0
                  ? I18n.format("updates.pageSubtitle.withUpdates", {count: Mods.updateCount})
                  : I18n.t("updates.pageSubtitle.current")
            maxTextWidth: 760
        }

        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            PrimaryButton {
                text: Mods.updateCheckBusy ? I18n.t("updates.checkBusy") : I18n.t("updates.check")
                icon: "refresh-cw"
                busy: Mods.updateCheckBusy
                disabled: Mods.updateCheckBusy
                onClicked: Mods.checkUpdates()
            }

            PrimaryButton {
                text: I18n.t("updates.updateAll")
                icon: "download"
                visible: Mods.updateCount > 0
                onClicked: page.updateAll()
            }
        }

        // ---- update list ------------------------------------------------- #
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            visible: Mods.updateCount > 0

            Repeater {
                model: Mods.updatesList

                Item {
                    id: updateDelegate
                    required property var modelData

                    Layout.fillWidth: true
                    implicitHeight: 86

                    UpdateCard {
                        anchors.fill: parent
                        name: updateDelegate.modelData.name
                        version: updateDelegate.modelData.version
                        newVersion: updateDelegate.modelData.newVersion
                        updatedAgo: updateDelegate.modelData.updatedAgo
                        sizeText: updateDelegate.modelData.sizeText
                        downloadState: Downloads.activeMap[updateDelegate.modelData.id] !== undefined
                                     ? Downloads.activeMap[updateDelegate.modelData.id]
                                     : null

                        onUpdateRequested: Downloads.startModUpdate(updateDelegate.modelData.id)
                    }
                }
            }
        }

        // ---- all done ------------------------------------------------------ #
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: Mods.updateCount === 0

            EmptyState {
                anchors.centerIn: parent
                width: parent.width
                icon: "check-circle"
                tint: Theme.success
                title: I18n.t("updates.allDone.title")
                subtitle: I18n.t("updates.allDone.subtitle")
            }
        }

        Item { Layout.fillHeight: true; Layout.minimumHeight: 8 }
    }
}
