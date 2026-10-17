"""Capturas reales de la app para el README y la página (docs/img/), con documentos de
ejemplo generados aquí mismo (nunca archivos personales).

    python tools\\make_screenshots.py

Genera: home-claro, home-oscuro, editor-claro, editor-oscuro, dividir-claro (WebP).
La configuración del usuario (~/.pdfkit/settings.json) se restaura al final.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "img"


def sample_pdf(path: Path) -> Path:
    """Un informe de ejemplo de 6 páginas (texto, títulos y una tabla)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    body = ("Este documento de ejemplo muestra cómo PDFKit edita texto en el lugar, con la misma "
            "fuente, tamaño y color del original. Todo el procesamiento ocurre en tu computadora: "
            "ningún archivo se sube a internet.")
    story = []
    for page in range(1, 7):
        story += [Paragraph(f"Informe trimestral · Sección {page}", styles["Title"]),
                  Paragraph("Resumen de ventas por región", styles["Heading2"]),
                  Paragraph(body, styles["BodyText"]), Spacer(1, 12)]
        rows = [["Región", "Enero", "Febrero", "Marzo"]] + [
            [name, f"{1200 + i * 130 + page * 7:,}", f"{1310 + i * 90:,}", f"{1405 + i * 120:,}"]
            for i, name in enumerate(["Norte", "Centro", "Sur", "Occidente", "Oriente"])]
        table = Table(rows, colWidths=[140, 90, 90, 90])
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8BCC8")),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F7")),
                                   ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
        story += [table, Spacer(1, 12), Paragraph(body, styles["BodyText"]), PageBreak()]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return path


def main() -> int:
    from PIL import ImageGrab

    from ui.app import App

    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="pdfkit_capturas_"))
    pdf = sample_pdf(work / "Informe trimestral.pdf")
    settings = Path.home() / ".pdfkit" / "settings.json"
    backup = settings.read_bytes() if settings.exists() else None
    app = App()
    app.geometry("1280x800+30+30")
    app.attributes("-topmost", True)

    def settle(ms):
        end = time.perf_counter() + ms / 1000
        while time.perf_counter() < end:
            app.update()

    def generic_output(view):
        """Ruta de salida genérica en las capturas (nunca la carpeta real del usuario)."""
        entry = view.output_selector.entry
        entry.delete(0, "end")
        entry.insert(0, r"C:\Users\Usuario\Documents\PDFKit")

    def shot(name):
        view = app._views.get(app._active) if getattr(app, "_active", None) else None
        if view is not None and getattr(view, "output_selector", None):
            generic_output(view)
        settle(700)
        x, y = app.winfo_rootx(), app.winfo_rooty()
        image = ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()), all_screens=True)
        image.save(OUT / f"{name}.webp", quality=88, method=6)
        print("captura", name, image.size, flush=True)

    def run():
        try:
            for mode in ("claro", "oscuro"):
                app.set_theme(mode, animate=False)
                app.show_view("home")
                shot(f"home-{mode}")
            for mode in ("claro", "oscuro"):
                app.set_theme(mode, animate=False)
                app.show_view("edit")
                v = app._views["edit"]
                if v.ed_session is None:
                    v.picker.add_files([str(pdf)])
                    end = time.time() + 30
                    while (v.ed_image is None or v._model() is None) and time.time() < end:
                        app.update()
                settle(800)
                line = next(l for l in v._model()["lines"] if "Resumen" in l["text"])
                v._select(line["id"])
                shot(f"editor-{mode}")
            app.set_theme("claro", animate=False)
            app.show_view("split")
            s = app._views["split"]
            s.picker.add_files([str(pdf)])
            s.mode.set("Tamaño máximo (MB)")
            s._mode_changed("Tamaño máximo (MB)")
            shot("dividir-claro")
        finally:
            app.destroy()

    app.after(800, run)
    try:
        app.mainloop()
    finally:
        if backup is not None:
            settings.write_bytes(backup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
