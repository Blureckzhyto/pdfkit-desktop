"""Pruebas del editor (v1.3.2): el texto editado conserva exactamente su fuente.

Casos: fuente estándar (Helvetica / Times), TrueType completa incrustada, subconjunto
(simple y CID) y línea con fuentes mezcladas (normal + negrita + otro color)."""
import re
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fitz
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from core import font_finder, pdf_editor, pdf_textops

TMP = Path(tempfile.mkdtemp(prefix="pdfkit_v132_"))
WIN = Path(r"C:\Windows\Fonts")
JAKARTA = Path(Path(__file__).resolve().parent.parent / "assets" / "fonts"
               r"\PlusJakartaSans-Regular.ttf")
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


# --------------------------------------------------------------- PDFs de prueba
def make_standard(path):
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setFont("Helvetica", 14)
    c.drawString(72, 760, "Hola mundo con Helvetica estandar")
    c.setFont("Times-Roman", 16.5)
    c.drawString(72, 720, "Texto en Times Roman para editar")
    c.save()


def make_full_truetype(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="F0", fontfile=str(WIN / "georgia.ttf"))
    page.insert_text((72, 90), "Georgia completa incrustada aqui", fontname="F0", fontsize=15,
                     color=(0.1, 0.2, 0.5))
    doc.save(str(path))


def make_subset(path, font_file, name, text, size=13):
    pdfmetrics.registerFont(TTFont(name, str(font_file)))
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setFont(name, size)
    c.drawString(72, 760, text)
    c.save()


def make_subset_cid(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="F0", fontfile=str(WIN / "calibri.ttf"))
    page.insert_text((72, 90), "Reporte trimestral de ventas", fontname="F0", fontsize=12.37)
    doc.subset_fonts()
    doc.save(str(path))


def make_mixed(path):
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    t = c.beginText(72, 760)
    t.setFont("Helvetica", 14)
    t.textOut("Total a pagar: ")
    t.setFont("Helvetica-Bold", 14)
    t.textOut("1500 pesos ")
    t.setFont("Times-Italic", 14)
    t.setFillColor(HexColor("#C0392B"))
    t.textOut("antes del viernes")
    c.drawText(t)
    c.save()


FIXTURES = {
    "estandar": TMP / "estandar.pdf", "truetype_completa": TMP / "truetype_completa.pdf",
    "subconjunto": TMP / "subconjunto.pdf", "subconjunto_cid": TMP / "subconjunto_cid.pdf",
    "mixta": TMP / "mixta.pdf", "subconjunto_no_instalada": TMP / "jakarta.pdf",
}
make_standard(FIXTURES["estandar"])
make_full_truetype(FIXTURES["truetype_completa"])
make_subset(FIXTURES["subconjunto"], WIN / "verdana.ttf", "Verdana", "Factura numero 2024 del cliente")
make_subset_cid(FIXTURES["subconjunto_cid"])
make_mixed(FIXTURES["mixta"])
make_subset(FIXTURES["subconjunto_no_instalada"], JAKARTA, "Jakarta", "Plan de trabajo anual", 15)


# --------------------------------------------------------------- utilidades
def spans(path, page=0):
    out = []
    with fitz.open(path) as doc:
        for b in doc[page].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if s["text"].strip():
                        out.append({"font": pdf_textops.clean_name(s["font"]), "size": s["size"],
                                    "color": s["color"], "origin": tuple(s["origin"]),
                                    "text": s["text"].replace("\xa0", " "), "bbox": tuple(s["bbox"])})
    return out


def content(path):
    with fitz.open(path) as doc:
        return doc[0].read_contents()


def save(session, state, name, allow=False):
    out = TMP / f"{name}.pdf"
    path, notes = session.save(out, {0: state}, list(range(session.page_count)), {},
                               allow_substitution=allow)
    return path, notes


def state(overrides):
    return {"overrides": overrides, "added": [], "z": None}


def same_span(a, b, tol=1e-3):
    """Mismo texto, fuente, tamaño, color y posición (con tolerancia de punto flotante)."""
    return (a["text"] == b["text"] and a["font"] == b["font"] and abs(a["size"] - b["size"]) < 1e-4
            and a["color"] == b["color"] and abs(a["origin"][0] - b["origin"][0]) < tol
            and abs(a["origin"][1] - b["origin"][1]) < tol)


def same_style(a, b, tol=0.01):
    return (a["font"] == b["font"] and abs(a["size"] - b["size"]) < 1e-3 and a["color"] == b["color"]
            and abs(a["origin"][1] - b["origin"][1]) < tol)


def edit_word(text, index=-1, replacement=None):
    words = text.split(" ")
    words[index] = replacement if replacement is not None else words[index].upper()[::-1]
    return " ".join(words)


