"""Edición del texto original en el propio contenido de la página (núcleo, sin UI).

En vez de borrar una línea y volver a escribirla con otra fuente, aquí se
interpreta el flujo de contenido de la página (y de sus Form XObjects): cada
glifo mostrado queda ubicado con su operador, su código, su posición y el
estado de texto vigente (fuente del PDF, tamaño, Tc, Tw, Tz, Tr, Ts, colores).
Con eso se pueden aplicar cambios mínimos:

* Quitar glifos: el operador se reescribe sin ellos y con ajustes TJ que dejan
  todos los demás glifos (y el punto final) exactamente donde estaban.
* Volver a escribir un fragmento: un objeto de texto nuevo justo después del
  original, con la MISMA fuente del PDF (mismo recurso, mismo buffer) y el mismo
  estado de texto y color. Un cambio de posición solo cambia la matriz de texto.
* Si la fuente del PDF no tiene algún carácter: la versión completa de esa
  fuente instalada en Windows; si tampoco existe, se pide confirmación
  (`needs_substitution`) antes de usar una parecida.

Coordenadas de salida: las de PyMuPDF (origen arriba a la izquierda), sobre el
mismo documento normalizado que usa EditorSession.
"""
from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field

import pikepdf

try:
    import pymupdf as fitz
except ImportError:  # PyMuPDF < 1.24
    import fitz

STD14 = {  # fuentes estándar sin incrustar -> métricas de PyMuPDF
    "helvetica": "helv", "helvetica-bold": "hebo", "helvetica-oblique": "heit",
    "helvetica-boldoblique": "hebi", "times-roman": "tiro", "times-bold": "tibo",
    "times-italic": "tiit", "times-bolditalic": "tibi", "courier": "cour",
    "courier-bold": "cobo", "courier-oblique": "coit", "courier-boldoblique": "cobi",
    "symbol": "symb", "zapfdingbats": "zadb",
}
STROKE_MODES = {1, 2, 5, 6}
MATCH_TOL = 0.6          # pt entre el origen calculado y el de PyMuPDF
EPS = 1e-4
_SUBSET = re.compile(r"^[A-Z]{6}\+")


def clean_name(name: str) -> str:
    return _SUBSET.sub("", name or "")


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _matrix(values) -> fitz.Matrix:
    return fitz.Matrix(*[_num(v) for v in values])


def _fmt(value: float):
    """Número compacto para el flujo de contenido."""
    value = round(value, 4)
    return int(value) if value == int(value) else value


# --------------------------------------------------------------------------- fuentes

def _parse_tounicode(data: bytes) -> dict[int, str]:
    text = data.decode("latin-1", "replace")
    out: dict[int, str] = {}

    def utf16(hexstr):
        raw = bytes.fromhex(hexstr if len(hexstr) % 2 == 0 else hexstr + "0")
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""

    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            out[int(src, 16)] = utf16(dst)
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        for lo, hi, rest in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)",
                                       block):
            lo_i, hi_i = int(lo, 16), int(hi, 16)
            if hi_i - lo_i > 0xFFFF:
                continue
            if rest.startswith("["):
                for n, dst in enumerate(re.findall(r"<([0-9A-Fa-f]*)>", rest)):
                    out[lo_i + n] = utf16(dst)
            else:
                base = utf16(rest[1:-1])
                if not base:
                    continue
                for n in range(hi_i - lo_i + 1):
                    out[lo_i + n] = base[:-1] + chr(ord(base[-1]) + n)
    return out


def _standard_encoding() -> dict[int, str]:
    table = {c: chr(c) for c in range(0x20, 0x7F)}
    table[0x27], table[0x60] = "\u2019", "\u2018"
    return table


def _base_encoding(name: str) -> dict[int, str]:
    codec = {"/WinAnsiEncoding": "cp1252", "/MacRomanEncoding": "mac_roman"}.get(name)
    if codec:
        table = {}
        for code in range(0x20, 0x100):
            try:
                table[code] = bytes([code]).decode(codec)
            except UnicodeDecodeError:
                pass
        if codec == "cp1252":
            table[0xA0] = " "  # el espacio duro de WinAnsi se dibuja como espacio
        return table
    return _standard_encoding()


