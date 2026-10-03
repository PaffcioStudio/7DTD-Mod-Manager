"""Realistic mock data so the UI looks like a finished product on first run.

Mod names/authors reference well-known community mods for flavour; everything
here is seed data only - the user's own Mods folder can be scanned instead
(see mod_scanner.py and Settings -> Game).
"""

from __future__ import annotations

from models.mod import make_date

# --------------------------------------------------------------------------- #
# installed mods
# --------------------------------------------------------------------------- #
# keys: id, name, author, category, version, new_version, enabled,
#       description, size_bytes, downloads, rating, tags, dependencies,
#       modified_files, installed, updated
MODS: list[dict] = [
    dict(
        id="darkness-falls",
        name="Darkness Falls",
        author="KhaineGB",
        category="Overhaul",
        version="4.10",
        new_version="",
        enabled=True,
        description=(
            "Definitywna przebudowa hardcore: własne klasy, wolniejszy progres, "
            "przemyślane zbalansowanie łupów i brutalny wczesny etap gry. "
            "Nie dla słabych nerwów."
        ),
        size_bytes=2_946_000_000,
        downloads=1_412_000,
        rating=4.9,
        tags=["przebudowa", "klasy", "hardcore"],
        dependencies=[],
        modified_files=["entityclasses.xml", "items.xml"],
        installed="2024-11-02 10:00",
        updated="2025-08-14 18:30",
    ),
    dict(
        id="undead-legacy",
        name="Undead Legacy",
        author="Subquake",
        category="Overhaul",
        version="3.21",
        new_version="",
        enabled=False,
        description=(
            "Konwersja totalna skupiona na eksploracji, głębi craftingu "
            "i immersyjnym przetrwaniu. Obecnie wyłączona na rzecz głównego "
            "zestawu."
        ),
        size_bytes=3_412_000_000,
        downloads=892_000,
        rating=4.8,
        tags=["przebudowa", "przetrwanie", "crafting"],
        dependencies=[],
        modified_files=["entityclasses.xml", "recipes.xml"],
        installed="2025-01-11 21:00",
        updated="2025-07-02 12:00",
    ),
    dict(
        id="ravenhearst",
        name="Ravenhearst",
        author="JaxTeller718",
        category="Overhaul",
        version="6.12",
        new_version="",
        enabled=False,
        description=(
            "Przebudowa osnuta na fabule: setki własnych stacji roboczych, "
            "NPC-ów i zadań. Spore pobieranie, niezapomniany świat."
        ),
        size_bytes=3_105_000_000,
        downloads=764_000,
        rating=4.7,
        tags=["przebudowa", "npc", "zadania"],
        dependencies=[],
        modified_files=["quests.xml"],
        installed="2025-02-20 16:45",
        updated="2025-06-18 09:10",
    ),
    dict(
        id="war-of-the-walkers",
        name="War of the Walkers",
        author="Stallionsden",
        category="Overhaul",
        version="5.8",
        new_version="",
        enabled=False,
        description=(
            "Bogata w funkcje przebudowa: nowe stacje robocze, magia dystansowa, "
            "drony i rozbudowana zawartość końcowego etapu gry."
        ),
        size_bytes=2_980_000_000,
        downloads=655_000,
        rating=4.6,
        tags=["przebudowa", "stacje robocze", "drony"],
        dependencies=[],
        modified_files=["recipes.xml"],
        installed="2025-03-05 19:20",
        updated="2025-05-30 14:00",
    ),
    dict(
        id="age-of-sorcery",
        name="Age of Sorcery 2",
        author="Xyth",
        category="Magic",
        version="2.4.1",
        new_version="",
        enabled=True,
        description=(
            "Pełny system magii dla 7DTD: księgi zaklęć, progres many, "
            "magiczne berła i kręgi przywołań."
        ),
        size_bytes=412_000_000,
        downloads=528_000,
        rating=4.8,
        tags=["magia", "zaklęcia", "progres"],
        dependencies=[],
        modified_files=["buffs.xml"],
        installed="2025-04-12 13:00",
        updated="2025-08-01 10:40",
    ),
    dict(
        id="better-quality-colors",
        name="Better Quality Colors",
        author="Sirillion",
        category="UI",
        version="3.2.1",
        new_version="3.3.0",
        enabled=True,
        description=(
            "Ulepsza kolory jakości przedmiotów - czystsza paleta i lepszy "
            "kontrast w całym interfejsie."
        ),
        size_bytes=8_400_000,
        downloads=412_000,
        rating=4.5,
        tags=["interfejs", "jakość życia", "kolory"],
        dependencies=[],
        modified_files=["uicolors.xml"],
        installed="2024-12-01 09:00",
        updated="2025-07-22 08:15",
    ),
    dict(
        id="agf-backpacks",
        name="AGF Backpacks - 62 Slots",
        author="arramus",
        category="Items",
        version="4.0.3",
        new_version="4.0.4",
        enabled=True,
        description=(
            "Dodaje serię plecaków AGF o pojemności do 62 slotów, wytwarzanych "
            "z materiałów z późnego etapu gry."
        ),
        size_bytes=14_200_000,
        downloads=689_000,
        rating=4.7,
        tags=["plecaki", "ekwipunek", "jakość życia"],
        dependencies=[],
        modified_files=["windows.xml"],
        installed="2024-10-18 11:30",
        updated="2025-08-10 17:00",
    ),
    dict(
        id="sixty-slot-backpack",
        name="60 Slot Backpack",
        author="Sphereii",
        category="Items",
        version="2.1",
        new_version="",
        enabled=True,
        description=(
            "Klasyczne rozszerzenie ekwipunku do 60 slotów. Wchodzi w konflikt "
            "z innymi modami modyfikującymi okno ekwipunku."
        ),
        size_bytes=9_800_000,
        downloads=720_000,
        rating=4.4,
        tags=["plecaki", "ekwipunek"],
        dependencies=[],
        modified_files=["windows.xml"],
        installed="2024-09-30 15:00",
        updated="2025-04-02 12:30",
    ),
    dict(
        id="new-pois-pack",
        name="New POIs Pack Vol. 3",
        author="Tallon Drake",
        category="World",
        version="2.4",
        new_version="2.5",
        enabled=True,
        description=(
            "Ponad 400 ręcznie zaprojektowanych lokacji: galerie handlowe, "
            "bunkry, farmy i miejskie ruiny wtapiające się w Navezgane "
            "i losowy generator świata."
        ),
        size_bytes=1_180_000_000,
        downloads=933_000,
        rating=4.8,
        tags=["lokacje", "świat", "prefaby"],
        dependencies=[],
        modified_files=["prefabs.xml"],
        installed="2025-01-25 10:10",
        updated="2025-08-18 20:00",
    ),
    dict(
        id="better-vehicles",
        name="Better Vehicles",
        author="Stallionsden",
        category="Vehicles",
        version="5.1.2",
        new_version="5.2.0",
        enabled=True,
        description=(
            "Przerobione prowadzenie pojazdów, zużycie paliwa i wytrzymałość "
            "oraz nowe malowania dla 4x4 i motocykla."
        ),
        size_bytes=86_000_000,
        downloads=356_000,
        rating=4.3,
        tags=["pojazdy", "prowadzenie"],
        dependencies=[],
        modified_files=["vehicles.xml"],
        installed="2024-12-20 14:00",
        updated="2025-08-05 16:20",
    ),
    dict(
        id="better-loot",
        name="Better Loot",
        author="Snufkin",
        category="Gameplay",
        version="1.9.3",
        new_version="",
        enabled=True,
        description=(
            "Ponownie balansuje pojemniki, aby eksploracja znów dawała "
            "satysfakcję - łup lepiej dopasowany do etapu gry."
        ),
        size_bytes=6_200_000,
        downloads=501_000,
        rating=4.6,
        tags=["łup", "balans"],
        dependencies=[],
        modified_files=["loot.xml"],
        installed="2025-02-14 09:45",
        updated="2025-07-11 19:00",
    ),
    dict(
        id="loot-overhaul",
        name="Loot Overhaul",
        author="Xyth",
        category="Gameplay",
        version="2.8",
        new_version="",
        enabled=True,
        description=(
            "Kompletne przepisanie ekonomii łupów: poziomy rzadkości, "
            "zapieczętowane skrzynie i unikalne legendarne przedmioty."
        ),
        size_bytes=22_700_000,
        downloads=445_000,
        rating=4.5,
        tags=["łup", "ekonomia", "legendarne"],
        dependencies=[],
        modified_files=["loot.xml"],
        installed="2025-03-01 12:00",
        updated="2025-07-28 11:30",
    ),
    dict(
        id="smx-ui",
        name="SMX UI Overhaul",
        author="Sirillion",
        category="UI",
        version="2.9.7",
        new_version="",
        enabled=True,
        description=(
            "Klasyczny, immersyjny zamiennik HUD-u: minimalistyczne paski "
            "zdrowia, własne ikony efektów i surowy wygląd ekwipunku."
        ),
        size_bytes=46_000_000,
        downloads=1_150_000,
        rating=4.9,
        tags=["interfejs", "hud", "immersja"],
        dependencies=[],
        modified_files=["xui.xml"],
        installed="2024-08-12 08:00",
        updated="2025-08-08 13:10",
    ),
    dict(
        id="forge-ui",
        name="Forge UI",
        author="KhaineGB",
        category="UI",
        version="1.4.2",
        new_version="",
        enabled=True,
        description=(
            "Nowoczesny, czysty redesign interfejsu: ciemne panele "
            "i wyrazista typografia menu oraz okien craftingu."
        ),
        size_bytes=12_500_000,
        downloads=298_000,
        rating=4.2,
        tags=["interfejs", "hud"],
        dependencies=[],
        modified_files=["xui.xml"],
        installed="2025-04-02 17:30",
        updated="2025-06-25 10:00",
    ),
    dict(
        id="hdhq-textures",
        name="HDHQ Texture Pack",
        author="Roland",
        category="Graphics",
        version="1.8.4",
        new_version="1.9",
        enabled=True,
        description=(
            "Tekstury w wysokiej rozdzielczości dla terenu, bloków "
            "i przedmiotów. Spore pobieranie, spektakularna poprawa oprawy."
        ),
        size_bytes=2_048_000_000,
        downloads=856_000,
        rating=4.7,
        tags=["tekstury", "grafika"],
        dependencies=[],
        modified_files=["textures.xml"],
        installed="2024-07-19 10:00",
        updated="2025-08-12 22:00",
    ),
    dict(
        id="electricity-expanded",
        name="Electricity Expanded",
        author="TormentedEmu",
        category="Gameplay",
        version="3.6.1",
        new_version="",
        enabled=True,
        description=(
            "Nowe komponenty elektryczne, przekaźniki, timery i bramki logiczne "
            "do poważnej automatyzacji bazy."
        ),
        size_bytes=34_000_000,
        downloads=267_000,
        rating=4.6,
        tags=["elektryka", "budowa bazy", "automatyzacja"],
        dependencies=[],
        modified_files=["power.xml"],
        installed="2025-01-08 09:20",
        updated="2025-07-15 15:40",
    ),
    dict(
        id="custom-zombies",
        name="Snufkin's Custom Zombies",
        author="Snufkin",
        category="Zombies",
        version="4.2.0",
        new_version="",
        enabled=True,
        description=(
            "Dodaje ponad 30 ręcznie dostrojonych archetypów zombie "
            "o unikalnej szybkości, obrażeniach i nocnym zachowaniu."
        ),
        size_bytes=58_000_000,
        downloads=634_000,
        rating=4.8,
        tags=["zombie", "trudność"],
        dependencies=[],
        modified_files=["zombies.xml"],
        installed="2024-11-20 19:00",
        updated="2025-08-02 12:00",
    ),
    dict(
        id="gyrocopter-overhaul",
        name="Gyrocopter Overhaul",
        author="Sphereii",
        category="Vehicles",
        version="1.6",
        new_version="",
        enabled=True,
        description=(
            "Realistyczny model lotu żyrokoptera, ulepszenia ładunkowe "
            "i opcjonalne punkty trasy autopilota."
        ),
        size_bytes=24_000_000,
        downloads=187_000,
        rating=4.1,
        tags=["pojazdy", "lotnictwo"],
        dependencies=[],
        modified_files=["gyrocopter.xml"],
        installed="2025-05-05 11:00",
        updated="2025-07-20 09:00",
    ),
    dict(
        id="bandits-npcs",
        name="Bandits & NPCs",
        author="Xyth",
        category="Zombies",
        version="2.3",
        new_version="",
        enabled=True,
        description=(
            "Wrogie obozy bandytów, przyjazni handlarze na szlaku i najemni "
            "towarzysze z prostymi rozkazami."
        ),
        size_bytes=165_000_000,
        downloads=421_000,
        rating=4.5,
        tags=["npc", "bandyci", "towarzysze"],
        dependencies=["custom-zombies"],
        modified_files=["npcs.xml"],
        installed="2025-03-18 14:30",
        updated="2025-08-16 18:45",
    ),
    dict(
        id="crop-rotation",
        name="Crop Rotation & Farming",
        author="TormentedEmu",
        category="Gameplay",
        version="1.2.5",
        new_version="",
        enabled=True,
        description=(
            "Głębsze rolnictwo: premie za płodozmian, szklarnie, nawadnianie "
            "i poziomy nasion."
        ),
        size_bytes=18_600_000,
        downloads=154_000,
        rating=4.3,
        tags=["rolnictwo", "przetrwanie"],
        dependencies=[],
        modified_files=["crops.xml"],
        installed="2025-02-27 16:00",
        updated="2025-06-10 08:30",
    ),
    dict(
        id="xp-balancer",
        name="XP Balancer Pro",
        author="KhaineGB",
        category="Gameplay",
        version="1.8.0",
        new_version="",
        enabled=True,
        description=(
            "Konfigurowalne krzywe doświadczenia dla każdej aktywności - "
            "crafting i eksploracja równie opłacalne jak walka z zombie."
        ),
        size_bytes=2_100_000,
        downloads=342_000,
        rating=4.4,
        tags=["progres", "balans"],
        dependencies=[],
        modified_files=["progression.xml"],
        installed="2024-12-12 12:12",
        updated="2025-05-14 10:00",
    ),
    dict(
        id="compopack",
        name="CompoPack 47",
        author="Magoli",
        category="World",
        version="47.2",
        new_version="47.3",
        enabled=True,
        description=(
            "Społecznościowy mega-pakiet prefabów: tysiące gotowych lokacji "
            "do losowo generowanych miast i własnych skupisk."
        ),
        size_bytes=1_420_000_000,
        downloads=1_210_000,
        rating=4.9,
        tags=["lokacje", "świat", "prefaby"],
        dependencies=[],
        modified_files=["rwgmixer.xml"],
        installed="2024-10-01 10:00",
        updated="2025-08-19 21:00",
    ),
    dict(
        id="zombie-loot-expansion",
        name="Zombie Loot Expansion",
        author="Snufkin",
        category="Zombies",
        version="2.0",
        new_version="",
        enabled=True,
        description=(
            "Zombie noszą to, na co wyglądają - pielęgniarki gubią leki, "
            "radiowozy taśmę izolacyjną i klej."
        ),
        size_bytes=640_000_000,
        downloads=388_000,
        rating=4.6,
        tags=["zombie", "łup"],
        dependencies=[],
        modified_files=["zombie-loot.xml"],
        installed="2025-08-21 09:30",
        updated="2025-08-21 09:30",
    ),
]

