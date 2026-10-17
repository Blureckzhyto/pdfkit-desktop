"""Herramientas de páginas: extraer, eliminar, ordenar, rotar, numerar, recortar
y reparar. Sin imports de UI; mensajes en español."""
from __future__ import annotations

from pathlib import Path

from .edit_sign import ENCRYPTED_MSG, _noop, _open, _overlay, _page_box, _upright, _write
from .edit_sign import parse_page_spec
from .utils import hex_to_rgb01

MM_TO_PT = 72 / 25.4


def parse_pages_ordered(spec: str, total: int) -> list[int]:
    """Como parse_page_spec pero respeta el orden escrito: '5, 1-2' -> [4, 0, 1]."""
    ordered: list[int] = []
    for part in spec.replace(";", ",").split(","):
        if part.strip():
            for index in parse_page_spec(part, total):  # valida cada parte
                if index not in ordered:
                    ordered.append(index)
    if not ordered:
        raise ValueError("Ingresa al menos una página o rango, por ejemplo 1, 3, 5-8.")
    return ordered


def _copy_pages(reader, indices: list[int], output) -> Path:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for i in indices:
        writer.add_page(reader.pages[i])
    if reader.metadata:
        writer.add_metadata({k: v for k, v in reader.metadata.items() if isinstance(v, str)})
    return _write(writer, output)


def get_page_count(src) -> int:
    return len(_open(src).pages)


def extract_pages(src, output, spec: str, progress=None) -> tuple[Path, int]:
    progress = progress or _noop
    reader = _open(src)
    indices = parse_pages_ordered(spec, len(reader.pages))
    progress(0.4, f"Extrayendo {len(indices)} página(s)…")
    path = _copy_pages(reader, indices, output)
    progress(1.0, None)
    return path, len(indices)


def delete_pages(src, output, spec: str, progress=None) -> tuple[Path, int, int]:
    """Devuelve (ruta, páginas eliminadas, páginas restantes)."""
    progress = progress or _noop
    reader = _open(src)
    total = len(reader.pages)
    remove = set(parse_page_spec(spec, total))
    keep = [i for i in range(total) if i not in remove]
    if not keep:
        raise ValueError("No puedes eliminar todas las páginas: el PDF quedaría vacío.")
    progress(0.4, f"Eliminando {len(remove)} página(s)…")
    path = _copy_pages(reader, keep, output)
    progress(1.0, None)
    return path, len(remove), len(keep)


def reorder_pages(src, output, order: list[int], progress=None) -> Path:
    """`order` = índices originales en el orden nuevo (los que faltan se descartan)."""
    progress = progress or _noop
    reader = _open(src)
    if not order:
        raise ValueError("No quedan páginas para guardar.")
    if any(not 0 <= i < len(reader.pages) for i in order):
        raise ValueError("El orden de páginas no coincide con el documento.")
    progress(0.4, "Guardando el nuevo orden…")
    path = _copy_pages(reader, order, output)
    progress(1.0, None)
    return path


def render_thumbnails(src, dpi: int = 40, progress=None) -> list:
    """Miniaturas de todas las páginas (imágenes PIL), en bloques para informar avance."""
    from pdf2image import convert_from_path

    from .pdf_tools import POPPLER_PATH

    progress = progress or _noop
    total = get_page_count(src)
    images = []
    block = 12
    for first in range(1, total + 1, block):
        last = min(total, first + block - 1)
        try:
            images.extend(convert_from_path(str(src), dpi=dpi, first_page=first, last_page=last,
                                            poppler_path=POPPLER_PATH, thread_count=2))
        except Exception as exc:
            raise RuntimeError(f"No se pudieron generar las miniaturas: {exc}") from exc
        progress(last / total, f"Miniaturas: {last} de {total}")
    return images


