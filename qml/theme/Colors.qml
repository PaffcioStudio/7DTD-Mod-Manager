pragma Singleton
import QtQuick

// Raw palette - do not use these directly in components,
// always go through Theme.qml which adds the dynamic bits (accent etc.).
//
// Trzy motywy: "dark" | "light" | "stalker" | "stalker-light". Każdy kolor jest związany z mode,
// dzięki czemu zmiana motywu przemalowuje cały interfejs na żywo.
// Motyw "stalker" korzysta z grafitów, sadzy, rdzawej czerwieni i wypalonego
// pomarańczu, z przygaszonymi kolorami statusów i kategorii.
// "stalker-light" przenosi ten język na jasną bazę: płótno khaki, papier,
// kurz i ciepłe szarości z rdzą, oliwką i przygaszonym błękitem jako akcentami.
QtObject {
    id: colors

    property string mode: "dark"   // "dark" | "light" | "stalker" | "stalker-light"

    // backgrounds
    property color bg0: mode === "stalker" ? "#0B0A08"
                       : mode === "stalker-light" ? "#E9E3D8"
                       : mode === "dark" ? "#0A0D12" : "#ECEEF2"
    property color bg1: mode === "stalker" ? "#121310"
                       : mode === "stalker-light" ? "#F4EFE5"
                       : mode === "dark" ? "#10141C" : "#F6F7F9"
    property color bg2: mode === "stalker" ? "#191A15"
                       : mode === "stalker-light" ? "#FBF8F0"
                       : mode === "dark" ? "#151B26" : "#FFFFFF"
    property color bg3: mode === "stalker" ? "#24231C"
                       : mode === "stalker-light" ? "#E3DBCF"
                       : mode === "dark" ? "#1B2231" : "#E9EBF0"
    property color bg4: mode === "stalker" ? "#302C22"
                       : mode === "stalker-light" ? "#D2C7B7"
                       : mode === "dark" ? "#222B3D" : "#DDE0E7"

    // borders
    property color border: mode === "stalker" ? "#3A3428"
                           : mode === "stalker-light" ? "#C7BBAA"
                           : mode === "dark" ? "#202839" : "#D3D8E1"
    property color borderHover: mode === "stalker" ? "#564739"
                                : mode === "stalker-light" ? "#AE9F8D"
                                : mode === "dark" ? "#2B3650" : "#B6C0D2"
    property color borderStrong: mode === "stalker" ? "#725B43"
                                : mode === "stalker-light" ? "#8F7760"
                                : mode === "dark" ? "#3A4763" : "#93A0B6"

    // text
    property color text: mode === "stalker" ? "#EEE7D9"
                         : mode === "stalker-light" ? "#2D261F"
                         : mode === "dark" ? "#E9EDF5" : "#171E2B"
    property color textSecondary: mode === "stalker" ? "#B4AA98"
                                 : mode === "stalker-light" ? "#62584D"
                                 : mode === "dark" ? "#9AA6BC" : "#48536A"
    property color textMuted: mode === "stalker" ? "#81796B"
                              : mode === "stalker-light" ? "#887B6C"
                              : mode === "dark" ? "#5F6B82" : "#7E89A0"
    property color textFaint: mode === "stalker" ? "#554F45"
                              : mode === "stalker-light" ? "#AA9D8E"
                              : mode === "dark" ? "#3E485C" : "#AAB4C6"

    // accents / status
    property color ember: mode === "stalker" ? "#E05A2A"
                           : mode === "stalker-light" ? "#C9542C"
                           : "#FF7A38"
    property color success: mode === "stalker" ? "#A8B84D"
                           : mode === "stalker-light" ? "#718D32"
                           : mode === "dark" ? "#3FCF8E" : "#149A57"
    property color warning: mode === "stalker" ? "#D5963A"
                           : mode === "stalker-light" ? "#B07419"
                           : mode === "dark" ? "#F5B841" : "#B07C10"
    property color danger: mode === "stalker" ? "#C33D36"
                          : mode === "stalker-light" ? "#B43B33"
                          : mode === "dark" ? "#EF5D5D" : "#D64545"
    property color info: mode === "stalker" ? "#829A97"
                        : mode === "stalker-light" ? "#4F7C78"
                        : mode === "dark" ? "#5CA9FF" : "#2E7FD0"

    // category colors
    property color catOverhaul: mode === "stalker" ? "#E06A34" : mode === "stalker-light" ? "#C95A30" : "#FF7A38"
    property color catGameplay: mode === "stalker" ? "#B6A05E" : mode === "stalker-light" ? "#738052" : "#5CA9FF"
    property color catUI:       mode === "stalker" ? "#988976" : mode === "stalker-light" ? "#776859" : "#A78BFA"
    property color catGraphics: mode === "stalker" ? "#829795" : mode === "stalker-light" ? "#4D7A77" : "#38BDF8"
    property color catVehicles: mode === "stalker" ? "#C58A44" : mode === "stalker-light" ? "#9C6A2E" : "#F5B841"
    property color catZombies:  mode === "stalker" ? "#A7B84D" : mode === "stalker-light" ? "#748B35" : "#84CC16"
    property color catItems:    mode === "stalker" ? "#A66E62" : mode === "stalker-light" ? "#8E5F55" : "#F472B6"
    property color catMagic:    mode === "stalker" ? "#9C7A63" : mode === "stalker-light" ? "#806C5D" : "#C084FC"
    property color catWorld:    mode === "stalker" ? "#7F927A" : mode === "stalker-light" ? "#63745F" : "#34D399"

    // misc
    property color shadow: "#000000"
    property color scrim: mode === "stalker" ? "#120A08"
                         : mode === "stalker-light" ? "#5D4D40"
                         : mode === "dark" ? "#05070B" : "#2A3140"
}
