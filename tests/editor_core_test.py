"""Pruebas del núcleo del editor real (core/pdf_editor.py) con PDFs reales."""
import sys
import tempfile
import traceback
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import Color, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from core.pdf_editor import EditorSession

TMP = Path(tempfile.mkdtemp(prefix="pliegue_editor_"))
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def run(name, fn):
    print(f"\n[{name}]")
    try:
        fn()
    except Exception:
        results.append(False)
        print(f"  FAIL  {name}: excepción")
        traceback.print_exc()


# ------------------------------------------------------------------ PDF de prueba
pdfmetrics.registerFont(TTFont("ArialTT", r"C:\Windows\Fonts\arial.ttf"))  # se incrusta como subconjunto
src = TMP / "fuentes.pdf"
logo = TMP / "logo.png"
Image.new("RGB", (120, 80), (30, 136, 229)).save(logo)
c = canvas.Canvas(str(src), pagesize=(595, 842))
c.setFillColor(HexColor("#FFE9A8"))
c.rect(60, 690, 300, 40, stroke=0, fill=1)                 # fondo vectorial bajo el texto
c.setFillColor(HexColor("#1F4E9E"))
c.setFont("ArialTT", 16)
c.drawString(72, 704, "Hola mundo cruel")                 # baseline y = 842-704 = 138
c.setFillColor(HexColor("#222222"))
c.setFont("Times-Roman", 12)
c.drawString(72, 650, "Linea en Times Roman")
c.drawString(72, 636, "Segunda linea muy cerca")          # líneas a 14 pt
c.setFont("Courier", 11)
c.drawString(72, 600, "Texto monoespaciado")
c.drawImage(str(logo), 380, 560, 120, 80)
c.setFont("ArialTT", 12)
c.drawString(72, 520, "Parrafo para mover")
c.showPage()
c.save()


def find_unit(model, text, level="line"):
    pool = model["lines"] if level == "line" else model["blocks"]
    return next(u for u in pool if text in u["text"])


def span_of(page, text):
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if text in span["text"]:
                    return span
    return None


def t_detect():
    s = EditorSession(src)
    m = s.analyze(0)
    line = find_unit(m, "Hola mundo cruel")
    st = line["style"]
    check("detecta líneas y estilo", abs(st["size"] - 16) < 0.1 and st["color"] == "#1F4E9E",
          f"{st['font']} {st['size']} {st['color']}")
    check("detecta la fuente incrustada (xref)", st["font_xref"] > 0, str(st["font_xref"]))
    check("línea base detectada", abs(line["lines"][0]["origin"][1] - 138) < 0.5,
          str(line["lines"][0]["origin"]))
    check("detecta la imagen", len(m["images"]) == 1 and m["images"][0]["movable"])
    times = find_unit(m, "Linea en Times")["style"]
    check("familia por nombre (Times → Times New Roman)", times["family"] == "Times New Roman", times["font"])
    check("familia monoespaciada", find_unit(m, "monoespaciado")["style"]["family"] == "Courier New")
    s.close()


def t_edit_word():
    s = EditorSession(src)
    m = s.analyze(0)
    line = find_unit(m, "Hola mundo cruel")
    out = TMP / "editado.pdf"
    state = {0: {"overrides": {line["id"]: {"text": "Hola mundo lunar"}}, "added": [], "z": None}}  # solo letras del subconjunto
    _p, notes = s.save(out, state, [0], {})
    doc = fitz.open(out)
    page = doc[0]
    text = page.get_text()
    span = span_of(page, "lunar")
    check("texto nuevo presente y viejo ausente", "Hola mundo lunar" in text and "cruel" not in text, repr(text[:40]))
    check("tamaño ±0.5 pt", span and abs(span["size"] - 16) <= 0.5, f"{span and span['size']}")
    check("línea base ±1 pt", span and abs(span["origin"][1] - 138) <= 1, f"{span and span['origin']}")
    check("color idéntico", span and f"#{span['color']:06X}" == "#1F4E9E", f"{span and hex(span['color'])}")
    check("subconjunto sin mapa Unicode (ReportLab): misma familia de Windows", all("ArialMT → Arial" in n for n in notes), str(notes))
    check("el resto del texto queda intacto",
          all(t in text for t in ("Linea en Times Roman", "Segunda linea muy cerca", "Texto monoespaciado",
                                  "Parrafo para mover")))
    check("la imagen queda intacta", len(page.get_image_info()) == 1
          and [round(v) for v in page.get_image_info()[0]["bbox"]] == [380, 202, 500, 282])
    fills = [d for d in page.get_drawings() if d.get("fill") and abs(d["fill"][0] - 1.0) < 0.01
             and abs(d["fill"][1] - 0.913) < 0.02]
    check("el fondo vectorial bajo el texto queda intacto", len(fills) == 1)
    doc.close()
    s.close()