class FontInfo:
    """Lo necesario de una fuente del PDF para medir, decodificar y codificar texto."""

    def __init__(self, fd, objnum: int):
        self.objnum = objnum
        self.subtype = str(fd.get("/Subtype", ""))
        self.basefont = str(fd.get("/BaseFont", "/?"))[1:]
        self.name = clean_name(self.basefont)
        self.subset = bool(_SUBSET.match(self.basefont))
        self.two_byte = self.subtype == "/Type0"
        self.supported = self.subtype != "/Type3"
        self.widths: dict[int, float] = {}
        self.default_width = 0.0
        self.to_unicode: dict[int, str] = {}
        self.encoding: dict[int, str] = {}
        self.buffer: bytes | None = None
        self.font_kind = ""
        self.std14 = None
        self.seen: set[int] = set()     # códigos dibujados en el documento (el glifo existe)
        self._fitz_font = False
        descriptor = None
        if self.two_byte:
            encoding = fd.get("/Encoding")
            if not (isinstance(encoding, pikepdf.Name) and str(encoding) == "/Identity-H"):
                self.supported = False       # CMaps verticales o predefinidos: no se editan aquí
            try:
                desc = fd.DescendantFonts[0]
            except Exception:
                desc, self.supported = {}, False
            self.default_width = _num(desc.get("/DW", 1000))
            self._parse_w(desc.get("/W"))
            descriptor = desc.get("/FontDescriptor")
        else:
            first = int(_num(fd.get("/FirstChar", 0)))
            widths = fd.get("/Widths")
            if widths is not None:
                for n, w in enumerate(widths):
                    self.widths[first + n] = _num(w)
            descriptor = fd.get("/FontDescriptor")
            if descriptor is not None:
                self.default_width = _num(descriptor.get("/MissingWidth", 0))
            self._parse_encoding(fd.get("/Encoding"))
        self.descriptor = {}
        if descriptor is not None:
            self.descriptor = {str(k)[1:]: str(v) for k, v in descriptor.items()
                               if not isinstance(v, pikepdf.Stream)}
            for key in ("/FontFile2", "/FontFile3", "/FontFile"):
                stream = descriptor.get(key)
                if stream is not None:
                    try:
                        self.buffer = bytes(stream.read_bytes())
                        self.font_kind = key[1:]
                    except Exception:
                        pass
                    break
        if self.buffer is None and not self.two_byte:
            code = STD14.get(self.name.lower().replace(",", "-"))
            if code:
                self.std14 = fitz.Font(code)
        to_unicode = fd.get("/ToUnicode")
        if to_unicode is not None:
            try:
                self.to_unicode = _parse_tounicode(bytes(to_unicode.read_bytes()))
            except Exception:
                pass
        self.reverse: dict[str, int] = {}
        for code, char in self.encoding.items():
            self.reverse.setdefault(char, code)
        for code, char in self.to_unicode.items():
            if len(char) == 1:
                self.reverse[char] = code   # ToUnicode manda sobre la codificación

    # ---------------------------------------------------------------- lectura
    def _parse_w(self, w):
        if w is None:
            return
        items = list(w)
        i = 0
        while i < len(items):
            first = int(_num(items[i]))
            nxt = items[i + 1] if i + 1 < len(items) else None
            if isinstance(nxt, pikepdf.Array):
                for n, value in enumerate(nxt):
                    self.widths[first + n] = _num(value)
                i += 2
            elif i + 2 < len(items):
                last, value = int(_num(nxt)), _num(items[i + 2])
                for code in range(first, last + 1):
                    self.widths[code] = value
                i += 3
            else:
                break

    def _parse_encoding(self, encoding):
        if isinstance(encoding, pikepdf.Name):
            self.encoding = _base_encoding(str(encoding))
        elif isinstance(encoding, pikepdf.Dictionary):
            self.encoding = _base_encoding(str(encoding.get("/BaseEncoding", "/StandardEncoding")))
            code = 0
            for item in encoding.get("/Differences", []):
                if isinstance(item, pikepdf.Name):
                    value = fitz.glyph_name_to_unicode(str(item)[1:])
                    if value and value != 0xFFFD:
                        self.encoding[code] = chr(value)
                    code += 1
                else:
                    code = int(_num(item))
        else:
            self.encoding = _standard_encoding() if self.subtype == "/Type1" else _base_encoding(
                "/WinAnsiEncoding")

    def codes(self, raw: bytes) -> list[int]:
        if self.two_byte:
            return [(raw[i] << 8) | (raw[i + 1] if i + 1 < len(raw) else 0) for i in range(0, len(raw), 2)]
        return list(raw)

    def code_bytes(self, code: int) -> bytes:
        return bytes([code >> 8, code & 0xFF]) if self.two_byte else bytes([code])

    def unicode(self, code: int) -> str | None:
        if code in self.to_unicode:
            return self.to_unicode[code]
        return self.encoding.get(code)

    def width(self, code: int) -> float:
        """Ancho del glifo en milésimas de em."""
        if code in self.widths:
            return self.widths[code]
        if self.std14 is not None:
            char = self.encoding.get(code)
            if char:
                return self.std14.glyph_advance(ord(char)) * 1000
        return self.default_width

    @property
    def description(self):
        """Familia, peso, estilo y clase reales de esta fuente (font_finder.describe)."""
        if getattr(self, "_description", None) is None:
            from . import font_finder

            buffer = self.buffer if self.font_kind in ("FontFile2", "FontFile3") else None
            self._description = font_finder.describe(self.basefont, buffer, self.descriptor)
        return self._description

    @property
    def fitz_font(self):
        if self._fitz_font is False:
            self._fitz_font = None
            if self.buffer:
                try:
                    self._fitz_font = fitz.Font(fontbuffer=self.buffer)
                except Exception:
                    pass
        return self._fitz_font

    # ---------------------------------------------------------------- escritura
    def _usable(self, code: int, char: str) -> bool:
        if code in self.seen:
            return True           # ya se dibuja en el documento: el glifo existe
        if self.buffer is None:
            return True           # sin incrustar: el lector usa la fuente completa
        font = self.fitz_font
        if font is not None and font.has_glyph(ord(char)):
            return True
        return not self.subset    # fuente completa: todo lo que su codificación nombra existe

    def code_for(self, char: str) -> int | None:
        """Código con el que esta fuente dibuja `char`, o None si no lo tiene."""
        for option in [char] + ([" "] if char == "\xa0" else []):
            code = self.reverse.get(option)
            if code is not None and self._usable(code, option):
                return code
        return None

    def encode(self, text: str):
        """Para cada carácter: su código, o `Space` si es un espacio sin glifo propio (se
        escribe como desplazamiento, con el ancho del espacio duro si la fuente lo tiene).
        Devuelve (items, caracteres que faltan)."""
        items, missing = [], []
        for char in text:
            code = self.code_for(char)
            if code is not None:
                items.append(code)
            elif char in " \xa0":
                nbsp = self.reverse.get("\xa0")
                items.append(Space(self.width(nbsp) if nbsp is not None else None))
            else:
                missing.append(char)
        return items, missing


