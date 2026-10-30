"""Testy czytnika opcji piaskownicy 7 Days to Die v3.x."""
import base64
from pathlib import Path

import pytest

from backend.sandbox_settings import (
    check_code, decode, discover_worlds, inspect, load_options, supports_sandbox,
)

EXAMPLE = (
    'AAAJABJACKADKAEKARFASIAZABBAGFDGGDGEDBDCAUBAMLBSEBFEBQEBGBBHFANBAOBBIBBJCBKCBLCBN'
    'ABOACDACVCBZFCFBCHACOHCPJCXACYFDMDDPHDTFEXGFFAEPAEUAETAFLFFMFFNFFOF'
)


def _by_id(decoded):
    return {row['id']: row for group in decoded['groups'] for row in group['entries']}


def test_complete_sample_code_decodes_all_49_changes():
    result = decode(EXAMPLE)
    assert result['valid']
    assert result['count'] == 49
    assert not result['unknown']
    options = _by_id(result)
    assert len(options) == 49
    assert options[0]['value_pl'] == '150%'
    assert options[2]['value_pl'] == '200%'
    assert options[17]['value_pl'] == '75%'
    assert options[66]['value_pl'] == '120 min'
    assert options[67]['value_pl'] == '20 h'
    assert options[51]['value_pl'] == '16 zombie'
    assert options[75]['value_pl'] == 'Wyłączone'
    assert options[127]['value_pl'] == 'Zawsze otwarte'
    assert options[135]['value_pl'] == '0'
    assert options[160]['value_pl'] == '75%'
    assert options[161]['value_pl'] == '75%'
    assert options[162]['value_pl'] == '75%'
    assert options[34]['value_pl'] == 'Trucht'
    assert options[35]['value_pl'] == 'Bieg'
    assert options[44]['value_pl'] == 'Szybko'


def test_names_and_descriptions_come_from_polish_and_english_catalog():
    result = decode('AAAJ')
    item = _by_id(result)[0]
    assert item['pl'] == 'Obrażenia zasięgowe'
    assert item['en'] == 'Ranged Damage'
    assert 'łuków' in item['description_pl']
    assert 'bows' in item['description_en']


def test_description_shortens_multiline_catalog_entries():
    result = decode('ABBE')
    item = _by_id(result)[27]
    assert item['description_short_pl'] == 'Określa, które przedmioty są upuszczane po śmierci.'
    assert item['description_short_en'] == 'Which items are dropped on death.'
    assert '\n' not in item['description_short_pl']


def test_space_and_lowercase_are_normalized():
    assert check_code(' aaaj\n abj ') == 'AAAJABJ'
    assert decode('A')['count'] == 0


@pytest.mark.parametrize('bad', ['', 'foo', 'AA', 'AAA', 'AAB', 'AAA!'])
def test_bad_format_rejected(bad):
    with pytest.raises(ValueError):
        check_code(bad)


def test_duplicate_option_rejected():
    with pytest.raises(ValueError, match='duplicate_option'):
        check_code('AAAJAAK')


def test_unknown_option_does_not_guess_value():
    item = _by_id(decode('AGJA'))[165]  # GJ = 165, nowa nieopisana opcja
    assert item['value_pl'] == 'Indeks 0'
    assert not item['verified']


def test_world_discovery_isolated_and_safe(tmp_path):
    root = tmp_path / 'instance'
    (root / 'Saves' / 'World' / 'Save').mkdir(parents=True)
    (root / 'Saves' / 'World' / 'Save' / 'gameOptions.sdf').write_bytes(b'none')
    (root / 'Saves' / 'World' / 'Other').mkdir()
    found = discover_worlds(root)
    assert found == [{'id': 'World/Save', 'label': 'World / Save'}]
    assert inspect(root, '../escape', 'AAAJ')['error'] == 'no_world'
    assert inspect(root, 'World/Save', '')['error'] == 'no_code'
    result = inspect(root, 'World/Save', 'AAAJ')
    assert result['count'] == 1
    assert result['source'] == 'input'


def test_sdf_auto_detection_only_for_named_code_field(tmp_path):
    save = tmp_path / 'Saves' / 'West Dujedade Valley' / 'Paffciolandia'
    save.mkdir(parents=True)
    f = save / 'gameOptions.sdf'
    f.write_bytes(b'SandboxCode=AAAJABJ\x00')
    item = inspect(tmp_path, 'West Dujedade Valley/Paffciolandia', '')
    assert item['count'] == 2
    assert item['source'] == 'game'
    f.write_bytes(b'not a setting AAAJABJ')
    assert inspect(tmp_path, 'West Dujedade Valley/Paffciolandia', '')['error'] == 'no_code'


