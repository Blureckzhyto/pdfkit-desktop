"""Pruebas del editor (v1.3.4): fuente completa para letras que faltan en un subconjunto.

Con una portada generada como la del caso real (Montserrat-Bold 14,14 pt incrustada como
subconjunto, dentro de un Form XObject: tests/fixtures.py) y con un PDF sintético con un subconjunto de Montserrat-Bold que solo
tiene mayúsculas."""
import os
import shutil
import sys
import tempfile
import traceback
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fitz
from PIL import ImageChops
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from core import font_finder, pdf_editor

TMP = Path(tempfile.mkdtemp(prefix="pdfkit_v134_"))
SHOTS = Path(__file__).parent / "_capturas" / "shots_v134"
SHOTS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(exist_ok=True)
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def run(name, fn):
    try:
        fn()
    except Exception as exc:
        traceback.print_exc()
        check(f"{name}: sin excepciones", False, repr(exc))


def spans_with(path, needle, page=0):
    out = []
    with fitz.open(path) as doc:
        for b in doc[page].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if needle in s["text"]:
                        out.append(s)
    return out


def chars_fonts(path, y_range, page=0):
    """Fuente de cada carácter dentro de una franja vertical."""
    out = []
    with fitz.open(path) as doc:
        for b in doc[page].get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    for ch in s["chars"]:
                        if y_range[0] <= ch["origin"][1] <= y_range[1]:
                            out.append((ch["c"], s["font"], round(s["size"], 2), s["color"], ch["origin"]))
    return out


def is_montserrat_bold(name):
    family, weight, _italic = font_finder.parse_name(name)
    return font_finder.family_key(family) == "montserrat" and weight == 700


def region(image, bbox, zoom, pad=4):
    x0, y0, x1, y1 = bbox
    return image.crop((int(x0 * zoom) - pad, int(y0 * zoom) - pad, int(x1 * zoom) + pad, int(y1 * zoom) + pad))


def same_pixels(a, b):
    return ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is None


# --------------------------------------------------------------- 1) archivo real
def test_real_file():
    import fixtures

    work = fixtures.portada(TMP / "portada.pdf")
    s = pdf_editor.EditorSession(work)
    line = next(l for l in s.analyze(0)["lines"] if "CARRERA" in l["text"])
    span = line["spans"][0]
    check("portada: la línea está en un formulario (Form XObject)",
          s._texts[0].op_of[span["gids"][0]].stream != "page")
    new = line["text"].replace("SISTEMAS", "Sistemas")
    state = {"overrides": {line["id"]: {"text": new}}, "added": [], "z": None}
    check("portada: no hace falta confirmar (Montserrat de la biblioteca es la misma familia)",
          s.pending_substitutions(0, state) == [])
    before_img, _l, _n = s.render_page(0, None, 3)
    after_img, layout, notes = s.render_page(0, state, 3)
    region(before_img, line["bbox"], 3, 8).save(SHOTS / "antes_linea_original.png")
    box = layout.get(line["id"], line["bbox"])
    region(after_img, [line["bbox"][0], line["bbox"][1], max(box[2], line["bbox"][2]), line["bbox"][3]],
           3, 8).save(SHOTS / "despues_linea_editada.png")
    out = TMP / "portada_editada.pdf"
    path, notes = s.save(out, {0: state}, list(range(s.page_count)), {})
    check("portada: se guarda sin pedir confirmación y sin avisos", not notes, str(notes))
    y = span["origin"][1]
    chars = chars_fonts(path, (y - 1, y + 1))
    text = "".join(c for c, *_ in chars)
    check("portada: el texto guardado es el editado", "Sistemas" in text and text.startswith("CARRERA"), text)
    check("portada: TODOS los caracteres de la línea son Montserrat Bold (nunca una serif)",
          chars and all(is_montserrat_bold(f) for _c, f, *_ in chars),
          str(sorted({f for _c, f, *_ in chars})))
    check("portada: mismo tamaño (14,14), color y línea base",
          all(abs(sz - 14.14) < 0.01 and col == span_color(span) and abs(o[1] - y) < 0.01
              for _c, _f, sz, col, o in chars), str(chars[:2]))
    first = next(c for c in chars if c[0] == "C")
    check("portada: la línea empieza en la misma x", abs(first[4][0] - span["origin"][0]) < 0.01)
    # lo que no cambió queda idéntico (mismos píxeles) a la izquierda de "Sistemas"
    with fitz.open(path) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
    from PIL import Image
    saved = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    sis_x = next(o[0] for c, _f, _s, _c2, o in chars if c == "S" and o[0] > 150)
    prefix_box = [line["bbox"][0], line["bbox"][1], sis_x - 1, line["bbox"][3]]
    check("portada: «CARRERA: INGENIERÍA EN » queda intacto (mismos píxeles)",
          same_pixels(region(before_img, prefix_box, 3, 0), region(saved, prefix_box, 3, 0)))
    check("portada: la vista previa es igual al guardado",
          same_pixels(region(after_img, line["bbox"], 3, 0), region(saved, line["bbox"], 3, 0)))
    # entrar y salir sin cambios no toca la página
    out2 = TMP / "portada_sin_cambios.pdf"
    s.save(out2, {0: {"overrides": {line["id"]: {"text": line["text"]}}, "added": [], "z": None}},
           list(range(s.page_count)), {})
    with fitz.open(work) as a, fitz.open(out2) as b:
        check("portada: editar sin cambios deja la página igual", a[0].read_contents() == b[0].read_contents()
              and a[0].get_text() == b[0].get_text())
    s.close()