@dataclass
class Space:
    """Espacio sin glifo propio: un desplazamiento (en milésimas de em, o None si hay que
    estimarlo)."""
    width: float | None = None


class ResolvedFont:
    """La fuente completa elegida por font_finder (la misma familia instalada o de la
    biblioteca, o una sustituta confirmada), lista para escribir: códigos = números de glifo."""

    def __init__(self, choice, text: str = ""):
        from . import font_finder

        self.choice = choice
        self.label = choice.label
        self.substitute = choice.substitute
        self.source = choice.face.source
        self.buffer = font_finder.static_buffer(choice, text)
        self.font = fitz.Font(fontbuffer=self.buffer)
        self.two_byte = True

    def covers(self, text: str) -> bool:
        return all(ch in "\n\r\t" or self.font.has_glyph(ord(ch)) or ch in " \xa0" for ch in text)

    def code_for(self, char: str) -> int:
        gid = self.font.has_glyph(ord(char))
        if not gid and char == "\xa0":
            gid = self.font.has_glyph(32)
        return gid

    def width_char(self, char: str) -> float:
        return self.font.glyph_advance(ord(char if self.font.has_glyph(ord(char)) else " ")) * 1000

    def subset_buffer(self, chars: set[str]) -> bytes:
        """Subconjunto con los glifos usados, conservando los números de glifo."""
        try:
            import logging
            from io import BytesIO

            from fontTools import subset as ft_subset
            from fontTools.ttLib import TTFont

            logging.getLogger("fontTools").setLevel(logging.ERROR)
            options = ft_subset.Options()
            options.retain_gids = True
            options.notdef_outline = True
            options.name_IDs = ["*"]
            options.layout_features = []
            font = TTFont(BytesIO(self.buffer))
            subsetter = ft_subset.Subsetter(options)
            subsetter.populate(unicodes={ord(c) for c in chars} | {32})
            subsetter.subset(font)
            out = BytesIO()
            font.save(out)
            return out.getvalue()
        except Exception:
            return self.buffer


