"""Event bus shared by the Python backend and the QML frontend."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class EventBus(QObject):
    """Exposed to QML as ``Bus``.

    Signals:
        notify(message, level)       -> toast notifications (level: success/warning/error/info)
        navigate(page)               -> change the active page
        openModRequested(modId)      -> open the mod details drawer

    Slots (callable from QML as well):
        toast(message, level)        -> emit notify
        goTo(page)                   -> emit navigate
        openMod(modId)               -> emit openModRequested
    """

    notify = Signal(str, str)
    # "QVariantMap" (nie object!): QML dostaje zwykły obiekt JS, a nie
    # nieprzezroczysty wrapper - inaczej I18n.format() nie odczyta {count}.
    notifyKey = Signal(str, "QVariantMap", str)
    navigate = Signal(str)
    openModRequested = Signal(str)

    @Slot(str, str)
    def toast(self, message: str, level: str = "info") -> None:
        self.notify.emit(message, level)

    @Slot(str, "QVariantMap", str)
    def toastKey(self, key: str, values=None, level: str = "info") -> None:
        self.notifyKey.emit(key, dict(values or {}), level)

    @Slot(str)
    def goTo(self, page: str) -> None:
        self.navigate.emit(page)

    @Slot(str)
    def openMod(self, mod_id: str) -> None:
        self.openModRequested.emit(mod_id)
