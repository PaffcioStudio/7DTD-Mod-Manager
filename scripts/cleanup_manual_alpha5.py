#!/usr/bin/env python3
"""Cofnij ręczną instalację Alpha 5 bez naruszania wersji z launchera.

Uruchom najpierw bez --apply, aby zobaczyć plan. --apply wykonuje operację.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


class UnsafeCleanup(RuntimeError):
    pass


def cleanup(home: Path, *, apply: bool = False) -> list[str]:
    home = home.expanduser().resolve()
    state = home / '.7dtd_modmanager'
    versions = state / 'game-versions'
    link = versions / 'alpha5.0'
    source = home / 'Gry' / '7DTD-Alpha-5.0'
    registry = state / 'game-versions.json'
    instances_path = state / 'instances.json'
    report: list[str] = []

    # Usuwamy wyłącznie dowiązanie wykonane przez dawną komendę.
    old_link = link.is_symlink() and link.resolve(strict=False) == source.resolve(strict=False)
    if link.is_symlink() and not old_link:
        raise UnsafeCleanup(f'alpha5.0 wskazuje już na inny folder: {link.resolve()}')
    if link.exists() and not link.is_symlink():
        report.append(f'Zachowano instalację menedżera (zwykły katalog): {link}')

    data = None
    records: list[dict] = []
    stale_index: int | None = None
    if registry.exists():
        data = json.loads(registry.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('versions'), list):
            raise UnsafeCleanup('Nieznana struktura game-versions.json. Nic nie zmieniono.')
        records = data['versions']
        for idx, item in enumerate(records):
            if not isinstance(item, dict):
                continue
            if item.get('branch') != 'alpha5.0':
                continue
            is_original = (
                item.get('dir') == str(link)
                and item.get('origin') in (None, '')
                and item.get('size_bytes') == 0
                and not item.get('source_dir')
            )
            if is_original and (old_link or not link.exists()):
                if stale_index is not None:
                    raise UnsafeCleanup('Kilka ręcznych wpisów alpha5.0. Wymagana kontrola.')
                stale_index = idx
            else:
                report.append('Zachowano wpis alpha5.0 należący do menedżera albo zaimportowany przez GUI.')

    # Inne wersje/instancje mogą jeszcze korzystać ze starego katalogu.
    external_refs: list[str] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if item.get('branch') == 'alpha5.0' and stale_index is not None and item is records[stale_index]:
            continue
        for key in ('dir', 'source_dir'):
            value = item.get(key)
            if value:
                p = Path(str(value)).expanduser()
                if p == source or (p.is_symlink() and p.resolve(strict=False) == source.resolve(strict=False)):
                    external_refs.append(str(item.get('branch', '?')))

    if versions.exists():
        for candidate in versions.iterdir():
            if candidate == link:
                continue
            if candidate.is_symlink() and candidate.resolve(strict=False) == source.resolve(strict=False):
                external_refs.append(candidate.name)

    if instances_path.exists():
        inst_data = json.loads(instances_path.read_text(encoding='utf-8'))
        for item in inst_data.get('instances', []) if isinstance(inst_data, dict) else []:
            if not isinstance(item, dict):
                continue
            if item.get('game_branch') == 'alpha5.0':
                report.append('UWAGA: Instancja "%s" ma wybraną alpha5.0. Po usunięciu ręcznej wersji ustaw jej wersję pobraną z launchera.' % item.get('name', '?'))
            exe = str(item.get('executable', '') or '')
            if exe and (exe.startswith(str(source) + os.sep) or exe == str(source)):
                external_refs.append('instancja: ' + str(item.get('name', '?')))

    if old_link:
        report.append(f'Dowiązanie do usunięcia: {link}')
    if stale_index is not None:
        report.append(f'Ręczny wpis do usunięcia: {registry} (alpha5.0)')
    if external_refs:
        report.append('Stary katalog jest jeszcze używany: ' + ', '.join(sorted(set(external_refs))))
        report.append(f'Zachowano oryginalne pliki: {source}')
    elif source.is_dir() and not source.is_symlink():
        if (source / '7DaysToDie.exe').is_file() and (source / '7DaysToDie_Data').is_dir():
            report.append(f'Stary, zewnętrzny katalog do usunięcia: {source}')
        else:
            raise UnsafeCleanup(f'Katalog {source} nie wygląda na pobraną grę. Nie usuwam go.')
    elif source.exists() or source.is_symlink():
        raise UnsafeCleanup(f'Nieoczekiwany typ ścieżki: {source}. Nic nie usuwam.')
    else:
        report.append('Stary katalog gry już nie istnieje.')

    if not apply:
        report.append('Podgląd. Aby wykonać operację, dodaj --apply.')
        return report

    # Zapisujemy atomowo rejestr dopiero po sprawdzeniu wszystkich ścieżek.
    if stale_index is not None:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup = registry.with_name(f'{registry.name}.bak-manual-alpha5-{stamp}')
        shutil.copy2(registry, backup)
        data['versions'] = [row for idx, row in enumerate(records) if idx != stale_index]
        temporary = registry.with_name(registry.name + '.manual-alpha5.tmp')
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            os.replace(temporary, registry)
        finally:
            temporary.unlink(missing_ok=True)
        report.append(f'Kopia rejestru: {backup}')

    if old_link:
        link.unlink()  # Ważne: nie usuwać celu dowiązania tym poleceniem.

    if not external_refs and source.is_dir() and not source.is_symlink():
        shutil.rmtree(source)
        report.append(f'Usunięto starą kopię: {source}')
    report.append('Gotowe. Nie zmieniono innych wersji, instancji ani katalogu narzędzi.')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Wykonaj czyszczenie; domyślnie podgląd')
    args = parser.parse_args()
    try:
        for line in cleanup(Path.home(), apply=args.apply):
            print(line)
    except (UnsafeCleanup, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f'Przerwano bez celowego usuwania innych plików: {exc}\n')


if __name__ == '__main__':
    main()
