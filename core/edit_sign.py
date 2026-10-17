"""Editar & firmar: edición avanzada, firmas, formularios, contraseñas y marcas
de agua. Sin imports de UI.

Los mensajes de las excepciones llegan tal cual a la interfaz, por eso están en
español. Las funciones largas aceptan `progress(fracción, mensaje)`.
"""
from __future__ import annotations

import math
import os
import secrets
import sys
from io import BytesIO
from pathlib import Path

from .utils import hex_to_rgb01

ENCRYPTED_MSG = ("Este PDF está protegido con contraseña. Desbloquéalo primero con "
                 "'Proteger / Desproteger'.")
NO_FIELDS_MSG = ("Este PDF no tiene campos de formulario. Puedes usar 'Editar PDF' "
                 "para añadir texto manualmente.")


def _noop(fraction: float, message: str | None = None) -> None:
    pass


def assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def _open(src):
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(src))
    except Exception as exc:
        raise RuntimeError(f"No se pudo leer el PDF: {exc}") from exc
    if reader.is_encrypted:
        raise RuntimeError(ENCRYPTED_MSG)
    return reader


def _write(writer, output) -> Path:
    with open(output, "wb") as fh:
        writer.write(fh)
    return Path(output)


def parse_page_spec(spec: str, total: int) -> list[int]:
    """'1-3, 5' -> [0, 1, 2, 4] (0-based, ordenado, sin repetidos)."""
    pages: set[int] = set()
    for part in spec.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                a, b = (int(x) for x in part.split("-", 1))
            else:
                a = b = int(part)
        except ValueError:
            raise ValueError(f"'{part}' no es un rango válido (usa por ejemplo 1-3, 5).") from None
        if a < 1 or b > total or a > b:
            raise ValueError(f"El rango '{part}' está fuera del documento ({total} páginas).")
        pages.update(range(a - 1, b))
    if not pages:
        raise ValueError("Ingresa al menos una página o rango, por ejemplo 1-3, 5.")
    return sorted(pages)


# --------------------------------------------------------------------------- overlays

def _upright(page) -> None:
    """Integra /Rotate al contenido para que las coordenadas coincidan con la
    página tal como se ve en pantalla."""
    if page.rotation:
        page.transfer_rotation_to_content()


def _page_box(page) -> tuple[float, float, float, float]:
    mb = page.mediabox
    return float(mb.left), float(mb.bottom), float(mb.width), float(mb.height)


def _overlay(draw, ox: float, oy: float, w: float, h: float):
    """Ejecuta draw(canvas) en un lienzo reportlab y devuelve una página pypdf.

    pypdf recorta la página superpuesta a su propia caja, así que el lienzo
    cubre desde el origen hasta el borde superior derecho absoluto."""
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas as rl_canvas

    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(max(ox, 0) + w, max(oy, 0) + h))
    draw(c)
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


# --------------------------------------------------------------------------- 1. editar

