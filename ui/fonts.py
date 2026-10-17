"""Fuentes incluidas: registro privado en Windows y elección de la familia de la
interfaz (Plus Jakarta Sans → Inter → Segoe UI)."""
from __future__ import annotations

import sys
import tkinter.font as tkfont

from ui.assets import asset_path

FONT_FILES = [
    "PlusJakartaSans-Regular.ttf", "PlusJakartaSans-SemiBold.ttf", "PlusJakartaSans-Bold.ttf",
    "PlusJakartaSans-Italic.ttf", "PlusJakartaSans-BoldItalic.ttf",
    "Inter-Regular.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf",
]
CANDIDATES = [  # (normal, semibold)
    ("Plus Jakarta Sans", "Plus Jakarta Sans SemiBold"),
    ("Inter", "Inter SemiBold"),
    ("Segoe UI", "Segoe UI Semibold"),
]
FR_PRIVATE = 0x10


def register_private_fonts() -> int:
    """Registra las fuentes solo para este proceso (no se instalan en el sistema).
    Tk no puede usar archivos de fuente directamente; así las ve por su nombre."""
    if sys.platform != "win32":
        return 0
    import ctypes

    added = 0
    for name in FONT_FILES:
        path = asset_path("fonts/" + name)
        if path.exists():
            added += ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0) > 0
    return added


_registered: dict[str, bool] = {}


def register_font_file(path: str) -> bool:
    """Registra un archivo de fuente solo para esta app (p. ej., la fuente incrustada de un
    PDF, para mostrar el texto con ella mientras se edita)."""
    if path in _registered:
        return _registered[path]
    ok = False
    if sys.platform == "win32":
        import ctypes

        try:
            ok = ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0) > 0
        except Exception:
            ok = False
    _registered[path] = ok
    return ok


def choose(root) -> tuple[str, str]:
    """Primera familia realmente disponible para Tk (comprobado con families())."""
    available = set(tkfont.families(root))
    for regular, semibold in CANDIDATES:
        if regular in available:
            return regular, semibold if semibold in available else regular
    return "Segoe UI", "Segoe UI Semibold"
