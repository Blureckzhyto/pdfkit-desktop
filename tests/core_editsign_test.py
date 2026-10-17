"""Pruebas de core/edit_sign.py con PDFs reales."""
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas

from core import edit_sign as es
from core import pdf_tools

TMP = Path(tempfile.mkdtemp(prefix="pdfkit_es_"))
SCALE = 100 / 72
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def run(name, fn):
    try:
        fn()
    except Exception:
        results.append(False)
        print(f"  FAIL  {name}: excepción")
        traceback.print_exc()


def text_of(path, i=0):
    return PdfReader(str(path)).pages[i].extract_text() or ""


def make_text_pdf(path, pages=3):
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    for i in range(pages):
        c.setFont("Helvetica", 24)
        c.drawString(72, 700, f"SECRETO{i}")
        c.drawString(72, 400, f"PUBLICO{i}")
        c.showPage()
    c.save()


base = TMP / "base.pdf"
make_text_pdf(base)
stamp = TMP / "stamp.png"
img = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
ImageDraw.Draw(img).ellipse((10, 10, 190, 90), fill=(255, 0, 0, 255))
img.save(stamp)


# ---------------------------------------------------------------- 1. editar
def t_edit():
    # "SECRETO0": baseline 700pt desde abajo -> top ~ 792-700-18 = 74pt
    redact = {"type": "redact", "x": 60 * SCALE, "y": 60 * SCALE, "w": 200 * SCALE, "h": 45 * SCALE}
    anns = {
        0: [redact,
            {"type": "text", "x": 300 * SCALE, "y": 200 * SCALE, "baseline": 214 * SCALE,
             "text": "Hola ñandú", "size": 14, "color": "#000000", "bold": True},
            {"type": "highlight", "x": 60 * SCALE, "y": 370 * SCALE, "w": 150 * SCALE, "h": 30 * SCALE,
             "color": "#FFE600"},
            {"type": "draw", "points": [(10, 10), (60, 80), (120, 30)], "width": 3, "color": "#1E5EFF"},
            {"type": "image", "path": str(stamp), "x": 300, "y": 600, "w": 120, "h": 60}],
    }
    out = TMP / "edited.pdf"
    es.apply_edits(base, out, anns, rotations={1: 90, 2: 270}, deleted=set(), scale=SCALE)
    t0 = text_of(out, 0)
    check("redacción elimina el texto de verdad", "SECRETO0" not in t0, repr(t0[:60]))
    check("redacción respeta el resto del texto", "PUBLICO0" in t0)
    check("texto agregado presente (negrita, acentos)", "Hola ñandú" in t0)
    r = PdfReader(str(out))
    check("rotación horaria aplicada (pág. 2 apaisada)", float(r.pages[1].mediabox.width) > float(r.pages[1].mediabox.height))
    check("rotación antihoraria aplicada (pág. 3 apaisada)", float(r.pages[2].mediabox.width) > float(r.pages[2].mediabox.height))
    check("páginas intactas tras rotar conservan texto", "SECRETO1" in text_of(out, 1))
    # la zona redactada debe verse negra en el render
    im = pdf_tools.render_page_image(out, 0, dpi=100)
    px = im.getpixel((int(100 * SCALE), int(80 * SCALE)))
    check("zona redactada se ve negra", sum(px[:3]) < 30, str(px))
    # eliminar páginas
    out2 = TMP / "deleted.pdf"
    es.apply_edits(base, out2, {}, {}, deleted={0, 2}, scale=SCALE)
    r2 = PdfReader(str(out2))
    check("eliminar páginas", len(r2.pages) == 1 and "SECRETO1" in text_of(out2, 0))
    try:
        es.apply_edits(base, TMP / "x.pdf", {}, {}, deleted={0, 1, 2}, scale=SCALE)
        check("rechaza eliminar todas", False)
    except ValueError as exc:
        check("rechaza eliminar todas (mensaje en español)", "páginas" in str(exc))