def apply_edits(src, output, annotations: dict[int, list[dict]], rotations: dict[int, int],
                deleted: set[int], scale: float, progress=None) -> Path:
    """Integra las ediciones en un PDF nuevo.

    Las coordenadas de `annotations[página]` son píxeles de la página renderizada
    (origen arriba a la izquierda) a `scale` píxeles por punto, medidos sobre la
    página tal como se ve (con la rotación extra aplicada). `rotations` son grados
    horarios acumulados (múltiplos de 90). Tipos de anotación:
      {"type": "text", "x", "y", "baseline", "text", "size" (pt), "color", "bold"}
      {"type": "highlight", "x", "y", "w", "h", "color"}
      {"type": "draw", "points": [(x, y), ...], "width" (pt), "color"}
      {"type": "image", "path", "x", "y", "w", "h"}
      {"type": "redact", "x", "y", "w", "h"}
    La redacción borra de verdad el texto, las imágenes y los trazos que quedan
    debajo (no es solo un rectángulo negro encima).
    """
    from pypdf import PdfReader, PdfWriter

    progress = progress or _noop
    reader = _open(src)
    total = len(reader.pages)

    # 1) eliminar y rotar páginas
    writer = PdfWriter()
    kept: list[int] = []
    crop_offsets: list[tuple[float, float]] = []
    for i, page in enumerate(reader.pages):
        if i in deleted:
            continue
        extra = rotations.get(i, 0) % 360
        if extra:
            page.rotate(extra)
        _upright(page)
        mb, cb = page.mediabox, page.cropbox
        crop_offsets.append((float(cb.left) - float(mb.left), float(mb.top) - float(cb.top)))
        writer.add_page(page)
        kept.append(i)
        progress(0.3 * (i + 1) / total, f"Preparando página {i + 1} de {total}")
    if not kept:
        raise ValueError("Todas las páginas están marcadas para eliminar: no queda nada para guardar.")
    buf = BytesIO()
    writer.write(buf)
    data = buf.getvalue()

    # 2) redacción real
    redactions = {}
    for n, orig in enumerate(kept):
        boxes = [a for a in annotations.get(orig, []) if a["type"] == "redact"]
        if boxes:
            redactions[n] = boxes
    if redactions:
        progress(0.45, "Aplicando redacción permanente…")
        data = _apply_redactions(data, redactions, crop_offsets, scale)

    # 3) superponer texto, resaltados, dibujos e imágenes
    writer = PdfWriter(clone_from=PdfReader(BytesIO(data)))
    for n, orig in enumerate(kept):
        anns = [a for a in annotations.get(orig, []) if a["type"] != "redact"]
        if anns:
            page = writer.pages[n]
            page.merge_page(_edit_overlay(page, anns, scale))
        progress(0.5 + 0.45 * (n + 1) / len(kept), f"Aplicando cambios en página {n + 1} de {len(kept)}")
    result = _write(writer, output)
    progress(1.0, None)
    return result


def _apply_redactions(data: bytes, redactions: dict[int, list[dict]],
                      crop_offsets: list[tuple[float, float]], scale: float) -> bytes:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # PyMuPDF < 1.24

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        for n, boxes in redactions.items():
            page = doc[n]
            # MuPDF mide desde la esquina superior izquierda de la CropBox;
            # el render de Poppler, desde la de la MediaBox.
            dx, dy = crop_offsets[n]
            for a in boxes:
                rect = fitz.Rect(a["x"] / scale - dx, a["y"] / scale - dy,
                                 (a["x"] + a["w"]) / scale - dx,
                                 (a["y"] + a["h"]) / scale - dy)
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
        return doc.tobytes(garbage=3, deflate=True)
    finally:
        doc.close()


def _edit_overlay(page, anns: list[dict], scale: float):
    from reportlab.lib.colors import Color
    from reportlab.lib.utils import ImageReader

    ox, oy, w, h = _page_box(page)

    def px(v: float) -> float:
        return v / scale

    def x_pt(x: float) -> float:
        return ox + px(x)

    def y_pt(y: float) -> float:  # píxel con origen arriba -> punto con origen abajo
        return oy + h - px(y)

    def draw(c):
        for a in anns:
            kind = a["type"]
            if kind == "text":
                r, g, b = hex_to_rgb01(a["color"])
                c.setFillColorRGB(r, g, b)
                c.setFont("Helvetica-Bold" if a.get("bold") else "Helvetica", a["size"])
                c.drawString(x_pt(a["x"]), y_pt(a.get("baseline", a["y"])), a["text"])
            elif kind == "highlight":
                r, g, b = hex_to_rgb01(a["color"])
                c.setFillColor(Color(r, g, b, alpha=0.35))
                c.rect(x_pt(a["x"]), y_pt(a["y"] + a["h"]), px(a["w"]), px(a["h"]),
                       stroke=0, fill=1)
            elif kind == "draw":
                pts = a["points"]
                if len(pts) < 2:
                    continue
                r, g, b = hex_to_rgb01(a["color"])
                c.setStrokeColorRGB(r, g, b)
                c.setLineWidth(a.get("width", 2))
                c.setLineCap(1)
                c.setLineJoin(1)
                path = c.beginPath()
                path.moveTo(x_pt(pts[0][0]), y_pt(pts[0][1]))
                for x, y in pts[1:]:
                    path.lineTo(x_pt(x), y_pt(y))
                c.drawPath(path, stroke=1, fill=0)
            elif kind == "image":
                if not Path(a["path"]).exists():
                    raise RuntimeError(f"No se encontró la imagen '{Path(a['path']).name}'.")
                c.drawImage(ImageReader(a["path"]), x_pt(a["x"]), y_pt(a["y"] + a["h"]),
                            px(a["w"]), px(a["h"]), mask="auto")

    return _overlay(draw, ox, oy, w, h)


