"""Documentos de prueba generados (nunca archivos personales).

`portada(path)` reproduce el caso real que motivó v1.3.4–1.3.5: una portada con
Montserrat-Bold 14,14 pt incrustada como SUBCONJUNTO (solo las letras usadas, todas
mayúsculas) y con el texto dentro de un Form XObject. Necesita la biblioteca de fuentes
(python tools/fetch_assets.py) para tomar Montserrat.

Si se define la variable de entorno PDFKIT_PORTADA con la ruta de un PDF real, las
pruebas usan una copia de ese archivo en lugar del generado.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LINES = [
    (60, 560, "ALUMNOS:"),
    (80, 580, "RAMIREZ TORRES ANA"),
    (60, 600, "GRUPO: 3B1"),
    (60, 620, "CARRERA: INGENIERÍA EN SISTEMAS COMPUTACIONALES"),
    (60, 640, "DOCENTE: CASTRO VEGA LUIS"),
    (60, 660, "MATERIA: PROGRAMACIÓN WEB"),
]


def montserrat_bold() -> bytes:
    from core import font_finder

    choice = font_finder.find_same(font_finder.describe("Montserrat-Bold"))
    if choice is None:
        raise RuntimeError("Falta Montserrat en assets/fonts/library: ejecuta python tools/fetch_assets.py")
    return font_finder.static_buffer(choice)


def portada(path: Path) -> Path:
    path = Path(path)
    real = os.environ.get("PDFKIT_PORTADA")
    if real and Path(real).exists():
        shutil.copy(real, path)
        return path
    import fitz

    inner = fitz.open()
    page = inner.new_page(width=595, height=842)
    page.insert_font(fontname="MontB", fontbuffer=montserrat_bold())
    for x, y, text in LINES:
        page.insert_text((x, y), text, fontname="MontB", fontsize=14.14, color=(0.07, 0.07, 0.07))
    inner.subset_fonts()                    # subconjunto: solo las letras usadas
    outer = fitz.open()
    target = outer.new_page(width=595, height=842)
    target.draw_rect(fitz.Rect(0, 0, 595, 120), color=None, fill=(0.0, 0.3, 0.6))
    target.show_pdf_page(target.rect, inner, 0)   # el texto queda dentro de un Form XObject
    outer.save(path, garbage=3, deflate=True)
    return path
