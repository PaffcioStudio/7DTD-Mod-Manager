import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "dashboard"
    maxWidth: 1280

    // stat card entrance stagger
    property bool statsShown: false
    onActiveChanged: if (active) { statsShown = false; statTimer.restart() } else statsShown = false
    Timer { id: statTimer; interval: 380; onTriggered: page.statsShown = true }

    property var statCards: [
        { titleKey: "dashboard.stat.installed", prop: "totalMods",    icon: "package",     tint: "accent" },
        { titleKey: "dashboard.stat.enabled",   prop: "enabledCount", icon: "check-circle", tint: "success" },
        { titleKey: "dashboard.stat.conflicts", prop: "conflictCount", icon: "shield-alert", tint: "warning", target: "conflicts" },
        { titleKey: "dashboard.stat.updates",   prop: "updateCount",  icon: "refresh-cw",  tint: "info", target: "updates" }
    ]

    AppScrollView {
        anchors.fill: parent
        contentHeight: dashColumn.implicitHeight

        ColumnLayout {
            id: dashColumn
            width: Math.min(parent.width, page.contentWidth)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Dimensions.spacingXxl

            PageDescription {
                text: I18n.t("dashboard.subtitle")
                maxTextWidth: 700
            }

            // ---- hero ---------------------------------------------------- #
            HeroCard {
                Layout.fillWidth: true
                periodicRotationActive: page.active
                gameRunning: Game.isRunning
            launchInProgress: Profiles.launchInProgress
                onPlayClicked: Game.isRunning
                    ? stopGameHero.ask(I18n.t("dashboard.stopGame.title"),
                        I18n.t("dashboard.stopGame.message"),
                        I18n.t("dashboard.stopGame.confirm"), true)
                    : Profiles.launchActive()
                onStopClicked: stopGameHero.ask(I18n.t("dashboard.stopGame.title"),
                    I18n.t("dashboard.stopGame.message"),
                    I18n.t("dashboard.stopGame.confirm"), true)
                onManageClicked: Bus.goTo("mods")
            }

            ConfirmModal {
                id: stopGameHero
                onConfirmed: Game.stopRunningGame()
            }

            // ---- stat cards ----------------------------------------------- #
            GridLayout {
                Layout.fillWidth: true
                columns: width > 1000 ? 4 : 2
                columnSpacing: Dimensions.spacingLg
                rowSpacing: Dimensions.spacingLg

                Repeater {
                    model: page.statCards

                    StatCard {
                        id: statCard
                        required property var modelData
                        required property int index

                        readonly property color resolvedTint: modelData.tint === "accent" ? Theme.accent
                            : modelData.tint === "success" ? Theme.success
                            : modelData.tint === "warning" ? Theme.warning
                            : modelData.tint === "info" ? Theme.info : Theme.accent

                        title: I18n.t(modelData.titleKey)
                        value: Mods[modelData.prop]
                        icon: modelData.icon
                        tint: resolvedTint
                        shown: page.statsShown
                        clickable: modelData.target !== undefined
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1

                        onClicked: Bus.goTo(modelData.target)

                        Timer {
                            interval: 60 + index * 80
                            running: page.active && !page.statsShown
                            onTriggered: statCard.shown = true
                        }
                    }
                }
            }

            // ---- dashboard utilities -------------------------------------- #
            RowLayout {
                Layout.fillWidth: true
                spacing: Dimensions.spacingLg

                // active instance
                Panel {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 252 * Dimensions.scale
                    Layout.minimumHeight: 252 * Dimensions.scale
                    pad: 22

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 16

                        SectionHeader {
                            title: I18n.t("dashboard.activeInstance.title")
                            caption: I18n.t("dashboard.activeInstance.caption")
                            Layout.fillWidth: true
                        }

                        // bind do property, nie do wywołania metody -
                        // opcje odświeżają się po dodaniu/usunięciu instancji
                        DropdownButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: Dimensions.controlHLg
                            disabled: Game.isRunning || Profiles.launchInProgress
                            options: Profiles.activeInstanceOptions
                            value: Profiles.activeProfileId
                            onPicked: (value) => {
                                if (value !== "" && value !== Profiles.activeProfileId)
                                    Profiles.activate(value)
                            }
                        }

                        RowLayout {
                            spacing: 10
                            Layout.fillWidth: true

                            Rectangle {
                                implicitWidth: 34
                                implicitHeight: 34
                                radius: 10
                                color: Theme.rgba(Theme.accent, 0.12)
                                border.width: 1
                                border.color: Theme.rgba(Theme.accent, 0.25)

                                Icon {
                                    anchors.centerIn: parent
                                    name: "layers"
                                    tint: Theme.accent
                                    size: 17
                                }
                            }

                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true

                                Text {
                                    text: I18n.format("dashboard.activeInstance.enabledMods", { enabled: Mods.enabledCount, total: Mods.totalMods })
                                    color: Theme.text
                                    font.pixelSize: Typography.small
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: Profiles.activeProfileId !== "" ? I18n.t("dashboard.activeInstance.ready") : I18n.t("dashboard.activeInstance.none")
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        Item { Layout.fillHeight: true; Layout.minimumHeight: 6 * Dimensions.scale }

                        SecondaryButton {
                            text: I18n.t("dashboard.activeInstance.manage")
                            icon: "chevron-right"
                            compact: true
                            onClicked: Bus.goTo("profiles")
                        }
                    }
                }

                // conflicts summary
                Panel {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 252 * Dimensions.scale
                    Layout.minimumHeight: 252 * Dimensions.scale
                    pad: 22
                    borderColor: Mods.conflictCount > 0
                        ? Theme.rgba(Theme.warning, 0.3)
                        : Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 16

                        SectionHeader {
                            title: I18n.t("dashboard.conflicts.title")
                            caption: Mods.conflictCount > 0
                                ? I18n.format("dashboard.conflicts.attention", { count: Mods.conflictCount })
                                : I18n.t("dashboard.conflicts.loadingOrder")
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 76 * Dimensions.scale
                            radius: Dimensions.radiusMd
                            color: Mods.conflictCount > 0
                                ? Theme.warningSoft
                                : Theme.rgba(Theme.success, 0.08)
                            border.width: 1
                            border.color: Mods.conflictCount > 0
                                ? Theme.rgba(Theme.warning, 0.25)
                                : Theme.rgba(Theme.success, 0.18)

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 12

                                Rectangle {
                                    implicitWidth: 36
                                    implicitHeight: 36
                                    radius: 10
                                    color: Mods.conflictCount > 0
                                        ? Theme.rgba(Theme.warning, 0.15)
                                        : Theme.rgba(Theme.success, 0.14)
                                    border.width: 1
                                    border.color: Mods.conflictCount > 0
                                        ? Theme.rgba(Theme.warning, 0.28)
                                        : Theme.rgba(Theme.success, 0.22)

                                    Icon {
                                        anchors.centerIn: parent
                                        name: Mods.conflictCount > 0 ? "shield-alert" : "check-circle"
                                        tint: Mods.conflictCount > 0 ? Theme.warning : Theme.success
                                        size: 18
                                    }
                                }

                                ColumnLayout {
                                    spacing: 2
                                    Layout.fillWidth: true

                                    Text {
                                        text: Mods.conflictCount > 0
                                            ? I18n.format("dashboard.conflicts.detected", { count: Mods.conflictCount })
                                            : I18n.t("dashboard.conflicts.none")
                                        color: Theme.text
                                        font.pixelSize: Typography.small
                                        font.weight: Font.DemiBold
                                        font.family: Theme.fontFamily
                                        Layout.fillWidth: true
                                    }

                                    Text {
                                        text: Mods.conflictCount > 0
                                            ? I18n.t("dashboard.conflicts.checkOrder")
                                            : I18n.t("dashboard.conflicts.safe")
                                        color: Theme.textMuted
                                        font.pixelSize: Typography.caption
                                        font.family: Theme.fontFamily
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }

                        SecondaryButton {
                            text: Mods.conflictCount > 0 ? I18n.t("dashboard.conflicts.view") : I18n.t("dashboard.conflicts.openList")
                            icon: Mods.conflictCount > 0 ? "shield-alert" : "chevron-right"
                            compact: true
                            onClicked: Bus.goTo("conflicts")
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true; Layout.minimumHeight: 12 }
        }
    }
}
