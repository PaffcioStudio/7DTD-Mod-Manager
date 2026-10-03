pragma Singleton
import QtQuick
import "../i18n"

// Central theme: colors (incl. live accent), fonts, motion durations,
// category/status lookups. Components must pull every visual constant
// from here - no duplicated styles across files.
QtObject {
    id: theme

    // ------------------------------------------------------------------ #
    // fonts (bundled Inter, system fallback otherwise)
    // ------------------------------------------------------------------ #
    property FontLoader _regular: FontLoader {
        source: Qt.resolvedUrl("../../assets/fonts/Inter-Regular.ttf")
    }
    property FontLoader _medium: FontLoader {
        source: Qt.resolvedUrl("../../assets/fonts/Inter-Medium.ttf")
    }
    property FontLoader _semiBold: FontLoader {
        source: Qt.resolvedUrl("../../assets/fonts/Inter-SemiBold.ttf")
    }
    property FontLoader _bold: FontLoader {
        source: Qt.resolvedUrl("../../assets/fonts/Inter-Bold.ttf")
    }
    property FontLoader _extraBold: FontLoader {
        source: Qt.resolvedUrl("../../assets/fonts/Inter-ExtraBold.ttf")
    }

    readonly property bool interReady: theme._regular.status === FontLoader.Ready
    readonly property string fontFamily: interReady ? "Inter" : "Noto Sans"

    // ------------------------------------------------------------------ #
    // colors
    // ------------------------------------------------------------------ #
    readonly property color bg0:          Colors.bg0
    readonly property color bg1:          Colors.bg1
    readonly property color bg2:          Colors.bg2
    readonly property color bg3:          Colors.bg3
    readonly property color bg4:          Colors.bg4
    readonly property color border:       Colors.border
    readonly property color borderHover:  Colors.borderHover
    readonly property color borderStrong: Colors.borderStrong
    readonly property color text:         Colors.text
    readonly property color textSecondary: Colors.textSecondary
    readonly property color textMuted:    Colors.textMuted
    readonly property color textFaint:    Colors.textFaint

    // live accent - bound to Settings.accentColor in Main.qml
    property color accent: Colors.ember
    readonly property color accentHover:   Qt.lighter(accent, 1.10)
    readonly property color accentPressed: Qt.darker(accent, 1.12)
    readonly property color accentSoft:    rgba(accent, 0.14)
    readonly property color accentSoftUp:  rgba(accent, 0.24)
    readonly property color accentForeground:      (mode === "stalker" || mode === "stalker-light") ? "#2A160E" : "#1C0E05"

    readonly property color success: Colors.success
    readonly property color warning: Colors.warning
    readonly property color danger:  Colors.danger
    readonly property color info:    Colors.info

    readonly property color successSoft: rgba(success, 0.14)
    readonly property color warningSoft: rgba(warning, 0.14)
    readonly property color dangerSoft:  rgba(danger, 0.14)
    readonly property color infoSoft:    rgba(info, 0.14)

    readonly property color shadowColor: (Colors.mode === "light" || Colors.mode === "stalker-light")
        ? Qt.rgba(0.12, 0.09, 0.06, 0.14)
        : (Colors.mode === "stalker"
            ? Qt.rgba(0.04, 0.015, 0.01, 0.58)
            : Qt.rgba(0, 0, 0, 0.45))
    readonly property color scrimColor: (Colors.mode === "light" || Colors.mode === "stalker-light")
        ? rgba(Colors.scrim, 0.42)
        : (Colors.mode === "stalker" ? rgba(Colors.scrim, 0.68) : rgba(Colors.scrim, 0.62))
    // Przyciemnienie nad grafikami zawsze pozostaje dostatecznie ciemne,
    // ale w Strefie przechodzi lekko w ciepły brąz zamiast neutralnej czerni.
    readonly property color imageOverlay: mode === "stalker" ? "#120907"
        : (mode === "stalker-light" ? "#4A2C20" : (mode === "dark" ? "#0A0D12" : "#18202B"))

    // hero (baner na Pulpicie) - tekst/nakładki/czipy zależne od motywu.
    // Strefa używa nocnego artworku z rdzawo-czerwonym gradingiem.
    readonly property string mode: Colors.mode
    readonly property color heroText:       (mode === "light" || mode === "stalker-light") ? "#34271D" : "#EEE7D9"
    readonly property color heroTextMuted:  (mode === "light" || mode === "stalker-light") ? "#9934271D" : "#99EEE7D9"
    readonly property color heroSep:        (mode === "light" || mode === "stalker-light") ? "#2A34271D" : "#2ED8C7B1"
    readonly property color heroChipBg:     mode === "stalker-light" ? "#D9FBF8F0" : (mode === "light" ? "#99FFFFFF" : (mode === "stalker" ? "#7A110C09" : "#59000000"))
    readonly property color heroChipBorder: mode === "stalker-light" ? "#4C7C6A56" : (mode === "light" ? "#2633291A" : (mode === "stalker" ? "#3FD66A39" : "#1FFFFFFF"))
    readonly property color heroOverlay:    mode === "stalker-light" ? "#EDE0D5" : (mode === "light" ? "#FFF6EE" : (mode === "stalker" ? "#1A0806" : "#05070B"))

    // ------------------------------------------------------------------ #
    // motion
    // ------------------------------------------------------------------ #
    property bool animationsEnabled: true
    readonly property int fast:   animationsEnabled ? 130 : 0
    readonly property int normal: animationsEnabled ? 220 : 0
    readonly property int slow:   animationsEnabled ? 340 : 0

    // ------------------------------------------------------------------ #
    // scroll physics
    // ------------------------------------------------------------------ #
    // Jeden spójny przelicznik dla myszy i touchpada.  Poprzednie widoki
    // miały różne kroki (48 / 140 px) i różne prędkości flicka, przez co
    // dokładnie ten sam ruch potrafił przewijać ekran o zupełnie inną
    // odległość.
    readonly property real wheelMouseStep: 88
    readonly property real wheelPixelLimit: 96

    function wheelDelta(pixelY, angleY) {
        let delta = Math.abs(pixelY) > 0.001
            ? pixelY
            : (angleY / 120.0) * wheelMouseStep

        // Touchpady potrafią wysłać pojedyncze bardzo duże delty.
        // Limit utrzymuje przewidywalne zachowanie bez sztucznej akceleracji.
        if (Math.abs(pixelY) > 0.001)
            delta = Math.max(-wheelPixelLimit, Math.min(wheelPixelLimit, delta))

        return delta
    }

    // ------------------------------------------------------------------ #
    // helpers
    // ------------------------------------------------------------------ #
    function shortPath(path) {
        const value = String(path || "")
        if (value.length <= 30) return value
        return value.slice(0, 12) + "…" + value.slice(-15)
    }

    function rgba(base, alpha) {
        return Qt.rgba(base.r, base.g, base.b, Math.max(0, Math.min(1, alpha)))
    }

    function catColor(category) {
        const map = {
            "Overhaul": Colors.catOverhaul, "Gameplay": Colors.catGameplay,
            "UI": Colors.catUI,             "Graphics": Colors.catGraphics,
            "Vehicles": Colors.catVehicles, "Zombies":  Colors.catZombies,
            "Items": Colors.catItems,       "Magic":    Colors.catMagic,
            "World": Colors.catWorld
        }
        return map[category] || Colors.info
    }

    function catIcon(category) {
        const map = {
            "Overhaul": "hammer",  "Gameplay": "gamepad", "UI": "layout",
            "Graphics": "image",   "Vehicles": "car",     "Zombies": "skull",
            "Items": "backpack",   "Magic": "sparkles",   "World": "globe"
        }
        return map[category] || "package"
    }

    // Categories are stored as stable EN keys; the UI displays Polish labels.
    function catLabel(category) {
        const key = String(category || "")
        if (key !== "" && I18n)
            return I18n.t("category." + key)
        return category
    }

    function statusColor(key) {
        const map = {
            "enabled": success, "disabled": textMuted,
            "update": accent, "conflict": warning,
            "completed": success, "failed": danger,
            "paused": warning, "queued": textMuted,
            "downloading": accent, "cancelled": textMuted,
            "success": success, "error": danger, "warning": warning,
            "info": info
        }
        return map[key] || textSecondary
    }
}