def t_neighbors():
    s = EditorSession(src)
    m = s.analyze(0)
    first = find_unit(m, "Linea en Times")
    out = TMP / "vecinas.pdf"
    s.save(out, {0: {"overrides": {first["id"]: {"text": "Linea cambiada"}}, "added": [], "z": None}}, [0], {})
    text = fitz.open(out)[0].get_text()
    check("editar una línea no toca la vecina (14 pt)", "Linea cambiada" in text
          and "Segunda linea muy cerca" in text and "Linea en Times" not in text, repr(text[:80]))
    s.close()


def t_missing_glyph():
    s = EditorSession(src)
    m = s.analyze(0)
    line = find_unit(m, "Hola mundo cruel")
    new_text = "Hola mundo Ωmega"       # Ω no está en el subconjunto incrustado
    report = s.font_note(0, line["id"], new_text)
    out = TMP / "sustitucion.pdf"
    _p, notes = s.save(out, {0: {"overrides": {line["id"]: {"text": new_text}}, "added": [], "z": None}},
                       [0], {})
    page = fitz.open(out)[0]
    span = span_of(page, "mega")
    check("glifo faltante: usa otra fuente", "Ωmega" in page.get_text() and span is not None)
    # v1.3.2: el subconjunto de Arial no tiene Ω, pero Arial completa está instalada: es la
    # misma fuente, así que se usa sin pedir confirmación (y la barra lo anticipa)
    check("glifo faltante: usa la versión completa de la misma fuente, sin sustituir",
          span and "arial" in span["font"].lower() and not notes and "las letras nuevas usan Arial" in report,
          f"{span and span['font']} | {report} | {notes}")
    check("la sustitución conserva tamaño y color", span and abs(span["size"] - 16) <= 0.5
          and f"#{span['color']:06X}" == "#1F4E9E")
    s.close()


def t_move():
    s = EditorSession(src)
    m = s.analyze(0)
    line = find_unit(m, "Parrafo para mover")
    image = m["images"][0]
    out = TMP / "movido.pdf"
    state = {0: {"overrides": {line["id"]: {"dx": 200, "dy": 40},
                               image["id"]: {"bbox": [100, 400, 220, 480]}}, "added": [], "z": None}}
    s.save(out, state, [0], {})
    page = fitz.open(out)[0]
    span = span_of(page, "Parrafo para mover")
    text = page.get_text()
    check("texto movido a la nueva posición", span and abs(span["origin"][0] - 272) < 1
          and abs(span["origin"][1] - (842 - 520 + 40)) < 1, f"{span and span['origin']}")
    check("texto movido sin duplicar", text.count("Parrafo para mover") == 1)
    info = page.get_image_info()
    check("imagen movida sin duplicar", len(info) == 1
          and [round(v) for v in info[0]["bbox"]] == [100, 400, 220, 480], str([i["bbox"] for i in info]))
    s.close()


def t_layers():
    s = EditorSession(src)
    m = s.analyze(0)
    line = find_unit(m, "Parrafo para mover")
    added = {"id": "N1", "kind": "image", "path": str(logo), "bbox": [60, 300, 260, 340]}
    order = s.default_order(m, {"added": [added]})
    order.remove("N1")
    order.insert(order.index(line["id"]), "N1")       # imagen nueva detrás del texto
    state = {0: {"overrides": {}, "added": [added], "z": order}}
    out = TMP / "capas.pdf"
    s.save(out, state, [0], {})
    page = fitz.open(out)[0]
    log = page.get_bboxlog()
    kinds = [k for k, bbox in log if fitz.Rect(bbox).intersects(fitz.Rect(60, 300, 260, 340))]
    first_image = next(i for i, k in enumerate(kinds) if "image" in k)
    first_text = next(i for i, k in enumerate(kinds) if "text" in k)
    check("capas: la imagen enviada atrás se dibuja antes que el texto", first_image < first_text,
          str(kinds))
    order2 = s.default_order(m, {"added": [added]})   # por defecto: imagen arriba de todo
    s.save(TMP / "capas2.pdf", {0: {"overrides": {}, "added": [added], "z": order2}}, [0], {})
    kinds2 = [k for k, bbox in fitz.open(TMP / "capas2.pdf")[0].get_bboxlog()
              if fitz.Rect(bbox).intersects(fitz.Rect(60, 300, 260, 340))]
    check("capas: traer al frente dibuja la imagen después del texto",
          max(i for i, k in enumerate(kinds2) if "image" in k) > max(i for i, k in enumerate(kinds2) if "text" in k),
          str(kinds2))
    s.close()


