import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "protons"
    maxWidth: 1080
    property string searchQuery: ""
    readonly property var filteredInstalled: filterVersions(Protons.installed)
    readonly property var filteredAvailable: filterVersions(Protons.available)
    function filterVersions(items) {
        const query = searchQuery.trim().toLowerCase()
        return query === "" ? items : items.filter(item => item.name.toLowerCase().indexOf(query) >= 0)
    }
    function fmtSize(bytes) {
        const mb = Number(bytes) / 1048576
        return mb >= 1024 ? (mb / 1024).toFixed(2) + " GB" : Math.round(mb) + " MB"
    }
    function sourceLabel(item) {
        return item.managed ? I18n.t("protons.source.manager")
             : item.path.indexOf("compatibilitytools.d/") >= 0 ? I18n.t("protons.source.custom")
             : I18n.t("protons.source.steam")
    }
    onActiveChanged: {
        if (active) {
            Protons.refreshInstalled()
            if (Protons.available.length === 0 && !Protons.busy)
                Protons.refreshAvailable()
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingMd
        RowLayout {
            Layout.fillWidth: true
            SearchBar {
                objectName: "protonSearch"
                Layout.fillWidth: true
                placeholder: I18n.t("protons.searchPlaceholder")
                searchText: page.searchQuery
                onSearchEdited: text => page.searchQuery = text
            }
            Item { Layout.fillWidth: true }
            SecondaryButton {
                text: I18n.t("protons.refresh")
                icon: "refresh-cw"
                enabled: !Protons.busy
                onClicked: { Protons.refreshInstalled(); Protons.refreshAvailable() }
            }
        }
        AppScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: versionsCol.implicitHeight
            ColumnLayout {
                id: versionsCol
                width: Math.max(0, parent.width - 48)
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 14
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 82
                    radius: 15
                    color: Theme.bg1
                    border.width: 1
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 12
                        Rectangle {
                            Layout.preferredWidth: 44
                            Layout.preferredHeight: 44
                            radius: 13
                            color: Theme.successSoft
                            border.width: 1
                            border.color: Theme.rgba(Theme.success, 0.28)
                            Icon { anchors.centerIn: parent; name: "globe"; size: 19; tint: Theme.success }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            RowLayout {
                                Text { text: I18n.t("protons.catalogTitle"); color: Theme.text; font.pixelSize: Typography.body + 1; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                                StatusBadge { key: "info"; label: "x86_64" }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: I18n.t("protons.catalogCaption")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    visible: Protons.busy && Protons.activeName !== ""
                    implicitHeight: 96
                    radius: 15
                    color: Theme.accentSoft
                    border.width: 1
                    border.color: Theme.rgba(Theme.accent, 0.28)
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 12
                        Rectangle {
                            Layout.preferredWidth: 42
                            Layout.preferredHeight: 42
                            radius: 12
                            color: Theme.bg2
                            border.width: 1
                            border.color: Theme.rgba(Theme.accent, 0.26)
                            Icon { anchors.centerIn: parent; name: "download"; size: 18; tint: Theme.accent }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            RowLayout {
                                Text { Layout.fillWidth: true; text: Protons.activeName; color: Theme.text; font.pixelSize: Typography.body + 1; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                                Text { text: Math.round(Protons.progress) + "%"; color: Theme.accent; font.pixelSize: Typography.body; font.weight: Font.Bold }
                            }
                            SlimProgress { Layout.fillWidth: true; value: Protons.progress / 100; barHeight: 6; indeterminate: Protons.progress <= 0 }
                            Text { text: I18n.resolveMessage(Protons.status); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                        }
                        SecondaryButton { text: I18n.t("protons.cancel"); compact: true; onClicked: Protons.cancel() }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    visible: Protons.status !== "" && !(Protons.busy && Protons.activeName !== "")
                    implicitHeight: statusText.implicitHeight + 24
                    radius: 12
                    color: Theme.bg1
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        id: statusText
                        anchors.fill: parent
                        anchors.margins: 12
                        text: I18n.resolveMessage(Protons.status)
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    SectionHeader {
                        title: I18n.t("protons.installed")
                        caption: I18n.t("protons.installedCaption")
                        StatusBadge { key: "success"; label: I18n.format("protons.searchCount", {shown: page.filteredInstalled.length, total: Protons.installed.length}) }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: versionsCol.width > 700 ? 2 : 1
                        columnSpacing: 10
                        rowSpacing: 10
                        Repeater {
                            model: page.filteredInstalled
                            delegate: Rectangle {
                                id: installedCard
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.preferredHeight: 72
                                radius: 13
                                color: Theme.bg2
                                border.width: 1
                                border.color: Theme.border
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 11
                                    spacing: 10
                                    Rectangle {
                                        Layout.preferredWidth: 34
                                        Layout.preferredHeight: 34
                                        radius: 10
                                        color: Theme.successSoft
                                        Icon { anchors.centerIn: parent; name: "check"; size: 15; tint: Theme.success }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text { Layout.fillWidth: true; text: installedCard.modelData.name; color: Theme.text; font.pixelSize: Typography.body; font.weight: Font.DemiBold; font.family: Theme.fontFamily; elide: Text.ElideRight }
                                        Text { Layout.fillWidth: true; text: page.sourceLabel(installedCard.modelData) + " · " + installedCard.modelData.path; color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily; elide: Text.ElideMiddle }
                                    }
                                    IconButton {
                                        buttonSize: 30
                                        iconSize: 13
                                        icon: "trash"
                                        danger: true
                                        visible: installedCard.modelData.managed
                                        enabled: !Protons.busy && !Game.isRunning
                                        tooltip: I18n.t("protons.remove")
                                        onClicked: { removeModal.protonPath = installedCard.modelData.path; removeModal.ask(I18n.t("protons.remove"), installedCard.modelData.name, I18n.t("protons.remove"), true) }
                                    }
                                }
                            }
                        }
                    }
                    Text { visible: Protons.installed.length === 0; text: I18n.t("protons.empty"); color: Theme.textMuted; font.pixelSize: Typography.caption }
                    Text { visible: Protons.installed.length > 0 && page.filteredInstalled.length === 0; text: I18n.t("protons.noMatches"); color: Theme.textMuted; font.pixelSize: Typography.caption }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    SectionHeader {
                        title: I18n.t("protons.available")
                        caption: I18n.t("protons.availableCaption")
                        StatusBadge { key: "info"; label: I18n.format("protons.searchCount", {shown: page.filteredAvailable.length, total: Protons.available.length}) }
                    }
                    Repeater {
                        model: page.filteredAvailable
                        delegate: Rectangle {
                            id: releaseRow
                            required property var modelData
                            required property int index
                            readonly property bool latest: Protons.available.length > 0 && modelData.name === Protons.available[0].name
                            readonly property bool installed: Protons.installed.some(p => p.name === modelData.filename.replace(".tar.gz", ""))
                            readonly property bool downloading: Protons.busy && Protons.activeName === modelData.name
                            Layout.fillWidth: true
                            implicitHeight: downloading ? 82 : 64
                            radius: 13
                            color: releaseHover.hovered ? Theme.bg3 : Theme.bg2
                            border.width: 1
                            border.color: downloading ? Theme.rgba(Theme.accent, 0.34) : releaseHover.hovered ? Theme.borderHover : Theme.border
                            Behavior on color { ColorAnimation { duration: Theme.fast } }
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 11
                                Rectangle {
                                    Layout.preferredWidth: 36
                                    Layout.preferredHeight: 36
                                    radius: 11
                                    color: releaseRow.latest ? Theme.accentSoft : Theme.bg1
                                    border.width: 1
                                    border.color: releaseRow.latest ? Theme.rgba(Theme.accent, 0.22) : Theme.border
                                    Icon { anchors.centerIn: parent; name: releaseRow.latest ? "star" : "package"; size: 16; tint: releaseRow.latest ? Theme.accent : Theme.textSecondary }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    RowLayout {
                                        Text { text: releaseRow.modelData.name; color: Theme.text; font.pixelSize: Typography.body; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                                        StatusBadge { visible: releaseRow.latest; key: "update"; label: I18n.t("protons.latest") }
                                    }
                                    Text { Layout.fillWidth: true; text: page.fmtSize(releaseRow.modelData.size) + (releaseRow.modelData.published ? " · " + releaseRow.modelData.published.slice(0, 10) : ""); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily; elide: Text.ElideRight }
                                    SlimProgress { Layout.fillWidth: true; visible: releaseRow.downloading; value: Protons.progress / 100; barHeight: 4 }
                                }
                                PrimaryButton {
                                    Layout.preferredWidth: 112
                                    Layout.minimumWidth: 112
                                    Layout.maximumWidth: 112
                                    text: releaseRow.installed ? I18n.t("protons.alreadyInstalled") : releaseRow.downloading ? Math.round(Protons.progress) + "%" : I18n.t("protons.download")
                                    icon: releaseRow.installed ? "check" : "download"
                                    busy: releaseRow.downloading
                                    disabled: Protons.busy || releaseRow.installed
                                    onClicked: Protons.download(releaseRow.modelData.name)
                                }
                            }
                            HoverHandler { id: releaseHover }
                        }
                    }
                    Text { visible: Protons.available.length > 0 && page.filteredAvailable.length === 0; text: I18n.t("protons.noMatches"); color: Theme.textMuted; font.pixelSize: Typography.caption }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: storageText.implicitHeight + 24
                    radius: 12
                    color: Theme.bg1
                    border.width: 1
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 11
                        spacing: 9
                        Icon { name: "info"; size: 15; tint: Theme.textMuted }
                        Text { id: storageText; Layout.fillWidth: true; text: I18n.t("protons.storageInfo"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily; wrapMode: Text.WordWrap }
                    }
                }
            }
        }
    }
    ConfirmModal { id: removeModal; property string protonPath: ""; onConfirmed: Protons.remove(protonPath) }
}
