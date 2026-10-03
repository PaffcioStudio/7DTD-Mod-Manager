import QtQuick
import "../theme"

// Centered modal dialog hosted in the window overlay (covers everything).
// Thin convenience layer over ModalBase - see ModalBase for the content /
// footer API (everything is inherited).
ModalBase {
    id: root

    cardWidth: 470

    // instancja może ustawić własną akcję zamknięcia (np. edycja instancji:
    // "zamknij = zapisz"); null = zwykłe zamknięcie
    property var closeHandler: null

    function open() { opened = true }
    function close() { opened = false }

    onCloseRequested: {
        if (closeHandler !== null) closeHandler()
        else close()
    }

    onOpenedChanged: {
        if (opened) root.forceActiveFocus()
    }

    // ESC obsługuje ModalBase (Keys.onEscapePressed -> closeRequested);
    // własny handler tutaj DODAWAŁ drugie emisje (podwójny zapis)
}
