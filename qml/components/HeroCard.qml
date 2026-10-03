import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Dashboard hero: game artwork, title, live stats strip and CTAs.
Item {
    id: root

    signal playClicked()
    signal stopClicked()
    signal manageClicked()

    // gra działa -> przycisk zamienia się w ZATRZYMAJ GRĘ (czerwony)
    property bool gameRunning: false
    property bool launchInProgress: false

    implicitHeight: 320
    clip: true

    property bool entered: false

    // Losowanie przy starcie jest zawsze aktywne. Okresowe losowanie w czasie
    // pracy można wyłączyć w Ustawieniach. Zestaw zawiera 5 grafik day i 5 night.
    readonly property int heroImageCount: 5
    property int heroImageIndex: 1 + Math.floor(Math.random() * heroImageCount)
    property int pendingHeroImageIndex: heroImageIndex
    property bool periodicRotationActive: false
    readonly property int heroRotationIntervalMs: 15 * 60 * 1000

    function nextHeroImageIndex() {
        if (heroImageCount <= 1) return 1
        var next = heroImageIndex
        while (next === heroImageIndex)
            next = 1 + Math.floor(Math.random() * heroImageCount)
        return next
    }

    function rotateHeroArtwork() {
        var next = nextHeroImageIndex()
        if (!Theme.animationsEnabled) {
            heroImageIndex = next
            return
        }
        pendingHeroImageIndex = next
        artworkFade.restart()
    }

    function commitHeroArtwork() {
        heroImageIndex = pendingHeroImageIndex
    }

    Component.onCompleted: enterTimer.start()
    Timer {
        id: enterTimer
        interval: 60
        onTriggered: root.entered = true
    }

    Timer {
        id: heroRotationTimer
        interval: root.heroRotationIntervalMs
        repeat: true
        running: root.periodicRotationActive && Settings.heroRotationEnabled
        onTriggered: root.rotateHeroArtwork()
    }

    SequentialAnimation {
        id: artworkFade
        running: false
        NumberAnimation {
            target: artwork
            property: "opacity"
            to: 0
            duration: Theme.normal
            easing.type: Easing.InQuad
        }
        ScriptAction { script: root.commitHeroArtwork() }
        NumberAnimation {
            target: artwork
            property: "opacity"
            to: 1
            duration: Theme.normal
            easing.type: Easing.OutQuad
        }
    }

    // ---- background artwork ---------------------------------------------- #
    Image {
        id: artwork
        anchors.fill: parent
        source: (Colors.mode === "light" || Colors.mode === "stalker-light")
            ? Qt.resolvedUrl(`../../assets/images/hero-day-${root.heroImageIndex}.png`)
            : Qt.resolvedUrl(`../../assets/images/hero-night-${root.heroImageIndex}.png`)
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: true

        // slow ken-burns drift
        SequentialAnimation on scale {
            running: Theme.animationsEnabled
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 1.055; duration: 26000; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1.055; to: 1.0; duration: 26000; easing.type: Easing.InOutSine }
        }
    }

    // gradient overlays (kolor trybowany - ciemna zasłona / jasna mgiełka)
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Theme.rgba(Theme.heroOverlay, 0.92) }
            GradientStop { position: 0.42; color: Theme.rgba(Theme.heroOverlay, 0.55) }
            GradientStop { position: 0.75; color: Theme.rgba(Theme.heroOverlay, 0.18) }
            GradientStop { position: 1.0; color: Theme.rgba(Theme.heroOverlay, 0.45) }
        }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.6; color: "transparent" }
            GradientStop { position: 1.0; color: Theme.rgba(Theme.heroOverlay, 0.75) }
        }
    }

    // ---- content ---------------------------------------------------------- #
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 34
        spacing: 0

        opacity: root.entered ? 1 : 0
        y: root.entered ? 0 : 22

        Behavior on opacity { NumberAnimation { duration: 520; easing.type: Easing.OutCubic } }
        Behavior on y { NumberAnimation { duration: 560; easing.type: Easing.OutCubic } }

        Item { Layout.fillHeight: true; Layout.maximumHeight: 18 }

        // kicker
        Item {
            implicitHeight: kickerBg.height
            Layout.bottomMargin: 14

            Rectangle {
                id: kickerBg
                width: kickerRow.implicitWidth + 22
                height: 26
                radius: 13
                color: Theme.accentSoft
                border.width: 1
                border.color: Theme.rgba(Theme.accent, 0.4)
            }

            Row {
                id: kickerRow
                anchors.centerIn: kickerBg
                spacing: 7

                Rectangle {
                    width: 6; height: 6; radius: 3
                    color: Theme.accent
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: I18n.t("hero.kicker")
                    color: Theme.accent
                    font.pixelSize: Typography.caption
                    font.weight: Font.Bold
                    font.letterSpacing: Typography.trackingCaps
                    font.family: Theme.fontFamily
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // game title
        Text {
            text: "7 DAYS TO DIE"
            color: Theme.heroText
            font.pixelSize: Typography.display
            font.weight: Font.Black
            font.letterSpacing: Typography.trackingWide
            font.family: Theme.fontFamily
            Layout.bottomMargin: 10
        }

        // meta chips
        Row {
            spacing: 10
            Layout.bottomMargin: 22

            HeroChip { label: Mods.gameVersion; icon: "tag" }
            HeroChip {
                label: Game.isDetected ? I18n.t("hero.gameDetected") : I18n.t("hero.gameNotDetected")
                icon: "check-circle"
                tint: Game.isDetected ? Theme.success : Theme.textMuted
            }
        }

        // stats strip
        Row {
            spacing: 26
            Layout.bottomMargin: 26

            HeroStat { value: Mods.totalMods;    label: I18n.t("hero.mods") }
            Rectangle { width: 1; height: 30; color: Theme.heroSep; anchors.verticalCenter: parent.verticalCenter }
            HeroStat { value: Mods.enabledCount; label: I18n.t("hero.enabled") }
            Rectangle { width: 1; height: 30; color: Theme.heroSep; anchors.verticalCenter: parent.verticalCenter }
            HeroStat {
                value: Mods.conflictCount
                label: I18n.t("hero.conflicts")
                tint: Mods.conflictCount > 0 ? Theme.warning : Theme.heroText
            }
            Rectangle { width: 1; height: 30; color: Theme.heroSep; anchors.verticalCenter: parent.verticalCenter }
            HeroStat {
                value: Mods.updateCount
                label: I18n.t("hero.updates")
                tint: Mods.updateCount > 0 ? Theme.accent : Theme.heroText
            }
        }

        // CTA row
        Row {
            spacing: 12

            PrimaryButton {
                text: root.gameRunning ? I18n.t("hero.stopGame") : I18n.t("hero.launchGame")
                icon: root.gameRunning ? "x-circle" : "play"
                large: true
                danger: root.gameRunning
                disabled: root.launchInProgress
                busy: root.launchInProgress
                onClicked: root.gameRunning ? root.stopClicked() : root.playClicked()
            }

            SecondaryButton {
                text: I18n.t("hero.manageMods")
                icon: "package"
                large: true
                onClicked: root.manageClicked()
            }
        }

        Item { Layout.fillHeight: true; Layout.maximumHeight: 6 }
    }

    // ------------------------------------------------------------------ #
    component HeroChip: Item {
        id: chip
        property string label: ""
        property string icon: ""
        property color tint: Theme.textSecondary
        implicitHeight: 26
        implicitWidth: row.implicitWidth + 24

        Rectangle {
            anchors.fill: parent
            radius: 13
            color: Theme.heroChipBg
            border.width: 1
            border.color: Theme.heroChipBorder
        }

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 7
            Icon {
                name: chip.icon
                size: 13
                tint: chip.tint
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: chip.label
                color: chip.tint
                font.pixelSize: Typography.caption
                font.weight: Font.Medium
                font.family: Theme.fontFamily
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    component HeroStat: Column {
        id: stat
        property string value: ""
        property string label: ""
        property color tint: Theme.heroText
        spacing: 0

        Text {
            text: stat.value
            color: stat.tint
            font.pixelSize: 24
            font.weight: Font.Black
            font.family: Theme.fontFamily
        }
        Text {
            text: stat.label
            color: Theme.heroTextMuted
            font.pixelSize: Typography.micro
            font.letterSpacing: Typography.trackingCaps
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
        }
    }
}
