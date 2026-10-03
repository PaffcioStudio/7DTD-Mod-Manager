#!/usr/bin/env python3
"""Generuje pełny zestaw angielskich zrzutów ekranu i przywraca oryginalne pliki."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def app_python() -> str:
    """Interpreter z .venv (PySide6) - systemowy python nie ma zależności."""
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    print("UWAGA: brak .venv - używam sys.executable (może nie mieć PySide6)")
    return sys.executable

REPLACEMENTS = {
    "qml/Main.qml": [
        ('title: "7 Days to Die - Menedżer modów"', 'title: "7 Days to Die - Mod Manager"'),
        ('"dashboard": ["Pulpit", "Przegląd Twoich modów"]',
         '"dashboard": ["Dashboard", "Overview of your mods"]'),
        ('"mods": ["Mody", Mods.totalMods + " zainstalowanych · " + Mods.enabledCount + " włączonych · " + Mods.conflictCount + " konfliktów"]',
         '"mods": ["Mods", Mods.totalMods + " installed · " + Mods.enabledCount + " enabled · " + Mods.conflictCount + " conflicts"]'),
        ('"profiles": ["Instancje", "Izolowane katalogi danych, flagi startowe i uruchamianie"]',
         '"profiles": ["Instances", "Isolated data folders, launch flags and game launcher"]'),
        ('"modpacks": ["Kopie zapasowe", Modpacks.count > 0 ? Modpacks.count + " kopii zapisanych" : "Pełne kopie danych instancji"]',
         '"modpacks": ["Backups", Modpacks.count > 0 ? Modpacks.count + " backups saved" : "Full instance data backups"]'),
        ('"downloads": ["Pobieranie", Downloads.activeCount > 0 ? Downloads.activeCount + " aktywnych" : "Zarządzaj pobieraniem"]',
         '"downloads": ["Downloads", Downloads.activeCount > 0 ? Downloads.activeCount + " active" : "Manage downloads"]'),
        ('"discover": ["Odkrywaj", "7 Days to Die Mods"]',
         '"discover": ["Discover", "7 Days to Die Mods"]'),
        ('"updates": ["Aktualizacje", Mods.updateCount > 0 ? Mods.updateCount + " dostępnych aktualizacji" : "Wszystkie mody są aktualne"]',
         '"updates": ["Updates", Mods.updateCount > 0 ? Mods.updateCount + " updates available" : "All mods are up to date"]'),
        ('"conflicts": ["Konflikty", Mods.conflictCount > 0 ? Mods.conflictCount + " wykrytych konfliktów" : "Brak konfliktów"]',
         '"conflicts": ["Conflicts", Mods.conflictCount > 0 ? Mods.conflictCount + " conflicts detected" : "No conflicts"]'),
        ('"settings": ["Ustawienia", "Skonfiguruj menedżera"]',
         '"settings": ["Settings", "Configure the manager"]'),
    ],
    "qml/components/AppSidebar.qml": [
        ('text: "MENEDŻER MODÓW"', 'text: "MOD MANAGER"'),
        ('label: "Pulpit"', 'label: "Dashboard"'),
        ('label: "Instancje"', 'label: "Instances"'),
        ('label: "Odkrywaj"', 'label: "Discover"'),
        ('label: "Mody"', 'label: "Mods"'),
        ('label: "Kopie zapasowe"', 'label: "Backups"'),
        ('label: "Aktualizacje"', 'label: "Updates"'),
        ('label: "Pobieranie"', 'label: "Downloads"'),
        ('label: "Ustawienia"', 'label: "Settings"'),
    ],
    "qml/components/AppHeader.qml": [
        ('property string pageTitle: "Pulpit"', 'property string pageTitle: "Dashboard"'),
        ('placeholder: "Szukaj modów…"', 'placeholder: "Search mods…"'),
    ],
    "qml/components/HeroCard.qml": [
        ('text: "MENEDŻER MODÓW"', 'text: "MOD MANAGER"'),
        ('Game.isDetected ? "Gra wykryta" : "Gra niewykryta"',
         'Game.isDetected ? "Game detected" : "Game not detected"'),
        ('label: "MODY"', 'label: "MODS"'),
        ('label: "WŁĄCZONE"', 'label: "ENABLED"'),
        ('label: "KONFLIKTY"', 'label: "CONFLICTS"'),
        ('label: "AKTUALIZACJE"', 'label: "UPDATES"'),
        ('"URUCHOM GRĘ"', '"LAUNCH GAME"'),
        ('text: "ZARZĄDZAJ MODAMI"', 'text: "MANAGE MODS"'),
    ],
    "qml/components/StatusBadge.qml": [
        ('"enabled": "Włączony"', '"enabled": "Enabled"'),
        ('"disabled": "Wyłączony"', '"disabled": "Disabled"'),
        ('"update": "Aktualizacja"', '"update": "Update"'),
        ('"conflict": "Konflikt"', '"conflict": "Conflict"'),
        ('"completed": "Zakończono"', '"completed": "Completed"'),
        ('"failed": "Niepowodzenie"', '"failed": "Failed"'),
        ('"paused": "Wstrzymano"', '"paused": "Paused"'),
        ('"queued": "W kolejce"', '"queued": "Queued"'),
        ('"downloading": "Pobieranie"', '"downloading": "Downloading"'),
        ('"cancelled": "Anulowano"', '"cancelled": "Cancelled"'),
        ('"success": "Gotowe"', '"success": "Ready"'),
        ('"error": "Błąd"', '"error": "Error"'),
        ('"warning": "Ostrzeżenie"', '"warning": "Warning"'),
    ],
    "qml/theme/Theme.qml": [
        ('"Overhaul": "Przebudowa", "Gameplay": "Rozgrywka", "UI": "Interfejs",',
         '"Overhaul": "Overhaul", "Gameplay": "Gameplay", "UI": "UI",'),
        ('"Graphics": "Grafika",   "Vehicles": "Pojazdy",   "Zombies": "Zombie",',
         '"Graphics": "Graphics",   "Vehicles": "Vehicles",   "Zombies": "Zombies",'),
        ('"Items": "Przedmioty",   "Magic": "Magia",        "World": "Świat"',
         '"Items": "Items",   "Magic": "Magic",        "World": "World"'),
    ],
    "qml/components/ModCard.qml": [
        ('text: "Konflikt"', 'text: "Conflict"'),
        ('text: "Autor: " + card.author + "  ·  Zaktualizowano " + card.updatedAgo + "  ·  " + Theme.catLabel(card.category)',
         'text: "Author: " + card.author + "  ·  Updated " + card.updatedAgo + "  ·  " + Theme.catLabel(card.category)'),
        ('text: "Szczegóły"', 'text: "Details"'),
    ],
    "qml/components/ModDetailsDrawer.qml": [
        ('("Autor: " + drawer.modData.author)', '("Author: " + drawer.modData.author)'),
        ('label: "Rozmiar"', 'label: "Size"'),
        ('label: "Ocena"', 'label: "Rating"'),
        ('label: "Pobrania"', 'label: "Downloads"'),
        ('label: "Zainstalowano"', 'label: "Installed"'),
        ('label: "Zaktualizowano"', 'label: "Updated"'),
        ('label: "Gra"', 'label: "Game"'),
        ('text: "OPIS"', 'text: "DESCRIPTION"'),
        ('text: "TAGI"', 'text: "TAGS"'),
        ('text: "WYMAGANIA"', 'text: "REQUIREMENTS"'),
        ('text: "ZALEŻNOŚCI"', 'text: "DEPENDENCIES"'),
        ('text: "Brak zależności"', 'text: "No dependencies"'),
        ('text: "KONFLIKTY"', 'text: "CONFLICTS"'),
        ('text: "W konflikcie z: "', 'text: "Conflicts with: "'),
        ('text: "Zobacz konflikty"', 'text: "View conflicts"'),
        ('drawer.modData.enabled === true ? "WYŁĄCZ MOD" : "WŁĄCZ MOD"',
         'drawer.modData.enabled === true ? "DISABLE MOD" : "ENABLE MOD"'),
    ],
    "qml/components/ProfileCard.qml": [
        ('text: "DZIAŁA"', 'text: "RUNNING"'),
        ('text: "AKTYWNA"', 'text: "ACTIVE"'),
        ('root.enabledCount + " / " + root.modCount + " modów"',
         'root.enabledCount + " / " + root.modCount + " mods"'),
        ('text: "Uruchom"', 'text: "Launch"'),
        ('root.isActive ? "Aktywna" : "Aktywuj"',
         'root.isActive ? "Active" : "Activate"'),
    ],
    "qml/components/ConflictCard.qml": [
        ('text: "w konflikcie z"', 'text: "conflicts with"'),
        ('text: "Przyczyna - oba mody modyfikują " + root.fileText',
         'text: "Reason - both mods modify " + root.fileText'),
        ('text: "Zachowaj " + root.modAName.split(" ")[0]',
         'text: "Keep " + root.modAName.split(" ")[0]'),
        ('text: "Zachowaj " + root.modBName.split(" ")[0]',
         'text: "Keep " + root.modBName.split(" ")[0]'),
        ('text: "Szczegóły"', 'text: "Details"'),
    ],
    "qml/components/UpdateCard.qml": [
        ('? (root.isDownloading ? "Pobieranie aktualizacji… " + Math.round(root.downloadState.progress) + "%" : "W kolejce do pobrania")',
         '? (root.isDownloading ? "Downloading update… " + Math.round(root.downloadState.progress) + "%" : "Queued for download")'),
        (': "Wydano " + root.updatedAgo + "  ·  " + root.sizeText',
         ': "Released " + root.updatedAgo + "  ·  " + root.sizeText'),
        ('text: root.isDone ? "Gotowe" : "Aktualizuj"',
         'text: root.isDone ? "Done" : "Update"'),
    ],
    "qml/pages/DashboardPage.qml": [
        ('title: "ZAINSTALOWANE"', 'title: "INSTALLED"'),
        ('title: "WŁĄCZONE"', 'title: "ENABLED"'),
        ('title: "KONFLIKTY"', 'title: "CONFLICTS"'),
        ('title: "AKTUALIZACJE"', 'title: "UPDATES"'),
        ('title: "Aktywna instancja"', 'title: "Active instance"'),
        ('"Włączonych modów: " + Mods.enabledCount + " z " + Mods.totalMods',
         '"Enabled mods: " + Mods.enabledCount + " of " + Mods.totalMods'),
        ('text: "Zarządzaj instancjami"', 'text: "Manage instances"'),
        ('title: "Konflikty"', 'title: "Conflicts"'),
        ('? Mods.conflictCount + " konfliktów wymaga Twojej uwagi"',
         '? Mods.conflictCount + " conflicts require your attention"'),
        (': "Wszystkie mody dogadują się ze sobą"',
         ': "All mods are compatible with each other"'),
        ('text: "Dwa lub więcej włączonych modów modyfikuje te same pliki gry. Kolejność ładowania decyduje, które zmiany wygrają."',
         'text: "Two or more enabled mods modify the same game files. Load order decides which changes win."'),
        ('text: "W bieżącej kolejności ładowania nie wykryto konfliktów między modami."',
         'text: "No conflicts detected between mods in the current load order."'),
        ('text: "Zobacz konflikty"', 'text: "View conflicts"'),
    ],
    "qml/pages/ModsPage.qml": [
        ('{ key: "all",       label: "Wszystkie" }', '{ key: "all",       label: "All" }'),
        ('{ key: "enabled",   label: "Włączone" }', '{ key: "enabled",   label: "Enabled" }'),
        ('{ key: "disabled",  label: "Wyłączone" }', '{ key: "disabled",  label: "Disabled" }'),
        ('{ key: "updates",   label: "Aktualizacje" }', '{ key: "updates",   label: "Updates" }'),
        ('{ key: "conflicts", label: "Konflikty" }', '{ key: "conflicts", label: "Conflicts" }'),
        ('{ value: "custom",    label: "Kolejność ładowania" }', '{ value: "custom",    label: "Load order" }'),
        ('{ value: "name",      label: "Nazwa" }', '{ value: "name",      label: "Name" }'),
        ('{ value: "installed", label: "Data instalacji" }', '{ value: "installed", label: "Install date" }'),
        ('{ value: "updated",   label: "Ostatnia aktualizacja" }', '{ value: "updated",   label: "Last updated" }'),
        ('{ value: "author",    label: "Autor" }', '{ value: "author",    label: "Author" }'),
        ('{ value: "size",      label: "Rozmiar" }', '{ value: "size",      label: "Size" }'),
        ('title: "Mody"', 'title: "Mods"'),
        ('"Wyświetlono " + modsView.count + " z " + Mods.totalMods + " modów · "',
         '"Showing " + modsView.count + " of " + Mods.totalMods + " mods · "'),
        ('+ Mods.enabledCount + " włączonych"', '+ Mods.enabledCount + " enabled"'),
        ('text: "Odśwież bibliotekę"', 'text: "Refresh library"'),
        ('text: "Importuj folder"', 'text: "Import folder"'),
        ('text: "Dodaj mod"', 'text: "Add mod"'),
        ('placeholder: "Szukaj modów…"', 'placeholder: "Search mods…"'),
        ('? "Pobieram ikony modów z 7daystodiemods.com: " + Mods.thumbStatus',
         '? "Fetching mod icons from 7daystodiemods.com: " + Mods.thumbStatus'),
        (': "Przeciągnij karty, aby zmienić kolejność ładowania - mody niżej na liście nadpisują pliki ładowane wcześniej."',
         ': "Drag cards to change load order - mods lower on the list override files loaded earlier."'),
        ('title: "Brak wyników"', 'title: "No results"'),
        (': "Brak modów w tej kategorii."', ': "No mods in this category."'),
        ('actionText: "Wyczyść filtry"', 'actionText: "Clear filters"'),
    ],
    "qml/pages/ProfilesPage.qml": [
        ('title: "Instancje"', 'title: "Instances"'),
        ('caption: "Izolowane katalogi danych, flagi startowe i uruchamianie przez Steam - aktywna instancja jest celem przycisku Uruchom"',
         'caption: "Isolated data folders, launch flags and Steam launcher - the active instance is the target of the Launch button"'),
        ('Game.isRunning ? "Zatrzymaj grę" : "Nowa instancja"',
         'Game.isRunning ? "Stop game" : "New instance"'),
        ('text: "Utwórz nową instancję"', 'text: "Create new instance"'),
    ],
    "qml/pages/BackupsPage.qml": [
        ('title: "Kopie zapasowe"', 'title: "Backups"'),
        ('caption: "Pełna kopia instancji - przywróć po usunięciu."',
         'caption: "Full instance backup - restore after deletion."'),
        ('text: "Utwórz kopię"', 'text: "Create backup"'),
        ('packDelegate.packItemCount + " elementów"', 'packDelegate.packItemCount + " items"'),
        ('"·  utworzono " + packDelegate.packCreatedText', '"·  created " + packDelegate.packCreatedText'),
        ('"·  aktualizowano " + packDelegate.packUpdatedText', '"·  updated " + packDelegate.packUpdatedText'),
        ('text: "Aktualizuj"', 'text: "Update"'),
        ('text: "Przywróć"', 'text: "Restore"'),
        ('title: "Brak kopii zapasowych"', 'title: "No backups"'),
        ('subtitle: "Utwórz kopię z instancji, żeby zachować pełny stan modów i zapisów."',
         'subtitle: "Create a backup from an instance to preserve the full state of mods and saves."'),
        ('actionText: "Utwórz z instancji"', 'actionText: "Create from instance"'),
    ],
    "qml/pages/ConflictsPage.qml": [
        ('title: "Konflikty modów"', 'title: "Mod conflicts"'),
        ('? Conflicts.count + " konfliktów między włączonymi modami"',
         '? Conflicts.count + " conflicts between enabled mods"'),
        (': "Nie wykryto konfliktów"', ': "No conflicts detected"'),
        ('text: "Przejdź do modów"', 'text: "Go to mods"'),
        ('title: "Brak konfliktów"', 'title: "No conflicts"'),
        ('subtitle: "Włączone mody nie kłócą się o te same pliki gry."',
         'subtitle: "Enabled mods do not modify the same game files."'),
    ],
    "qml/pages/UpdatesPage.qml": [
        ('title: "Dostępne aktualizacje"', 'title: "Available updates"'),
        ('? Mods.updateCount + " modów ma nowsze wersje"',
         '? Mods.updateCount + " mods have newer versions"'),
        (': "Wszystko jest aktualne"', ': "Everything is up to date"'),
        ('Mods.updateCheckBusy ? "Sprawdzanie…" : "Sprawdź aktualizacje"',
         'Mods.updateCheckBusy ? "Checking…" : "Check for updates"'),
        ('text: "Aktualizuj wszystkie"', 'text: "Update all"'),
        ('title: "Wszystkie mody są aktualne"', 'title: "All mods are up to date"'),
        ('subtitle: "Nowe wersje pojawią się tutaj, gdy tylko autorzy je wydadzą."',
         'subtitle: "New versions will appear here as soon as authors release them."'),
    ],
    "qml/pages/DownloadsPage.qml": [
        ('title: "Pobieranie"', 'title: "Downloads"'),
        ('? Downloads.activeCount + " w toku · " + Downloads.completedCount + " zakończonych"',
         '? Downloads.activeCount + " in progress · " + Downloads.completedCount + " completed"'),
        (': "Zarządzaj pobieraniem modów i aktualizacji"',
         ': "Manage mod and update downloads"'),
        ('text: "Wyczyść zakończone"', 'text: "Clear completed"'),
        ('placeholder: "Wklej link do modpacka (Git / GitHub / .zip) albo moda z 7daystodiemods.com…"',
         'placeholder: "Paste a modpack link (Git / GitHub / .zip) or a mod URL from 7daystodiemods.com…"'),
        ('text: "Pobierz z URL"', 'text: "Download from URL"'),
        ('text: "AKTYWNE"', 'text: "ACTIVE"'),
        ('text: "ZAKOŃCZONE"', 'text: "COMPLETED"'),
        ('subtitle: "Zainstalowano i gotowe do użycia"', 'subtitle: "Installed and ready to use"'),
        ('statusText: "Zakończono"', 'statusText: "Completed"'),
        ('title: "Brak pobrań"', 'title: "No downloads"'),
        ('subtitle: "Wklej link do modpacka albo moda z 7daystodiemods.com powyżej, albo przejdź do strony Aktualizacje."',
         'subtitle: "Paste a modpack or 7daystodiemods.com link above, or go to the Updates page."'),
        ('actionText: "Przejdź do aktualizacji"', 'actionText: "Go to updates"'),
    ],
    "qml/pages/DiscoverPage.qml": [
        ('placeholder: "Szukaj w katalogu modów..."', 'placeholder: "Search mod catalog..."'),
        ('text: "Odśwież"', 'text: "Refresh"'),
        ('text: "Pobieranie"', 'text: "Downloads"'),
        ('Discover.busy ? "Wyszukiwanie..." : Discover.total + " wyników"',
         'Discover.busy ? "Searching..." : Discover.total + " results"'),
        ('card.modelData.downloads + " pobrań"', 'card.modelData.downloads + " downloads"'),
        ('card.downloading ? "W kolejce" : card.stateKey === "completed" ? "Pobrano" : "Pobierz"',
         'card.downloading ? "Queued" : card.stateKey === "completed" ? "Downloaded" : "Download"'),
        ('Discover.busy ? "Ładowanie katalogu..." : Discover.error || "Brak modów pasujących do wybranych filtrów."',
         'Discover.busy ? "Loading catalog..." : Discover.error || "No mods matching the selected filters."'),
    ],
    "qml/pages/SettingsPage.qml": [
        ('label: "Ogólne"', 'label: "General"'),
        ('label: "Gra"', 'label: "Game"'),
        ('label: "Pobieranie"', 'label: "Downloads"'),
        ('label: "Wygląd"', 'label: "Appearance"'),
        ('label: "Zaawansowane"', 'label: "Advanced"'),
        ('title: "Ogólne"', 'title: "General"'),
        ('caption: "Podstawowe zachowanie aplikacji"', 'caption: "Basic application behavior"'),
        ('label: "Język"', 'label: "Language"'),
        ('description: "Język interfejsu (kolejne tłumaczenia w planach)"',
         'description: "Interface language (more translations planned)"'),
        ('{ value: "pl", label: "Polski" }', '{ value: "pl", label: "English" }'),
        ('label: "Motyw"', 'label: "Theme"'),
        ('description: "Zmienia się natychmiast, bez restartu aplikacji"',
         'description: "Applies immediately without restarting the application"'),
        ('{ value: "dark", label: "Ciemny" }', '{ value: "dark", label: "Dark" }'),
        ('{ value: "light", label: "Jasny" }', '{ value: "light", label: "Light" }'),
        ('{ value: "stalker", label: "Strefa" }', '{ value: "stalker", label: "Zone" }'),
        ('label: "Uruchamiaj zminimalizowane"', 'label: "Start minimized"'),
        ('description: "Uruchamiaj menedżera zminimalizowanego do zasobnika systemowego"',
         'description: "Start the manager minimized to the system tray"'),
        ('{ key: "general",    label: "Ogólne",       icon: "sliders" }',
         '{ key: "general",    label: "General",      icon: "sliders" }'),
        ('{ key: "game",       label: "Gra",          icon: "gamepad" }',
         '{ key: "game",       label: "Game",         icon: "gamepad" }'),
        ('{ key: "downloads",  label: "Pobieranie",   icon: "download" }',
         '{ key: "downloads",  label: "Downloads",    icon: "download" }'),
        ('{ key: "appearance", label: "Wygląd",       icon: "palette" }',
         '{ key: "appearance", label: "Appearance",   icon: "palette" }'),
        ('{ key: "advanced",   label: "Zaawansowane", icon: "terminal" }',
         '{ key: "advanced",   label: "Advanced",     icon: "terminal" }'),
    ],
    "src/models/mod.py": [
        ('_MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",\n           "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]',
         '_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]'),
        ('return "nieznana data"', 'return "unknown date"'),
        ('return "właśnie teraz"', 'return "just now"'),
        ('return f"{minutes} min temu"', 'return f"{minutes} min ago"'),
        ("return f\"{hours} {_pl_plural(hours, 'godzinę', 'godziny', 'godz.')} temu\"",
         'return f"{hours} h ago"'),
        ("return f\"{days} {_pl_plural(days, 'dzień', 'dni', 'dni')} temu\"",
         'return f"{days} d ago"'),
        ("return f\"{months} {_pl_plural(months, 'miesiąc', 'miesiące', 'miesięcy')} temu\"",
         'return f"{months} mo ago"'),
        ("return f\"{years} {_pl_plural(years, 'rok', 'lata', 'lat')} temu\"",
         'return f"{years} yr ago"'),
    ],
    "src/models/profile.py": [
        ('return "domyślna lokalizacja gry"', 'return "default game location"'),
    ],
    "src/backend/profile_manager.py": [
        ('name=instance.name,', 'name="Main" if instance.name == "Główna" else instance.name,'),
        ('"Gra bez izolacji danych - zachowanie jak bez menedżera"',
         '"Game without data isolation - standard behavior"'),
        ('{"value": i.instance_id, "label": i.name}',
         '{"value": i.instance_id, "label": "Main" if i.name == "Główna" else i.name}'),
    ],
    "src/backend/mod_manager.py": [
        ('category="Biblioteka"', 'category="Library"'),
        ('author=entry.author or "Nieznany"', 'author=entry.author or "Unknown"'),
        ('description=entry.description,',
         'description={"Beer Regens Health": "Beer grants a small passive health regeneration bonus while buzzed, similar to Grandpa\'s moonshine.", "Quality Colors": "Allows choosing a custom color for each item quality tier and displays it as the item icon background in every inventory slot.", "CATUI": "Completely redesigned QoL interface: clean HUD (health, stamina, food, water, buffs, stats and ping) and enemy health bars.", "CATUI_toolbelt_more_slot": "CATUI add-on expanding the toolbelt with additional slots. Simple UI mod by BigCat.", "CATUI Craft Queue Fix": "Prevents duplicate entries in the crafting queue when a single click is registered twice."}.get(entry.title, entry.description),'),
    ],
    "src/backend/conflict_detector.py": [
        ('f"Oba mody modyfikują plik {file_name}. Mod "\n                            f"załadowany później nadpisze zmiany drugiego - "\n                            f"wyłącz jeden z nich lub scal zmiany ręcznie."',
         'f"Both mods modify {file_name}. The mod loaded later will override the other\'s changes - disable one of them or merge the changes manually."'),
    ],
    "src/backend/discover.py": [
        ('self._categories = [{"value": "", "label": "Wszystkie kategorie"}]',
         'self._categories = [{"value": "", "label": "All categories"}]'),
        ('self._versions = [{"value": "", "label": "Wszystkie wersje"}]',
         'self._versions = [{"value": "", "label": "All versions"}]'),
    ],
}


def first_mod_id() -> str:
    lib_path = Path.home() / ".7dtd_modmanager" / "mm-library.json"
    if lib_path.is_file():
        try:
            data = json.loads(lib_path.read_text(encoding="utf-8"))
            entries = data.get("entries") or []
            if entries and isinstance(entries[0], dict):
                return str(entries[0].get("library_id") or "darkness-falls")
        except Exception:
            pass
    return "darkness-falls"


def main() -> None:
    mod_id = first_mod_id()

    # (nazwa pliku wyjściowego, --page, --open-drawer, czas oczekiwania w ms)
    targets = [
        ("dashboard-en.png", "dashboard", "", 1800),
        ("mods-en.png", "mods", "", 1800),
        ("drawer-en.png", "mods", mod_id, 2000),
        ("profiles-en.png", "profiles", "", 1800),
        ("conflicts-en.png", "conflicts", "", 1800),
        ("updates-en.png", "updates", "", 1800),
        ("downloads-en.png", "downloads", "", 1800),
        ("settings-en.png", "settings", "", 1800),
        ("discover-en.png", "discover", "", 3200),
        ("modpacks-en.png", "modpacks", "", 1800),
    ]

    # opcjonalny filtr z linii komend, np.: python tests/screenshot_en.py mods settings
    only = {arg.removesuffix("-en.png").removesuffix(".png") for arg in sys.argv[1:]}
    if only:
        targets = [t for t in targets if t[0].removesuffix("-en.png") in only or t[1] in only]

    backups: dict[Path, str] = {}
    try:
        for rel_path, pairs in REPLACEMENTS.items():
            path = ROOT / rel_path
            original = path.read_text(encoding="utf-8")
            backups[path] = original
            modified = original
            for old, new in pairs:
                modified = modified.replace(old, new)
            path.write_text(modified, encoding="utf-8")

        out_dir = ROOT / "docs" / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)

        for filename, page, drawer_mod, wait_ms in targets:
            out_png = out_dir / filename
            cmd = [
                app_python(), str(ROOT / "src" / "main.py"),
                "--page", page,
                "--width", "1400",
                "--height", "880",
                "--wait", str(wait_ms),
                "--screenshot", str(out_png),
            ]
            if drawer_mod:
                cmd.extend(["--open-drawer", drawer_mod])

            print(f"[{filename}] generowanie widoku '{page}'...")
            subprocess.run(cmd, cwd=ROOT, check=True,
                           env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})

        print(f"Gotowe - wygenerowano {len(targets)} zrzutów w {out_dir}")
    finally:
        for path, content in backups.items():
            path.write_text(content, encoding="utf-8")
        print("Przywrócono oryginalne pliki.")


if __name__ == "__main__":
    main()
