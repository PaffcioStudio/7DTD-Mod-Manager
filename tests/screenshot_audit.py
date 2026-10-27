#!/usr/bin/env python3
"""Capture every page in four themes and two languages using disposable HOME.

Usage: .venv/bin/python tests/screenshot_audit.py /tmp/7dtd-audit/screenshots
Produces PNGs, per-launch logs and a machine-readable report. No real user data.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['dashboard','profiles','mods','discover','downloads','updates',
         'steam_releases','protons','game_profiles','modpacks','conflicts','settings']


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for theme in ['dark','light','stalker','stalker-light']:
        for language in ['pl','en']:
            for page in PAGES:
                name = f'{theme}-{language}-{page}'
                home = output / 'homes' / name
                data = home / '.7dtd_modmanager'
                data.mkdir(parents=True, exist_ok=True)
                (data/'settings.json').write_text(json.dumps({
                    'themeMode': theme, 'language': language,
                    'autoCheckAppUpdates': False, 'animationsEnabled': False,
                    'sidebarGameExpanded': True, 'sidebarToolsExpanded': True,
                }))
                env = dict(os.environ, HOME=str(home), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
                command = [sys.executable, str(ROOT/'src/main.py'), '--page', page,
                           '--screenshot', str(output/(name+'.png')), '--wait','450',
                           '--width','1150','--height','700']
                result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=60)
                log = result.stdout + result.stderr
                (output/(name+'.log')).write_text(log)
                warnings = [line for line in log.splitlines() if 'QML:' in line or 'Error:' in line]
                reports.append({'name':name, 'code': result.returncode, 'warnings': warnings})
            print(theme, language, 'captured', flush=True)
    (output/'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    print('captures:',len(reports),'failures:',sum(r['code'] != 0 for r in reports), flush=True)
    return int(any(r['code'] != 0 for r in reports))

if __name__ == '__main__':
    raise SystemExit(main())
