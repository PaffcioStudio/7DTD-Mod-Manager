"""Odczyt formatu "devalue" używanego przez Nuxt w ``<script id="__NUXT_DATA__">``.

Payload to płaska tablica wartości. Obiekty i tablice wewnątrz nie trzymają
wartości bezpośrednio - zamiast tego pola są liczbami całkowitymi, które są
indeksami do tej tablicy (tak zapisywane są m.in. stringi i liczby użyte jako
wartości pól). ``null``/``true``/``false`` są inline, ujemne liczby oznaczają
"undefined".
"""

from __future__ import annotations

from services.i18n_message import message as i18n_message

import json
import re
from typing import Any

__NUXT_DATA_RE = re.compile(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)


def extract_payload(html: str) -> list[Any]:
    """Wyciąga surową tablicę payloadu __NUXT_DATA__ z HTML-u strony."""
    match = __NUXT_DATA_RE.search(html)
    if match is None:
        raise ValueError(i18n_message("discover.error.payloadMissing"))
    return json.loads(match.group(1))


def build_all(data: list[Any]) -> list[Any]:
    """Buduje wartości wszystkich slotów payloadu (ze współdzielonym memo).

    Zwraca listę o długości ``data`` - pod każdym indeksem jest zbudowana
    wartość danego slotu. Zbudowane drzewa współdzielą węzły tam, gdzie
    payload współdzieli referencje; cykle są obsługiwane.
    """
    memo: dict[int, Any] = {}

    def deref(ref: Any) -> Any:
        if isinstance(ref, int) and not isinstance(ref, bool):
            return None if ref < 0 else build(ref)
        return ref

    def build(idx: int) -> Any:
        if idx in memo:
            return memo[idx]
        value = data[idx]
        if isinstance(value, list):
            out: list[Any] = []
            memo[idx] = out  # rezerwa przed rekurencją - zabezpieczenie na cykle
            out.extend(deref(item) for item in value)
            return out
        if isinstance(value, dict):
            obj: dict[str, Any] = {}
            memo[idx] = obj
            for key, item in value.items():
                obj[key] = deref(item)
            return obj
        memo[idx] = value  # str / int / float / bool / None - wartość surowa
        return value

    return [build(i) for i in range(len(data))]


def unflatten(data: list[Any]) -> Any:
    """Buduje pełne drzewo obiektów z płaskiego payloadu devalue (slot 0)."""
    return build_all(data)[0]