# --------------------------------------------------------------------------- intérprete

@dataclass
class TextState:
    font_res: str = ""
    font: FontInfo | None = None
    size: float = 0.0
    tc: float = 0.0
    tw: float = 0.0
    th: float = 1.0
    tl: float = 0.0
    tr: int = 0
    ts: float = 0.0
    ctm: fitz.Matrix = field(default_factory=lambda: fitz.Matrix(1, 0, 0, 1, 0, 0))
    fill: list = field(default_factory=list)       # instrucciones de color de relleno vigentes
    stroke: list = field(default_factory=list)
    gstate: list = field(default_factory=list)     # gs, w, J, j, M, d… de este nivel

    def copy(self) -> "TextState":
        return TextState(self.font_res, self.font, self.size, self.tc, self.tw, self.th, self.tl,
                         self.tr, self.ts, fitz.Matrix(self.ctm), list(self.fill), list(self.stroke),
                         list(self.gstate))


@dataclass
class Glyph:
    gid: int
    stream: object
    op: int
    code: int
    x: float          # desplazamiento en espacio de texto desde el inicio del operador
    adv: float
    origin: tuple     # coordenadas de PyMuPDF
    char: str | None
    owner: str | None = None


@dataclass
class ShowOp:
    stream: object
    index: int
    operator: str
    operands: list
    state: TextState
    tm: fitz.Matrix           # matriz de texto al empezar a mostrar
    tlm: fitz.Matrix = None   # matriz de línea vigente
    line_x: float = 0.0       # avance desde el inicio de la línea hasta este operador
    glyphs: list = field(default_factory=list)
    end_x: float = 0.0
    bt_end: int = -1


class PageText:
    """Resultado de interpretar una página: glifos ubicados y operadores que los dibujan."""

    def __init__(self):
        self.streams: dict[object, bytes] = {}     # "page" o número de objeto del formulario
        self.forms: dict[int, int] = {}            # formulario -> veces que se dibuja
        self.ops: list[ShowOp] = []
        self.glyphs: list[Glyph] = []
        self.fonts: dict[int, FontInfo] = {}
        self.page_tm = fitz.Matrix(1, 0, 0, 1, 0, 0)
        self.op_of: dict[int, ShowOp] = {}
        self.ok = False


def interpret(fdoc, pk: pikepdf.Pdf, index: int, fonts: dict[int, FontInfo]) -> PageText:
    result = PageText()
    page = fdoc[index]
    result.page_tm = fitz.Matrix(page.transformation_matrix)
    try:
        data = page.read_contents()
        pk_page = pk.pages[index].obj
    except Exception:
        return result
    resources = _inherited(pk_page, "/Resources")
    result.streams["page"] = data
    _walk(result, data, "page", resources, TextState(), fonts, depth=0)
    result.fonts = fonts
    result.ok = True
    return result


def _inherited(obj, key):
    node = obj
    for _ in range(32):
        if node is None:
            return None
        value = node.get(key)
        if value is not None:
            return value
        node = node.get("/Parent")
    return None


_PARSE_LOCK = threading.Lock()
_OWNER = None


def parse(data: bytes):
    """Instrucciones de un flujo de contenido (el Pdf dueño debe seguir vivo mientras se lee)."""
    global _OWNER
    with _PARSE_LOCK:
        if _OWNER is None:
            _OWNER = pikepdf.new()
        stream = pikepdf.Stream(_OWNER, data)
        return list(pikepdf.parse_content_stream(stream))


def unparse(instructions) -> bytes:
    with _PARSE_LOCK:
        return pikepdf.unparse_content_stream(instructions)


