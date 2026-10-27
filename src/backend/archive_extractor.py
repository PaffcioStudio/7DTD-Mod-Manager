"""Bezpieczne rozpakowywanie archiwów modów ZIP, 7z i RAR.

ZIP jest obsługiwany istniejącym kodem w modpack_downloader. Dla 7z/RAR
używamy systemowego libarchive (bez zależności od zewnętrznego polecenia 7z).
Wpisy są przepisywane strumieniowo, nigdy rozpakowywane przez narzędzie CLI
bez kontroli ścieżek lub typów plików.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import logging
import stat
from pathlib import Path

from backend.fileops import check_cancel, ensure_free_space, raise_if_no_space
from services.i18n_message import message as i18n_message

logger = logging.getLogger(__name__)
ARCHIVE_SUFFIXES = frozenset({".zip", ".7z", ".rar"})
CHUNK = 256 * 1024


class ArchiveFormatError(Exception):
    """Uszkodzone, nieobsługiwane lub niebezpieczne archiwum."""


def _libarchive():
    name = ctypes.util.find_library("archive")
    if not name:
        raise ArchiveFormatError(i18n_message("download.error.archiveLibraryMissing"))
    try:
        lib = ctypes.CDLL(name)
    except OSError as exc:
        raise ArchiveFormatError(i18n_message("download.error.archiveLibraryMissing")) from exc
    ptr = ctypes.c_void_p
    lib.archive_read_new.restype = ptr
    lib.archive_read_support_filter_all.argtypes = [ptr]
    lib.archive_read_support_format_all.argtypes = [ptr]
    lib.archive_read_open_filename.argtypes = [ptr, ctypes.c_char_p, ctypes.c_size_t]
    lib.archive_read_next_header.argtypes = [ptr, ctypes.POINTER(ptr)]
    lib.archive_read_data.argtypes = [ptr, ptr, ctypes.c_size_t]
    lib.archive_read_data.restype = ctypes.c_ssize_t
    lib.archive_read_data_skip.argtypes = [ptr]
    lib.archive_read_free.argtypes = [ptr]
    lib.archive_error_string.argtypes = [ptr]
    lib.archive_error_string.restype = ctypes.c_char_p
    lib.archive_entry_pathname.argtypes = [ptr]
    lib.archive_entry_pathname.restype = ctypes.c_char_p
    lib.archive_entry_filetype.argtypes = [ptr]
    lib.archive_entry_filetype.restype = ctypes.c_uint
    lib.archive_entry_size.argtypes = [ptr]
    lib.archive_entry_size.restype = ctypes.c_int64
    lib.archive_entry_symlink.argtypes = [ptr]
    lib.archive_entry_symlink.restype = ctypes.c_char_p
    lib.archive_entry_hardlink.argtypes = [ptr]
    lib.archive_entry_hardlink.restype = ctypes.c_char_p
    return lib


def _archive_error(lib, reader):
    msg = lib.archive_error_string(reader)
    return msg.decode("utf-8", errors="replace") if msg else "nieznany błąd archiwum"


def _validated_target(root: Path, raw: str) -> Path | None:
    path = raw.replace("\\", "/")
    if path in ("", ".", "./"):
        return None
    if path.startswith("/") or "\x00" in path:
        raise ArchiveFormatError(i18n_message("download.error.unsafePath", {"path": raw}))
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if ".." in parts or any(":" in p for p in parts):
        raise ArchiveFormatError(i18n_message("download.error.unsafePath", {"path": raw}))
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        raise ArchiveFormatError(i18n_message("download.error.outsidePath", {"path": raw}))
    return target


def _entries(lib, archive: Path, cancel_event=None):
    reader = lib.archive_read_new()
    if not reader:
        raise ArchiveFormatError("Nie udało się zainicjalizować libarchive")
    try:
        lib.archive_read_support_filter_all(reader)
        lib.archive_read_support_format_all(reader)
        result = lib.archive_read_open_filename(reader, str(archive).encode(), 10240)
        if result < 0:
            raise ArchiveFormatError(_archive_error(lib, reader))
        entry = ctypes.c_void_p()
        while True:
            check_cancel(cancel_event)
            status = lib.archive_read_next_header(reader, ctypes.byref(entry))
            if status == 1:  # ARCHIVE_EOF
                return
            if status < 0:
                raise ArchiveFormatError(_archive_error(lib, reader))
            yield reader, entry
    finally:
        lib.archive_read_free(reader)


def extract_libarchive(archive: Path, destination: Path, *, progress_cb=None, cancel_event=None) -> None:
    """Rozpakuj 7z/RAR z kontrolą ścieżek, rodzaju wpisu, miejsca i anulowania.

    Dwa przebiegi umożliwiają sprawdzenie sumarycznego rozmiaru przed
    zapisaniem danych. Symlinki, hardlinki i urządzenia są odrzucane.
    """
    lib = _libarchive()
    root = destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    expected = []
    size = 0
    for reader, entry in _entries(lib, archive, cancel_event):
        raw = (lib.archive_entry_pathname(entry) or b"").decode("utf-8", errors="surrogateescape")
        target = _validated_target(root, raw)
        mode = lib.archive_entry_filetype(entry)
        if lib.archive_entry_symlink(entry) or lib.archive_entry_hardlink(entry):
            raise ArchiveFormatError(i18n_message("download.error.unsafePath", {"path": raw}))
        if target is None:
            if mode not in (0, stat.S_IFDIR):
                raise ArchiveFormatError(i18n_message("download.error.unsafePath", {"path": raw}))
        elif mode not in (stat.S_IFDIR, stat.S_IFREG, 0):
            raise ArchiveFormatError(i18n_message("download.error.unsafePath", {"path": raw}))
        entry_size = lib.archive_entry_size(entry)
        if entry_size < 0:
            raise ArchiveFormatError(i18n_message("download.mod.invalidArchive"))
        if mode != stat.S_IFDIR and target is not None:
            size += entry_size
        expected.append((raw, target, mode))
        if len(expected) > 250000:
            raise ArchiveFormatError(i18n_message("download.mod.invalidArchive"))
        # Przy archiwach solid libarchive musi ominąć dane kolejnego wpisu.
        if lib.archive_read_data_skip(reader) < 0:
            raise ArchiveFormatError(_archive_error(lib, reader))
    ensure_free_space(root, size)
    if not expected:
        raise ArchiveFormatError(i18n_message("download.mod.invalidArchive"))

    buffer = ctypes.create_string_buffer(CHUNK)
    extracted = 0
    for reader, entry in _entries(lib, archive, cancel_event):
        raw, target, mode = expected[extracted]
        if target is not None:
            if mode == stat.S_IFDIR:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with target.open("wb") as output:
                        while True:
                            check_cancel(cancel_event)
                            count = lib.archive_read_data(reader, buffer, CHUNK)
                            if count == 0:
                                break
                            if count < 0:
                                raise ArchiveFormatError(_archive_error(lib, reader))
                            output.write(buffer.raw[:count])
                except OSError as exc:
                    raise_if_no_space(exc, root)
                    raise
        if progress_cb:
            progress_cb(extracted + 1, len(expected), i18n_message("download.mod.extracting", {"name": raw}))
        extracted += 1
    if extracted != len(expected):
        raise ArchiveFormatError(i18n_message("download.mod.invalidArchive"))


def has_compressed_archive_signature(path: Path) -> bool:
    with path.open("rb") as source:
        header = source.read(8)
    return header.startswith((b"7z\xbc\xaf\x27\x1c", b"Rar!\x1a\x07"))


def extract_archive(archive: Path, destination: Path, *, progress_cb=None, cancel_event=None) -> None:
    """Wybierz backend ekstrakcji na podstawie rzeczywistego formatu pliku."""
    import zipfile
    if zipfile.is_zipfile(archive):
        # Zachowujemy sprawdzoną implementację ZIP.
        from backend.modpack_downloader import _extract_zip
        _extract_zip(archive, destination, progress_cb=progress_cb, cancel_event=cancel_event)
        return
    if not has_compressed_archive_signature(archive):
        raise ArchiveFormatError(i18n_message("download.mod.invalidArchive"))
    try:
        extract_libarchive(archive, destination, progress_cb=progress_cb, cancel_event=cancel_event)
    except ArchiveFormatError:
        raise
    except (ValueError, OSError) as exc:
        raise ArchiveFormatError(i18n_message("download.mod.invalidArchive")) from exc


def archive_is_complete(archive: Path) -> bool:
    """Sprawdź integralność 7z/RAR przed ponownym wykorzystaniem pobrania."""
    try:
        lib = _libarchive()
        seen = False
        buffer = ctypes.create_string_buffer(CHUNK)
        for reader, _ in _entries(lib, archive):
            seen = True
            while True:
                count = lib.archive_read_data(reader, buffer, CHUNK)
                if count == 0:
                    break
                if count < 0:
                    return False
        return seen
    except (ArchiveFormatError, OSError):
        return False
