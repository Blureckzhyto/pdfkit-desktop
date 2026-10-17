"""Prueba de punta a punta del editor real y del diseño 1.3, bajo mainloop."""
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import img2pdf
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont, ImageGrab
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

SHOTS = Path(__file__).parent / "_capturas" / "shots_v13"
SHOTS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="pdfkit_gui13_"))
SETTINGS = Path.home() / ".pdfkit" / "settings.json"
backup = SETTINGS.read_bytes() if SETTINGS.exists() else None

# documento con fuente incrustada con mapa Unicode (Georgia) + Times + imagen, 3 páginas
src = TMP / "informe.pdf"
doc = fitz.open()
for n in range(3):
    page = doc.new_page()
    page.insert_font(fontname="F0", fontfile=r"C:\Windows\Fonts\georgia.ttf")
    page.insert_text((72, 100), f"Informe trimestral {n + 1}", fontname="F0", fontsize=20,
                     color=(0.12, 0.31, 0.62))
    page.insert_text((72, 140), "Ventas en crecimiento sostenido", fontname="tiro", fontsize=12)
    page.insert_text((72, 156), "Segunda linea del parrafo", fontname="tiro", fontsize=12)
    page.insert_image(fitz.Rect(320, 200, 480, 300), stream=(lambda b: (Image.new(
        "RGB", (160, 100), (229, 72, 77)).save(b, "PNG"), b.getvalue())[1])(BytesIO()))
doc.save(src)
doc.close()
scan = TMP / "escaneo.pdf"
img = Image.new("RGB", (1654, 2339), "white")
ImageDraw.Draw(img).text((200, 300), "Contrato de servicios", fill="black",
                         font=ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 50))
buf = BytesIO()
img.save(buf, "PNG", dpi=(200, 200))
scan.write_bytes(img2pdf.convert(buf.getvalue()))

from ui import anim, theme
from ui.app import App

app = App()
app.attributes("-topmost", True)
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def grab(name):
    app.update_idletasks()
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height())).save(SHOTS / f"{name}.png")


class E:
    def __init__(self, x, y, state=0, delta=0):
        self.x, self.y, self.state, self.delta = x, y, state, delta


steps = []


def step(fn):
    steps.append(fn)
    return fn


def run_steps():
    if not steps:
        finish()
        return
    fn = steps.pop(0)
    try:
        wait_for = fn()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        check(f"{fn.__name__}: sin excepciones", False, repr(exc))
        wait_for = None
    deadline = time.time() + 180

    def poll():
        if wait_for is None or wait_for() or time.time() > deadline:
            app.after(120, run_steps)
        else:
            app.after(120, poll)

    app.after(200, poll)


def v():
    return app._views["edit"]


def screen_center(view, uid):
    x0, y0, x1, y1 = view._to_screen(view._box(uid))
    return (x0 + x1) / 2, (y0 + y1) / 2


def find(view, text):
    model = view._model()
    return next(l for l in model["lines"] if text in l["text"].replace(" ", " "))


def rendered(view):
    token = view.ed_token
    return lambda: view.ed_image is not None and view.ed_render_job is None and token <= view.ed_token


@step
def s_open():
    indicator_y = getattr(app, "_indicator_y", None)
    app.show_view("edit")
    view = v()
    check("barra lateral: el indicador se desliza al ítem activo", app._indicator_y != indicator_y)
    view.output_selector.entry.delete(0, "end")
    view.output_selector.entry.insert(0, str(TMP))
    view.picker.add_files([str(src)])
    return lambda: view.ed_image is not None and view.ed_current in view.ed_models


@step
def s_hover_select():
    view = v()
    line = find(view, "Informe trimestral")
    check("detecta el estilo original", line["style"]["font"].startswith("Georgia")
          and abs(line["style"]["size"] - 20) < 0.1, f"{line['style']['font']} {line['style']['size']}")
    x, y = screen_center(view, line["id"])
    view._on_motion(E(x, y))
    check("hover resalta la línea", view.ed_hover == line["id"])
    view._on_double(E(x, y))
    widget, uid, font = view.ed_editor
    check("doble clic abre el editor en el lugar, con el texto", widget.get("1.0", "end-1c").replace(" ", " ") == "Informe trimestral 1")
    check("el editor usa la misma familia, tamaño y color", font.actual("family") == "Georgia"
          and abs(abs(font.cget("size")) - round(20 * view.ed_scale)) <= 1
          and widget.cget("fg").upper() == line["style"]["color"],
          f"{font.actual('family')} {font.cget('size')} {widget.cget('fg')}")
    grab("editor_inline")
    widget.delete("1.0", "end")
    widget.insert("1.0", "Informe anual 1")
    view._commit_edit()
    return rendered(view)