def span_color(span):
    return int(span["color"].lstrip("#"), 16)


# --------------------------------------------------------------- 2) subconjunto sintético
def montserrat_bold_file():
    face = font_finder.find_same(font_finder.describe("Montserrat-Bold"))
    data = font_finder.static_buffer(face)
    path = TMP / "Montserrat-Bold.ttf"
    path.write_bytes(data)
    return path


def make_synthetic():
    pdfmetrics.registerFont(TTFont("Montserrat-Bold", str(montserrat_bold_file())))
    path = TMP / "mayusculas.pdf"
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setFillColorRGB(0.1, 0.2, 0.45)
    c.setFont("Montserrat-Bold", 14.14)
    c.drawString(60, 700, "CARRERA: INGENIERIA EN SISTEMAS COMPUTACIONALES")
    c.save()
    return path


def test_synthetic_found():
    path = make_synthetic()
    s = pdf_editor.EditorSession(path)
    line = s.analyze(0)["lines"][0]
    info = s._span_font(s._texts[0], line["spans"][0])
    check("sintético: subconjunto sin minúsculas", info.subset and info.code_for("i") is None,
          info.basefont)
    new = line["text"].replace("SISTEMAS", "Sistemas")
    state = {"overrides": {line["id"]: {"text": new}}, "added": [], "z": None}
    out = TMP / "mayusculas_editado.pdf"
    _p, notes = s.save(out, {0: state}, [0], {})
    span0 = line["spans"][0]
    chars = chars_fonts(out, (span0["origin"][1] - 1, span0["origin"][1] + 1))
    check("sintético: con Montserrat en la biblioteca, todo sale Montserrat Bold sin diálogo",
          not notes and chars and all(is_montserrat_bold(f) for _c, f, *_ in chars),
          str(sorted({f for _c, f, *_ in chars})))
    check("sintético: mismo tamaño, color y línea base",
          all(abs(sz - 14.14) < 0.01 and col == span_color(span0) and abs(o[1] - span0["origin"][1]) < 0.01
              for _c, _f, sz, col, o in chars))
    s.close()