# --------------------------------------------------------------------------- 2. firmar

SIGNATURE_SUPERSAMPLE = 3   # las firmas se generan a 3x para que se impriman nítidas
SCREEN_PX_TO_PT = 0.75      # 96 ppp de pantalla -> puntos PDF

_SCRIPT_FONTS = [
    ("Segoe Script", "segoesc.ttf"),
    ("Lucida Handwriting", "LHANDW.TTF"),
    ("Ink Free", "Inkfree.ttf"),
    ("Brush Script MT", "BRUSHSCI.TTF"),
    ("Freestyle Script", "FREESCPT.TTF"),
    ("Vladimir Script", "VLADIMIR.TTF"),
    ("Kunstler Script", "KUNSTLER.TTF"),
    ("Mistral", "MISTRAL.TTF"),
]


def signature_fonts() -> dict[str, str]:
    """Fuentes manuscritas disponibles: nombre -> ruta. Dancing Script viene incluida."""
    fonts: dict[str, str] = {}
    bundled = assets_dir() / "fonts" / "DancingScript.ttf"
    if bundled.exists():
        fonts["Dancing Script"] = str(bundled)
    font_dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    if os.environ.get("LOCALAPPDATA"):
        font_dirs.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts")
    for name, filename in _SCRIPT_FONTS:
        for folder in font_dirs:
            candidate = folder / filename
            if candidate.exists():
                fonts[name] = str(candidate)
                break
    return fonts


def _trim(img, pad: int):
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        return None
    x0, y0, x1, y1 = bbox
    return img.crop((max(0, x0 - pad), max(0, y0 - pad),
                     min(img.width, x1 + pad), min(img.height, y1 + pad)))


def _rgba(hex_color: str) -> tuple[int, int, int, int]:
    from PIL import ImageColor
    return ImageColor.getrgb(hex_color)[:3] + (255,)


