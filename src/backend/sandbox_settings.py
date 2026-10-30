"""Podgląd kodów piaskownicy 7DTD 3.x. Moduł nie modyfikuje zapisów gry."""
from __future__ import annotations

import base64
import binascii
import json
import re
from pathlib import Path

DATA_FILE = Path(__file__).with_name('sandbox_options_v34.json')
_CODE_RE = re.compile(r'A(?:[A-Z]{3}){0,225}\Z')
_V3_BRANCH_RE = re.compile(r'v?3(?:\.\d+)*(?:[-_][a-z0-9]+)*\Z', re.IGNORECASE)
_SANDBOX_LIVE_BRANCHES = frozenset({'public', 'latest', 'latest_experimental',
                                    'latest_experimental_fallback'})


def supports_sandbox(branch: str) -> bool:
    """Nie dopuszcza wersji 2.x i Alpha, a przyszłe wydania 3.x wykrywa automatycznie."""
    normalized = (branch or '').strip().lower()
    return normalized in _SANDBOX_LIVE_BRANCHES or bool(_V3_BRANCH_RE.fullmatch(normalized))

# Opcje tekstowe (indeksy odpowiadają wyborom gry).
_MOVES = {'pl': ['Chód', 'Trucht', 'Bieg', 'Sprint', 'Koszmar'],
          'en': ['Walk', 'Jog', 'Run', 'Sprint', 'Nightmare']}
_CATEGORIES = {
    'player': ('Gracz', 'Player'), 'entities': ('Zombie i istoty', 'Entities'),
    'world': ('Świat', 'World'), 'resources': ('Łupy i zasoby', 'Loot and resources'),
    'crafting': ('Rzemiosło', 'Crafting'), 'tasks': ('Zadania', 'Tasks'),
    'traders': ('Handlarze', 'Traders'), 'misc': ('Różne', 'Misc'),
}


def load_options() -> dict[int, dict]:
    """Wersjonowany katalog opcji z lokalizacji i konfiguracji gry v3.4."""
    payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    return {item['id']: item for item in payload['options']}


def check_code(code: str) -> str:
    candidate = ''.join((code or '').upper().split())
    if not _CODE_RE.fullmatch(candidate):
        raise ValueError('invalid_format')
    seen: set[int] = set()
    for offset in range(1, len(candidate), 3):
        part = candidate[offset:offset + 3]
        index = (ord(part[0]) - 65) * 26 + ord(part[1]) - 65
        if index in seen:
            raise ValueError('duplicate_option')
        seen.add(index)
    return candidate


def _short_description(text: str) -> str:
    """Pokazuje krótki sens ustawienia, bez list wartości i opisów pobocznych."""
    normalized = (text or '').replace('\\n', '\n')
    paragraph = normalized.split('\n\n', 1)[0].split('\n', 1)[0].strip()
    first = re.split(r'(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„])', paragraph, maxsplit=1)[0]
    first = re.sub(r'\s+', ' ', first)
    if len(first) > 150:
        first = first[:147].rsplit(' ', 1)[0].rstrip('.,;:') + '…'
    return first


def _format_value(option: dict, raw: str, language: str) -> str:
    """Wartości specjalne opisujemy słownie, liczby bez dopowiadania semantyki."""
    i = option['id']
    if raw in ('true', 'false'):
        return ('Włączone' if raw == 'true' else 'Wyłączone') if language == 'pl' else ('Enabled' if raw == 'true' else 'Disabled')
    if i in (34, 35, 36, 37) and raw.isdigit():
        n = int(raw)
        return _MOVES[language][n] if n < 5 else raw
    if i == 66:
        return f'{raw} min'
    if i == 67:
        return f'{raw} h'
    if i == 51:
        return f'{raw} ' + ('zombie' if language == 'pl' else 'zombies')
    if i == 75 and raw == '-1':
        return 'Wyłączone' if language == 'pl' else 'Disabled'
    if i == 123 and raw == '-1':
        return 'Bez limitu' if language == 'pl' else 'Unlimited'
    if i == 27:
        # Kolejność z DropOnDeath: 0 nic, 1 wszystko, 2 pas, 3 plecak, 4 usuń.
        names = (['Nic', 'Wszystko', 'Pas narzędzi', 'Plecak', 'Usuń wszystko']
                 if language == 'pl' else ['Nothing', 'Everything', 'Toolbelt', 'Backpack', 'Delete all'])
        n = int(raw)
        return names[n] if n < len(names) else raw
    if i in (20, 39, 44, 127, 135):
        # Wartości liczbowe tych opcji są enumami, nie procentami.
        if i == 20:
            # To mnożnik przeciążenia. Nie nazywamy go pojemnością ekwipunku.
            return f'{float(raw):g}×'
        if i == 39 and raw == '0':
            return 'Wyłączony' if language == 'pl' else 'Off'
        if i == 44:
            labels = (['Domyślnie', 'Bardzo wolno', 'Wolno', 'Normalnie', 'Szybko', 'Bardzo szybko']
                      if language == 'pl' else ['Default', 'Very slow', 'Slow', 'Normal', 'Fast', 'Very fast'])
            return labels[int(raw)]
        if i == 127:
            labels = (['Domyślnie', 'Rano', 'W południe', 'Wieczorem', 'Nocą', 'Zamknięte w Krwawy Księżyc', 'Zawsze otwarte']
                      if language == 'pl' else ['Default', 'Morning', 'Midday', 'Evening', 'Night', 'Closed during Blood Moon', 'Always open'])
            return labels[int(raw)]
        return raw
    if i in (25, 29, 12, 17, 18, 31, 32, 33, 42, 57, 59, 73, 76, 90, 93, 97,
             141, 142, 143, 144, 160, 161, 162, 0, 1, 2, 3, 4):
        return f'{float(raw) * 100:g}%'
    if i in (48, 49, 50, 52, 54, 74, 77, 94, 100, 106, 109, 113, 115, 116, 117,
             121, 122, 127, 132, 133, 135, 136, 137):
        return raw
    # Inne mnożniki podawane w formie bezpiecznej, bez zgadywania jednostki.
    return raw