def test_synthetic_missing_library():
    path = TMP / "mayusculas.pdf"
    real_index = font_finder.font_index()
    font_finder._INDEX = [f for f in real_index if font_finder.family_key(f.family) != "montserrat"]
    try:
        s = pdf_editor.EditorSession(path)
        line = s.analyze(0)["lines"][0]
        new = line["text"].replace("SISTEMAS", "Sistemas")
        state = {"overrides": {line["id"]: {"text": new}}, "added": [], "z": None}
        pending = s.pending_substitutions(0, state)
        check("sin Montserrat: se pide confirmación", len(pending) == 1, str(pending))
        if pending:
            sub = pending[0]["substitute"]
            desc = font_finder.describe(sub)
            check("sin Montserrat: la parecida ofrecida es una sans negrita (nunca serif)",
                  desc.kind == "sans" and desc.weight == 700 and "times" not in sub.lower(), sub)
            check("sin Montserrat: el diálogo tiene la muestra de las dos fuentes",
                  pending[0]["substitute_display"] is not None)
        before, _l, _n = s.render_page(0, None, 3)
        preview, _l, _n = s.render_page(0, state, 3)
        check("sin Montserrat: la vista previa sigue mostrando el original hasta responder",
              same_pixels(region(before, line["bbox"], 3), region(preview, line["bbox"], 3)))
        try:
            s.save(TMP / "x.pdf", {0: state}, [0], {})
            check("sin Montserrat: guardar pide confirmación", False)
        except pdf_editor.SubstitutionNeeded:
            check("sin Montserrat: guardar pide confirmación", True)
        if pending:
            state["overrides"][line["id"]]["font_ok"] = pending[0]["substitute"]
            accepted, _l, _n = s.render_page(0, state, 3)
            check("aceptada: la vista previa muestra la sustituta",
                  not same_pixels(region(before, line["bbox"], 3), region(accepted, line["bbox"], 3)))
            out = TMP / "mayusculas_sustituta.pdf"
            _p, notes = s.save(out, {0: state}, [0], {})
            y = line["spans"][0]["origin"][1]
            fonts = {f for _c, f, *_ in chars_fonts(out, (y - 1, y + 1))}
            check("aceptada: se guarda con la sustituta solo donde hace falta",
                  any(font_finder.family_key(sub.split()[0]) in font_finder.family_key(f) for f in fonts)
                  and notes, f"{fonts} {notes}")
        s.close()
    finally:
        font_finder._INDEX = real_index


# --------------------------------------------------------------- 3) carpeta de fuentes del usuario
def test_user_folder():
    from fontTools.ttLib import TTFont as FT

    fake = TMP / "localappdata"
    folder = fake / "Microsoft" / "Windows" / "Fonts"
    folder.mkdir(parents=True)
    font = FT(str(Path(font_finder.library_dir()) / "Lato" / "Lato-Bold.ttf"))
    for record in font["name"].names:
        if record.nameID in (1, 4, 16):
            record.string = record.toUnicode().replace("Lato", "Pdfkit Prueba")
        if record.nameID == 6:
            record.string = record.toUnicode().replace("Lato", "PdfkitPrueba")
    font.save(str(folder / "PdfkitPrueba-Bold.ttf"))
    old = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(fake)
    try:
        faces = font_finder.font_index(refresh=True)
        choice = font_finder.find_same(font_finder.describe("ABCDEF+PdfkitPrueba-Bold"), faces)
        check("se encuentra una fuente instalada solo en la carpeta del usuario",
              choice is not None and choice.face.source == "usuario" and not choice.substitute,
              choice and choice.reason)
    finally:
        if old is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old
        font_finder._INDEX = None
        font_finder.font_index()


# --------------------------------------------------------------- 4) clasificación
def test_classification():
    for name, kind, weight in (("Montserrat-Bold", "sans", 700), ("TimesNewRomanPS-BoldMT", "serif", 700),
                               ("Helvetica", "sans", 400), ("CourierNewPSMT", "mono", 400),
                               ("ABCDEF+Garamond-Italic", "serif", 400), ("Poppins-SemiBold", "sans", 600)):
        d = font_finder.describe(name)
        check(f"clasificación {name}: {kind} {weight}", d.kind == kind and d.weight == weight,
              f"{d.kind} {d.weight}")
    d = font_finder.describe("LeagueSpartan-Bold")
    sim = font_finder.find_similar(d)
    check("una geométrica sin instalar se sustituye por otra geométrica sans negrita",
          sim and sim.face.family in ("Poppins", "DM Sans", "Montserrat") and sim.weight == 700,
          sim and sim.label)


for name, fn in (("archivo real", test_real_file), ("subconjunto sintético", test_synthetic_found),
                 ("sin la familia", test_synthetic_missing_library), ("carpeta del usuario", test_user_folder),
                 ("clasificación", test_classification)):
    run(name, fn)
print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK — {TMP}")
sys.exit(0 if results and all(results) else 1)