def t_redact_cropbox():
    # MediaBox desplazada + CropBox menor: el render (MediaBox) y MuPDF (CropBox) difieren
    src = TMP / "crop.pdf"
    make_text_pdf(src, pages=1)
    w = PdfWriter(clone_from=PdfReader(str(src)))
    p = w.pages[0]
    p.cropbox = RectangleObject((40, 100, 560, 760))
    w.write(str(src))
    # render de la MediaBox: SECRETO0 sigue en x=72pt, top≈74pt desde arriba de la MediaBox
    redact = {"type": "redact", "x": 60 * SCALE, "y": 60 * SCALE, "w": 200 * SCALE, "h": 45 * SCALE}
    out = TMP / "crop_redacted.pdf"
    es.apply_edits(src, out, {0: [redact]}, {}, set(), SCALE)
    t = text_of(out)
    check("redacción correcta con CropBox distinta", "SECRETO0" not in t and "PUBLICO0" in t, repr(t[:60]))


def t_redact_rotated_source():
    # página que ya trae /Rotate 90: las coordenadas son de la página tal como se ve
    src = TMP / "rot.pdf"
    make_text_pdf(src, pages=1)
    w = PdfWriter(clone_from=PdfReader(str(src)))
    w.pages[0].rotate(90)
    w.write(str(src))
    im = pdf_tools.render_page_image(src, 0, dpi=100)  # apaisada: 792x612pt
    # tras rotar 90° horario, el punto (x, y_top) pasa a (h - y_top, x): SECRETO0 (x 72-190, top 74-98)
    # queda en x ≈ 792-98..792-74 = 694..718, y ≈ 72..190
    redact = {"type": "redact", "x": 680 * SCALE, "y": 60 * SCALE, "w": 50 * SCALE, "h": 150 * SCALE}
    out = TMP / "rot_redacted.pdf"
    es.apply_edits(src, out, {0: [redact]}, {}, set(), SCALE)
    t = text_of(out)
    check("redacción en página con /Rotate previa", "SECRETO0" not in t and "PUBLICO0" in t,
          f"render {im.size}, texto {t[:40]!r}")


# ---------------------------------------------------------------- 2. firmar
def t_sign():
    fonts = es.signature_fonts()
    check("fuente incluida Dancing Script disponible", "Dancing Script" in fonts, ", ".join(fonts))
    drawn = es.render_drawn_signature([[(10, 50), (60, 20), (120, 80), (200, 40)], [(220, 60)]], "#000000")
    check("firma dibujada genera imagen RGBA", drawn is not None and drawn[0].mode == "RGBA",
          f"{drawn[0].size}, {drawn[1]:.0f}pt")
    typed = es.render_text_signature("Juan Pérez", fonts["Dancing Script"], "#1E5EFF", 48)
    check("firma escrita genera imagen", typed is not None and typed[0].width > typed[0].height)
    check("firma vacía devuelve None", es.render_text_signature("  ", fonts["Dancing Script"], "#000", 48) is None
          and es.render_drawn_signature([], "#000") is None)
    # imagen sin alfa (escaneo sobre papel blanco) -> fondo transparente
    scan = TMP / "scan.jpg"
    s = Image.new("RGB", (300, 120), "white")
    ImageDraw.Draw(s).line((20, 90, 150, 20, 280, 80), fill="black", width=6)
    s.save(scan)
    loaded, nat = es.load_signature_image(scan)
    check("imagen JPG: papel blanco pasa a transparente", loaded.getpixel((2, 2))[3] == 0)

    out = TMP / "signed.pdf"
    es.sign_pdf(base, out, 1, typed[0], (300, 600, 180, 180 * typed[0].height / typed[0].width))
    im = pdf_tools.render_page_image(out, 1, dpi=100)
    # dentro de la caja pero lejos de los trazos tiene que verse el papel (no negro)
    corner = im.getpixel((int(301 * SCALE), int(601 * SCALE)))
    check("firma conserva transparencia (sin fondo negro)", sum(corner[:3]) > 700, str(corner))
    ink = [im.getpixel((x, y)) for x in range(int(300 * SCALE), int(480 * SCALE), 3)
           for y in range(int(600 * SCALE), int(650 * SCALE), 3)]
    check("la tinta azul de la firma aparece", any(p[2] > 150 and p[0] < 120 for p in ink))
    check("las otras páginas quedan intactas", "SECRETO0" in text_of(out, 0))


