"""Capturas reales para la Microsoft Store: 1920x1080 (16:9), tema claro y oscuro, con
documentos de ejemplo generados aquí (nunca archivos personales).

    python tools\\make_store_screenshots.py [x,y del monitor]

La ventana se abre en pantalla completa en un monitor de 1920x1080 (por defecto el segundo,
si existe: a 125 % la interfaz se ve del tamaño de una laptop típica) y se captura tal cual,
sin reescalar. Genera store_listing/capturas/NN-<vista>-<tema>.png. Usa una carpeta de datos
temporal (como make_screenshots.py): no toca la configuración del usuario.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_screenshots import sample_pdf  # noqa: E402  (también prepara la carpeta de datos temporal)

sys.path.insert(0, str(ROOT))
OUT = ROOT / "store_listing" / "capturas"
SIZE = (1920, 1080)
SHOTS = [("home", "inicio"), ("edit", "editor"), ("split", "dividir-por-tamano"), ("pdf2word", "pdf-a-word")]


def monitors() -> list[tuple[int, int, int, int]]:
    import ctypes
    from ctypes import wintypes

    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                              wintypes.LPARAM)

    def collect(_h, _dc, rect, _l):
        r = rect.contents
        found.append((r.left, r.top, r.right, r.bottom))
        return 1

    ctypes.windll.user32.EnumDisplayMonitors(None, None, proc(collect), 0)
    return found


def main(argv: list[str]) -> int:
    from PIL import ImageGrab

    from ui import startup

    startup.prepare()   # DPI por monitor, como la app real
    from ui.app import App

    screens = [m for m in monitors() if (m[2] - m[0], m[3] - m[1]) == SIZE]
    if argv:
        x, y = (int(v) for v in argv[0].split(","))
        screens = [m for m in screens if (m[0], m[1]) == (x, y)]
    if not screens:
        raise SystemExit("Hace falta un monitor de 1920x1080")
    left, top = screens[-1][:2]
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="pliegue_capturas_store_"))
    pdf = sample_pdf(work / "Informe trimestral.pdf")
    app = App()
    app.geometry(f"+{left + 40}+{top + 40}")
    app.update()
    app.maxsize(10000, 10000)
    app.attributes("-fullscreen", True)
    app.attributes("-topmost", True)

    def settle(ms):
        end = time.perf_counter() + ms / 1000
        while time.perf_counter() < end:
            app.update()

    def generic_output(view):
        entry = view.output_selector.entry
        entry.delete(0, "end")
        entry.insert(0, r"C:\Users\Usuario\Documents\Pliegue")

    def load(view, timeout=30):
        if getattr(view, "picker", None) is not None and not getattr(view.picker, "files", None):
            view.picker.add_files([str(pdf)])
        settle(600)

    def prepare(key):
        app.show_view(key)
        view = app._views.get(key)
        if key == "edit":
            if view.ed_session is None:
                view.picker.add_files([str(pdf)])
                end = time.time() + 30
                while (view.ed_image is None or view._model() is None) and time.time() < end:
                    app.update()
            settle(800)
            line = next(l for l in view._model()["lines"] if "Resumen" in l["text"])
            view._select(line["id"])
        elif key in ("split", "pdf2word"):
            load(view)
            if key == "split":
                view.mode.set("Tamaño máximo (MB)")
                view._mode_changed("Tamaño máximo (MB)")
        if view is not None and getattr(view, "output_selector", None):
            generic_output(view)

    def shot(number, name):
        settle(900)
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        if (w, h) != SIZE:
            raise RuntimeError(f"la ventana mide {w}x{h}, no 1920x1080")
        image = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).convert("RGB")
        path = OUT / f"{number:02d}-{name}.png"
        image.save(path, optimize=True)
        print("captura", path.name, image.size, flush=True)

    def run():
        try:
            number = 1
            for mode in ("claro", "oscuro"):
                app.set_theme(mode, animate=False)
                for key, name in SHOTS:
                    prepare(key)
                    shot(number, f"{name}-{mode}")
                    number += 1
        finally:
            app.destroy()

    app.after(1200, run)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