def render_page_thumbnails(src, indices, max_size=(112, 150)) -> dict:
    """Miniaturas solo de las páginas pedidas ({índice: imagen PIL} que cabe en
    `max_size`), para cargarlas a medida que se ven. Usa PyMuPDF en el mismo
    proceso: unos milisegundos por página."""
    import fitz
    from PIL import Image

    try:
        doc = fitz.open(str(src))
    except Exception as exc:
        raise RuntimeError(f"No se pudieron generar las miniaturas: {exc}") from exc
    try:
        if doc.needs_pass:
            raise ValueError(ENCRYPTED_MSG)
        thumbs = {}
        for index in indices:
            page = doc[index]
            zoom = min(max_size[0] / page.rect.width, max_size[1] / page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            thumbs[index] = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return thumbs
    finally:
        doc.close()


# --------------------------------------------------------------------------- rotar

def get_rotations(src) -> list[int]:
    return [page.rotation % 360 for page in _open(src).pages]


def rotate_pages(src, output, rotations: dict[int, int], progress=None) -> tuple[Path, int]:
    """`rotations` = {índice: grados absolutos (0/90/180/270)}. Devuelve (ruta, cambiadas)."""
    from pypdf import PdfWriter

    progress = progress or _noop
    reader = _open(src)
    writer = PdfWriter(clone_from=reader)
    changed = 0
    for i, degrees in rotations.items():
        if degrees % 90:
            raise ValueError("La rotación tiene que ser 0°, 90°, 180° o 270°.")
        page = writer.pages[i]
        if page.rotation % 360 != degrees % 360:
            page.rotation = degrees % 360
            changed += 1
    progress(0.6, "Guardando…")
    path = _write(writer, output)
    progress(1.0, None)
    return path, changed


# --------------------------------------------------------------------------- números de página

NUMBER_POSITIONS = ("bottom_center", "bottom_right", "bottom_left", "top_center")
NUMBER_FORMATS = {
    "n": "{n}",
    "pagina_n": "Página {n}",
    "n_de_total": "{n} / {total}",
    "pagina_n_de_total": "Página {n} de {total}",
}
_EDGE_MARGIN = 28  # ~1 cm


def add_page_numbers(src, output, position: str = "bottom_center", start: int = 1,
                     fmt: str = "n", size: float = 11, color: str = "#1A1A2E",
                     pages_spec: str | None = None, progress=None) -> tuple[Path, int]:
    """Numera las páginas elegidas de forma consecutiva desde `start`. Devuelve
    (ruta, páginas numeradas). En los formatos con total, N es el último número."""
    from pypdf import PdfWriter

    progress = progress or _noop
    if position not in NUMBER_POSITIONS:
        raise ValueError(f"Posición desconocida: {position}")
    if fmt not in NUMBER_FORMATS:
        raise ValueError(f"Formato desconocido: {fmt}")
    reader = _open(src)
    writer = PdfWriter(clone_from=reader)
    total = len(writer.pages)
    targets = list(range(total)) if not pages_spec else parse_page_spec(pages_spec, total)
    last_number = start + len(targets) - 1
    r, g, b = hex_to_rgb01(color)
    template = NUMBER_FORMATS[fmt]
    for n, i in enumerate(targets):
        page = writer.pages[i]
        _upright(page)
        ox, oy, w, h = _page_box(page)
        label = template.format(n=start + n, total=last_number)

        def draw(c, label=label, ox=ox, oy=oy, w=w, h=h):
            c.setFillColorRGB(r, g, b)
            c.setFont("Helvetica", size)
            y = oy + h - _EDGE_MARGIN - size if position == "top_center" else oy + _EDGE_MARGIN
            if position in ("bottom_center", "top_center"):
                c.drawCentredString(ox + w / 2, y, label)
            elif position == "bottom_right":
                c.drawRightString(ox + w - _EDGE_MARGIN, y, label)
            else:
                c.drawString(ox + _EDGE_MARGIN, y, label)

        page.merge_page(_overlay(draw, ox, oy, w, h))
        progress(0.95 * (n + 1) / len(targets), f"Numerando página {i + 1} ({n + 1} de {len(targets)})")
    path = _write(writer, output)
    progress(1.0, None)
    return path, len(targets)


# --------------------------------------------------------------------------- recortar

def page_sizes_pt(src) -> list[tuple[float, float]]:
    """Tamaño de cada página tal como se ve (ancho, alto) en puntos."""
    sizes = []
    for page in _open(src).pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        sizes.append((h, w) if page.rotation % 180 else (w, h))
    return sizes


def crop_pages(src, output, margins_mm: tuple[float, float, float, float],
               pages: list[int] | None = None, progress=None) -> tuple[Path, int]:
    """Recorta (arriba, abajo, izquierda, derecha) en mm, medidos sobre la página tal
    como se ve. Ajusta MediaBox y CropBox para que el recorte valga en cualquier
    visor. `pages` = índices a recortar (None = todas)."""
    from pypdf import PdfWriter
    from pypdf.generic import RectangleObject

    progress = progress or _noop
    top, bottom, left, right = (max(0.0, float(m)) * MM_TO_PT for m in margins_mm)
    if not any((top, bottom, left, right)):
        raise ValueError("Ingresa al menos un margen mayor que cero.")
    reader = _open(src)
    writer = PdfWriter(clone_from=reader)
    targets = list(range(len(writer.pages))) if pages is None else pages
    for n, i in enumerate(targets):
        page = writer.pages[i]
        _upright(page)
        ox, oy, w, h = _page_box(page)
        if left + right >= w - 10 or top + bottom >= h - 10:
            raise ValueError(f"Los márgenes son más grandes que la página {i + 1}.")
        box = RectangleObject((ox + left, oy + bottom, ox + w - right, oy + h - top))
        page.mediabox = box
        page.cropbox = box
        for name in ("/TrimBox", "/BleedBox", "/ArtBox"):
            if name in page:
                del page[name]
        progress(0.9 * (n + 1) / len(targets), f"Recortando página {i + 1}")
    path = _write(writer, output)
    progress(1.0, None)
    return path, len(targets)


# --------------------------------------------------------------------------- reparar

def repair_pdf(src, output, progress=None) -> tuple[Path, list[str], int]:
    """Abre el PDF con qpdf (vía pikepdf), que reconstruye tablas de referencias y
    objetos dañados, y guarda una copia limpia. Devuelve (ruta, avisos, páginas)."""
    import pikepdf

    progress = progress or _noop
    progress(0.2, "Analizando el archivo…")
    try:
        pdf = pikepdf.open(str(src), attempt_recovery=True)
    except pikepdf.PasswordError as exc:
        raise RuntimeError(ENCRYPTED_MSG) from exc
    except Exception as exc:
        raise RuntimeError(
            "No se pudo recuperar el PDF: el archivo está demasiado dañado incluso para "
            f"el modo de reparación ({exc})."
        ) from exc
    with pdf:
        warnings = [str(w) for w in pdf.get_warnings()]
        try:
            pages = len(pdf.pages)
        except Exception as exc:
            raise RuntimeError(f"El PDF se abrió pero sus páginas no se pueden leer ({exc}).") from exc
        if pages == 0:
            raise RuntimeError("No se pudo recuperar ninguna página de este PDF.")
        progress(0.6, "Guardando copia reparada…")
        pdf.save(str(output), fix_metadata_version=True, compress_streams=True)
        warnings += [str(w) for w in pdf.get_warnings() if str(w) not in warnings]
    prefix = f"{src}: "
    warnings = [w[len(prefix):] if w.startswith(prefix) else w for w in warnings]
    progress(1.0, None)
    return Path(output), warnings, pages