def test_catalog_matches_3_x_known_identifiers():
    data = load_options()
    assert data[0]['key'] == 'RangedDamage'
    assert data[127]['key'] == 'TraderHours'
    assert data[160]['key'] == 'InfectionChance'
    assert data[161]['key'] == 'HungerMultiplier'
    assert data[162]['key'] == 'ThirstMultiplier'


def test_drop_on_death_values_in_correct_order():
    # Option BB = 27, kodowanie pozycji: B B [A..E].
    for letter, value in (('A', 'Nic'), ('B', 'Wszystko'),
                          ('C', 'Pas narzędzi'), ('D', 'Plecak'),
                          ('E', 'Usuń wszystko')):
        result = _by_id(decode('AB' + 'B' + letter))
        assert result[27]['value_pl'] == value


def test_encumbrance_value_remains_numeric():
    result = _by_id(decode('AAUA'))
    assert result[20]['value_pl'] == '10×'


def _sdf_binary_record(code: str) -> bytes:
    """Tworzy rekord SandboxCode taki, jaki zapisuje gra v3.4."""
    encoded = base64.b64encode(code.encode('ascii'))
    # String w pliku ma długość u16 i ponownie długość 7-bitową.
    n = len(encoded)
    varint = bytearray()
    while n >= 128:
        varint.append((n & 127) | 128)
        n >>= 7
    varint.append(n)
    return (b'\x01\x01' + b'\x02\x0b\x00\x0bSandboxCode'
            + len(encoded).to_bytes(2, 'little') + varint + encoded + b'\x01\x00')


def test_real_sdf_base64_record_is_loaded_from_selected_world(tmp_path):
    save = tmp_path / 'Saves' / 'West Dujedade Valley' / 'Paffciolandia'
    save.mkdir(parents=True)
    code = EXAMPLE
    (save / 'gameOptions.sdf').write_bytes(_sdf_binary_record(code))
    result = inspect(tmp_path, 'West Dujedade Valley/Paffciolandia', '')
    assert result['valid'] is True
    assert result['source'] == 'game'
    assert result['code'] == code
    assert result['count'] == 49


def test_sdf_binary_parser_rejects_damaged_lengths(tmp_path):
    save = tmp_path / 'Saves' / 'World' / 'Save'
    save.mkdir(parents=True)
    record = bytearray(_sdf_binary_record('AAAJABJ'))
    marker = b'SandboxCode'
    pos = record.index(marker) + len(marker)
    record[pos] = 255
    (save / 'gameOptions.sdf').write_bytes(record)
    assert inspect(tmp_path, 'World/Save', '')['error'] == 'no_code'


def test_sdf_world_specific_settings(tmp_path):
    for world, code in (('North/First', 'AAAJ'), ('South/Second', 'AABJ')):
        save = tmp_path / 'Saves' / world
        save.mkdir(parents=True)
        (save / 'gameOptions.sdf').write_bytes(_sdf_binary_record(code))
    assert inspect(tmp_path, 'North/First', '')['code'] == 'AAAJ'
    assert inspect(tmp_path, 'South/Second', '')['code'] == 'AABJ'


@pytest.mark.parametrize('branch', [
    'public', 'PUBLIC', 'latest_experimental', 'latest_experimental_fallback',
    'v3', 'V3.0', 'v3.4.0', 'v3.9.0', 'v3.10.13', '3.4.4',
])
def test_sandbox_supported_for_current_and_future_v3(branch):
    assert supports_sandbox(branch)


@pytest.mark.parametrize('branch', [
    '', 'v2', 'v2.6', 'v1.4', 'alpha21.2', 'alpha19.6', 'v30.0.0',
    'v4.0', 'private_branch', 'v3unknown',
])
def test_sandbox_rejected_for_older_or_unsupported_releases(branch):
    assert not supports_sandbox(branch)


def test_live_world_code_takes_precedence_over_stored_launcher_code(tmp_path):
    save = tmp_path / 'Saves' / 'World' / 'Save'
    save.mkdir(parents=True)
    (save / 'gameOptions.sdf').write_bytes(_sdf_binary_record('AAAJ'))
    current = inspect(tmp_path, 'World/Save', '', 'AABJ')
    assert current['source'] == 'game'
    assert current['code'] == 'AAAJ'
    manual = inspect(tmp_path, 'World/Save', 'AACK', 'AABJ')
    assert manual['source'] == 'input'
    assert manual['code'] == 'AACK'
    (save / 'gameOptions.sdf').write_bytes(b'no-code')
    fallback = inspect(tmp_path, 'World/Save', '', 'AABJ')
    assert fallback['source'] == 'saved'
    assert fallback['code'] == 'AABJ'


def test_future_option_has_safe_short_descriptions():
    result = decode('AGJA')
    item = _by_id(result)[165]
    assert item['description_short_pl'] == ''
    assert item['description_short_en'] == ''
