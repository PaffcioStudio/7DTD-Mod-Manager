"""Dedykowany log autoinstalacji pobranych modów/modpacków (logs/installs.log).

Cel: łatwa diagnoza problemów z pobieraniem, wypakowywaniem i instalacją
overhauli/modpacków/modów - BEZ zależności od ustawienia loggingEnabled
(log jest zawsze aktywny). Format: timestamp + poziom + komunikat.

Użycie:
    from services import install_log
    install_log.info("INSTANCE ready: %r -> %s", name, data_dir)
    install_log.exception("URL download failed")   # w bloku except (traceback)
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from services import filesystem_service as fs

MAX_LOG_BYTES = 8 * 1024 * 1024
BACKUP_COUNT = 3
TRIM_KEEP_BYTES = MAX_LOG_BYTES // 2

_logger: logging.Logger | None = None


def _trim_oversized_log(path) -> None:
    """Nie pozwól, żeby stary runaway log został zachowany w całości."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) <= MAX_LOG_BYTES:
            return
        keep = TRIM_KEEP_BYTES
        with open(path, "rb") as src:
            src.seek(-keep, os.SEEK_END)
            data = src.read()
        # Zacznij od pełnej linii, nie od losowego środka wpisu.
        newline = data.find(b"\n")
        if newline >= 0:
            data = data[newline + 1:]
        tmp = path.with_suffix(path.suffix + ".trimmed")
        with open(tmp, "wb") as dst:
            dst.write(
                b"# installs.log was compacted because it exceeded the safety limit.\n"
            )
            dst.write(data)
        os.replace(tmp, path)
    except OSError:
        # Logowanie diagnostyczne nie może blokować startu aplikacji.
        pass


def logger() -> logging.Logger:
    """Logger zapisujący do logs/installs.log (tworzony leniwie)."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("installs.pipeline")
        # INFO = wpisy operacyjne; surowy stdout DepotDownloadera jest
        # wysyłany przez install_log.debug() i domyślnie nie trafia do pliku.
        _logger.setLevel(logging.INFO)
        _logger.propagate = False
        log_path = fs.ensure_dir(fs.logs_dir()) / "installs.log"
        _trim_oversized_log(log_path)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
        _logger.addHandler(handler)
    return _logger


def debug(msg: str, *args) -> None:
    logger().debug(msg, *args)


def info(msg: str, *args) -> None:
    logger().info(msg, *args)


def warning(msg: str, *args) -> None:
    logger().warning(msg, *args)


def error(msg: str, *args) -> None:
    logger().error(msg, *args)


def exception(msg: str, *args) -> None:
    """Poziom ERROR + traceback - wywoływać tylko z bloku except."""
    logger().exception(msg, *args)
