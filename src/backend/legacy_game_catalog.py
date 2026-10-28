"""Archiwalne wydania 7 Days to Die z publicznych manifestów Steam.

Źródło: https://community.thefunpimps.com/threads/guide-how-to-download-almost-every-past-steam-version-of-7-days-to-die-from-steam.11268/
Wartości po strzałce w historii Steam są NOWYM manifestem wydania.
Do uruchamiania przez Proton wybieramy wyłącznie depoty Windows.
Wersja Alpha 8.8 należy już do normalnych branchy Steam.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LegacyRelease:
    branch: str
    label: str
    date: str
    depot: str
    manifest: str
    osarch: str
    download_available: bool = True
    steam_branch: bool = False


# branch | nazwa | data | depot Windows | manifest | architektura
# Osobne wpisy zachowują poprawki wydane pod tym samym numerem Alpha.
_ROWS = """
alpha5.0|Alpha 5|2013-12-13|251571|8674858241122065491|32
alpha5.0-fix1|Alpha 5 - quick fix|2013-12-14|251571|4247862906762382576|32
alpha5.0-fix2|Alpha 5 - additional fixes|2013-12-21|251571|5316387393437744190|32
alpha6.0|Alpha 6|2014-01-15|251574|7417461347934718866|32
alpha6.1|Alpha 6.1|2014-01-17|251574|2792130306057376529|32
alpha6.2|Alpha 6.2|2014-01-30|251574|3925976303593507227|32
alpha6.3|Alpha 6.3|2014-02-03|251574|1876530437970127190|32
alpha6.4|Alpha 6.4|2014-02-06|251574|862254068326349864|32
alpha7.0|Alpha 7|2014-02-28|251576|1730022800995997518|64
alpha7.1|Alpha 7.1|2014-03-01|251576|6987708882669660417|64
alpha7.2|Alpha 7.2|2014-03-04|251576|165752785413164407|64
alpha7.3|Alpha 7.3|2014-03-07|251576|7089868188207379992|64
alpha7.3-v2|Alpha 7.3 v2|2014-03-07|251576|2677701425442127837|64
alpha7.4|Alpha 7.4|2014-03-08|251576|2150331560898874531|64
alpha7.5|Alpha 7.5|2014-03-09|251576|6815326274139184895|64
alpha7.6|Alpha 7.6|2014-03-15|251576|4546807630044588160|64
alpha7.7|Alpha 7.7|2014-03-18|251576|3515394596294775971|64
alpha7.7-b7|Alpha 7.7 b7 fix|2014-03-24|251576|2595209504322754915|64
alpha7.8|Alpha 7.8|2014-04-04|251576|5597089491074022279|64
alpha7.9|Alpha 7.9|2014-04-08|251576|5614543131868497954|64
alpha7.10|Alpha 7.10|2014-04-19|251576|4644625435838178353|64
alpha7.11|Alpha 7.11|2014-04-21|251576|6548888709412020723|64
alpha8.0|Alpha 8|2014-05-06|251576|8665947380848930159|64
alpha8.1|Alpha 8.1|2014-05-10|251576|6788823199049484219|64
alpha8.2|Alpha 8.2|2014-05-22|251576|505044936065153283|64
alpha8.3|Alpha 8.3|2014-05-28|251576|4703636079767854386|64
alpha8.4|Alpha 8.4|2014-05-30|251576|6732440793525449112|64
alpha8.5|Alpha 8.5|2014-05-31|251576|4011021809865817079|64
alpha8.6|Alpha 8.6|2014-06-14|251576|4085200615993808623|64
alpha8.6-ninja|Alpha 8.6 - ninja patch|2014-06-15|251576|6738103586104812619|64
alpha8.7|Alpha 8.7|2014-07-09|251576|7508090567390550102|64
alpha8.8|Alpha 8.8 (Steam)|2014-07-23|251576|2055364469586533071|64
""".strip()


# Audyt z 28.10.2026: depot Alpha 6 nie jest już przypisany do gry.
# Wpisy zostają na liście, bo nadal można zaimportować własną kopię.
def _parse_catalog() -> tuple[LegacyRelease, ...]:
    parsed = []
    for line in _ROWS.splitlines():
        branch, label, release_date, depot, manifest, arch = line.split("|")
        parsed.append(LegacyRelease(
            branch, label, release_date, depot, manifest, arch,
            download_available=(depot != "251574"),
            steam_branch=(branch == "alpha8.8"),
        ))
    assert len({item.branch for item in parsed}) == len(parsed)
    return tuple(parsed)


# Zwykłe numery Alpha są wspólne dla obu języków. Warianty wydań
# dostają klucze tłumaczeń, bez wpisywania polskiego tekstu do danych Steam.
_TRANSLATED_RELEASES = frozenset({
    "alpha5.0-fix1", "alpha5.0-fix2", "alpha7.3-v2",
    "alpha7.7-b7", "alpha8.6-ninja", "alpha8.8",
})

RELEASES = _parse_catalog()
RELEASE_BY_BRANCH = {item.branch: item for item in RELEASES}


def release_options() -> list[dict]:
    """Dane do listy wyboru, bez niebezpiecznych numerów wpisywanych ręcznie."""
    return [
        {
            "branch": entry.branch,
            "label": entry.label,
            "label_key": ("steamReleases.legacy.release." + entry.branch
                          if entry.branch in _TRANSLATED_RELEASES else ""),
            "date": date.fromisoformat(entry.date).strftime("%d-%m-%Y"),
            "depot": entry.depot,
            "manifest": entry.manifest,
            "osarch": entry.osarch,
            "download_available": entry.download_available,
            "steam_branch": entry.steam_branch,
        }
        for entry in RELEASES
    ]