# --------------------------------------------------------------------------- #
# profiles (id, name, description, states, created, color)
# --------------------------------------------------------------------------- #
def _enabled_snapshot(mods: list[dict]) -> dict:
    return {m["id"]: bool(m["enabled"]) for m in mods}


PROFILES: list[dict] = [
    dict(
        id="vanilla-plus",
        name="Vanilla Plus",
        description="Tylko mody poprawiające wygodę - rdzeń gry pozostaje nienaruszony.",
        mod_states={
            "better-quality-colors": True,
            "agf-backpacks": True,
            "better-vehicles": True,
            "xp-balancer": True,
            "crop-rotation": True,
            "electricity-expanded": True,
            "new-pois-pack": False,
            "hdhq-textures": True,
        },
        created="2025-01-15 18:00",
        color_tag="#5CA9FF",
    ),
    dict(
        id="main-setup",
        name="Mój główny zestaw",
        description="Pełny zestaw ze wszystkim, w co aktualnie gram.",
        mod_states=None,  # filled from MODS snapshot below
        created="2025-04-10 20:30",
        color_tag="#FF7A38",
    ),
    dict(
        id="hardcore-survival",
        name="Hardcore Survival",
        description="Darkness Falls z minimum udogodnień. Weź bandaże.",
        mod_states={
            "darkness-falls": True,
            "custom-zombies": True,
            "bandits-npcs": True,
            "better-loot": True,
            "loot-overhaul": False,
            "smx-ui": True,
            "sixty-slot-backpack": False,
            "compopack": True,
            "new-pois-pack": True,
            "xp-balancer": True,
            "crop-rotation": True,
            "electricity-expanded": True,
        },
        created="2025-06-02 21:15",
        color_tag="#EF5D5D",
    ),
    dict(
        id="multiplayer-weekend",
        name="Weekend multiplayer",
        description="Lekki i stabilny zestaw na sesje na serwerze dedykowanym.",
        mod_states={
            "better-quality-colors": True,
            "sixty-slot-backpack": True,
            "new-pois-pack": True,
            "compopack": True,
            "better-vehicles": True,
            "electricity-expanded": True,
            "crop-rotation": True,
            "xp-balancer": True,
            "hdhq-textures": True,
        },
        created="2025-07-08 19:45",
        color_tag="#34D399",
    ),
]

