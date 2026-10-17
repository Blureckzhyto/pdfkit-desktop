"""Preparación de Windows antes de crear la ventana: DPI, identidad en la barra de
tareas y fuentes incluidas. Se puede llamar más de una vez."""
from __future__ import annotations

import sys

APP_USER_MODEL_ID = "PDFKit.App"
_done = False
_MARKS: list[tuple[str, float]] = []   # (etapa, time.time()) del arranque


def mark(label: str) -> None:
    import time

    _MARKS.append((label, time.time()))


def process_start() -> float:
    """Cuándo Windows creó este proceso (time.time()); incluye lo que tarda el cargador."""
    import time

    if sys.platform != "win32":
        return _MARKS[0][1] if _MARKS else time.time()
    import ctypes
    from ctypes import wintypes

    times = [wintypes.FILETIME() for _ in range(4)]
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes(kernel32.GetCurrentProcess(), *[ctypes.byref(t) for t in times])
    created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    return created / 1e7 - 11644473600     # FILETIME (1601) -> época Unix


def close_splash() -> None:
    """Cierra la pantalla de carga del exe (PyInstaller --splash), si la hay."""
    try:
        import pyi_splash  # solo existe en el exe compilado con --splash
    except ImportError:
        return
    try:
        pyi_splash.close()
    except Exception:
        pass


def write_timing(version: str) -> None:
    """Deja en logs/inicio.log cuánto tardó cada etapa del arranque (desde el doble clic)."""
    import os
    from pathlib import Path

    start = process_start()
    parts = " · ".join(f"{label} {stamp - start:.2f} s" for label, stamp in _MARKS)
    kind = ("onedir" if getattr(sys, "_MEIPASS", "").startswith(os.path.dirname(sys.executable))
            else "onefile") if getattr(sys, "frozen", False) else "código"
    try:
        folder = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PDFKit" / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        import time

        with open(folder / "inicio.log", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {version} ({kind}): {parts}\n")
    except OSError:
        pass


def prepare() -> None:
    global _done
    if _done:
        return
    _done = True
    _error_log()
    _tk_cleanup_in_main_thread()
    if sys.platform != "win32":
        return
    import ctypes

    try:  # nitidez en pantallas con escala (125 %, 150 %, ...)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    try:  # sin esto la barra de tareas muestra el icono genérico de Python
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass
    from ui.fonts import register_private_fonts

    register_private_fonts()
    _font_log()


_LATE: list = []   # borrados de objetos de Tk pedidos desde otro hilo


def _tk_cleanup_in_main_thread() -> None:
    """Los objetos de Tk (fuentes, imágenes, variables) se borran en Tk desde su __del__.
    Si el recolector de basura corre en un hilo de trabajo, ese __del__ llama a Tk desde ese
    hilo y espera al hilo principal; si el principal espera a su vez un candado que tiene
    ese hilo (p. ej. el de la sesión del editor), la app se congela. Desde otros hilos el
    borrado se pospone y lo hace `flush_tk_cleanup` en el hilo principal."""
    import threading
    import tkinter
    import tkinter.font

    from PIL import ImageTk

    for cls in (tkinter.font.Font, tkinter.Image, tkinter.Variable, ImageTk.PhotoImage):
        original = cls.__dict__.get("__del__")
        if original is None or getattr(original, "_pdfkit", False):
            continue

        def guarded(self, _original=original):
            if threading.current_thread() is threading.main_thread():
                _original(self)
            else:
                _LATE.append((_original, self))

        guarded._pdfkit = True
        cls.__del__ = guarded


def flush_tk_cleanup() -> None:
    """Hace (en el hilo principal) los borrados de Tk que llegaron desde otros hilos."""
    while _LATE:
        delete, obj = _LATE.pop()
        try:
            delete(obj)
        except Exception:
            pass   # el intérprete de Tk ya no existe: no hay nada que borrar


def _error_log() -> None:
    """errores.log y ningún error sin registrar (hilos y excepciones sin atrapar)."""
    import threading

    from core import errors

    errors.setup()
    previous = threading.excepthook

    def thread_hook(args):
        errors.record(f"Error sin atrapar en el hilo {getattr(args.thread, 'name', '?')}", args.exc_value)
        previous(args)

    threading.excepthook = thread_hook
    original = sys.excepthook

    def main_hook(kind, value, tb):
        errors.record("Error sin atrapar", value)
        original(kind, value, tb)

    sys.excepthook = main_hook


def _font_log() -> None:
    """Cada decisión de fuente del editor queda en %LOCALAPPDATA%\\PDFKit\\logs\\fuentes.log."""
    import logging
    import os
    from logging.handlers import RotatingFileHandler
    from pathlib import Path

    try:
        folder = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PDFKit" / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / "fuentes.log", maxBytes=1_000_000, backupCount=2,
                                      encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger = logging.getLogger("pdfkit.fonts")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    except OSError:
        pass


DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_DARK_BEFORE_20H1 = 19


def set_dark_titlebar(hwnd: int, dark: bool) -> None:
    """Barra de título oscura (o clara) de Windows, sin ocultar ni mostrar la ventana."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        value = ctypes.c_int(1 if dark else 0)
        dwm = ctypes.windll.dwmapi
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, _DWMWA_DARK_BEFORE_20H1):
            if dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attribute, ctypes.byref(value),
                                         ctypes.sizeof(value)) == 0:
                break
        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED: repinta el marco
        ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0, 0x37)
    except Exception:
        pass


def titlebar_is_dark(hwnd: int) -> bool | None:
    if sys.platform != "win32":
        return None
    import ctypes

    value = ctypes.c_int(0)
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        ctypes.c_void_p(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value),
        ctypes.sizeof(value))
    return bool(value.value) if result == 0 else None


_icon_handles: list = []


def set_native_icon(hwnd: int, ico_path: str) -> None:
    """Asigna a la ventana los cuadros del .ico del tamaño exacto que usa Windows:
    24 px (por escala) en la barra de tareas y el ícono pequeño del sistema en la barra
    de título, para que no se reescale y se vea nítido."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
                                        ctypes.c_void_p]
        dpi = user32.GetDpiForWindow(ctypes.c_void_p(hwnd)) or 96
        sizes = {1: round(24 * dpi / 96),  # ICON_BIG -> barra de tareas
                 0: user32.GetSystemMetricsForDpi(49, dpi)}  # ICON_SMALL (SM_CXSMICON)
        for kind, px in sizes.items():
            handle = user32.LoadImageW(None, ico_path, 1, px, px, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if handle:
                _icon_handles.append(handle)
                user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0080, kind, handle)  # WM_SETICON
    except Exception:
        pass