@step
def s_after_edit():
    view = v()
    line = find(view, "Informe trimestral")
    check("la edición queda en el estado", view._st()["overrides"][line["id"]]["text"] == "Informe anual 1")
    check("nota de fuente: reutiliza la original", "original" in view.ed_font_note.lower(),
          view.ed_font_note)
    # mover la imagen arrastrándola
    image = view._model()["images"][0]
    x, y = screen_center(view, image["id"])
    view._on_press(E(x, y))
    view._on_drag(E(x + 10, y + 5))
    view._on_drag(E(x - 60, y + 80))
    view._on_release(E(x - 60, y + 80))
    box = view._st()["overrides"][image["id"]]["bbox"]
    check("arrastrar mueve la imagen", abs(box[0] - (320 - 60 / view.ed_scale)) < 1.5, str([round(b) for b in box]))
    # empujar con las flechas
    view._nudge(1, 0, 10)
    box2 = view._st()["overrides"][image["id"]]["bbox"]
    check("Mayús+flecha mueve 10 pt", abs(box2[0] - box[0] - 10) < 0.01)
    # capas: enviar atrás
    view._layer("back")
    check("enviar atrás reordena las capas", view._st()["z"][0] == image["id"])
    view._layer("front")
    check("traer al frente", view._st()["z"][-1] == image["id"])
    # deshacer / rehacer
    undo_count = len(view.ed_undo)
    view._undo()
    check("Ctrl+Z deshace", view._st()["z"][0] == image["id"] and len(view.ed_redo) == 1)
    view._redo()
    check("Ctrl+Y rehace", view._st()["z"][-1] == image["id"] and len(view.ed_undo) == undo_count)
    return rendered(view)


@step
def s_add_text():
    view = v()
    line = find(view, "Ventas en crecimiento")
    view._set_tool("text")
    x0, y0, x1, y1 = view._to_screen(line["bbox"])
    view._on_press(E(x0 + 2, y1 + 40))
    widget, uid, font = view.ed_editor
    element = view._element(uid)
    check("añadir texto toma el estilo cercano", abs(element["style"]["size"] - 12) < 0.1
          and element["style"]["family"] == "Times New Roman", f"{element['style']['family']} {element['style']['size']}")
    widget.insert("1.0", "Nota agregada")
    view._commit_edit()
    view._set_tool("select")
    # borrar con Supr: la segunda línea
    second = find(view, "Segunda linea")
    view._select(second["id"])
    view._delete_selected()
    check("Supr borra el elemento", view._st()["overrides"][second["id"]].get("deleted"))
    return rendered(view)


@step
def s_props():
    view = v()
    line = find(view, "Ventas en crecimiento")
    view._select(line["id"])
    view._set_style("bold", True)
    check("propiedades: negrita", view._st()["overrides"][line["id"]]["style"]["bold"])
    view._set_level("block")
    check("nivel párrafo", view.ed_level == "block")
    view._set_level("line")
    view._zoom_step(1)
    check("zoom con los botones", view.ed_zoom.endswith("%"))
    return rendered(view)


@step
def s_layers_panel():
    view = v()
    view._toggle_layers()
    check("panel de capas visible con los elementos", view.ed_layers_visible
          and len(view.ed_layer_rows) >= 3, str(len(view.ed_layer_rows)))
    grab("editor_capas")
    return lambda: len(view.ed_thumbs) >= 3


@step
def s_thumbs():
    view = v()
    slots, _ = view._thumb_slots()
    check("miniaturas de las 3 páginas", len(slots) == 3 and len(view.ed_thumbs) == 3)
    # arrastrar la página 3 al principio
    _i, top3, h3 = slots[2]
    view._thumb_press(E(40, top3 + 10))
    view._thumb_motion(E(40, top3 - 40))
    view._thumb_motion(E(40, 2))
    view._thumb_release(E(40, 2))
    check("arrastrar miniaturas reordena las páginas", view.ed_order == [2, 0, 1], str(view.ed_order))
    view.run()
    return lambda: not view._running


@step
def s_saved():
    view = v()
    out = TMP / "informe_editado.pdf"
    check("guardado", out.exists(), view.status.cget("text"))
    if out.exists():
        doc = fitz.open(out)
        texts = [p.get_text().replace(" ", " ") for p in doc]
        original_first = texts[1]  # la página 1 original quedó en segundo lugar
        check("PDF: orden de páginas aplicado", "Informe trimestral 3" in texts[0])
        check("PDF: texto editado con la fuente original", "Informe anual 1" in original_first
              and "trimestral 1" not in original_first)
        span = next(s for b in doc[1].get_text("dict")["blocks"] for l in b.get("lines", [])
                    for s in l["spans"] if "anual" in s["text"])
        check("PDF: mismo tamaño y color", abs(span["size"] - 20) < 0.5 and f"#{span['color']:06X}" == "#1F4F9E",
              f"{span['size']} #{span['color']:06X} {span['font']}")
        check("PDF: texto agregado y línea borrada", "Nota agregada" in original_first
              and "Segunda linea" not in original_first)
        check("PDF: imagen movida (sin duplicar)", len(doc[1].get_image_info()) == 1)
    check("toast de éxito visible", any(t.winfo_exists() for t in app.toasts.toasts))
    grab("editor_guardado_toast")
    view.picker.add_files([str(scan)])
    return lambda: view.ed_image is not None and view.ed_models.get(0, {}).get("ocr")


@step
def s_ocr():
    view = v()
    check("página escaneada: insignia de OCR visible", view.ed_badge.winfo_manager() == "place")
    texts = [l["text"] for l in view._model()["lines"]]
    check("página escaneada: líneas detectadas", "Contrato de servicios" in texts, str(texts))
    grab("editor_ocr")
    app._reduce.select()
    app._toggle_motion()
    check("Reducir animaciones desactiva las animaciones", anim.ENABLED is False)
    app._reduce.deselect()
    app._toggle_motion()
    app.show_view("home")
    return None


def finish():
    grab("home_v13")
    app.destroy()


app.after(900, run_steps)
app.after(900000, app.destroy)
try:
    app.mainloop()
finally:
    if backup is not None:
        SETTINGS.write_bytes(backup)
print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK — {TMP}")
sys.exit(0 if results and all(results) else 1)