def run(name, fn):
    try:
        fn()
    except Exception as exc:
        traceback.print_exc()
        check(f"{name}: sin excepciones", False, repr(exc))


# --------------------------------------------------------------- 1) entrar y salir sin cambios
def test_no_change():
    for key, path in FIXTURES.items():
        s = pdf_editor.EditorSession(path)
        model = s.analyze(0)
        line = model["lines"][0]
        out, _notes = save(s, state({line["id"]: {"text": line["text"]}}), f"{key}_sin_cambios")
        check(f"{key}: entrar y salir sin cambios no toca el contenido", content(out) == content(path))
        check(f"{key}: mismas fuentes, textos y posiciones", spans(out) == spans(path))
        check(f"{key}: el tamaño no se redondea", line["style"]["size"] == spans(path)[0]["size"],
              f"{line['style']['size']!r}")
        s.close()


# --------------------------------------------------------------- 2) cambiar una palabra
def test_change_word():
    for key in ("estandar", "truetype_completa", "subconjunto", "subconjunto_cid"):
        path = FIXTURES[key]
        s = pdf_editor.EditorSession(path)
        line = s.analyze(0)["lines"][0]
        new_text = edit_word(line["text"].replace("\xa0", " "), -1, "listo")
        out, notes = save(s, state({line["id"]: {"text": new_text}}), f"{key}_palabra")
        before, after = spans(path), spans(out)
        changed = [a for a in after if "listo" in a["text"]]
        check(f"{key}: la palabra cambió", changed and changed[0]["text"].strip().endswith("listo"),
              str([a["text"] for a in after]))
        if changed:
            check(f"{key}: misma fuente, tamaño, color y línea base",
                  same_style(changed[0], before[0]),
                  f"{before[0]['font']} {before[0]['size']} → {changed[0]['font']} {changed[0]['size']}")
            check(f"{key}: empieza en la misma posición",
                  abs(changed[0]["origin"][0] - before[0]["origin"][0]) < 0.05)
        check(f"{key}: sin avisos de sustitución", not notes, str(notes))
        rest_before = [b for b in before if b["origin"][1] != before[0]["origin"][1]]
        rest_after = [a for a in after if a["origin"][1] != before[0]["origin"][1]]
        check(f"{key}: las otras líneas quedan idénticas", rest_before == rest_after)
        s.close()


def test_mixed_line():
    path = FIXTURES["mixta"]
    s = pdf_editor.EditorSession(path)
    line = s.analyze(0)["lines"][0]
    check("mixta: la línea tiene 3 fragmentos con sus fuentes",
          [sp["font"] for sp in line["spans"]] == ["Helvetica", "Helvetica-Bold", "Times-Italic"])
    out, notes = save(s, state({line["id"]: {"text": line["text"].replace("viernes", "lunes")}}),
                      "mixta_palabra")
    before, after = spans(path), spans(out)
    check("mixta: solo cambia el fragmento editado",
          same_span(after[0], before[0]) and same_span(after[1], before[1]),
          str([a["text"] for a in after]))
    check("mixta: el fragmento editado conserva Times-Italic, 14 pt y el rojo",
          len(after) == 3 and after[2]["text"] == "antes del lunes" and same_style(after[2], before[2]),
          str(after[2:]))
    check("mixta: el fragmento editado empieza donde estaba",
          len(after) == 3 and abs(after[2]["origin"][0] - before[2]["origin"][0]) < 0.05)
    # editar la negrita no toca los otros dos
    out2, _ = save(s, state({line["id"]: {"text": line["text"].replace("1500", "2750")}}), "mixta_negrita")
    after2 = spans(out2)
    check("mixta: editar la negrita conserva Helvetica-Bold y no toca los vecinos",
          same_span(after2[0], before[0]) and same_span(after2[2], before[2])
          and after2[1]["text"] == "2750 pesos "
          and same_style(after2[1], before[1]), str(after2))
    # contenido: los operadores de los fragmentos intactos siguen ahí tal cual
    raw = content(out2)
    check("mixta: el texto intacto sigue en su operador original",
          b"(Total a pagar: ) Tj" in raw.replace(b"\n", b" ") or b"(Total a pagar: )" in raw)
    s.close()


