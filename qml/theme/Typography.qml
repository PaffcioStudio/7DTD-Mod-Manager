pragma Singleton
import QtQuick

// Typography scale - all sizes react to Dimensions.scale (UI scale setting).
QtObject {
    readonly property real s: Dimensions.scale

    readonly property real display:  38 * s     // hero title
    readonly property real h1:       22 * s     // page title
    readonly property real h2:       16 * s     // section title
    readonly property real h3:       14 * s     // card title
    readonly property real body:     13 * s
    readonly property real small:    12 * s
    readonly property real caption:  11 * s
    readonly property real micro:    10 * s
    readonly property real statBig:  30 * s     // stat card number

    readonly property int weightMedium:   Font.Medium
    readonly property int weightSemiBold: Font.DemiBold
    readonly property int weightBold:     Font.Bold
    readonly property int weightExtraBold: Font.Black

    // letter spacing (px)
    readonly property real trackingWide:   0.4
    readonly property real trackingWider:  0.8
    readonly property real trackingCaps:   1.2
}