def _walk(result: PageText, data: bytes, key, resources, initial: TextState, fonts, depth):
    try:
        instructions = parse(data)
    except Exception:
        return
    st = initial.copy()
    st.gstate = []
    stack: list[TextState] = []
    tm = tlm = fitz.Matrix(1, 0, 0, 1, 0, 0)
    line_x = 0.0
    open_ops: list[ShowOp] = []
    font_dict = resources.get("/Font") if resources is not None else None
    xobjects = resources.get("/XObject") if resources is not None else None

    def font_for(name):
        if font_dict is None or name not in font_dict:
            return None
        obj = font_dict[name]
        objnum = obj.objgen[0]
        if objnum not in fonts:
            try:
                fonts[objnum] = FontInfo(obj, objnum)
            except Exception:
                return None
        return fonts[objnum]

    for i, ins in enumerate(instructions):
        op = str(getattr(ins, "operator", ""))
        args = list(getattr(ins, "operands", []))
        if op == "q":
            stack.append(st.copy())
            st.gstate = []
        elif op == "Q":
            if stack:
                st = stack.pop()   # el estado de texto también es parte del estado gráfico
        elif op == "cm" and len(args) == 6:
            st.ctm = _matrix(args) * st.ctm
        elif op == "BT":
            tm = tlm = fitz.Matrix(1, 0, 0, 1, 0, 0)
            line_x = 0.0
            open_ops = []
        elif op == "ET":
            for show in open_ops:
                show.bt_end = i
            open_ops = []
        elif op == "Tf" and len(args) == 2:
            st.font_res, st.size = str(args[0]), _num(args[1])
            st.font = font_for(args[0])
        elif op == "Tc" and args:
            st.tc = _num(args[0])
        elif op == "Tw" and args:
            st.tw = _num(args[0])
        elif op == "Tz" and args:
            st.th = _num(args[0]) / 100
        elif op == "TL" and args:
            st.tl = _num(args[0])
        elif op == "Tr" and args:
            st.tr = int(_num(args[0]))
        elif op == "Ts" and args:
            st.ts = _num(args[0])
        elif op in ("Td", "TD") and len(args) == 2:
            if op == "TD":
                st.tl = -_num(args[1])
            tlm = fitz.Matrix(1, 0, 0, 1, _num(args[0]), _num(args[1])) * tlm
            tm, line_x = fitz.Matrix(tlm), 0.0
        elif op == "Tm" and len(args) == 6:
            tlm = _matrix(args)
            tm, line_x = fitz.Matrix(tlm), 0.0
        elif op == "T*":
            tlm = fitz.Matrix(1, 0, 0, 1, 0, -st.tl) * tlm
            tm, line_x = fitz.Matrix(tlm), 0.0
        elif op in ("Tj", "TJ", "'", '"'):
            if op == '"' and len(args) == 3:
                st.tw, st.tc = _num(args[0]), _num(args[1])
            if op in ("'", '"'):
                tlm = fitz.Matrix(1, 0, 0, 1, 0, -st.tl) * tlm
                tm, line_x = fitz.Matrix(tlm), 0.0
            show = ShowOp(key, i, op, args, st.copy(), fitz.Matrix(tm), fitz.Matrix(tlm), line_x)
            items = args[0] if op == "TJ" and args else ([args[-1]] if args else [])
            x = _show(result, show, items)
            show.end_x = x
            result.ops.append(show)
            open_ops.append(show)
            tm = fitz.Matrix(1, 0, 0, 1, x, 0) * tm
            line_x += x
        elif op in ("g", "rg", "k"):
            st.fill = [ins]
        elif op in ("G", "RG", "K"):
            st.stroke = [ins]
        elif op == "cs":
            st.fill = [ins]
        elif op == "CS":
            st.stroke = [ins]
        elif op in ("sc", "scn"):
            st.fill = [x for x in st.fill[:1] if str(x.operator) == "cs"] + [ins]
        elif op in ("SC", "SCN"):
            st.stroke = [x for x in st.stroke[:1] if str(x.operator) == "CS"] + [ins]
        elif op in ("gs", "w", "J", "j", "M", "d", "ri", "i"):
            st.gstate.append(ins)
        elif op == "Do" and args and xobjects is not None and depth < 8:
            name = args[0]
            if name in xobjects:
                form = xobjects[name]
                if str(form.get("/Subtype", "")) == "/Form":
                    objnum = form.objgen[0]
                    result.forms[objnum] = result.forms.get(objnum, 0) + 1
                    try:
                        form_data = bytes(form.read_bytes())
                    except Exception:
                        continue
                    result.streams.setdefault(objnum, form_data)
                    inner = st.copy()   # el formulario hereda el estado gráfico vigente
                    inner.ctm = _matrix(form.get("/Matrix", [1, 0, 0, 1, 0, 0])) * st.ctm
                    # el color del formulario es el vigente al dibujarlo (se conserva)
                    form_res = form.get("/Resources", resources)
                    _walk(result, form_data, objnum, form_res, inner, fonts, depth + 1)