def render_drawn_signature(strokes: list[list[tuple[float, float]]], color: str,
                           width: float = 2.5):
    """Trazos en píxeles de pantalla -> (imagen RGBA recortada, ancho natural en pt),
    o None si no hay trazos."""
    from PIL import Image, ImageDraw

    strokes = [s for s in strokes if s]
    if not strokes:
        return None
    k = SIGNATURE_SUPERSAMPLE
    max_x = max(x for s in strokes for x, _ in s)
    max_y = max(y for s in strokes for _, y in s)
    img = Image.new("RGBA", (int((max_x + 10) * k), int((max_y + 10) * k)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill = _rgba(color)
    line_w = max(1, round(width * k))
    r = line_w / 2
    for stroke in strokes:
        pts = [(x * k, y * k) for x, y in stroke]
        if len(pts) > 1:
            draw.line(pts, fill=fill, width=line_w, joint="curve")
        for x, y in pts:  # puntas redondeadas y trazos de un solo punto
            draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)
    img = _trim(img, 2 * k)
    if img is None:
        return None
    return img, img.width / k * SCREEN_PX_TO_PT


def render_text_signature(text: str, font_path: str, color: str, size: int = 48):
    """Texto en una fuente manuscrita -> (imagen RGBA recortada, ancho natural en pt),
    o None si el texto está vacío."""
    from PIL import Image, ImageDraw, ImageFont

    text = text.strip()
    if not text:
        return None
    k = SIGNATURE_SUPERSAMPLE
    try:
        font = ImageFont.truetype(font_path, int(size * k))
    except OSError as exc:
        raise RuntimeError(f"No se pudo cargar la fuente: {exc}") from exc
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    x0, y0, x1, y1 = probe.textbbox((0, 0), text, font=font)
    pad = int(size * k * 0.4)  # margen para los rasgos que sobresalen
    img = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - x0, pad - y0), text, font=font, fill=_rgba(color))
    img = _trim(img, 2 * k)
    if img is None:
        return None
    return img, img.width / k * SCREEN_PX_TO_PT


