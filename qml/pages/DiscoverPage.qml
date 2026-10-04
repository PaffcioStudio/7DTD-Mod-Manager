import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "discover"
    property bool loaded: false
    // domyślne filtry z Ustawień ( discoverDefaultCategory/Version ) - po
    // zapisaniu użytkownik wchodzi na Odkrywaj z gotowymi filtrami
    property string query: ""
    property string category: Settings.discoverDefaultCategory
    property string version: Settings.discoverDefaultVersion
    property string createdAfter: Settings.discoverDefaultCreatedAfter
    property bool includeAdult: Settings.discoverDefaultIncludeAdult
    // provider katalogu: "web" (7D2D Mods) | "local" (GitHub - overhaule z
    // lokalnego manifestu). Boot.discoverProvider służy tylko do testowego
    // wymuszenia providera; normalnie odtwarzamy zapisany filtr użytkownika.
    property string provider: (Boot.discoverProvider === "local" || Boot.discoverProvider === "web")
                             ? Boot.discoverProvider
                             : Settings.discoverDefaultProvider
    property var categoryOptions: []
    property var versionOptions: []

    // Tłumaczymy tylko pozycję "Wszystkie"; nazwy kategorii i wersji gry
    // zostają takie, jak zwraca serwis (oryginalne, np. Overhaul, Interface).
    function localizeCatalogOptions(options, allKey) {
        const source = options || []
        return source.map(function(opt) {
            const item = {value: opt.value, label: opt.label}
            if (item.value === "")
                item.label = I18n.t(allKey)
            return item
        })
    }

    function refreshI18nOptions() {
        page.categoryOptions = localizeCatalogOptions(Discover.categories, "discover.filter.allCategories")
        page.versionOptions = localizeCatalogOptions(Discover.versions, "discover.filter.allVersions")
    }

    function resultsLabel(count) {
        if (count === 1)
            return I18n.format("discover.results.one", {count: count})
        if (I18n.language === "pl" && count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20))
            return I18n.format("discover.results.few", {count: count})
        return I18n.format("discover.results.many", {count: count})
    }

    function openDetails(slug) {
        webDrawer.openWith(slug, page.version)
    }

    WebModDrawer { id: webDrawer }
    LocalModDrawer { id: localDrawer }

    function search(number, refresh) {
        searchDelay.stop()
        Discover.provider = page.provider
        Discover.search(query, category, version, number, refresh,
                        createdAfter, includeAdult)
        results.contentY = 0
    }
    onActiveChanged: {
        if (active && !loaded) {
            loaded = true
            search(1, false)
        }
    }
    Timer { id: searchDelay; interval: 450; onTriggered: page.search(1, false) }

    Component.onCompleted: page.refreshI18nOptions()

    Connections {
        target: I18n
        function onLanguageChanged() { page.refreshI18nOptions() }
    }

    Connections {
        target: Discover
        function onChanged() { page.refreshI18nOptions() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        spacing: 16

        PageDescription {
            text: I18n.t("discover.subtitle")
            maxTextWidth: 760
        }

        RowLayout {
            Layout.fillWidth: true
            SearchBar {
                Layout.fillWidth: true
                placeholder: page.provider === "web"
                             ? I18n.t("discover.search.webPlaceholder")
                             : I18n.t("discover.search.localPlaceholder")
                searchText: page.query
                onSearchEdited: (text) => { page.query = text; searchDelay.restart() }
                onAccepted: page.search(1, false)
            }
            SecondaryButton {
                icon: "refresh-cw"
                text: I18n.t("discover.refresh")
                busy: Discover.busy
                disabled: Discover.busy
                onClicked: page.search(Discover.page, true)
            }
            SecondaryButton {
                icon: "download"
                text: I18n.t("discover.downloads")
                onClicked: Bus.goTo("downloads")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            DropdownButton {
                options: [
                    { value: "web", label: I18n.t("discover.provider.web") },
                    { value: "local", label: I18n.t("discover.provider.local") }
                ]
                value: page.provider
                onPicked: (value) => {
                    if (page.provider === value) return
                    page.provider = value
                    if (value !== "web") {
                        page.category = ""
                        page.version = ""
                        page.createdAfter = ""
                        page.includeAdult = false
                    }
                    page.search(1, false)
                }
            }
            DropdownButton {
                visible: page.provider === "web"
                options: page.categoryOptions
                value: page.category
                onPicked: (value) => { page.category = value; page.search(1, false) }
            }
            DropdownButton {
                visible: page.provider === "web"
                options: page.versionOptions
                value: page.version
                onPicked: (value) => { page.version = value; page.search(1, false) }
            }
            DropdownButton {
                visible: page.provider === "web"
                options: [
                    { value: "", label: I18n.t("discover.time.any") },
                    { value: "7d", label: I18n.t("discover.time.7d") },
                    { value: "30d", label: I18n.t("discover.time.30d") },
                    { value: "365d", label: I18n.t("discover.time.365d") }
                ]
                value: page.createdAfter
                onPicked: (value) => { page.createdAfter = value; page.search(1, false) }
            }
            RowLayout {
                visible: page.provider === "web"
                spacing: 8
                Layout.preferredHeight: Dimensions.controlH

                Text {
                    text: I18n.t("discover.adult")
                    color: page.includeAdult ? Theme.text : Theme.textSecondary
                    font.pixelSize: Typography.small
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                }

                ToggleSwitch {
                    checked: page.includeAdult
                    onToggled: (checked) => { page.includeAdult = checked; page.search(1, false) }
                }
            }
            IconButton {
                visible: true
                icon: "save"
                tooltip: I18n.t("discover.saveDefaults.tooltip")
                onClicked: {
                    Settings.discoverDefaultProvider = page.provider
                    Settings.discoverDefaultCategory = page.category
                    Settings.discoverDefaultVersion = page.version
                    Settings.discoverDefaultCreatedAfter = page.createdAfter
                    Settings.discoverDefaultIncludeAdult = page.includeAdult
                    Bus.toast(I18n.t("discover.saveDefaults.toast"), "success")
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                text: Discover.busy ? I18n.t("discover.searching") : page.resultsLabel(Discover.total)
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Typography.small
            }
        }

        Text {
            visible: Discover.offline
            Layout.fillWidth: true
            text: I18n.t("discover.offline")
            color: Theme.warning
            font.family: Theme.fontFamily
            font.pixelSize: Typography.small
            wrapMode: Text.WordWrap
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: results
                anchors.fill: parent
                clip: true
                spacing: 10
                model: Discover.items
                boundsBehavior: Flickable.StopAtBounds
                flickDeceleration: 5200
                maximumFlickVelocity: 1800
                WheelHandler {
                    target: null
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: (event) => {
                        const maxY = Math.max(0, results.contentHeight - results.height)
                        if (maxY <= 0) { event.accepted = false; return }
                        const step = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                        results.contentY = Math.max(0, Math.min(maxY, results.contentY - step))
                        event.accepted = true
                    }
                }
                ScrollBar.vertical: AppScrollBar {}
                delegate: Rectangle {
                    id: card
                    required property var modelData
                    width: results.width - 14
                    height: 174
                    radius: 8
                    color: Theme.bg2
                    border.color: cardHover.hovered ? Theme.borderHover : Theme.border
                    readonly property string downloadKey: page.provider === "web" ? modelData.slug : modelData.url
                    readonly property string stateKey: Downloads.modDownloads[downloadKey] || ""
                    readonly property bool downloading: ["queued", "downloading", "paused"].indexOf(stateKey) >= 0

                    // Klik w główną część karty otwiera szczegóły. Footer z
                    // przyciskami pozostaje osobnym obszarem, więc kliknięcie
                    // w Pobierz / link zewnętrzny nie otwiera drawera.
                    Item {
                        id: detailsHitArea
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: parent.height - 58
                        TapHandler {
                            onTapped: {
                                // web: szczegóły ze strony; lokalne: drawer
                                // z PEŁNYM opisem (karta ucina elizją)
                                if (page.provider === "web")
                                    page.openDetails(card.modelData.slug)
                                else
                                    localDrawer.openWith(card.modelData)
                            }
                        }
                    }
                    HoverHandler { id: cardHover }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 16
                        Rectangle {
                            Layout.preferredWidth: Math.min(216, card.width * 0.24)
                            Layout.fillHeight: true
                            color: Theme.bg1
                            clip: true
                            Image {
                                id: thumbnail
                                anchors.fill: parent
                                source: card.modelData.thumbnail
                                asynchronous: true
                                // kwadratowe miniaturki (1:1) przycinamy do
                                // szerokiego kadru ze środkiem; reszta mieści
                                // się w całości (letterbox)
                                fillMode: card.modelData.thumbCrop
                                          ? Image.PreserveAspectCrop
                                          : Image.PreserveAspectFit
                                // przy Crop nie ograniczamy źródła (zniekształcałoby kadrowanie)
                                sourceSize.width: card.modelData.thumbCrop ? 0 : 432
                            }
                            Icon {
                                anchors.centerIn: parent
                                name: "image"
                                tint: Theme.textMuted
                                size: 28
                                visible: thumbnail.status !== Image.Ready
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 5
                            Text {
                                Layout.fillWidth: true
                                text: card.modelData.title
                                textFormat: Text.PlainText
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: Typography.body + 2
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                maximumLineCount: 2
                                wrapMode: Text.Wrap
                            }
                            Text {
                                Layout.fillWidth: true
                                text: card.modelData.author + " · " + card.modelData.category
                                textFormat: Text.PlainText
                                color: Theme.textMuted
                                font.family: Theme.fontFamily
                                font.pixelSize: Typography.small
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                text: (I18n.language === "en" && card.modelData.summaryEn)
                                      ? card.modelData.summaryEn : card.modelData.summary
                                textFormat: Text.PlainText
                                color: Theme.textSecondary
                                font.family: Theme.fontFamily
                                font.pixelSize: Typography.small
                                wrapMode: Text.Wrap
                                elide: Text.ElideRight
                                maximumLineCount: 2
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    // wersje + kategorie (mogą być długie -
                                    // ucina się z elizją), liczba pobrań ma
                                    // SWOJE stałe miejsce po prawej
                                    Layout.fillWidth: true
                                    text: card.modelData.versions
                                          + (card.modelData.category !== "" ? " · " + card.modelData.category : "")
                                    textFormat: Text.PlainText
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Typography.small
                                    elide: Text.ElideRight
                                }

                                Text {
                                    text: I18n.format("discover.downloadsCount", {count: card.modelData.downloads})
                                    textFormat: Text.PlainText
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Typography.small
                                }
                                IconButton {
                                    icon: "external-link"
                                    tooltip: I18n.t("discover.openModPage")
                                    onClicked: Qt.openUrlExternally(card.modelData.url)
                                }
                                SecondaryButton {
                                    icon: card.downloading ? "clock" : card.stateKey === "completed" ? "check" : "download"
                                    text: card.downloading ? I18n.t("discover.download.queued") : card.stateKey === "completed" ? I18n.t("discover.download.completed") : I18n.t("discover.download.action")
                                    disabled: card.downloading || card.stateKey === "completed"
                                    onClicked: {
                                        // web: slug moda (scraper); lokalne:
                                        // bezpośrednie źródło z manifestu
                                        // (git / GitHub releases / zip) z
                                        // ładną nazwą instalowaną jako
                                        // dedykowana instancja Overhaul
                                        if (page.provider === "web")
                                            Downloads.startModDownloadWithVersion(
                                                card.modelData.slug, page.version)
                                        else
                                            Downloads.startUrlDownloadNamed(
                                                card.modelData.url, card.modelData.title,
                                                card.modelData.game_version || card.modelData.versions || page.version)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(420, parent.width)
                visible: Discover.items.length === 0
                spacing: 16
                BusyIndicator { Layout.alignment: Qt.AlignHCenter; running: Discover.busy; visible: running }
                Text {
                    Layout.fillWidth: true
                    text: Discover.busy ? I18n.t("discover.loading") : Discover.error === "discover.error.fetchFailed" ? I18n.t("discover.error.fetchFailed") : (Discover.error || I18n.t("discover.empty"))
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Typography.body
                }
                SecondaryButton {
                    Layout.alignment: Qt.AlignHCenter
                    visible: Discover.error !== ""
                    text: I18n.t("discover.retry")
                    icon: "refresh-cw"
                    onClicked: page.search(1, true)
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            IconButton {
                icon: "arrow-right"
                iconRotation: 180
                tooltip: I18n.t("discover.pagination.previous")
                enabled: !Discover.busy && Discover.error === "" && Discover.page > 1
                opacity: enabled ? 1 : 0.4
                onClicked: page.search(Discover.page - 1, false)
            }
            Text {
                text: Discover.page + " / " + Discover.pages
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Typography.body
            }
            IconButton {
                icon: "arrow-right"
                tooltip: I18n.t("discover.pagination.next")
                enabled: !Discover.busy && Discover.error === "" && Discover.page < Discover.pages
                opacity: enabled ? 1 : 0.4
                onClicked: page.search(Discover.page + 1, false)
            }
            Item { Layout.fillWidth: true }
        }
    }
}