def _show(result: PageText, show: ShowOp, items) -> float:
    st, font = show.state, show.state.font
    x = 0.0
    if font is None or not font.supported:
        return x
    for item in items:
        if isinstance(item, pikepdf.String):
            for code in font.codes(bytes(item)):
                adv = (font.width(code) / 1000 * st.size + st.tc
                       + (st.tw if not font.two_byte and code == 32 else 0)) * st.th
                point = fitz.Point(x, st.ts) * show.tm * st.ctm * result.page_tm
                glyph = Glyph(len(result.glyphs), show.stream, show.index, code, x, adv,
                              (point.x, point.y), font.unicode(code))
                font.seen.add(code)
                result.glyphs.append(glyph)
                show.glyphs.append(glyph)
                x += adv
        else:
            x -= _num(item) / 1000 * st.size * st.th
    return x


def match_chars(page_text: PageText, spans_chars):
    """Asigna a cada carácter de PyMuPDF (origen, texto) el glifo dibujado. Devuelve una
    lista de ids de glifo (o None) por carácter."""
    buckets: dict[tuple, list[Glyph]] = {}
    for g in page_text.glyphs:
        buckets.setdefault((round(g.origin[0]), round(g.origin[1])), []).append(g)
    used: set[int] = set()
    out = []
    for origin, char in spans_chars:
        best, best_d = None, MATCH_TOL
        bx, by = round(origin[0]), round(origin[1])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for g in buckets.get((bx + dx, by + dy), ()):
                    if g.gid in used:
                        continue
                    d = math.hypot(g.origin[0] - origin[0], g.origin[1] - origin[1])
                    same = g.char is None or g.char == char or {g.char, char} <= {" ", "\xa0"}
                    if same and d < best_d:
                        best, best_d = g, d
        if best is not None:
            used.add(best.gid)
        out.append(best.gid if best is not None else None)
    return out


# --------------------------------------------------------------------------- reescritura

@dataclass
class Run:
    """Texto a escribir con el estado (fuente, tamaño, Tc, Tw, Tz, Tr, Ts, color) de `state`."""
    state: TextState
    tm: fitz.Matrix
    items: list               # bytes de códigos o desplazamientos (float, espacio de texto)
    font_res: str | None = None
    two_byte: bool | None = None