ACTIVE_PROFILE_ID = "main-setup"

# fill the "My Main Setup" profile from the seed state
for profile in PROFILES:
    if profile["mod_states"] is None:
        profile["mod_states"] = _enabled_snapshot(MODS)


# --------------------------------------------------------------------------- #
# downloadable catalog (mods NOT installed yet)
# --------------------------------------------------------------------------- #
CATALOG: list[dict] = [
    dict(
        id="smarter-hordes",
        name="Smarter Hordes",
        author="Snufkin",
        category="Zombies",
        version="4.0",
        size_bytes=48_000_000,
        downloads=512_000,
        rating=4.7,
        description=(
            "Hordy badają Twoje umocnienia, wyłamują drugorzędne mury "
            "i pamiętają słabe punkty między krwawymi księżycami."
        ),
        tags=["zombie", "ai", "hordy"],
    ),
    dict(
        id="navezgane-roads",
        name="Navezgane Expanded Roads",
        author="Tallon Drake",
        category="World",
        version="1.4",
        size_bytes=210_000_000,
        downloads=176_000,
        rating=4.4,
        description="Poszerzone autostrady, widokowe trasy i naprawione mosty w całym Navezgane.",
        tags=["świat", "drogi"],
    ),
    dict(
        id="city-generation",
        name="Custom City Generation",
        author="Xyth",
        category="World",
        version="3.1",
        size_bytes=1_820_000_000,
        downloads=289_000,
        rating=4.6,
        description="Śródmieścia, strefy przemysłowe i przedmieścia z zróżnicowaną wysokością zabudowy.",
        tags=["świat", "miasta", "rwg"],
    ),
    dict(
        id="medieval-fortresses",
        name="Medieval Fortresses Pack",
        author="JaxTeller718",
        category="World",
        version="2.2",
        size_bytes=960_000_000,
        downloads=134_000,
        rating=4.5,
        description="Zamki, twierdze i otoczone murami miasteczka - gotowe do splądrowania lub objęcia jako baza.",
        tags=["lokacje", "średniowiecze"],
    ),
    dict(
        id="real-darkness",
        name="Real Darkness",
        author="Roland",
        category="Graphics",
        version="2.1",
        size_bytes=12_000_000,
        downloads=298_000,
        rating=4.2,
        description="Czarne jak smoła noce, stożkowy snop latarek i klimatyczne cienie we wnętrzach.",
        tags=["grafika", "atmosfera"],
    ),
]

# --------------------------------------------------------------------------- #
# initial download queue state
# --------------------------------------------------------------------------- #
INITIAL_ACTIVE_DOWNLOAD = dict(
    kind="update",
    ref_id="hdhq-textures",
    title="HDHQ Texture Pack - v1.9",
    subtitle="Aktualizacja · tekstury 2K",
    progress=0.82,          # fraction
    total_bytes=2_048_000_000,
)

INITIAL_COMPLETED_DOWNLOAD = dict(
    kind="catalog",
    ref_id="zombie-loot-expansion",
    title="Zombie Loot Expansion - v2.0",
    subtitle="Instalacja",
    total_bytes=640_000_000,
)


def seed_mods() -> list[dict]:
    """Deep-ish copy of the seed mod list."""
    return [dict(m) for m in MODS]


def seed_profiles() -> list[dict]:
    return [dict(p, mod_states=dict(p["mod_states"])) for p in PROFILES]


def catalog_entry(catalog_id: str) -> dict | None:
    for entry in CATALOG:
        if entry["id"] == catalog_id:
            return dict(entry)
    return None


def parse_date(text: str):
    return make_date(text)
