"""OCR: agrega una capa de texto invisible a PDFs escaneados. Sin imports de UI.

Usa el Tesseract incluido en assets/tesseract (o el del sistema). Tesseract
genera solo la capa de texto (textonly_pdf) y se superpone sobre la página
original, así que la calidad y el peso de las imágenes no cambian.
"""
from __future__ import annotations

import os
import shutil
from io import BytesIO
from pathlib import Path

from .edit_sign import _noop, _open, _page_box, _upright, _write, assets_dir

LANGUAGES = {"spa": "Español", "eng": "Inglés", "spa+eng": "Ambos"}
_EXISTING_TEXT_MIN = 20  # caracteres a partir de los cuales una página ya "tiene texto"


def tesseract_paths() -> tuple[str, str | None]:
    """(ejecutable, carpeta tessdata o None para la del sistema)."""
    bundled = assets_dir() / "tesseract"
    exe = bundled / "tesseract.exe"
    if exe.exists():
        return str(exe), str(bundled / "tessdata")
    found = shutil.which("tesseract")
    if found:
        return found, None
    raise RuntimeError("No se encontró Tesseract OCR: falta la carpeta assets/tesseract.")


def ocr_pdf(src, output, lang: str = "spa", dpi: int = 300, skip_text_pages: bool = True,
            progress=None) -> tuple[Path, int, int]:
    """Devuelve (ruta, páginas procesadas, páginas que ya tenían texto)."""
    import pytesseract
    from pypdf import PdfReader, PdfWriter, Transformation

    from .pdf_tools import render_page_image

    progress = progress or _noop
    if lang not in LANGUAGES:
        raise ValueError(f"Idioma de OCR desconocido: {lang}")
    exe, tessdata = tesseract_paths()
    pytesseract.pytesseract.tesseract_cmd = exe
    if tessdata:
        # por variable de entorno: en Windows pytesseract deja las comillas de
        # --tessdata-dir dentro de la ruta, y la ruta puede tener espacios
        os.environ["TESSDATA_PREFIX"] = tessdata
    config = f"--dpi {dpi} -c textonly_pdf=1"

    reader = _open(src)
    writer = PdfWriter(clone_from=reader)
    total = len(writer.pages)
    done = skipped = 0
    for i, page in enumerate(writer.pages):
        progress(i / total, f"Procesando página {i + 1} de {total}…")
        if skip_text_pages and len((page.extract_text() or "").strip()) >= _EXISTING_TEXT_MIN:
            skipped += 1
            continue
        image = render_page_image(src, i, dpi=dpi)
        try:
            data = pytesseract.image_to_pdf_or_hocr(image, extension="pdf", lang=lang,
                                                    config=config)
        except Exception as exc:
            raise RuntimeError(f"Tesseract falló en la página {i + 1}: {exc}") from exc
        text_layer = PdfReader(BytesIO(data)).pages[0]
        _upright(page)
        ox, oy, w, h = _page_box(page)
        tw, th = float(text_layer.mediabox.width), float(text_layer.mediabox.height)
        page.merge_transformed_page(
            text_layer, Transformation().scale(w / tw, h / th).translate(ox, oy))
        done += 1
    progress(0.98, "Guardando…")
    path = _write(writer, output)
    progress(1.0, None)
    return path, done, skipped
