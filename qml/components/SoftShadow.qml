import QtQuick
import QtQuick.Effects
import "../theme"

// Drop shadow wrapper around MultiEffect (the modern replacement for the
// deprecated QtGraphicalEffects). Declare BEFORE the elevated item so the
// item paints on top of its own shadow.
//   SoftShadow { source: myCard; elevation: 2 }
MultiEffect {
    property real elevation: 1.0     // 0..3

    shadowEnabled: true
    shadowColor: Theme.shadowColor
    autoPaddingEnabled: true
    shadowBlur: 0.35 + 0.12 * elevation
    shadowVerticalOffset: 3 + 3 * elevation
    opacity: 0.5 + 0.16 * elevation
}
