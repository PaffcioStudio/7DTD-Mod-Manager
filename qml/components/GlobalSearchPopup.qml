import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

Item {
    id: root

    property string query: ""
    property bool active: false
    property bool busy: false
    property bool onlineChecked: false
    property bool onlineOffline: false
    readonly property int websiteResultCount: {
        let count = 0
        for (let i = 0; i < results.length; i++) {
            if (results[i].kind === "discover")
                count++
        }
        return count
    }
    property string error: ""
    property string errorKey: ""
    property var errorValues: ({})
    property var results: []
    signal resultClicked(string kind, string itemId, string title)
    signal showOnlineRequested(string query)

    visible: active && query.trim() !== ""
    implicitWidth: 520
    implicitHeight: card.height
    width: Math.min(520, parent ? parent.width - 24 : 520)
    height: card.height
    z: 900

    Rectangle {
        id: card
        width: parent.width
        implicitHeight: content.implicitHeight + 16
        height: Math.min(530, implicitHeight)
        radius: 13
        color: Theme.bg2
        border.width: 1
        border.color: Theme.borderHover
        layer.enabled: true

        ColumnLayout {
            id: content
            anchors.fill: parent
            anchors.margins: 10
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 6
                Layout.rightMargin: 6
                Layout.preferredHeight: 28

                Text {
                    text: I18n.t("globalSearch.title")
                    color: Theme.text
                    font.pixelSize: Typography.small + 1
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                }
                Item { Layout.fillWidth: true }
                Text {
                    visible: root.busy
                    text: I18n.t("globalSearch.searchingWebsite")
                    color: Theme.textMuted
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                }
            }

            Flickable {
                id: searchResultsFlick
                acceptedButtons: Qt.NoButton
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(400, resultsColumn.implicitHeight)
                clip: true
                contentHeight: resultsColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds

                WheelHandler {
                    target: null
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: (event) => {
                        const maxY = Math.max(0, searchResultsFlick.contentHeight - searchResultsFlick.height)
                        if (maxY <= 0) { event.accepted = false; return }
                        searchResultsFlick.cancelFlick()
                        const step = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                        searchResultsFlick.contentY = Math.max(0, Math.min(maxY, searchResultsFlick.contentY - step))
                        event.accepted = true
                    }
                }

                ColumnLayout {
                    id: resultsColumn
                    width: parent.width
                    spacing: 2

                    Repeater {
                        model: root.results

                        delegate: ColumnLayout {
                            required property var modelData
                            required property int index
                            width: resultsColumn.width
                            spacing: 3

                            Text {
                                visible: index === 0 || root.results[index - 1].sectionKey !== modelData.sectionKey
                                text: I18n.t((modelData && modelData.sectionKey) || "globalSearch.title") || ""
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                                Layout.leftMargin: 8
                                Layout.topMargin: index === 0 ? 2 : 9
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 48
                                radius: 9
                                color: hover.hovered ? Theme.bg3 : "transparent"

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 10

                                    Item {
                                        Layout.preferredWidth: 28
                                        Layout.preferredHeight: 28
                                        Layout.alignment: Qt.AlignVCenter
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: 8
                                            color: Theme.rgba(Theme.accent, 0.12)
                                        }
                                        Icon {
                                            anchors.centerIn: parent
                                            name: modelData.icon || "search"
                                            tint: Theme.accent
                                            size: 15
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1
                                        Text {
                                            text: I18n.resolveMessage(modelData.title)
                                            color: Theme.text
                                            font.pixelSize: Typography.small + 0.5
                                            font.weight: Font.DemiBold
                                            font.family: Theme.fontFamily
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: I18n.resolveMessage(modelData.subtitle || (modelData.subtitleKey ? I18n.t(modelData.subtitleKey) : ""))
                                            color: Theme.textMuted
                                            font.pixelSize: Typography.caption
                                            font.family: Theme.fontFamily
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Icon {
                                        name: "arrow-right"
                                        tint: Theme.textMuted
                                        size: 14
                                    }
                                }

                                HoverHandler { id: hover }
                                TapHandler {
                                    gesturePolicy: TapHandler.ReleaseWithinBounds
                                    onTapped: root.resultClicked(
                                        modelData.kind,
                                        modelData.id,
                                        modelData.title
                                    )
                                }
                            }
                        }
                    }

                    Text {
                        visible: !root.busy && root.results.length === 0 && root.onlineChecked && root.error === "" && root.errorKey === ""
                        text: I18n.format("globalSearch.noResults", {query: root.query})
                        color: Theme.textMuted
                        font.pixelSize: Typography.small
                        font.family: Theme.fontFamily
                        Layout.leftMargin: 8
                        Layout.topMargin: 12
                        Layout.bottomMargin: 8
                    }

                    Text {
                        visible: root.onlineChecked && !root.busy && root.results.length > 0
                                 && root.websiteResultCount === 0
                                 && root.error === "" && root.errorKey === ""
                        text: I18n.t("globalSearch.noWebsiteResults")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        Layout.leftMargin: 8
                        Layout.topMargin: 8
                    }

                    Text {
                        visible: root.error !== "" || root.errorKey !== ""
                        text: root.errorKey !== "" ? I18n.format(root.errorKey, root.errorValues) : root.error
                        color: Theme.warning
                        font.pixelSize: Typography.small
                        font.family: Theme.fontFamily
                        Layout.leftMargin: 8
                        Layout.topMargin: 10
                        Layout.bottomMargin: 4
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Theme.border
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 5
                Layout.rightMargin: 5
                Layout.preferredHeight: 38
                spacing: 8

                Icon {
                    name: root.onlineOffline ? "alert-triangle" : "globe"
                    size: 14
                    tint: root.onlineOffline ? Theme.warning : Theme.textMuted
                }
                Text {
                    Layout.fillWidth: true
                    text: root.onlineOffline ? I18n.t("globalSearch.cachedWebsite")
                          : root.busy ? I18n.t("globalSearch.searchingWebsite")
                          : I18n.t("globalSearch.websiteSource")
                    color: Theme.textMuted
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
                SecondaryButton {
                    compact: true
                    icon: "arrow-right"
                    text: I18n.t("globalSearch.viewAllWebsite")
                    onClicked: root.showOnlineRequested(root.query)
                }
            }
        }
    }
}