# ---------------------------------------------------------------- 3. formularios
def make_form(path):
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    form = c.acroForm
    c.drawString(72, 720, "Nombre:")
    form.textfield(name="nombre", tooltip="Nombre completo", x=150, y=710, width=250, height=20)
    form.checkbox(name="acepto", tooltip="Acepto", x=150, y=670, size=16)
    form.radio(name="plan", value="basico", x=150, y=630, size=16, selected=True)
    form.radio(name="plan", value="pro", x=200, y=630, size=16)
    form.choice(name="pais", tooltip="País", value="AR", options=["AR", "UY", "CL"], x=150, y=590,
                width=120, height=20)
    c.showPage()
    c.save()


def t_forms():
    src = TMP / "form.pdf"
    make_form(src)
    fields = es.get_form_fields(src)
    by = {f["name"]: f for f in fields}
    print("    campos:", [(f["name"], f["type"], f["value"], f["options"]) for f in fields])
    check("detecta los 4 campos", set(by) == {"nombre", "acepto", "plan", "pais"}, str(list(by)))
    check("tipos correctos", by["nombre"]["type"] == "text" and by["acepto"]["type"] == "checkbox"
          and by["plan"]["type"] == "radio" and by["pais"]["type"] == "choice")
    check("tooltip como etiqueta", by["nombre"]["label"] == "Nombre completo")
    on = by["acepto"]["options"][0][0]
    pro = next(o[0] for o in by["plan"]["options"] if "pro" in o[0])
    out = TMP / "form_filled.pdf"
    es.fill_form(src, out, {"nombre": "Ana Gómez", "acepto": on, "plan": pro, "pais": "UY"})
    after = {f["name"]: f["value"] for f in es.get_form_fields(out)}
    check("texto escrito", after["nombre"] == "Ana Gómez", after["nombre"])
    check("casilla marcada", after["acepto"] == on, after["acepto"])
    check("opción elegida", after["plan"] == pro, after["plan"])
    check("lista desplegable", after["pais"] == "UY", after["pais"])
    plan_v = PdfReader(str(out)).get_fields()["plan"]["/V"]
    check("valor de opción guardado como nombre PDF", type(plan_v).__name__ == "NameObject", type(plan_v).__name__)
    try:
        es.get_form_fields(base)
        empty = es.get_form_fields(base) == []
    except Exception:
        empty = False
    check("PDF sin formulario devuelve lista vacía", empty)


