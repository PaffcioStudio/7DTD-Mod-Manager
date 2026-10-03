pragma Singleton
import QtQuick

// Scalable dimensions. `scale` is bound to Settings.uiScale from Main.qml.
QtObject {
    property real scale: 1.0

    // spacing
    readonly property real spacingXs:  4  * scale
    readonly property real spacingSm:  8  * scale
    readonly property real spacingMd:  12 * scale
    readonly property real spacingLg:  16 * scale
    readonly property real spacingXl:  20 * scale
    readonly property real spacingXxl: 28 * scale

    // radii
    readonly property real radiusSm: 8
    readonly property real radiusMd: 12
    readonly property real radiusLg: 16
    readonly property real radiusXl: 20

    // control heights
    readonly property real controlHSm: 30
    readonly property real controlH:   38
    readonly property real controlHLg: 46

    // layout
    readonly property real sidebarW:   240
    readonly property real headerH:    64
    readonly property real pagePad:    24 * scale
    readonly property real maxContentW: 1280
}
