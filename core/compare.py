"""Comparar dos PDFs: diferencias de texto (difflib) o visuales (píxel a píxel).
Sin imports de UI."""
from __future__ import annotations

import difflib
from pathlib import Path

from .edit_sign import _noop, _open


def _lines(src) -> tuple[list[str], int]:
    reader = _open(src)
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines.extend(line.rstrip() for line in text.splitlines() if line.strip())
    return lines, len(reader.pages)


def compare_text(src_a, src_b, progress=None) -> dict:
    """Devuelve {"rows": [(texto_a, estado_a, texto_b, estado_b)], "pages_a", "pages_b",
    "added", "removed", "identical"}. Estados: equal / removed / added / empty."""
    progress = progress or _noop
    progress(0.2, "Extrayendo el texto del primer PDF…")
    lines_a, pages_a = _lines(src_a)
    progress(0.5, "Extrayendo el texto del segundo PDF…")
    lines_b, pages_b = _lines(src_b)
    if not lines_a and not lines_b:
        raise ValueError("Ninguno de los dos PDFs tiene texto seleccionable. Prueba el modo VISUAL.")
    progress(0.8, "Comparando…")
    rows: list[tuple[str, str, str, str]] = []
    added = removed = 0
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "equal":
            rows.extend((lines_a[a0 + k], "equal", lines_b[b0 + k], "equal") for k in range(a1 - a0))
            continue
        left, right = lines_a[a0:a1], lines_b[b0:b1]
        removed += len(left)
        added += len(right)
        for k in range(max(len(left), len(right))):
            rows.append((left[k] if k < len(left) else "", "removed" if k < len(left) else "empty",
                         right[k] if k < len(right) else "", "added" if k < len(right) else "empty"))
    progress(1.0, None)
    return {"rows": rows, "pages_a": pages_a, "pages_b": pages_b, "added": added,
            "removed": removed, "identical": added == 0 and removed == 0}


def compare_visual(src_a, src_b, output, dpi: int = 100, threshold: int = 40,
                   progress=None) -> dict:
    """Genera un PDF con cada par de páginas lado a lado y las diferencias en rojo.
    Devuelve {"path", "changed_pages" (1-based), "pages_a", "pages_b", "compared"}."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

    from .pdf_tools import render_page_image

    progress = progress or _noop
    pages_a = len(_open(src_a).pages)
    pages_b = len(_open(src_b).pages)
    compared = min(pages_a, pages_b)
    red = (229, 57, 53)
    try:
        font = ImageFont.load_default(size=16)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    sheets, changed = [], []
    for i in range(compared):
        progress(i / compared, f"Comparando página {i + 1} de {compared}…")
        a = render_page_image(src_a, i, dpi=dpi).convert("RGB")
        b = render_page_image(src_b, i, dpi=dpi).convert("RGB")
        if b.size != a.size:
            b = b.resize(a.size, Image.LANCZOS)
        diff = ImageChops.difference(a, b).convert("L")
        mask = diff.point(lambda v: 255 if v > threshold else 0)
        if mask.getbbox():
            changed.append(i + 1)
            mask = mask.filter(ImageFilter.MaxFilter(7))  # engrosa para que se vea
        overlay = Image.new("RGB", a.size, red)
        marked = [Image.composite(overlay, Image.blend(page, Image.new("RGB", a.size, "white"), 0.35),
                                  mask) for page in (a, b)]
        header = 34
        sheet = Image.new("RGB", (a.width * 2 + 30, a.height + header), "white")
        draw = ImageDraw.Draw(sheet)
        status = "con diferencias" if (i + 1) in changed else "sin diferencias"
        draw.text((10, 8), f"Página {i + 1} — A (izquierda) / B (derecha) — {status}",
                  fill=(26, 26, 46), font=font)
        sheet.paste(marked[0], (10, header))
        sheet.paste(marked[1], (a.width + 20, header))
        sheets.append(sheet)
    if not sheets:
        raise ValueError("Alguno de los PDFs no tiene páginas.")
    progress(0.97, "Guardando el informe…")
    sheets[0].save(str(output), "PDF", save_all=True, append_images=sheets[1:], resolution=dpi)
    progress(1.0, None)
    return {"path": Path(output), "changed_pages": changed, "pages_a": pages_a,
            "pages_b": pages_b, "compared": compared}
