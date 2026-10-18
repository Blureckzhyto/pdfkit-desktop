"""Errores de la app: nada se pierde en silencio.

Todo error inesperado (hilos de trabajo, callbacks de Tk, el editor) queda con su traza
completa en %LOCALAPPDATA%\\Pliegue\\logs\\errores.log. En el exe (sin consola)
sys.stderr es None, así que ese archivo es el único lugar donde se ven.
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

log = logging.getLogger("pdfkit.errors")
actions = logging.getLogger("pdfkit.actions")   # acciones del usuario que conviene rastrear


def logs_dir() -> Path:
    from core import paths

    return paths.logs_dir()


def setup() -> None:
    """errores.log y acciones.log (una sola vez) y salida estándar segura en el exe sin consola."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:      # exe "windowed": print/traceback no deben fallar
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    for logger, filename in ((log, "errores.log"), (actions, "acciones.log")):
        _file_handler(logger, filename)


def _file_handler(logger: logging.Logger, filename: str) -> None:
    if any(getattr(h, "_pdfkit", False) for h in logger.handlers):
        return
    from logging.handlers import RotatingFileHandler

    try:
        folder = logs_dir()
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / filename, maxBytes=1_000_000, backupCount=2,
                                      encoding="utf-8")
    except OSError:
        return
    handler._pdfkit = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def record(context: str, exc: BaseException | None = None) -> None:
    """Escribe `context` y la traza completa (de `exc` o de la excepción en curso)."""
    if exc is not None:
        trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    else:
        trace = traceback.format_exc()
    log.error("%s\n%s", context, trace.rstrip())


def reason(exc: BaseException) -> str:
    """Motivo corto y legible para mostrar al usuario."""
    return str(exc).strip() or type(exc).__name__
