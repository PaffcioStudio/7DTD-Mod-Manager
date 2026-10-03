import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Top application bar: page title, global search, game status, settings,
// and (custom frame mode) window controls. Doubles as the drag handle.
Item {
    id: header

    property string pageTitle: I18n.t("dashboard.title")
    property string pageSubtitle: ""
    property bool searchVisible: true
    property string searchText: ""
    readonly property bool searchFocused: searchBox.searchFocused
    readonly property real searchLeft: searchBox.x
    readonly property real searchWidth: searchBox.width
    readonly property real searchBottom: searchBox.y + searchBox.height
    property bool gameDetected: false
    property string gameTooltip: I18n.t("app.gameNotDetectedTooltip")
    property bool showWindowButtons: false
    property bool dragEnabled: true
    readonly property bool maximized: {
        const win = ApplicationWindow.window
        return win && win.visibility === Window.Maximized
    }

    signal searchEdited(string text)
    signal searchAccepted()
    signal settingsRequested()
    signal gameStatusRequested()
    signal accountRequested()
    signal searchFocusRequested()
    property alias accountAnchor: accountButton

    implicitHeight: Dimensions.headerH

    function focusSearch() {
        searchBox.forceFocusInput()
    }

    function closeSearch() {
        searchBox.clearFocus()
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.bg1
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.border
    }

    // ---- title-bar drag area (below the interactive controls) ------------ #
    MouseArea {
        anchors.fill: parent
        enabled: header.dragEnabled
        onPressed: (mouse) => {
            const win = ApplicationWindow.window
            if (win) win.startSystemMove()
        }
        onDoubleClicked: (mouse) => {
            const win = ApplicationWindow.window
            if (win) {
                if (win.visibility === Window.Maximized) win.showNormal()
                else win.showMaximized()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 12
        spacing: 16

        // page title
        ColumnLayout {
            spacing: 1
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: 0

            Text {
                text: header.pageTitle
                color: Theme.text
                font.pixelSize: Typography.h1
                font.weight: Font.Bold
                font.family: Theme.fontFamily
            }

            Text {
                visible: header.pageSubtitle !== ""
                text: header.pageSubtitle
                color: Theme.textMuted
                font.pixelSize: Typography.caption + 0.5
                font.family: Theme.fontFamily
            }
        }

        Item { Layout.fillWidth: true }

        // global search
        SearchBar {
            id: searchBox
            visible: header.searchVisible
            Layout.alignment: Qt.AlignVCenter
            // Keep the search field compact so the window controls always have room
            Layout.maximumWidth: Math.max(160, header.width - 560)
            preferredWidth: searchBox.searchFocused ? 340 : 270
            placeholder: I18n.t("globalSearch.placeholder")
            searchText: header.searchText

            Behavior on preferredWidth {
                NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic }
            }

            onSearchEdited: (text) => header.searchEdited(text)
            onAccepted: header.searchAccepted()
        }

        // game status
        Item {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 30
            implicitHeight: 30

            Rectangle {
                anchors.centerIn: parent
                width: 9
                height: 9
                radius: 5
                color: header.gameDetected ? Theme.success : Theme.textMuted
            }

            HoverHandler { id: gameHover }
            TapHandler { onTapped: header.gameStatusRequested() }

            // tooltip - below the dot: the header sits at the very top of the
            // window, so an above-dot tooltip would leave the window frame.
            // Horizontally clamped so long paths never cross the window edge.
            Item {
                opacity: gameHover.hovered ? 1 : 0
                visible: opacity > 0.01
                width: Math.min(gameTipText.implicitWidth + 18, 340)
                height: 26
                anchors.top: parent.bottom
                anchors.topMargin: 8
                x: {
                    const centered = (parent.width - width) / 2
                    const win = Window.window
                    if (!win)
                        return centered
                    const pt = parent.mapToItem(win.contentItem, parent.width / 2, 0)
                    const half = width / 2
                    const margin = 8
                    const desired = Math.max(half + margin,
                                             Math.min(pt.x, win.contentItem.width - half - margin))
                    return desired - half - (pt.x - parent.width / 2)
                }
                z: 9999

                Behavior on opacity { NumberAnimation { duration: 160 } }

                Rectangle {
                    anchors.fill: parent
                    radius: 7
                    color: Theme.bg2
                    border.width: 1
                    border.color: Theme.borderHover
                }

                Text {
                    id: gameTipText
                    anchors.centerIn: parent
                    width: Math.min(implicitWidth, 322)
                    elide: Text.ElideMiddle
                    text: header.gameTooltip
                    color: Theme.textSecondary
                    font.pixelSize: Typography.small
                    font.family: Theme.fontFamily
                }
            }
        }

        IconButton {
            id: accountButton
            objectName: "accountButton"
            icon: "user"
            tooltip: GameVersions.hasSavedSession
                     ? I18n.format("header.steam.connectedTooltip", {username: GameVersions.steamUsername})
                     : I18n.t("header.steam.loginTooltip")
            // Konto pozostaje dostępne podczas pobierania wersji gry. Modal
            // może wtedy tylko pokazać stan konta/pobierania, bez blokowania UI.
            tint: GameVersions.hasSavedSession ? Theme.success : Theme.textSecondary
            hoverTint: GameVersions.hasSavedSession ? Theme.success : Theme.text
            iconSize: 17
            z: 20
            onClicked: Qt.callLater(function() { header.accountRequested() })
        }

        IconButton {
            icon: "sliders"
            tooltip: I18n.t("header.settingsTooltip")
            iconSize: 17
            onClicked: header.settingsRequested()
        }

        Rectangle {
            visible: header.showWindowButtons
            width: 1
            height: 24
            color: Theme.border
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: 4
        }

        // window controls
        Row {
            visible: header.showWindowButtons
            spacing: 2
            Layout.alignment: Qt.AlignVCenter

            IconButton {
                icon: "window-min"
                tooltip: I18n.t("header.minimizeTooltip")
                buttonSize: 38
                radius: 9
                onClicked: {
                    const win = ApplicationWindow.window
                    if (win) win.showMinimized()
                }
            }

            IconButton {
                icon: header.maximized ? "restore" : "maximize"
                tooltip: header.maximized ? I18n.t("header.restoreTooltip") : I18n.t("header.maximizeTooltip")
                buttonSize: 38
                radius: 9
                onClicked: {
                    const win = ApplicationWindow.window
                    if (!win) return
                    if (win.visibility === Window.Maximized) win.showNormal()
                    else win.showMaximized()
                }
            }

            IconButton {
                icon: "x"
                tooltip: I18n.t("header.closeTooltip")
                buttonSize: 38
                radius: 9
                danger: true
                onClicked: {
                    const win = ApplicationWindow.window
                    if (win) win.close()
                }
            }
        }
    }
}