def decode(code: str) -> dict:
    """Dekoduje tylko zmiany. Pominięte opcje mają wartości domyślne gry."""
    normalized = check_code(code)
    lookup = load_options()
    by_category: dict[str, list] = {}
    unknown = []
    for position in range(1, len(normalized), 3):
        chunk = normalized[position:position + 3]
        option_id = (ord(chunk[0]) - 65) * 26 + ord(chunk[1]) - 65
        value_index = ord(chunk[2]) - 65
        option = lookup.get(option_id)
        if option is None or value_index >= len(option['values']):
            unknown.append(chunk)
            by_category.setdefault('misc', []).append({
                'id': option_id, 'code': chunk, 'pl': f'Opcja {chunk[:2]}',
                'en': f'Option {chunk[:2]}', 'description_pl': '',
                'description_en': '', 'description_short_pl': '',
                'description_short_en': '', 'value_pl': f'Indeks {value_index}',
                'value_en': f'Index {value_index}', 'verified': False,
            })
            continue
        raw = option['values'][value_index]
        by_category.setdefault(option['category'], []).append({
            'id': option_id, 'code': chunk, 'pl': option['pl'], 'en': option['en'],
            'description_pl': option['description_pl'],
            'description_en': option['description_en'],
            'description_short_pl': _short_description(option['description_pl']),
            'description_short_en': _short_description(option['description_en']),
            'value_pl': _format_value(option, raw, 'pl'),
            'value_en': _format_value(option, raw, 'en'),
            'verified': True,
        })
    groups = []
    for category, (pl, en) in _CATEGORIES.items():
        if category in by_category:
            groups.append({'id': category, 'pl': pl, 'en': en, 'entries': by_category[category]})
    return {'valid': True, 'code': normalized, 'count': (len(normalized)-1)//3,
            'groups': groups, 'unknown': unknown}


def discover_worlds(data_path: Path | None) -> list[dict]:
    if data_path is None:
        return []
    saves = data_path / 'Saves'
    if not saves.is_dir():
        return []
    worlds = []
    for world in sorted(saves.iterdir()):
        if not world.is_dir() or world.is_symlink():
            continue
        for save in sorted(world.iterdir()):
            if save.is_symlink() or not save.is_dir():
                continue
            if not (save / 'gameOptions.sdf').is_file():
                continue
            worlds.append({'id': world.name + '/' + save.name,
                           'label': world.name + ' / ' + save.name})
    return worlds


def _read_sdf_sandbox_code(data: bytes) -> str:
    """Odczytuje pole SandboxCode z pliku SDF gry (tekst w Base64)."""
    # Format z v3.4: typ string, długość nazwy, nazwa pola,
    # długość wartości u16, długość 7-bitowa i zapis Base64.
    marker = b"\x02\x0b\x00\x0bSandboxCode"
    start = data.find(marker)
    if start < 0:
        return ''
    pos = start + len(marker)
    if pos + 3 > len(data):
        return ''
    length = int.from_bytes(data[pos:pos + 2], 'little')
    pos += 2
    # Druga długość jest kodowana tak jak string w BinaryWriter.
    encoded_length = 0
    for shift in range(0, 35, 7):
        if pos >= len(data):
            return ''
        value = data[pos]
        pos += 1
        encoded_length |= (value & 0x7f) << shift
        if value < 0x80:
            break
    else:
        return ''
    if length != encoded_length or length == 0 or length > 4096:
        return ''
    if pos + length > len(data):
        return ''
    try:
        encoded = data[pos:pos + length]
        code = base64.b64decode(encoded, validate=True).decode('ascii')
        return check_code(code)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return ''


def _code_from_save(data_path: Path, world_id: str) -> str:
    """Odczytuje ustawienia zapisu, nie zapisuje niczego do gry."""
    path = data_path / 'Saves' / world_id / 'gameOptions.sdf'
    try:
        if path.stat().st_size > 4 * 1024 * 1024:
            return ''
        data = path.read_bytes()
    except OSError:
        return ''
    code = _read_sdf_sandbox_code(data)
    if code:
        return code
    # Starsze lub zmodyfikowane instalacje mogą trzymać wartość jawnie.
    for encoding in ('utf-8', 'utf-16-le'):
        decoded = data.decode(encoding, errors='ignore')
        result = re.search(r'SandboxCode[\x00\s=:"\']{0,64}(A(?:[A-Z]{3}){1,225})', decoded)
        if result:
            try:
                return check_code(result.group(1))
            except ValueError:
                pass
    return ''


def inspect(data_path: Path | None, world_id: str, code: str, stored: str = '') -> dict:
    selected = next((w for w in discover_worlds(data_path) if w['id'] == world_id), None)
    if selected is None:
        return {'valid': False, 'error': 'no_world', 'groups': [], 'code': ''}
    detected = _code_from_save(data_path, world_id) if data_path else ''
    # Zapis świata ma pierwszeństwo przed ręcznym kodem zachowanym w launcherze.
    effective = (code or '').strip() or detected or stored
    if not effective:
        return {'valid': False, 'error': 'no_code', 'groups': [], 'code': '', 'source': ''}
    try:
        result = decode(effective)
        result['source'] = ('input' if (code or '').strip()
                            else 'game' if detected else 'saved')
        return result
    except ValueError as exc:
        return {'valid': False, 'error': str(exc), 'groups': [], 'code': effective}
