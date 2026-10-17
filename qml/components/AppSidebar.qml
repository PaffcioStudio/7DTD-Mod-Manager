import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Fixed application sidebar: logo, primary navigation, settings, version.
Item {
    id: sidebar

    signal navigateRequested(string page)

    property string activePage: "dashboard"
    property int updatesCount: 0
    property int downloadsActive: 0
    property bool titleBarDragEnabled: true

    // Screenshots render a deterministic layout using local state. This never
    // writes to Settings.sidebarGameExpanded / sidebarToolsExpanded, while the
    // normal application continues remembering group expansion as before.
    readonly property bool screenshotPreview: Boot.sidebarPreview !== ""
    property bool previewGameExpanded: Boot.sidebarPreview === "game"
    property bool previewToolsExpanded: Boot.sidebarPreview === "tools"

    implicitWidth: Dimensions.sidebarW

    // The five frequently used destinations stay visible. Secondary pages
    // remain reachable inside two lightweight, independently saved groups.
    readonly property var navItems: [
        { page: "dashboard", key: "nav.dashboard", icon: "grid", badge: "none" },
        { page: "profiles", key: "nav.instances", icon: "layers", badge: "none" },
        { page: "mods", key: "nav.mods", icon: "package", badge: "none" },
        { page: "discover", key: "nav.discover", icon: "globe", badge: "none" },
        { page: "downloads", key: "nav.downloads", icon: "download", badge: "dot" }
    ]
    readonly property var gameItems: [
        { page: "steam_releases", key: "nav.steamReleases", icon: "download", badge: "none" },
        { page: "protons", key: "nav.protons", icon: "terminal", badge: "none" }
    ]
    readonly property var toolItems: [
        { page: "game_profiles", key: "nav.gameProfiles", icon: "file-text", badge: "none" },
        { page: "modpacks", key: "nav.backups", icon: "backpack", badge: "none" },
        { page: "updates", key: "nav.updates", icon: "refresh-cw", badge: "count" }
    ]

    // Navigation can also originate from global search, keyboard shortcuts,
    // notifications or deep links. Reveal the destination in that case.
    function revealActiveGroup() {
        if (activePage === "steam_releases" || activePage === "protons") {
            if (screenshotPreview)
                previewGameExpanded = true
            else
                Settings.sidebarGameExpanded = true
        } else if (activePage === "game_profiles" || activePage === "modpacks"
                   || activePage === "updates") {
            if (screenshotPreview)
                previewToolsExpanded = true
            else
                Settings.sidebarToolsExpanded = true
        }
    }

    function scrollToActivePage() {
        var item = null
        for (var i = 0; i < primaryLinks.count; ++i) {
            var primary = primaryLinks.itemAt(i)
            if (primary && primary.pageName === activePage) {
                item = primary
                break
            }
        }
        if (!item)
            item = gameGroup.itemForPage(activePage) || toolsGroup.itemForPage(activePage)
        if (!item)
            return  // Settings lives in the fixed footer.

        var top = item.mapToItem(navigationColumn, 0, 0).y
        var bottom = top + item.height
        if (top < navigationFlickable.contentY)
            navigationFlickable.contentY = Math.max(0, top - 6)
        else if (bottom > navigationFlickable.contentY + navigationFlickable.height)
            navigationFlickable.contentY = Math.min(
                Math.max(0, navigationFlickable.contentHeight - navigationFlickable.height),
                bottom - navigationFlickable.height + 6)
    }

    // Wait until the 160 ms group animation has finished before scrolling to
    // a page opened via global search, keyboard shortcut or the event bus.
    Timer {
        id: activeItemScrollTimer
        interval: Theme.animationsEnabled ? 190 : 0
        repeat: false
        onTriggered: sidebar.scrollToActivePage()
    }
    onActivePageChanged: {
        revealActiveGroup()
        activeItemScrollTimer.restart()
    }
    Component.onCompleted: revealActiveGroup()

    Rectangle {
        anchors.fill: parent
        color: Theme.bg1
    }

    Rectangle {
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: 1
        color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 18
        anchors.bottomMargin: 16
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 4

        // ---- logo -------------------------------------------------------- #
        Item {
            id: logoArea
            Layout.fillWidth: true
            Layout.bottomMargin: 22
            implicitHeight: 52

            // window drag handle (custom title bar)
            MouseArea {
                anchors.fill: parent
                enabled: sidebar.titleBarDragEnabled
                onPressed: (mouse) => {
                    const win = ApplicationWindow.window
                    if (win) win.startSystemMove()
                }
            }

            RowLayout {
                anchors.fill: parent
                spacing: 12

                Image {
                    source: Qt.resolvedUrl("../../assets/icons/app-icon.svg")
                    sourceSize.width: 44
                    sourceSize.height: 44
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    spacing: 1
                    Layout.alignment: Qt.AlignVCenter

                    Text {
                        text: "7DTD"
                        color: Theme.text
                        font.pixelSize: Typography.h2 + 2
                        font.weight: Font.Bold
                        font.family: Theme.fontFamily
                    }

                    Text {
                        text: I18n.t("brand.manager")
                        color: Theme.accent
                        font.pixelSize: Typography.micro
                        font.weight: Font.DemiBold
                        font.letterSpacing: Typography.trackingWider
                        font.family: Theme.fontFamily
                    }
                }
            }
        }

        // ---- scrollable navigation -------------------------------------- #
        // Keep Settings and the version footer anchored to the bottom even on
        // small windows or with a larger interface scale.
        Flickable {
            id: navigationFlickable
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentHeight: navigationColumn.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
            interactive: contentHeight > height

            // Reuse the application's theme-aware scrollbar.
            ScrollBar.vertical: AppScrollBar {
                policy: ScrollBar.AsNeeded
            }
            onContentHeightChanged: contentY = Math.max(0, Math.min(
                contentY, Math.max(0, contentHeight - height)))

            ColumnLayout {
                id: navigationColumn
                width: navigationFlickable.width - (navigationFlickable.contentHeight > navigationFlickable.height ? 7 : 0)
                spacing: 4

                Repeater {
                    id: primaryLinks
                    model: sidebar.navItems

                    SidebarNavItem {
                        required property var modelData
                        pageName: modelData.page
                        label: I18n.t(modelData.key)
                        icon: modelData.icon
                        active: sidebar.activePage === modelData.page
                        badgeCount: modelData.badge === "count" ? sidebar.updatesCount : -1
                        showDot: modelData.badge === "dot" && sidebar.downloadsActive > 0
                        Layout.fillWidth: true
                        onNav: (page) => sidebar.navigateRequested(page)
                    }
                }

                Item { Layout.preferredHeight: 10 }

                SidebarGroup {
                    id: gameGroup
                    Layout.fillWidth: true
                    label: I18n.t("nav.gameEnvironment")
                    icon: "gamepad"
                    items: sidebar.gameItems
                    expanded: sidebar.screenshotPreview ? sidebar.previewGameExpanded : Settings.sidebarGameExpanded
                    containsActivePage: sidebar.activePage === "steam_releases"
                                        || sidebar.activePage === "protons"
                    onToggleRequested: {
                        if (sidebar.screenshotPreview)
                            sidebar.previewGameExpanded = !sidebar.previewGameExpanded
                        else
                            Settings.sidebarGameExpanded = !Settings.sidebarGameExpanded
                    }
                    onNavigateRequested: (page) => sidebar.navigateRequested(page)
                }

                SidebarGroup {
                    id: toolsGroup
                    Layout.fillWidth: true
                    label: I18n.t("nav.tools")
                    icon: "wrench"
                    items: sidebar.toolItems
                    expanded: sidebar.screenshotPreview ? sidebar.previewToolsExpanded : Settings.sidebarToolsExpanded
                    containsActivePage: sidebar.activePage === "game_profiles"
                                        || sidebar.activePage === "modpacks"
                                        || sidebar.activePage === "updates"
                    // Preserve update visibility while the Tools group is closed.
                    badgeCount: expanded ? -1 : sidebar.updatesCount
                    onToggleRequested: {
                        if (sidebar.screenshotPreview)
                            sidebar.previewToolsExpanded = !sidebar.previewToolsExpanded
                        else
                            Settings.sidebarToolsExpanded = !Settings.sidebarToolsExpanded
                    }
                    onNavigateRequested: (page) => sidebar.navigateRequested(page)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            Layout.bottomMargin: 4
        }

        // ---- settings ----------------------------------------------------- #
        SidebarNavItem {
            pageName: "settings"
            label: I18n.t("nav.settings")
            icon: "sliders"
            active: sidebar.activePage === "settings"
            Layout.fillWidth: true
            onNav: (page) => sidebar.navigateRequested(page)
        }

        // ---- version footer ------------------------------------------------ #
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 14
            spacing: 6

            Rectangle {
                width: 5
                height: 5
                radius: 3
                color: Theme.success
                opacity: 0.8
            }

            Text {
                text: "v" + App.version
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "7DTD"
                color: Theme.textFaint
                font.pixelSize: Typography.micro
                font.letterSpacing: Typography.trackingWide
                font.family: Theme.fontFamily
            }
        }
    }

    // ------------------------------------------------------------------ #
    // A heading toggles its own children without navigating to a placeholder
    // page. The clipping container provides a brief reveal animation.
    component SidebarGroup: ColumnLayout {
        id: group

        signal toggleRequested()
        signal navigateRequested(string page)

        property string label: ""
        property string icon: ""
        property var items: []
        property bool expanded: false
        property bool containsActivePage: false
        property int badgeCount: -1

        spacing: 2

        function itemForPage(page) {
            for (var i = 0; i < childRepeater.count; ++i) {
                var item = childRepeater.itemAt(i)
                if (item && item.pageName === page)
                    return item
            }
            return null
        }

        Item {
            id: groupHeader
            Layout.fillWidth: true
            implicitHeight: 42

            Rectangle {
                anchors.fill: parent
                radius: 10
                color: groupHover.hovered ? Theme.bg3 : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.fast } }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                Icon {
                    name: group.icon
                    size: 18
                    tint: group.containsActivePage ? Theme.accent
                         : (groupHover.hovered ? Theme.text : Theme.textSecondary)
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    text: group.label
                    color: group.containsActivePage ? Theme.text
                         : (groupHover.hovered ? Theme.text : Theme.textSecondary)
                    font.pixelSize: Typography.body
                    font.weight: group.containsActivePage ? Font.DemiBold : Font.Medium
                    font.family: Theme.fontFamily
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                }

                Rectangle {
                    visible: group.badgeCount > 0
                    width: groupBadge.implicitWidth + 12
                    height: 20
                    radius: 10
                    color: Theme.accentSoftUp
                    Layout.alignment: Qt.AlignVCenter
                    Text {
                        id: groupBadge
                        anchors.centerIn: parent
                        text: group.badgeCount
                        color: Theme.accent
                        font.pixelSize: Typography.caption
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                    }
                }

                Icon {
                    name: "chevron-right"
                    size: 15
                    tint: Theme.textMuted
                    rotation: group.expanded ? 90 : 0
                    Layout.alignment: Qt.AlignVCenter
                    Behavior on rotation {
                        NumberAnimation { duration: Theme.animationsEnabled ? 160 : 0; easing.type: Easing.OutCubic }
                    }
                }
            }

            HoverHandler { id: groupHover }
            TapHandler { onTapped: group.toggleRequested() }
        }

        Item {
            id: groupClip
            Layout.fillWidth: true
            property real revealedHeight: group.expanded ? childLinks.implicitHeight : 0
            Layout.preferredHeight: revealedHeight
            clip: true

            Behavior on revealedHeight {
                NumberAnimation { duration: Theme.animationsEnabled ? 160 : 0; easing.type: Easing.OutCubic }
            }

            ColumnLayout {
                id: childLinks
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                spacing: 2

                Repeater {
                    id: childRepeater
                    model: group.items
                    SidebarNavItem {
                        required property var modelData
                        Layout.fillWidth: true
                        pageName: modelData.page
                        label: I18n.t(modelData.key)
                        icon: modelData.icon
                        indent: 14
                        active: sidebar.activePage === modelData.page
                        badgeCount: modelData.badge === "count" ? sidebar.updatesCount : -1
                        showDot: modelData.badge === "dot" && sidebar.downloadsActive > 0
                        onNav: (page) => group.navigateRequested(page)
                    }
                }
            }
        }
    }

    component SidebarNavItem: Item {
        id: navItem

        signal nav(string page)

        property string pageName: ""
        property string label: ""
        property string icon: ""
        property bool active: false
        property int badgeCount: -1
        property bool showDot: false
        property int indent: 0

        implicitHeight: 42

        Rectangle {
            anchors.fill: parent
            radius: 10
            color: navItem.active ? Theme.accentSoft
                 : (hover.hovered ? Theme.bg3 : "transparent")
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }

        // left accent indicator
        Rectangle {
            visible: navItem.active
            width: 3
            radius: 2
            anchors.left: parent.left
            anchors.leftMargin: navItem.indent > 0 ? 5 : -7
            anchors.top: parent.top
            anchors.topMargin: 9
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 9
            color: Theme.accent

            Behavior on opacity { NumberAnimation { duration: Theme.normal } }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12 + navItem.indent
            anchors.rightMargin: 10
            spacing: 12

            Icon {
                name: navItem.icon
                size: 18
                tint: navItem.active ? Theme.accent
                     : (hover.hovered ? Theme.text : Theme.textSecondary)
                Layout.alignment: Qt.AlignVCenter
                Behavior on tint { ColorAnimation { duration: Theme.fast } }
            }

            Text {
                text: navItem.label
                color: navItem.active ? Theme.text
                     : (hover.hovered ? Theme.text : Theme.textSecondary)
                font.pixelSize: Typography.body
                font.weight: navItem.active ? Font.DemiBold : Font.Medium
                font.family: Theme.fontFamily
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                Behavior on color { ColorAnimation { duration: Theme.fast } }
            }

            // active downloads dot
            Rectangle {
                visible: navItem.showDot
                width: 9
                height: 9
                radius: 5
                color: Theme.accent
                Layout.alignment: Qt.AlignVCenter

                SequentialAnimation on opacity {
                    running: navItem.showDot && Theme.animationsEnabled
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.35; duration: 900; easing.type: Easing.InOutQuad }
                    NumberAnimation { from: 0.35; to: 1.0; duration: 900; easing.type: Easing.InOutQuad }
                }
            }

            // updates count badge
            Rectangle {
                visible: navItem.badgeCount > 0
                width: badgeText.implicitWidth + 12
                height: 20
                radius: 10
                color: Theme.accentSoftUp
                Layout.alignment: Qt.AlignVCenter

                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: navItem.badgeCount
                    color: Theme.accent
                    font.pixelSize: Typography.caption
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                }
            }
        }

        HoverHandler { id: hover }
        TapHandler { onTapped: navItem.nav(navItem.pageName) }
    }
}