def t_ocr():
    scan = TMP / "escaneo.pdf"
    img = Image.new("RGB", (1654, 2339), "white")      # A4 a 200 ppp
    d = ImageDraw.Draw(img)
    arial = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 50)      # 50 px a 200 ppp = 18 pt
    times = ImageFont.truetype(r"C:\Windows\Fonts\times.ttf", 50)
    d.text((200, 300), "Contrato de servicios", fill=(20, 40, 120), font=arial)
    d.text((200, 500), "Firmado en Buenos Aires", fill=(0, 0, 0), font=times)
    buf = BytesIO()
    img.save(buf, "PNG", dpi=(200, 200))
    import img2pdf
    scan.write_bytes(img2pdf.convert(buf.getvalue()))
    s = EditorSession(scan)
    m = s.analyze(0, ocr_lang="spa")
    texts = [l["text"] for l in m["lines"]]
    check("OCR: página marcada como escaneada", m["ocr"])
    check("OCR: líneas detectadas coinciden", "Contrato de servicios" in texts and "Firmado en Buenos Aires" in texts,
          str(texts))
    a = next(l for l in m["lines"] if l["text"].startswith("Contrato"))
    t = next(l for l in m["lines"] if l["text"].startswith("Firmado"))
    check("OCR: tamaño estimado ≈ 18 pt", abs(a["style"]["size"] - 18) <= 2, str(a["style"]["size"]))
    check("OCR: color del texto estimado", a["style"]["color"] not in ("#FFFFFF",)
          and int(a["style"]["color"][5:7], 16) > int(a["style"]["color"][1:3], 16), a["style"]["color"])
    check("OCR: fondo blanco", a["bg"] in ("#FFFFFF", "#FEFEFE", "#FDFDFD"), a["bg"])
    check("OCR: heurística serif/sans", not a["style"]["serif"] and t["style"]["serif"],
          f"{a['style']['family']} / {t['style']['family']}")
    out = TMP / "ocr_editado.pdf"
    s.save(out, {0: {"overrides": {a["id"]: {"text": "Contrato"}}, "added": [], "z": None}}, [0], {})
    page = fitz.open(out)[0]
    span = span_of(page, "Contrato")
    check("OCR: edición escrita como texto real", span is not None and abs(span["size"] - a["style"]["size"]) < 0.5)
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
    old = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    # donde estaba la palabra "servicios" (a la derecha) ahora no hay tinta azul
    region = old.crop((int(a["bbox"][0] + 95), int(a["bbox"][1]), int(a["bbox"][2]), int(a["bbox"][3])))
    blue = sum(1 for p in region.getdata() if p[2] > 90 and p[0] < 80)
    check("OCR: el texto original quedó tapado con el color de fondo", blue < 15, f"{blue} px azules")
    s.close()


def t_rotated_source():
    from pypdf import PdfReader, PdfWriter
    rot = TMP / "rotada.pdf"
    w = PdfWriter(clone_from=PdfReader(str(src)))
    w.pages[0].rotate(90)
    w.write(str(rot))
    s = EditorSession(rot)
    m = s.analyze(0)
    line = find_unit(m, "Hola mundo cruel")
    out = TMP / "rotada_editada.pdf"
    s.save(out, {0: {"overrides": {line["id"]: {"text": "Hola mundo feliz"}}, "added": [], "z": None}}, [0], {})
    text = fitz.open(out)[0].get_text()
    check("página con /Rotate: se edita en la orientación visible", "feliz" in text and "cruel" not in text)
    s.close()


def t_page_ops():
    s = EditorSession(src)
    from reportlab.pdfgen import canvas as c2
    multi = TMP / "multi.pdf"
    cc = c2.Canvas(str(multi))
    for i in range(3):
        cc.drawString(72, 700, f"PAG{i + 1}")
        cc.showPage()
    cc.save()
    s = EditorSession(multi)
    out = TMP / "orden.pdf"
    s.save(out, {}, [2, 0], {2: 90})
    doc = fitz.open(out)
    check("orden, eliminación y rotación de páginas", doc.page_count == 2 and "PAG3" in doc[0].get_text()
          and doc[0].rotation == 90 and "PAG1" in doc[1].get_text())
    s.close()


def t_reuse_embedded():
    # fuente incrustada con mapa Unicode completo (como la de Word): debe reutilizarse
    path = TMP / "incrustada.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_font(fontname="F0", fontfile=r"C:\Windows\Fonts\georgia.ttf")
    page.insert_text((72, 100), "Informe trimestral de ventas", fontname="F0", fontsize=14,
                     color=(0.5, 0.1, 0.1))
    doc.save(path)
    doc.close()
    s = EditorSession(path)
    line = s.analyze(0)["lines"][0]
    out = TMP / "incrustada_editada.pdf"
    _p, notes = s.save(out, {0: {"overrides": {line["id"]: {"text": "Informe anual de ventas"}},
                                 "added": [], "z": None}}, [0], {})
    page = fitz.open(out)[0]
    span = span_of(page, "anual")
    check("reutiliza la fuente incrustada si tiene los glifos", not notes and span
          and "Georgia" in span["font"], f"{span and span['font']} {notes}")
    check("texto buscable con espacios normales", "Informe anual de ventas" in page.get_text())
    s.close()


for name, fn in [("detección", t_detect), ("editar una palabra", t_edit_word), ("líneas vecinas", t_neighbors),
                 ("glifo faltante", t_missing_glyph), ("mover", t_move), ("capas", t_layers), ("OCR", t_ocr),
                 ("página rotada", t_rotated_source), ("páginas", t_page_ops),
                 ("fuente incrustada reutilizada", t_reuse_embedded)]:
    run(name, fn)
print(f"\n{sum(results)}/{len(results)} OK — {TMP}")
sys.exit(0 if all(results) else 1)
