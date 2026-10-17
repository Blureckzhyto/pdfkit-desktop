"""Nombre del archivo de salida (v1.3.3): reglas del núcleo y uso real en varias herramientas."""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageGrab
from reportlab.pdfgen import canvas as rl_canvas

from core.utils import clean_filename, named_output, rename_outputs

TMP = Path(tempfile.mkdtemp(prefix="pdfkit_nombre_"))
SHOTS = Path(__file__).parent / "_capturas" / "shots_v133"
SHOTS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(exist_ok=True)
SETTINGS = Path.home() / ".pdfkit" / "settings.json"
backup = SETTINGS.read_bytes() if SETTINGS.exists() else None
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


# ------------------------------------------------------------------ núcleo
out = TMP / "nucleo"
out.mkdir()
check("vacío: nombre automático", named_output(out, "doc_unido.pdf", "") == out / "doc_unido.pdf")
check("nombre elegido + extensión de la herramienta",
      named_output(out, "doc_unido.pdf", "Contrato final") == out / "Contrato final.pdf")
check("si ya trae la extensión no se duplica",
      named_output(out, "doc.docx", "informe.DOCX") == out / "informe.docx")
check("caracteres no válidos en Windows se reemplazan",
      named_output(out, "a.pdf", 'Factura: 3/4 "julio"?') == out / "Factura_ 3_4 _julio__.pdf",
      named_output(out, "a.pdf", 'Factura: 3/4 "julio"?').name)
check("nombres reservados de Windows", clean_filename("CON") == "_CON")
check("solo caracteres inválidos o espacios: automático",
      named_output(out, "doc_ocr.pdf", " ... ") == out / "doc_ocr.pdf")
(out / "Contrato final.pdf").write_bytes(b"x")
check("no pisa un archivo existente", named_output(out, "a.pdf", "Contrato final") == out / "Contrato final (1).pdf")
parts = []
for n in (1, 2, 3):
    p = out / f"doc_parte{n:02d}.pdf"
    p.write_bytes(b"x")
    parts.append(p)
renamed = rename_outputs(parts, "Capitulos", "doc")
check("varios archivos: nombre + lo que los distingue",
      [p.name for p in renamed] == ["Capitulos_parte01.pdf", "Capitulos_parte02.pdf", "Capitulos_parte03.pdf"]
      and all(p.exists() for p in renamed) and not any(p.exists() for p in parts), str([p.name for p in renamed]))
imgs = []
for name in ("playa.jpg", "montana.jpg"):
    p = out / name
    p.write_bytes(b"x")
    imgs.append(p)
renamed = rename_outputs(imgs, "Vacaciones")
check("varias imágenes de distinto origen: nombre + número",
      [p.name for p in renamed] == ["Vacaciones_1.jpg", "Vacaciones_2.jpg"], str([p.name for p in renamed]))
check("sin nombre no se renombra nada", rename_outputs(renamed, "") == renamed)

# ------------------------------------------------------------------ interfaz
doc = TMP / "doc.pdf"
c = rl_canvas.Canvas(str(doc))
for i in range(4):
    c.drawString(72, 700, f"Pagina {i + 1}")
    c.showPage()
c.save()
doc2 = TMP / "doc2.pdf"
doc2.write_bytes(doc.read_bytes())
photo = TMP / "foto.png"
Image.new("RGB", (300, 200), "steelblue").save(photo)

from ui.app import App

app = App()
app.geometry("1320x840+40+40")
app.attributes("-topmost", True)
gui_out = TMP / "salida"
gui_out.mkdir()


def wait(cond, timeout=90):
    end = time.time() + timeout
    while not cond() and time.time() < end:
        app.update()
    return cond()


def view(key, name):
    app.show_view(key)
    v = app._views[key]
    v.output_selector.entry.delete(0, "end")
    v.output_selector.entry.insert(0, str(gui_out))
    v.output_selector.name_entry.delete(0, "end")
    if name:
        v.output_selector.name_entry.insert(0, name)
    app.update()
    return v


def run():
    v = view("merge", "Expediente completo")
    v.picker.add_files([str(doc), str(doc2)])
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()),
                   all_screens=True).save(SHOTS / "nombre_salida.png")
    v.run()
    wait(lambda: not v._running)
    check("Unir PDF usa el nombre elegido", (gui_out / "Expediente completo.pdf").exists(),
          v.status.cget("text"))

    v = view("compress", "")
    v.picker.add_files([str(doc)])
    v.run()
    wait(lambda: not v._running)
    check("vacío: Comprimir usa el nombre automático", (gui_out / "doc_comprimido.pdf").exists(),
          v.status.cget("text"))

    v = view("split", "Capitulo")
    v.picker.add_files([str(doc)])
    v.mode.set("Cada N páginas")
    v._mode_changed("Cada N páginas")
    v.value_entry.insert(0, "2")
    v.run()
    wait(lambda: not v._running)
    made = sorted(p.name for p in gui_out.glob("Capitulo*.pdf"))
    check("Dividir: varios archivos con el nombre elegido como base", len(made) == 2
          and all(n.startswith("Capitulo_") for n in made), str(made))

    v = view("pdf2word", "Informe.docx")
    v.picker.add_files([str(doc)])
    v.run()
    wait(lambda: not v._running)
    check("PDF a Word: la extensión escrita no se duplica", (gui_out / "Informe.docx").exists(),
          str(sorted(p.name for p in gui_out.glob("Informe*"))))

    v = view("imgconvert", "Portada")
    v.picker.add_files([str(photo)])
    v.format.set("JPG")
    v.run()
    wait(lambda: not v._running)
    check("Convertir imágenes: una imagen toma el nombre elegido", (gui_out / "Portada.jpg").exists(),
          str(sorted(p.name for p in gui_out.iterdir())))

    v = view("merge", "Expediente completo")
    v.picker.add_files([str(doc), str(doc2)])
    v.run()
    wait(lambda: not v._running)
    check("repetir el nombre no pisa el archivo anterior", (gui_out / "Expediente completo (1).pdf").exists())
    app.destroy()


app.after(800, run)
app.after(300000, app.destroy)
try:
    app.mainloop()
finally:
    if backup is not None:
        SETTINGS.write_bytes(backup)
print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK — {TMP}")
sys.exit(0 if results and all(results) else 1)
