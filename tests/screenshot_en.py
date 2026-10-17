#!/usr/bin/env python3
"""Capture the real English GUI using current local data and live services.

No source rewrites, mock entries or permanent changes to language settings.
Usage: .venv/bin/python tests/screenshot_en.py [protons sidebar-game ...]
All screenshots use an isolated navigation layout and never write settings.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from services.filesystem_service import library_metadata_path
TARGETS = (
    ('dashboard-en.png', 'dashboard', 1800),
    ('mods-en.png', 'mods', 1800),
    ('drawer-en.png', 'mods', 2000),
    ('profiles-en.png', 'profiles', 1800),
    ('steam-releases-en.png', 'steam_releases', 6000),
    ('protons-en.png', 'protons', 2500),
    ('game-profiles-en.png', 'game_profiles', 1800),
    ('conflicts-en.png', 'conflicts', 1800),
    ('updates-en.png', 'updates', 1800),
    ('downloads-en.png', 'downloads', 1800),
    ('settings-en.png', 'settings', 1800),
    ('discover-en.png', 'discover', 5000),
    ('backups-en.png', 'modpacks', 1800),
    # The same real Dashboard with three controlled sidebar states.
    ('sidebar-default-en.png', 'dashboard', 1800),
    ('sidebar-game-en.png', 'dashboard', 1800),
    ('sidebar-tools-en.png', 'dashboard', 1800),
)

SIDEBAR_MODES = {
    'sidebar-default-en.png': 'default',
    'sidebar-game-en.png': 'game',
    'sidebar-tools-en.png': 'tools',
}


def app_python() -> str:
    executable = ROOT / '.venv' / 'bin' / 'python'
    return str(executable) if executable.is_file() else sys.executable


def first_mod_id() -> str:
    library = library_metadata_path()
    try:
        entries = json.loads(library.read_text(encoding='utf-8')).get('entries', [])
        if isinstance(entries, dict):
            entries = list(entries.values())
        return next(str(item['library_id']) for item in entries if isinstance(item, dict) and item.get('library_id'))
    except (OSError, ValueError, AttributeError, StopIteration):
        return ''


def selected_targets(names):
    wanted = {name.removesuffix('-en.png').removesuffix('.png').replace('-', '_') for name in names}
    if 'modpacks' in wanted:
        wanted.add('backups')
    known = {filename.removesuffix('-en.png').replace('-', '_') for filename, _, _ in TARGETS} | {
        page for filename, page, _ in TARGETS if filename not in SIDEBAR_MODES
    }
    unknown = wanted - known
    if unknown:
        raise ValueError('Unknown screenshot targets: ' + ', '.join(sorted(unknown)))
    return [target for target in TARGETS if not wanted
            or target[0].removesuffix('-en.png').replace('-', '_') in wanted
            or (target[0] not in SIDEBAR_MODES and target[1] in wanted)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pages', nargs='*', help='optional pages or screenshot filenames')
    args = parser.parse_args()
    try:
        targets = selected_targets(args.pages)
    except ValueError as exc:
        parser.error(str(exc))
    mod_id = first_mod_id()
    out_dir = ROOT / "docs" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    captured = 0
    for filename, page, wait in targets:
        if filename == 'drawer-en.png' and not mod_id:
            print('Skipping drawer: the current library has no mod to display.', flush=True)
            continue
        destination = out_dir / filename
        command = [app_python(), str(ROOT / 'src' / 'main.py'), '--language', 'en',
                   '--page', page, '--width', '1400', '--height', '880',
                   '--wait', str(wait), '--screenshot', str(destination),
                   '--sidebar-preview', SIDEBAR_MODES.get(filename, 'default')]
        if filename == 'drawer-en.png':
            command.extend(['--open-drawer', mod_id])
        print(f'[{filename}] Capturing current GUI: {page}', flush=True)
        result = subprocess.run(command, cwd=ROOT, timeout=120, capture_output=True, text=True,
                                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'})
        if result.returncode:
            print(result.stdout + result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode)
        if not destination.is_file() or destination.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
            raise RuntimeError(f'Missing or invalid GUI screenshot: {destination}')
        if filename == 'backups-en.png':
            # Keep the historical alias in sync with the same actual capture.
            (out_dir / 'modpacks-en.png').write_bytes(destination.read_bytes())
        captured += 1
    print(f'Captured {captured} screens in {out_dir}', flush=True)


if __name__ == '__main__':
    main()