class Rewriter:
    def __init__(self, page_text: PageText):
        self.pt = page_text
        self.removed: set[int] = set()
        self.after: dict[object, dict[int, list]] = {}    # flujo -> índice -> instrucciones

    @property
    def changed(self) -> bool:
        return bool(self.removed or self.after)

    def remove(self, gids) -> None:
        self.removed.update(g for g in gids if g is not None)

    def emit_after(self, op: ShowOp, run: Run) -> None:
        """Escribe `run` justo después de `op`, dentro del mismo objeto de texto (así el
        orden de lectura no cambia) y deja la posición del texto como estaba."""
        st = op.state
        if st.size * st.th and op.tlm is not None:
            self.after.setdefault(op.stream, {}).setdefault(op.index, []).extend(
                self._inline_ops(op, run))
        else:   # sin escala no se puede restaurar la posición: objeto de texto aparte
            anchor = op.bt_end if op.bt_end >= 0 else op.index
            self.after.setdefault(op.stream, {}).setdefault(anchor, []).extend(self._run_ops(run))

    def _inline_ops(self, op: ShowOp, run: Run):
        st = op.state
        own = st.font_res if st.font_res.startswith("/") else "/" + st.font_res
        out = []
        if run.font_res:
            name = run.font_res if run.font_res.startswith("/") else "/" + run.font_res
            out.append(self._ins([pikepdf.Name(name), _fmt(st.size)], "Tf"))
        out.append(self._ins([_fmt(v) for v in run.tm], "Tm"))
        out.append(self._tj(run.items, st))
        if run.font_res:
            out.append(self._ins([pikepdf.Name(own), _fmt(st.size)], "Tf"))
        # vuelve a la matriz de línea y avanza hasta donde terminaba el original
        out.append(self._ins([_fmt(v) for v in op.tlm], "Tm"))
        advance = op.line_x + op.end_x
        if abs(advance) > EPS:
            out.append(self._tj([advance], st))
        return out

    def layer_stream(self, runs) -> bytes:
        """Flujo independiente (con la matriz completa) para dibujar `runs` en otra capa."""
        ops = []
        for run in runs:
            ops += self._run_ops(run, with_ctm=True)
        return unparse(ops)

    # ---------------------------------------------------------------- instrucciones
    @staticmethod
    def _ins(operands, operator):
        return pikepdf.ContentStreamInstruction(operands, pikepdf.Operator(operator))

    def _tj(self, items, st: TextState):
        scale = st.size * st.th
        array, buf = [], b""
        for item in items:
            if isinstance(item, (bytes, bytearray)):
                buf += item
            elif abs(item) > EPS and scale:
                if buf:
                    array.append(pikepdf.String(buf))
                    buf = b""
                array.append(_fmt(-item * 1000 / scale))
        if buf:
            array.append(pikepdf.String(buf))
        return self._ins([pikepdf.Array(array)], "TJ")

    def _run_ops(self, run: Run, with_ctm: bool = False):
        st = run.state
        out = [self._ins([], "q")]
        if with_ctm:
            out.append(self._ins([_fmt(v) for v in st.ctm], "cm"))
        # el color vigente al dibujar el original (sin color explícito: el negro inicial)
        out += list(st.gstate) + (list(st.fill) or [self._ins([0], "g")])
        if st.tr in STROKE_MODES:
            out += list(st.stroke) or [self._ins([0], "G")]
        font_res = run.font_res or st.font_res
        if not font_res.startswith("/"):
            font_res = "/" + font_res
        out += [self._ins([], "BT"), self._ins([pikepdf.Name(font_res), _fmt(st.size)], "Tf")]
        if st.tc:
            out.append(self._ins([_fmt(st.tc)], "Tc"))
        if st.tw:
            out.append(self._ins([_fmt(st.tw)], "Tw"))
        if abs(st.th - 1) > EPS:
            out.append(self._ins([_fmt(st.th * 100)], "Tz"))
        if st.tr:
            out.append(self._ins([st.tr], "Tr"))
        if st.ts:
            out.append(self._ins([_fmt(st.ts)], "Ts"))
        out.append(self._ins([_fmt(v) for v in run.tm], "Tm"))
        out.append(self._tj(run.items, st))
        out += [self._ins([], "ET"), self._ins([], "Q")]
        return out

    def _rebuilt(self, show: ShowOp):
        """El operador sin los glifos quitados: los demás quedan en su lugar exacto."""
        st = show.state
        items, cur = [], 0.0
        font = st.font
        for g in show.glyphs:
            if g.gid in self.removed:
                continue
            if abs(g.x - cur) > EPS:
                items.append(g.x - cur)
            items.append(font.code_bytes(g.code))
            cur = g.x + g.adv
        if abs(show.end_x - cur) > EPS:
            items.append(show.end_x - cur)
        prefix = []
        if show.operator == "'":
            prefix = [self._ins([], "T*")]
        elif show.operator == '"' and len(show.operands) == 3:
            prefix = [self._ins([show.operands[0]], "Tw"), self._ins([show.operands[1]], "Tc"),
                      self._ins([], "T*")]
        return prefix + [self._tj(items, st)]

    # ---------------------------------------------------------------- aplicar
    def apply(self, fdoc, index: int) -> None:
        by_stream: dict[object, dict[int, ShowOp]] = {}
        for show in self.pt.ops:
            if any(g.gid in self.removed for g in show.glyphs):
                by_stream.setdefault(show.stream, {})[show.index] = show
        streams = set(by_stream) | set(self.after)
        page = fdoc[index]
        for key in streams:
            instructions = parse(self.pt.streams[key])
            replace = by_stream.get(key, {})
            extra = self.after.get(key, {})
            out = []
            for i, ins in enumerate(instructions):
                out.extend(self._rebuilt(replace[i]) if i in replace else [ins])
                out.extend(extra.get(i, []))
            data = unparse(out)
            if key == "page":
                contents = page.get_contents()
                fdoc.update_stream(contents[0], data)
                for other in contents[1:]:
                    fdoc.update_stream(other, b"")
            else:
                fdoc.update_stream(key, data)