def load_signature_image(path):
    """Imagen de firma -> (RGBA recortada, ancho natural en pt). Si no tiene canal
    alfa (p. ej. una foto o un escaneo), el papel blanco se vuelve transparente."""
    from PIL import Image, ImageOps

    try:
        with Image.open(path) as opened:
            im = ImageOps.exif_transpose(opened)
            im.load()
    except Exception as exc:
        raise RuntimeError(f"No se pudo abrir la imagen: {exc}") from exc
    has_alpha = "A" in im.getbands() or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA")
    if not has_alpha:
        alpha = im.convert("L").point(lambda v: max(0, min(255, (240 - v) * 255 // 60)))
        im.putalpha(alpha)
    trimmed = _trim(im, 4)
    if trimmed is None:
        raise ValueError("La imagen está vacía o es completamente transparente.")
    if max(trimmed.size) > 2000:
        trimmed.thumbnail((2000, 2000))
    return trimmed, min(180.0, trimmed.width * SCREEN_PX_TO_PT)


def sign_pdf(src, output, page_index: int, signature, box: tuple[float, float, float, float],
             progress=None) -> Path:
    """Estampa `signature` (imagen RGBA de PIL) como capa transparente.

    `box` = (x, y, ancho, alto) en puntos, con origen arriba a la izquierda de la
    página tal como se ve en pantalla."""
    from pypdf import PdfWriter
    from reportlab.lib.utils import ImageReader

    progress = progress or _noop
    reader = _open(src)
    if not 0 <= page_index < len(reader.pages):
        raise ValueError("La página elegida no existe en este PDF.")
    progress(0.2, "Preparando la página…")
    writer = PdfWriter(clone_from=reader)
    page = writer.pages[page_index]
    _upright(page)
    ox, oy, w, h = _page_box(page)
    x, y, bw, bh = box
    sig = signature.convert("RGBA")

    def draw(c):
        c.drawImage(ImageReader(sig), ox + x, oy + h - y - bh, bw, bh, mask="auto")

    progress(0.5, "Estampando la firma…")
    page.merge_page(_overlay(draw, ox, oy, w, h))
    result = _write(writer, output)
    progress(1.0, None)
    return result


# --------------------------------------------------------------------------- 3. formularios

_FF_READONLY = 1
_FF_MULTILINE = 1 << 12
_FF_RADIO = 1 << 15
_FF_PUSHBUTTON = 1 << 16


def _button_states(field) -> list[str]:
    states = [str(s) for s in (field.get("/_States_") or [])]
    if not states:
        widgets = [field] + [k.get_object() for k in (field.get("/Kids") or [])]
        for widget in widgets:
            ap = widget.get("/AP")
            if ap is not None and "/N" in ap.get_object():
                states.extend(str(s) for s in ap.get_object()["/N"].get_object().keys())
    seen = []
    for s in states:
        if s != "/Off" and s not in seen:
            seen.append(s)
    return seen or ["/Yes"]


def get_form_fields(src) -> list[dict]:
    """Campos rellenables (AcroForm) del PDF, en orden de documento.

    Cada campo: {"name", "label", "type": text|checkbox|radio|choice, "value",
    "options": [(valor, texto visible)], "multiline", "readonly"}."""
    reader = _open(src)
    try:
        fields = reader.get_fields() or {}
    except Exception as exc:
        raise RuntimeError(f"No se pudieron leer los campos del formulario: {exc}") from exc

    result = []
    for name, field in fields.items():
        ft = field.get("/FT")
        if ft is None:
            continue
        kids = field.get("/Kids") or []
        if any("/T" in kid.get_object() for kid in kids):
            continue  # nodo intermedio: sus hijos se listan por separado
        flags = int(field.get("/Ff", 0) or 0)
        value = field.get("/V")
        entry = {
            "name": name,
            "label": str(field.get("/TU") or name),
            "readonly": bool(flags & _FF_READONLY),
            "multiline": False,
            "options": [],
        }
        if ft == "/Tx":
            entry.update(type="text", value="" if value is None else str(value),
                         multiline=bool(flags & _FF_MULTILINE))
        elif ft == "/Btn":
            if flags & _FF_PUSHBUTTON:
                continue
            states = _button_states(field)
            entry.update(type="radio" if flags & _FF_RADIO else "checkbox",
                         value=str(value) if value is not None else "/Off",
                         options=[(s, s.lstrip("/")) for s in states])
        elif ft == "/Ch":
            options = []
            for opt in field.get("/Opt") or []:
                opt = opt.get_object() if hasattr(opt, "get_object") else opt
                if isinstance(opt, list) and len(opt) >= 2:
                    options.append((str(opt[0]), str(opt[1])))
                else:
                    options.append((str(opt), str(opt)))
            if not options:
                entry.update(type="text", value="" if value is None else str(value))
            else:
                if isinstance(value, list):
                    value = value[0] if value else None
                entry.update(type="choice", value="" if value is None else str(value),
                             options=options)
        else:
            continue  # campos de firma digital: no se rellenan como texto
        result.append(entry)
    return result


def fill_form(src, output, values: dict[str, str], progress=None) -> Path:
    """Escribe los valores en los campos. Casillas y botones de opción reciben el
    nombre de su estado ('/Yes', '/Off', ...)."""
    from pypdf import PdfWriter

    progress = progress or _noop
    reader = _open(src)
    if not reader.get_fields():
        raise ValueError(NO_FIELDS_MSG)
    progress(0.2, "Copiando el documento…")
    writer = PdfWriter(clone_from=reader)
    progress(0.5, "Escribiendo los valores…")
    try:
        writer.update_page_form_field_values(None, values, auto_regenerate=True)
    except Exception as exc:
        raise RuntimeError(f"No se pudo completar el formulario: {exc}") from exc
    _normalize_button_values(writer)
    result = _write(writer, output)
    progress(1.0, None)
    return result


def _normalize_button_values(writer) -> None:
    """pypdf guarda el /V de los grupos de opción como texto; la especificación
    pide un nombre PDF. Se corrige para que todos los visores lo lean bien."""
    from pypdf.generic import NameObject, TextStringObject

    acro = writer.root_object.get("/AcroForm")
    if acro is None:
        return

    def visit(field_refs, inherited_ft=None):
        for ref in field_refs or []:
            field = ref.get_object()
            ft = field.get("/FT", inherited_ft)
            value = field.get("/V")
            if ft == "/Btn" and isinstance(value, TextStringObject) and value.startswith("/"):
                field[NameObject("/V")] = NameObject(str(value))
            visit(field.get("/Kids"), ft)

    visit(acro.get_object().get("/Fields"))


# --------------------------------------------------------------------------- 4. proteger

def _aes_available() -> bool:
    for module in ("cryptography", "Crypto"):
        try:
            __import__(module)
            return True
        except ImportError:
            continue
    return False


def protect_pdf(src, output, user_password: str, owner_password: str,
                allow_print: bool = True, allow_copy: bool = True,
                allow_modify: bool = False, progress=None) -> tuple[Path, str, bool]:
    """Cifra el PDF. Devuelve (ruta, algoritmo, se_generó_contraseña_de_propietario).

    Sin contraseña de propietario se genera una aleatoria: si fuera igual a la de
    usuario, quien abre el PDF tendría permisos totales y las restricciones no
    servirían."""
    from pypdf import PdfWriter
    from pypdf.constants import UserAccessPermissions as Perm

    progress = progress or _noop
    if not user_password and not owner_password:
        raise ValueError("Ingresa al menos una contraseña.")
    reader = _open(src)

    permissions = Perm(0xFFFFFFFC)  # todos los permisos (valor por defecto de pypdf)
    if not allow_print:
        permissions &= ~(Perm.PRINT | Perm.PRINT_TO_REPRESENTATION)
    if not allow_copy:
        permissions &= ~(Perm.EXTRACT | Perm.EXTRACT_TEXT_AND_GRAPHICS)
    if not allow_modify:
        permissions &= ~(Perm.MODIFY | Perm.ADD_OR_MODIFY | Perm.FILL_FORM_FIELDS
                         | Perm.ASSEMBLE_DOC)
    generated = not owner_password
    if generated:
        owner_password = secrets.token_urlsafe(24)

    progress(0.3, "Cifrando…")
    algorithms = ["AES-256", "RC4-128"] if _aes_available() else ["RC4-128"]
    last_error: Exception | None = None
    for algorithm in algorithms:
        try:
            writer = PdfWriter(clone_from=reader)
            writer.encrypt(user_password or "", owner_password,
                           permissions_flag=permissions, algorithm=algorithm)
            buf = BytesIO()
            writer.write(buf)
        except Exception as exc:
            last_error = exc
            continue
        Path(output).write_bytes(buf.getvalue())
        progress(1.0, None)
        return Path(output), algorithm, generated
    raise RuntimeError(f"No se pudo cifrar el PDF: {last_error}")


def unprotect_pdf(src, output, password: str, progress=None) -> Path:
    from pypdf import PasswordType, PdfReader, PdfWriter

    progress = progress or _noop
    try:
        reader = PdfReader(str(src))
    except Exception as exc:
        raise RuntimeError(f"No se pudo leer el PDF: {exc}") from exc
    if not reader.is_encrypted:
        raise ValueError("Este PDF no está protegido con contraseña.")
    progress(0.2, "Verificando la contraseña…")
    try:
        result = reader.decrypt(password)
    except Exception as exc:
        raise RuntimeError(f"No se pudo descifrar el PDF: {exc}") from exc
    if result == PasswordType.NOT_DECRYPTED:
        raise ValueError("Contraseña incorrecta.")
    progress(0.5, "Guardando copia sin contraseña…")
    writer = PdfWriter(clone_from=reader)
    path = _write(writer, output)
    progress(1.0, None)
    return path


# --------------------------------------------------------------------------- 5. marca de agua

WATERMARK_POSITIONS = ("diagonal", "horizontal", "corner")
_CORNER_MARGIN = 36  # 1/2 pulgada


def _stamp_pages(src, output, make_overlay, pages_spec: str | None, progress) -> tuple[Path, int]:
    from pypdf import PdfWriter

    reader = _open(src)
    writer = PdfWriter(clone_from=reader)
    total = len(writer.pages)
    targets = list(range(total)) if not pages_spec else parse_page_spec(pages_spec, total)
    cache: dict[tuple, object] = {}
    for n, i in enumerate(targets):
        page = writer.pages[i]
        _upright(page)
        ox, oy, w, h = _page_box(page)
        key = (round(ox, 2), round(oy, 2), round(w, 2), round(h, 2))
        if key not in cache:
            cache[key] = make_overlay(ox, oy, w, h)
        page.merge_page(cache[key])
        progress(0.95 * (n + 1) / len(targets), f"Página {i + 1} ({n + 1} de {len(targets)})")
    path = _write(writer, output)
    progress(1.0, None)
    return path, len(targets)


def watermark_text(src, output, text: str, size: float = 60, opacity: float = 0.3,
                   color: str = "#888888", position: str = "diagonal",
                   pages_spec: str | None = None, progress=None) -> tuple[Path, int]:
    """Devuelve (ruta, cantidad de páginas marcadas). El texto se achica solo si no
    entra en la página."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    progress = progress or _noop
    text = text.strip()
    if not text:
        raise ValueError("Escribe el texto de la marca de agua.")
    if position not in WATERMARK_POSITIONS:
        raise ValueError(f"Posición desconocida: {position}")
    font = "Helvetica-Bold"
    r, g, b = hex_to_rgb01(color)

    def make_overlay(ox, oy, w, h):
        limit = {"diagonal": math.hypot(w, h) * 0.8, "horizontal": w * 0.9,
                 "corner": w * 0.5}[position]
        font_size = size
        text_w = stringWidth(text, font, font_size)
        if text_w > limit:
            font_size *= limit / text_w

        def draw(c):
            c.setFillColorRGB(r, g, b)
            c.setFillAlpha(opacity)
            c.setFont(font, font_size)
            if position == "corner":
                c.drawRightString(ox + w - _CORNER_MARGIN, oy + _CORNER_MARGIN, text)
                return
            c.saveState()
            c.translate(ox + w / 2, oy + h / 2)
            if position == "diagonal":
                c.rotate(math.degrees(math.atan2(h, w)))
            c.drawCentredString(0, -font_size * 0.35, text)
            c.restoreState()

        return _overlay(draw, ox, oy, w, h)

    return _stamp_pages(src, output, make_overlay, pages_spec, progress)


def watermark_image(src, output, image_path, opacity: float = 0.3, scale: float = 0.4,
                    position: str = "diagonal", pages_spec: str | None = None,
                    progress=None) -> tuple[Path, int]:
    """`scale` = fracción del ancho de la página. Devuelve (ruta, páginas marcadas)."""
    from PIL import Image
    from reportlab.lib.utils import ImageReader

    progress = progress or _noop
    if position not in WATERMARK_POSITIONS:
        raise ValueError(f"Posición desconocida: {position}")
    try:
        with Image.open(image_path) as opened:
            im = opened.convert("RGBA")
    except Exception as exc:
        raise RuntimeError(f"No se pudo abrir la imagen: {exc}") from exc
    im.putalpha(im.getchannel("A").point(lambda v: int(v * opacity)))
    aspect = im.height / im.width

    def make_overlay(ox, oy, w, h):
        target_w = w * scale
        target_h = target_w * aspect
        if target_h > h * 0.9:
            target_h = h * 0.9
            target_w = target_h / aspect

        def draw(c):
            img = ImageReader(im)
            if position == "corner":
                c.drawImage(img, ox + w - _CORNER_MARGIN - target_w, oy + _CORNER_MARGIN,
                            target_w, target_h, mask="auto")
                return
            c.saveState()
            c.translate(ox + w / 2, oy + h / 2)
            if position == "diagonal":
                c.rotate(math.degrees(math.atan2(h, w)))
            c.drawImage(img, -target_w / 2, -target_h / 2, target_w, target_h, mask="auto")
            c.restoreState()

        return _overlay(draw, ox, oy, w, h)

    return _stamp_pages(src, output, make_overlay, pages_spec, progress)