# ---------------------------------------------------------------- 4. proteger
def t_protect():
    out = TMP / "prot.pdf"
    path, algo, gen = es.protect_pdf(base, out, "abrir123", "", allow_print=True,
                                     allow_copy=False, allow_modify=False)
    check("cifra con AES-256", algo == "AES-256", algo)
    check("genera contraseña de propietario si falta", gen)
    r = PdfReader(str(out))
    check("el PDF queda cifrado", r.is_encrypted)
    check("sin contraseña no se lee", r.decrypt("mala") == 0)
    r = PdfReader(str(out))
    check("con la contraseña de usuario se lee", r.decrypt("abrir123") != 0 and "SECRETO0" in r.pages[0].extract_text())
    perms = r.user_access_permissions
    from pypdf.constants import UserAccessPermissions as P
    check("permisos: impresión sí, copia no, edición no",
          bool(perms & P.PRINT) and not perms & P.EXTRACT and not perms & P.MODIFY, str(perms))
    try:
        es.apply_edits(out, TMP / "y.pdf", {}, {}, set(), SCALE)
        check("otras herramientas avisan si está protegido", False)
    except RuntimeError as exc:
        check("otras herramientas avisan si está protegido", "Desbloquéalo" in str(exc))
    unl = TMP / "unlocked.pdf"
    es.unprotect_pdf(out, unl, "abrir123")
    check("desproteger con contraseña correcta", not PdfReader(str(unl)).is_encrypted and "SECRETO0" in text_of(unl))
    try:
        es.unprotect_pdf(out, TMP / "z.pdf", "incorrecta")
        check("contraseña incorrecta rechazada", False)
    except ValueError as exc:
        check("contraseña incorrecta rechazada", "incorrecta" in str(exc))
    try:
        es.unprotect_pdf(base, TMP / "z.pdf", "x")
        check("avisa si no estaba protegido", False)
    except ValueError as exc:
        check("avisa si no estaba protegido", "no está protegido" in str(exc))
    # respaldo RC4-128 cuando AES no está disponible
    original = es._aes_available
    es._aes_available = lambda: False
    try:
        _, algo2, _ = es.protect_pdf(base, TMP / "rc4.pdf", "u", "o")
    finally:
        es._aes_available = original
    r = PdfReader(str(TMP / "rc4.pdf"))
    check("respaldo RC4-128", algo2 == "RC4-128" and r.decrypt("o") != 0, algo2)
    try:
        es.protect_pdf(base, TMP / "w.pdf", "", "")
        check("exige al menos una contraseña", False)
    except ValueError:
        check("exige al menos una contraseña", True)


# ---------------------------------------------------------------- 5. marca de agua
def t_watermark():
    out = TMP / "wm.pdf"
    path, n = es.watermark_text(base, out, "CONFIDENCIAL", size=60, opacity=0.3,
                                color="#FF2D2D", position="diagonal")
    check("marca de texto en todas las páginas", n == 3 and all("CONFIDENCIAL" in text_of(out, i) for i in range(3)))
    out2 = TMP / "wm_range.pdf"
    _, n2 = es.watermark_text(base, out2, "BORRADOR", position="corner", pages_spec="2-3")
    check("rango de páginas", n2 == 2 and "BORRADOR" not in text_of(out2, 0) and "BORRADOR" in text_of(out2, 2))
    _, _ = es.watermark_text(base, TMP / "wm_h.pdf", "MUY LARGO " * 20, position="horizontal")
    im = pdf_tools.render_page_image(out, 0, dpi=50)
    reds = sum(1 for x in range(0, im.width, 2) for y in range(0, im.height, 2)
               if im.getpixel((x, y))[0] > 200 and im.getpixel((x, y))[1] < 230)
    check("marca semitransparente visible", reds > 50, f"{reds} píxeles rojizos")
    out3 = TMP / "wm_img.pdf"
    _, n3 = es.watermark_image(base, out3, stamp, opacity=0.4, scale=0.3, position="corner",
                               pages_spec="1")
    im3 = pdf_tools.render_page_image(out3, 0, dpi=50)
    # caja de la imagen a 50 ppp: x 272-400, y 461-525 -> centro de la elipse
    px = im3.getpixel((336, 493))
    check("marca de imagen con opacidad (rojo claro, no opaco)", px[0] > 200 and 100 < px[1] < 240, str(px))
    try:
        es.watermark_text(base, TMP / "q.pdf", "X", pages_spec="7-9")
        check("rango fuera del documento rechazado", False)
    except ValueError as exc:
        check("rango fuera del documento rechazado (español)", "fuera del documento" in str(exc))


for name, fn in [("editar", t_edit), ("redacción cropbox", t_redact_cropbox),
                 ("redacción rotada", t_redact_rotated_source), ("firmar", t_sign),
                 ("formularios", t_forms), ("proteger", t_protect), ("marca de agua", t_watermark)]:
    print(f"\n[{name}]")
    run(name, fn)

print(f"\n{sum(results)}/{len(results)} OK — archivos en {TMP}")
sys.exit(0 if all(results) else 1)
