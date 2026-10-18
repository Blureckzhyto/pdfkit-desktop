"""Búsqueda de la fuente completa para el texto editado (núcleo, sin UI).

Orden cuando la fuente incrustada en el PDF no tiene algún carácter (los
subconjuntos solo traen los glifos usados):

1. La fuente incrustada, si tiene todos los glifos (lo decide pdf_textops).
2. La misma familia, peso y estilo instalada en Windows: C:\\Windows\\Fonts y la
   carpeta de fuentes del usuario (%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts).
3. La misma familia en la biblioteca incluida (assets/fonts/library).
4. Solo si nada de lo anterior coincide: una fuente PARECIDA elegida por
   clasificación (sans geométrica, sans, serif, mono; mismo peso y estilo). Esto es
   una sustitución y siempre requiere confirmación.

Familia, peso y estilo se leen de la tabla de nombres y de OS/2 de cada archivo
(fontTools), no del nombre del archivo. El índice se arma una vez y se guarda en
%LOCALAPPDATA%\\Pliegue\\font_index.json (solo se vuelven a leer los archivos que
cambiaron). Cada decisión queda en el registro "pdfkit.fonts".
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from dataclasses import asdict, dataclass, field
from io import BytesIO
from pathlib import Path

log = logging.getLogger("pdfkit.fonts")

WEIGHT_WORDS = {
    "thin": 100, "hairline": 100, "extralight": 200, "ultralight": 200, "light": 300,
    "regular": 400, "normal": 400, "book": 400, "roman": 400, "medium": 500, "semibold": 600,
    "demibold": 600, "demi": 600, "bold": 700, "extrabold": 800, "ultrabold": 800, "black": 900,
    "heavy": 900,
}
ITALIC_WORDS = {"italic", "oblique", "it", "ital", "inclined", "slanted"}
NOISE_WORDS = {"mt", "ps", "psmt", "std", "pro", "lt", "web", "otf", "ttf"}
SERIF_NAMES = ("times", "garamond", "georgia", "cambria", "caladea", "tinos", "palatino", "baskerville",
               "bodoni", "minion", "merriweather", "lora", "playfair", "bookantiqua", "century schoolbook",
               "centuryschoolbook", "didot", "caslon", "charter", "liberationserif", "notoserif",
               "sourceserif", "crimson", "libre baskerville", "librebaskerville", "ptserif", "roboto slab",
               "robotoslab", "rockwell", "constantia", "sylfaen", "bookman")
MONO_NAMES = ("mono", "courier", "cousine", "consolas", "code", "menlo", "inconsolata", "lucidaconsole")
GEOMETRIC_NAMES = ("montserrat", "poppins", "futura", "avenir", "gotham", "centurygothic", "proxima",
                   "leaguespartan", "spartan", "raleway", "quicksand", "nunito", "dmsans", "questrial",
                   "comfortaa", "josefin", "kumbh", "outfit", "urbanist", "sora", "manrope", "jost",
                   "lexend", "gilroy", "brandon", "tt norms", "ttnorms", "circular", "sofia")
# equivalentes métricos (mismo ancho de cada carácter) de las fuentes más comunes
METRIC_TWINS = {
    "helvetica": ["Arial", "Arimo"], "arial": ["Arimo", "Liberation Sans"],
    "times": ["Times New Roman", "Tinos"], "timesnewroman": ["Tinos", "Liberation Serif"],
    "courier": ["Courier New", "Cousine"], "couriernew": ["Cousine", "Liberation Mono"],
    "calibri": ["Carlito"], "cambria": ["Caladea"],
}
# fuentes parecidas por clasificación (todas en la biblioteca incluida)
SIMILAR = {
    "geometric": ["Poppins", "DM Sans", "Montserrat"],
    "sans": ["Inter", "Open Sans", "Arimo", "Noto Sans", "Roboto"],
    "serif": ["Tinos", "Noto Serif", "Lora"],
    "mono": ["Cousine"],
}


def family_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def strip_subset(name: str) -> str:
    return re.sub(r"^[A-Z]{6}\+", "", name or "")


def parse_name(name: str) -> tuple[str, int | None, bool]:
    """'BAAAAA+Montserrat-Bold' -> ('Montserrat', 700, False); también 'Montserrat,Bold',
    'Montserrat Bold Italic', 'Arial-BoldItalicMT', 'MontserratSemiBold'."""
    base = strip_subset(name)
    base = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base)          # CamelCase -> palabras
    tokens = [t for t in re.split(r"[-,_\s]+", base) if t]
    weight, italic = None, False
    while tokens:
        low = tokens[-1].lower()
        if low in NOISE_WORDS:
            tokens.pop()
        elif low in ITALIC_WORDS:
            italic = True
            tokens.pop()
        elif low in WEIGHT_WORDS and not (low == "roman" and len(tokens) > 1
                                           and tokens[-2].lower() == "new"):
            weight = WEIGHT_WORDS[low] if weight is None else weight
            tokens.pop()
        elif low in ("semi", "extra", "ultra", "demi") and weight is not None:
            weight = {"semi": 600, "demi": 600, "extra": 800, "ultra": 800}[low] if weight == 700 else (
                200 if weight == 300 else weight)
            tokens.pop()
        else:
            break
    return " ".join(tokens) or base, weight, italic


# --------------------------------------------------------------------------- descripción

@dataclass
class FontDescription:
    """Lo que se sabe de una fuente del PDF: familia, peso, estilo y clase."""
    name: str                 # nombre del PDF sin prefijo de subconjunto
    family: str
    weight: int = 400
    italic: bool = False
    kind: str = "sans"        # sans | serif | mono | script
    geometric: bool = False
    evidence: list = field(default_factory=list)


def describe(basefont: str, buffer: bytes | None = None, descriptor: dict | None = None) -> FontDescription:
    """Familia, peso, estilo y clasificación de una fuente del PDF a partir de su propio
    archivo incrustado (tablas name y OS/2), su nombre y su descriptor. Nunca usa una
    clase por defecto que no sea sans."""
    name = strip_subset(basefont)
    family, weight, italic = parse_name(name)
    desc = FontDescription(name=name, family=family, weight=weight or 400, italic=italic)
    panose = family_class = fixed = None
    if buffer:
        try:
            from fontTools.ttLib import TTFont

            font = TTFont(BytesIO(buffer), lazy=True)
            names = {r.nameID: r.toUnicode() for r in font["name"].names
                     if r.nameID in (1, 2, 16, 17)} if "name" in font else {}
            embedded_family = names.get(16) or names.get(1)
            if embedded_family and family_key(embedded_family) and not embedded_family.startswith("+"):
                desc.family = embedded_family
                desc.evidence.append(f"familia de la tabla name: {embedded_family}")
            if "OS/2" in font:
                os2 = font["OS/2"]
                if 1 <= os2.usWeightClass <= 1000:
                    desc.weight = int(os2.usWeightClass)
                    desc.evidence.append(f"peso OS/2: {desc.weight}")
                if os2.fsSelection & 1:
                    desc.italic = True
                panose, family_class = os2.panose, os2.sFamilyClass >> 8
            if "post" in font and font["post"].isFixedPitch:
                fixed = True
        except Exception as exc:
            desc.evidence.append(f"no se pudo leer la fuente incrustada: {exc}")
    descriptor = descriptor or {}
    flags = int(descriptor.get("Flags", 0) or 0)
    if weight is None and not any("peso OS/2" in e for e in desc.evidence):
        fw = descriptor.get("FontWeight")
        stem = descriptor.get("StemV")
        if fw:
            desc.weight = int(float(fw))
        elif stem and float(stem) >= 120:
            desc.weight = 700
        elif flags & 262144:      # ForceBold
            desc.weight = 700
    if flags & 64 or abs(float(descriptor.get("ItalicAngle", 0) or 0)) > 1:
        desc.italic = True
    # clasificación: archivo > nombre > descriptor; por defecto sans
    key = family_key(desc.family) + family_key(name)
    if fixed or (panose is not None and panose.bFamilyType == 2 and panose.bProportion == 9) \
            or any(k in key for k in MONO_NAMES) or flags & 1:
        desc.kind = "mono"
    elif panose is not None and panose.bFamilyType == 2 and 11 <= panose.bSerifStyle <= 13:
        desc.kind = "sans"
        desc.evidence.append("panose: sin serifa")
    elif panose is not None and panose.bFamilyType == 2 and 2 <= panose.bSerifStyle <= 10:
        desc.kind = "serif"
        desc.evidence.append("panose: con serifa")
    elif family_class in (1, 2, 3, 4, 5, 7):
        desc.kind = "serif"
        desc.evidence.append(f"OS/2 sFamilyClass {family_class}: serifa")
    elif family_class == 8:
        desc.kind = "sans"
        desc.evidence.append("OS/2 sFamilyClass 8: sin serifa")
    elif family_class == 10 or "script" in key:
        desc.kind = "script"
    elif "sans" in key or any(k in key for k in GEOMETRIC_NAMES):
        desc.kind = "sans"
    elif any(k in key for k in SERIF_NAMES) or ("serif" in key and "sans" not in key):
        desc.kind = "serif"
    elif flags & 2 and not any(k in key for k in ("sans", "grotesk", "gothic")):
        desc.kind = "serif"
        desc.evidence.append("descriptor del PDF: serifa")
    desc.geometric = desc.kind == "sans" and any(k in key for k in GEOMETRIC_NAMES)
    return desc


# --------------------------------------------------------------------------- índice

@dataclass
class Face:
    path: str
    index: int
    family: str
    style: str
    weight: int
    italic: bool
    source: str                       # sistema | usuario | biblioteca
    wght: list | None = None          # [mín, máx] si es variable
    axes: dict | None = None          # valores por defecto de todos los ejes (variables)
    ps: str = ""


def _app_dir() -> Path:
    from core import paths

    return paths.data_dir()


def library_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "fonts" / "library"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent / "assets" / "fonts" / "library"


def font_dirs() -> list[tuple[Path, str]]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    local = os.environ.get("LOCALAPPDATA")
    dirs = [(windir, "sistema")]
    if local:
        dirs.append((Path(local) / "Microsoft" / "Windows" / "Fonts", "usuario"))
    dirs.append((library_dir(), "biblioteca"))
    return dirs


def _registry_user_fonts() -> list[Path]:
    """Fuentes instaladas por el usuario fuera de las carpetas habituales."""
    if sys.platform != "win32":
        return []
    import winreg

    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
            n = 0
            while True:
                try:
                    _label, value, _t = winreg.EnumValue(key, n)
                except OSError:
                    break
                n += 1
                if os.path.isabs(value):
                    out.append(Path(value))
    except OSError:
        pass
    return out


def _read_faces(path: Path, source: str) -> list[dict]:
    from fontTools.ttLib import TTCollection, TTFont

    faces = []
    try:
        if path.suffix.lower() == ".ttc":
            count = len(TTCollection(str(path), lazy=True).fonts)
        else:
            count = 1
        for index in range(count):
            font = TTFont(str(path), fontNumber=index, lazy=True)
            names = {r.nameID: r.toUnicode() for r in font["name"].names
                     if r.nameID in (1, 2, 6, 16, 17) and r.platformID in (3, 1)}
            family = names.get(16) or names.get(1) or path.stem
            style = names.get(17) or names.get(2) or "Regular"
            os2 = font["OS/2"] if "OS/2" in font else None
            weight = int(os2.usWeightClass) if os2 is not None else WEIGHT_WORDS.get(
                family_key(style).replace("italic", "") or "regular", 400)
            italic = bool(os2.fsSelection & 1) if os2 is not None else "italic" in style.lower()
            face = {"path": str(path), "index": index, "family": family, "style": style,
                    "weight": weight, "italic": italic, "source": source, "ps": names.get(6, "")}
            if "fvar" in font:
                axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
                face["axes"] = axes
                wght = next((a for a in font["fvar"].axes if a.axisTag == "wght"), None)
                if wght is not None:
                    face["wght"] = [wght.minValue, wght.maxValue]
            faces.append(face)
    except Exception as exc:
        log.debug("no se pudo leer %s: %s", path, exc)
    return faces


_INDEX: list[Face] | None = None
_INDEX_LOCK = threading.Lock()


def font_index(refresh: bool = False, extra_dirs: list[tuple[Path, str]] | None = None) -> list[Face]:
    """Todas las caras instaladas e incluidas (en caché en disco y en memoria)."""
    global _INDEX
    with _INDEX_LOCK:
        if _INDEX is not None and not refresh and not extra_dirs:
            return _INDEX
        cache_path = _app_dir() / "font_index.json"
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        except Exception:
            cache = {}
        files: list[tuple[Path, str]] = []
        for folder, source in list(font_dirs()) + list(extra_dirs or []):
            if folder.is_dir():
                files += [(p, source) for p in folder.rglob("*")
                          if p.suffix.lower() in (".ttf", ".otf", ".ttc")]
        known = {str(p) for p, _s in files}
        files += [(p, "usuario") for p in _registry_user_fonts() if p.exists() and str(p) not in known]
        faces, fresh = [], {}
        for path, source in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            stamp = [stat.st_mtime, stat.st_size, source]
            entry = cache.get(str(path))
            if entry and entry.get("stamp") == stamp:
                found = entry["faces"]
            else:
                found = _read_faces(path, source)
            fresh[str(path)] = {"stamp": stamp, "faces": found}
            faces += [Face(**f) for f in found]
        if not extra_dirs:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(fresh), encoding="utf-8")
            except OSError:
                pass
            _INDEX = faces
        log.info("índice de fuentes: %d caras (%s)", len(faces),
                 ", ".join(f"{s}: {sum(f.source == s for f in faces)}" for s in ("sistema", "usuario", "biblioteca")))
        return faces


# --------------------------------------------------------------------------- búsqueda

@dataclass
class Choice:
    face: Face
    weight: int
    italic: bool
    substitute: bool          # True = otra familia (requiere confirmación)
    reason: str

    @property
    def label(self) -> str:
        style = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "", 500: "Medium", 600: "SemiBold",
                 700: "Bold", 800: "ExtraBold", 900: "Black"}.get(round(self.weight / 100) * 100, "")
        style = (style + (" Italic" if self.italic else "")).strip()
        return f"{self.face.family} {style}".strip()


def _weight_ok(face: Face, weight: int, exact: bool) -> bool:
    if face.wght:
        return face.wght[0] <= weight <= face.wght[1]
    return face.weight == weight if exact else abs(face.weight - weight) <= 100


def _pick(faces: list[Face], family: str, weight: int, italic: bool, exact: bool = True):
    key = family_key(family)
    matches = [f for f in faces if family_key(f.family) == key
               or family_key(parse_name(f.ps)[0]) == key]
    matches = [f for f in matches if f.italic == italic and _weight_ok(f, weight, exact)]
    if not matches:
        return None
    order = {"sistema": 0, "usuario": 1, "biblioteca": 2}
    matches.sort(key=lambda f: (order.get(f.source, 3), 0 if f.wght else abs(f.weight - weight)))
    return matches[0]


def find_same(desc: FontDescription, faces: list[Face] | None = None) -> Choice | None:
    """La misma familia, peso y estilo, instalada o en la biblioteca."""
    faces = font_index() if faces is None else faces
    for family in dict.fromkeys([desc.family, parse_name(desc.name)[0]]):
        face = _pick(faces, family, desc.weight, desc.italic)
        if face is not None:
            choice = Choice(face, desc.weight, desc.italic, False,
                            f"misma familia ({face.source}): {face.path}")
            log.info("fuente %s %d%s -> %s", desc.name, desc.weight, " cursiva" if desc.italic else "",
                     choice.reason)
            return choice
    log.info("fuente %s %d%s: no está instalada ni en la biblioteca", desc.name, desc.weight,
             " cursiva" if desc.italic else "")
    return None


def find_similar(desc: FontDescription, faces: list[Face] | None = None) -> Choice | None:
    """Una fuente parecida por clasificación, con el mismo peso y estilo (nunca una serif
    para una sans ni al revés)."""
    faces = font_index() if faces is None else faces
    kind = "geometric" if desc.geometric else (desc.kind if desc.kind in SIMILAR else "sans")
    twins = METRIC_TWINS.get(family_key(desc.family), [])
    candidates = twins + SIMILAR[kind] + [f for f in SIMILAR["sans" if kind != "serif" else "serif"]
                                          if f not in SIMILAR[kind]]
    for exact in (True, False):
        for family in candidates:
            if family_key(family) == family_key(desc.family):
                continue
            face = _pick(faces, family, desc.weight, desc.italic, exact)
            if face is not None:
                weight = desc.weight if face.wght else face.weight
                choice = Choice(face, weight, desc.italic, True,
                                f"parecida ({kind}, {desc.kind}): {face.family}")
                log.info("fuente %s -> sustituta %s (%s)", desc.name, choice.label, choice.reason)
                return choice
    log.warning("fuente %s: no hay ninguna fuente parecida disponible", desc.name)
    return None


# --------------------------------------------------------------------------- archivos

_STATIC: dict[tuple, bytes] = {}
_STATIC_LOCK = threading.Lock()
# lo que se deja de cada fuente: latín completo, puntuación, monedas y símbolos comunes
BASE_CHARS = (set(range(0x20, 0x250)) | set(range(0x2000, 0x2070)) | set(range(0x20A0, 0x20C0))
              | set(range(0x2100, 0x2200)) | {0x2212, 0x2022, 0x25CF})


def static_buffer(choice: Choice, extra: str = "") -> bytes:
    """La fuente elegida lista para usar: recortada al latín (y a `extra`) conservando los
    números de glifo, sin tablas de composición (el PDF lleva los glifos ya elegidos) y,
    si es variable, fija en el peso pedido. En caché (memoria y disco)."""
    face = choice.face
    wanted = {ord(c) for c in extra} - BASE_CHARS
    key = (face.path, face.index, choice.weight, frozenset(wanted))
    with _STATIC_LOCK:
        if key in _STATIC:
            return _STATIC[key]
        import hashlib

        tag = hashlib.sha1(repr(("v3", face.path, face.index, choice.weight, sorted(wanted),
                                 os.path.getmtime(face.path))).encode()).hexdigest()[:16]
        cache = _app_dir() / "font_cache" / f"{family_key(face.family)}_{choice.weight}_{tag}.ttf"
        if cache.exists():
            _STATIC[key] = cache.read_bytes()
            return _STATIC[key]
        from fontTools import subset as ft_subset
        from fontTools.ttLib import TTFont

        logging.getLogger("fontTools").setLevel(logging.ERROR)
        font = TTFont(face.path, fontNumber=face.index)
        options = ft_subset.Options()
        options.retain_gids = True
        options.notdef_outline = True
        options.name_IDs = ["*"]
        options.layout_features = []
        options.drop_tables += ["GSUB", "GPOS", "GDEF", "kern", "DSIG", "STAT"]
        subsetter = ft_subset.Subsetter(options)
        subsetter.populate(unicodes=BASE_CHARS | wanted)
        subsetter.subset(font)
        if "fvar" in font:
            from fontTools.varLib import instancer

            location = dict(face.axes or {})
            if "wght" in location:
                location["wght"] = max(face.wght[0], min(face.wght[1], choice.weight))
            font = instancer.instantiateVariableFont(font, location)
            _name_instance(font, choice)
        out = BytesIO()
        font.save(out)
        _STATIC[key] = out.getvalue()
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(_STATIC[key])
        except OSError:
            pass
        log.info("fuente preparada: %s (%d bytes)", choice.label, len(_STATIC[key]))
        return _STATIC[key]


def _name_instance(font, choice: Choice) -> None:
    """Nombres y bits de estilo de una instancia fija ("Montserrat Bold"), para que el PDF
    y Windows la identifiquen igual que la original."""
    family = choice.face.family
    style = choice.label[len(family):].strip() or "Regular"
    ribbi = style in ("Regular", "Bold", "Italic", "Bold Italic")
    legacy_family = family if ribbi else f"{family} {style.replace(' Italic', '')}"
    legacy_style = style if ribbi else ("Italic" if choice.italic else "Regular")
    values = {1: legacy_family, 2: legacy_style, 4: f"{family} {style}".replace(" Regular", ""),
              6: f"{family}-{style}".replace(" ", ""), 16: family, 17: style}
    table = font["name"]
    for name_id in (1, 2, 3, 4, 6, 16, 17, 25):
        table.removeNames(nameID=name_id)
    for name_id, value in values.items():
        table.setName(value, name_id, 3, 1, 0x409)
        table.setName(value, name_id, 1, 0, 0)
    table.setName(f"{values[6]};Pliegue", 3, 3, 1, 0x409)
    if "OS/2" in font:
        os2 = font["OS/2"]
        os2.usWeightClass = int(choice.weight)
        bold = choice.weight >= 700
        os2.fsSelection = (os2.fsSelection & ~0b1100001) | (0b100000 if bold else 0) \
            | (1 if choice.italic else 0) | (0b1000000 if not bold and not choice.italic else 0)
    if "head" in font:
        font["head"].macStyle = (1 if choice.weight >= 700 else 0) | (2 if choice.italic else 0)


def display_file(choice: Choice) -> tuple[str, str]:
    """Archivo (en la carpeta temporal) y familia para mostrar la fuente en pantalla."""
    import tempfile

    data = static_buffer(choice)
    folder = Path(tempfile.gettempdir()) / "pliegue_fonts"
    folder.mkdir(exist_ok=True)
    name = f"{os.getpid()}_{family_key(choice.face.family)}_{choice.weight}{'i' if choice.italic else ''}.ttf"
    path = folder / name
    if not path.exists():
        path.write_bytes(data)
    return str(path), choice.face.family


def describe_dict(desc: FontDescription) -> dict:
    return asdict(desc)