# --------------------------------------------------------------- 3) carácter que falta en el subconjunto
def test_missing_glyph():
    for key, char, family in (("subconjunto", "é", "Verdana"), ("subconjunto_cid", "ñ", "Calibri")):
        path = FIXTURES[key]
        s = pdf_editor.EditorSession(path)
        line = s.analyze(0)["lines"][0]
        font = s._span_font(s._texts[0], line["spans"][0])
        check(f"{key}: el subconjunto no tiene '{char}'", font.code_for(char) is None)
        new_text = edit_word(line["text"].replace("\xa0", " "), 0, f"Añ{char}o")
        out, notes = save(s, state({line["id"]: {"text": new_text}}), f"{key}_falta")
        after = spans(out)
        new_span = next((a for a in after if char in a["text"]), None)
        check(f"{key}: se usa la versión completa instalada de {family}",
              new_span is not None and family.lower() in new_span["font"].lower().replace(" ", ""),
              str(new_span))
        check(f"{key}: sin pedir confirmación (es la misma fuente)", not notes, str(notes))
        if new_span:
            check(f"{key}: mismo tamaño y línea base", abs(new_span["size"] - spans(path)[0]["size"]) < 1e-3
                  and abs(new_span["origin"][1] - spans(path)[0]["origin"][1]) < 0.01)
        s.close()
    # fuentes que no están instaladas: se pide confirmación y nada se sustituye sin ella
    cases = [("subconjunto_no_instalada", "ß")] if font_finder.find_same(font_finder.describe("PlusJakartaSans-Regular")) is None \
        else []
    cases.append(("estandar", "Ω"))
    for key, char in cases:
        path = FIXTURES[key]
        s = pdf_editor.EditorSession(path)
        line = s.analyze(0)["lines"][0]
        new_text = line["text"] + f" {char}"
        try:
            save(s, state({line["id"]: {"text": new_text}}), f"{key}_sin_confirmar")
            check(f"{key}: pide confirmación antes de sustituir", False, "guardó sin preguntar")
        except pdf_editor.SubstitutionNeeded as exc:
            item = exc.items[0]
            check(f"{key}: pide confirmación antes de sustituir",
                  char in item["missing"] and item["substitute"], str(item))
            check(f"{key}: no se escribió ningún archivo", not (TMP / f"{key}_sin_confirmar.pdf").exists())
        out, notes = save(s, state({line["id"]: {"text": new_text}}), f"{key}_confirmado", allow=True)
        after = spans(out)
        check(f"{key}: con confirmación se usa la fuente parecida y se avisa",
              any(char in a["text"] for a in after) and notes, str(notes))
        note = s.font_note(0, line["id"], new_text)
        check(f"{key}: la barra de propiedades lo anticipa", "no incluye" in note, note)
        s.close()


# --------------------------------------------------------------- 4) mover sin editar
def test_move():
    for key, path in FIXTURES.items():
        s = pdf_editor.EditorSession(path)
        line = s.analyze(0)["lines"][0]
        out, notes = save(s, state({line["id"]: {"dx": 30, "dy": 20}}), f"{key}_movido")
        before = [b for b in spans(path) if abs(b["origin"][1] - spans(path)[0]["origin"][1]) < 0.5]
        after = spans(out)
        moved = [a for a in after if abs(a["origin"][1] - (before[0]["origin"][1] + 20)) < 0.05]
        ok = len(moved) == len(before) and all(
            m["font"] == b["font"] and abs(m["size"] - b["size"]) < 1e-3 and m["color"] == b["color"]
            and m["text"] == b["text"] and abs(m["origin"][0] - b["origin"][0] - 30) < 0.05
            for m, b in zip(moved, before))
        check(f"{key}: mover conserva fuente y tamaño (solo cambia la posición)", ok,
              f"{[(b['font'], b['origin']) for b in before]} → {[(m['font'], m['origin']) for m in moved]}")
        check(f"{key}: mover no avisa sustituciones", not notes, str(notes))
        s.close()


# --------------------------------------------------------------- 5) borrar y párrafo
def test_delete_and_block():
    path = FIXTURES["estandar"]
    s = pdf_editor.EditorSession(path)
    model = s.analyze(0)
    first, second = model["lines"][0], model["lines"][1]
    out, _ = save(s, state({first["id"]: {"deleted": True}}), "estandar_borrado")
    after = spans(out)
    check("borrar una línea quita solo esa línea", [a["text"] for a in after] == [second["text"]]
          and after[0] == spans(path)[1])
    s.close()
    path = FIXTURES["mixta"]
    s = pdf_editor.EditorSession(path)
    block = s.analyze(0)["blocks"][0]
    out, _ = save(s, state({block["id"]: {"text": block["text"].replace("viernes", "jueves")}}),
                  "mixta_parrafo")
    after, before = spans(out), spans(path)
    check("párrafo: un cambio sin reacomodar líneas edita solo ese fragmento",
          same_span(after[0], before[0]) and same_span(after[1], before[1])
          and after[2]["text"] == "antes del jueves" and same_style(after[2], before[2]),
          str(after))
    s.close()


for name, fn in (("sin cambios", test_no_change), ("palabra", test_change_word),
                 ("línea mixta", test_mixed_line), ("glifo faltante", test_missing_glyph),
                 ("mover", test_move), ("borrar y párrafo", test_delete_and_block)):
    run(name, fn)

print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK — {TMP}")
sys.exit(0 if results and all(results) else 1)
