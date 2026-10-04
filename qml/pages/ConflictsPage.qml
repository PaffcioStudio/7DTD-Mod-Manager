import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "conflicts"
    maxWidth: 1000

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingXl

        PageDescription {
            text: Mods.conflictCount > 0
                  ? I18n.format("conflicts.subtitle.withConflicts", {count: Mods.conflictCount})
                  : I18n.t("conflicts.subtitle.none")
            maxTextWidth: 760
        }

        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            SecondaryButton {
                text: I18n.t("conflicts.goMods")
                icon: "package"
                onClicked: Bus.goTo("mods")
            }
        }

        // ---- conflict list ------------------------------------------------ #
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Dimensions.spacingLg
            visible: Conflicts.count > 0

            Repeater {
                model: Conflicts.model

                Item {
                    id: conflictDelegate
                    required property string modAId
                    required property string modAName
                    required property string modBId
                    required property string modBName
                    required property string fileText
                    required property string reasonText

                    Layout.fillWidth: true
                    implicitHeight: conflictCard.implicitHeight

                    ConflictCard {
                        id: conflictCard
                        width: parent.width

                        modAId: conflictDelegate.modAId
                        modAName: conflictDelegate.modAName
                        modBId: conflictDelegate.modBId
                        modBName: conflictDelegate.modBName
                        fileText: conflictDelegate.fileText
                        reasonText: conflictDelegate.reasonText

                        onViewModRequested: (modId) => Bus.openMod(modId)
                        onResolveRequested: (keepId, disableId) => {
                            Mods.setEnabled(disableId, false)
                        }
                    }
                }
            }
        }

        // ---- empty ---------------------------------------------------------- #
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: Conflicts.count === 0

            EmptyState {
                anchors.centerIn: parent
                width: parent.width
                icon: "shield"
                tint: Theme.success
                title: I18n.t("conflicts.empty.title")
                subtitle: I18n.t("conflicts.empty.subtitle")
            }
        }

        Item { Layout.fillHeight: true; Layout.minimumHeight: 8 }
    }
}
