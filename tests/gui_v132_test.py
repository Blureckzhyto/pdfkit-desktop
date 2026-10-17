"""Pruebas GUI del editor (v1.3.2): clic, temblor, doble clic, paneo, tolerancia y
confirmación de sustitución de fuentes, a 50 %, 100 % y 200 % de zoom."""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fitz
from PIL import ImageGrab
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as rl_canvas

TMP = Path(tempfile.mkdtemp(prefix="pdfkit_gui132_"))
SHOTS = Path(__file__).parent / "_capturas" / "shots_v132"
SHOTS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(exist_ok=True)
SETTINGS = Path.home() / ".pdfkit" / "settings.json"
backup = SETTINGS.read_bytes() if SETTINGS.exists() else None

doc_path = TMP / "lineas.pdf"
c = rl_canvas.Canvas(str(doc_path), pagesize=(595, 842))
for n, y in enumerate(range(780, 80, -60)):
    t = c.beginText(72, y)
    t.setFont("Helvetica", 15)
    t.textOut(f"Renglon {n + 1} con texto normal ")
    t.setFont("Helvetica-Bold", 15)
    t.textOut("y negrita ")
    t.setFont("Times-Italic", 15)
    t.setFillColor(HexColor("#C0392B"))
    t.textOut("en rojo")
    c.drawText(t)
c.save()

import tkinter as tk

errors = []
tk.Tk.report_callback_exception = lambda self, exc, val, tb: errors.append(f"{exc.__name__}: {val}")

from ui.app import App

app = App()
app.geometry("1320x840+40+40")
app.attributes("-topmost", True)
results, log = [], []
v = None


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def settle(ms=300):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        app.update()


def wait(cond, timeout=60):
    end = time.time() + timeout
    while not cond() and time.time() < end:
        app.update()
    return cond()


def view_state():
    cnv = v.ed_canvas
    return (cnv.winfo_rooty(), cnv.winfo_height(), round(cnv.canvasx(0), 1), round(cnv.canvasy(0), 1),
            v.ed_zoom, round(v.ed_scale, 4))


def line_point(uid, fx=0.3):
    """Punto de pantalla (relativo al lienzo) dentro de la caja de `uid`, a la vista."""
    cnv = v.ed_canvas
    x0, y0, x1, y1 = v._to_screen(v._box(uid))
    top = cnv.canvasy(0)
    if not (top + 20 < y0 and y1 < top + cnv.winfo_height() - 20):   # traerla a la vista
        region = float(cnv.cget("scrollregion").split()[3])
        cnv.yview_moveto(max(0.0, (y0 - 120) / region))
        settle(150)
    return int(x0 + (x1 - x0) * fx - cnv.canvasx(0)), int((y0 + y1) / 2 - cnv.canvasy(0))


def press(x, y):
    v.ed_canvas.event_generate("<Button-1>", x=x, y=y)


def motion(x, y):
    v.ed_canvas.event_generate("<B1-Motion>", x=x, y=y, state=0x100)


def release(x, y):
    v.ed_canvas.event_generate("<ButtonRelease-1>", x=x, y=y, state=0x100)


def click(x, y, jitter=0):
    press(x, y)
    if jitter:
        motion(x + jitter, y)
    release(x + jitter, y)


def changes():
    return {k: o for k, o in v._st()["overrides"].items() if o}


def run():
    global v
    app.show_view("edit")
    v = app._views["edit"]
    v.picker.add_files([str(doc_path)])
    wait(lambda: v.ed_image is not None and v._model() is not None)
    settle(600)
    lines = v._model()["lines"]
    target = lines[3]["id"]
    for zoom in ("50 %", "100 %", "200 %"):
        v._commit_edit(cancel=True)
        v._select(None)
        v._set_zoom(zoom)
        wait(lambda: abs(v.ed_scale - int(zoom.split()[0]) / 100 * 96 / 72) < 1e-6 and v.ed_image is not None)
        settle(400)
        if zoom == "200 %":
            v.ed_canvas.yview_moveto(0.25)
            settle(150)
        x, y = line_point(target)
        before = view_state()
        settle(600)   # que no cuente como doble clic con el anterior
        click(x, y)
        settle(250)
        check(f"{zoom}: un clic selecciona el texto", v.ed_selected == target, str(v.ed_selected))
        check(f"{zoom}: seleccionar no mueve la vista ni el lienzo", view_state() == before,
              f"{before} → {view_state()}")
        settle(600)
        v._select(None)
        settle(100)
        before = view_state()
        click(x, y, jitter=2)
        settle(250)
        check(f"{zoom}: clic con 2 px de temblor sigue siendo clic (selecciona, no mueve)",
              v.ed_selected == target and not changes() and view_state() == before,
              f"{changes()} {before} → {view_state()}")
        settle(600)
        # doble clic: dos clics seguidos en el mismo lugar
        before = view_state()
        press(x, y)
        release(x, y)
        press(x, y)
        release(x, y)
        settle(300)
        check(f"{zoom}: doble clic entra a editar", v.ed_editor is not None and v.ed_editor[1] == target)
        check(f"{zoom}: editar no cambia el desplazamiento ni el zoom", view_state() == before,
              f"{before} → {view_state()}")
        if zoom == "100 %":
            app.update_idletasks()
            x0 = app.winfo_rootx()
            y0 = app.winfo_rooty()
            ImageGrab.grab(bbox=(x0, y0, x0 + app.winfo_width(), y0 + app.winfo_height()),
                           all_screens=True).save(SHOTS / "editando_100.png")
        v._commit_edit(cancel=True)
        settle(200)
        check(f"{zoom}: salir sin cambios no deja cambios", not changes(), str(changes()))

    # clic sobre un texto ya elegido: edita con el cursor donde se hizo clic
    v._set_zoom("100 %")
    wait(lambda: v.ed_image is not None and abs(v.ed_scale - 96 / 72) < 1e-6)
    settle(400)
    v._select(None)
    x, y = line_point(target, fx=0.5)
    settle(600)
    click(x, y)
    settle(700)
    before = view_state()
    click(x, y)
    settle(300)
    editor = v.ed_editor
    check("clic sobre el texto ya elegido entra a editar", editor is not None)
    if editor:
        widget = editor[0]
        index = int(widget.index("insert").split(".")[1])
        text = v._element(target)["text"]
        check("el cursor queda donde se hizo clic (no al final)", 0 < index < len(text) - 2,
              f"columna {index} de {len(text)}")
        check("entrar a editar no mueve la vista", view_state() == before)
        v._commit_edit(cancel=True)
        settle(200)

    # arrastre de verdad: más de 4 px mueve el elemento, nunca la vista
    v._select(None)
    x, y = line_point(target)
    settle(600)
    before = view_state()
    press(x, y)
    for step in range(1, 6):
        motion(x + step * 6, y + step * 2)
    release(x + 30, y + 10)
    settle(400)
    moved = v._st()["overrides"].get(target, {})
    check("arrastrar más de 4 px mueve el texto (no la vista)",
          abs(moved.get("dx", 0)) > 10 and view_state()[2:] == before[2:], f"{moved} {view_state()}")
    v._undo()
    settle(400)

    # arrastrar sobre un área vacía no desplaza la vista
    v.ed_canvas.yview_moveto(0)
    settle(150)
    before = view_state()
    press(8, 8)
    for step in range(1, 6):
        motion(8 + step * 20, 8 + step * 20)
    release(108, 108)
    settle(200)
    check("arrastre izquierdo en vacío no desplaza la vista", view_state() == before)

    # Espacio + arrastre sí mueve la vista
    v._set_zoom("200 %")
    wait(lambda: v.ed_image is not None and v.ed_scale > 2.5)
    settle(400)
    v.ed_canvas.yview_moveto(0.3)
    settle(150)
    before = view_state()
    v.ed_canvas.focus_set()
    v._space_down()
    press(300, 300)
    motion(300, 250)
    motion(300, 200)
    release(300, 200)
    v._space_up()
    settle(200)
    check("Espacio + arrastre mueve la vista", view_state()[3] > before[3] + 50,
          f"{before[3]} → {view_state()[3]}")
    v.ed_canvas.event_generate("<ButtonPress-2>", x=300, y=300)
    v.ed_canvas.event_generate("<B2-Motion>", x=300, y=350, state=0x200)
    settle(150)
    check("arrastre con el botón central mueve la vista", view_state()[3] < before[3] + 100)

    # tolerancia de 3 px alrededor de la caja, a cualquier zoom
    for zoom in ("50 %", "200 %"):
        v._set_zoom(zoom)
        wait(lambda: v.ed_image is not None and abs(v.ed_scale - int(zoom.split()[0]) / 100 * 96 / 72) < 1e-6)
        settle(300)
        line_point(target)
        x0, y0, x1, y1 = v._to_screen(v._box(target))
        sx, sy = v.ed_canvas.canvasx(0), v.ed_canvas.canvasy(0)
        near = v._hit(*v._to_pt(x0 - 2 - sx, (y0 + y1) / 2 - sy))
        far = v._hit(*v._to_pt(x0 - 7 - sx, (y0 + y1) / 2 - sy))
        check(f"{zoom}: 2 px fuera de la caja aún la toca; 7 px fuera ya no", near == target and far != target,
              f"{near} / {far}")

    # la barra de propiedades muestra la fuente y el tamaño reales
    v._set_zoom("100 %")
    wait(lambda: v.ed_image is not None and abs(v.ed_scale - 96 / 72) < 1e-6)
    settle(300)
    v._select(target)
    wait(lambda: "Fuente original" in v.ed_font_note, 10)
    settle(200)
    check("la barra muestra la fuente y el tamaño reales",
          "Helvetica 15 pt" in v.ed_font_note and "Helvetica-Bold" in v.ed_font_note
          and "Times-Italic" in v.ed_font_note, v.ed_font_note)

    # guardar con un carácter que la fuente original no tiene: se pregunta antes
    v._push_undo()
    v._st()["overrides"].setdefault(target, {})["text"] = v._element(target)["text"] + " Ω"
    v._after_change()
    out_dir = TMP / "salida"
    out_dir.mkdir()
    v.output_selector.entry.delete(0, "end")
    v.output_selector.entry.insert(0, str(out_dir))
    v.run()
    wait(lambda: getattr(v, "ed_subst_dialog", None) is not None, 60)
    settle(500)
    dialog = getattr(v, "ed_subst_dialog", None)
    check("aparece el diálogo de sustitución antes de guardar", dialog is not None)
    if dialog is not None:
        labels = [b.cget("text") for b in dialog.ed_buttons.values()]
        check("el diálogo ofrece las tres opciones",
              labels[0].startswith("Usar fuente similar (") and labels[1:] == ["Editar el texto", "Cancelar"],
              str(labels))
        dialog.update_idletasks()
        x0, y0 = dialog.winfo_rootx(), dialog.winfo_rooty()
        ImageGrab.grab(bbox=(x0 - 8, y0 - 32, x0 + dialog.winfo_width() + 8, y0 + dialog.winfo_height() + 8),
                       all_screens=True).save(SHOTS / "dialogo_sustitucion.png")
        dialog.ed_buttons["cancel"].invoke()
        settle(300)
        check("Cancelar no guarda nada", not list(out_dir.glob("*.pdf")))
        v.run()
        wait(lambda: getattr(v, "ed_subst_dialog", None) is not None, 60)
        settle(300)
        v.ed_subst_dialog.ed_buttons["substitute"].invoke()
        wait(lambda: list(out_dir.glob("*.pdf")) and not v._running, 60)
        settle(300)
        saved = list(out_dir.glob("*.pdf"))
        text = fitz.open(saved[0])[0].get_text() if saved else ""
        check("Usar fuente similar guarda con el carácter", saved and "Ω" in text, v.status.cget("text"))

    check("sin excepciones en la interfaz", not errors, "; ".join(errors[:3]))
    app.destroy()


app.after(800, run)
app.after(600000, app.destroy)
try:
    app.mainloop()
finally:
    if backup is not None:
        SETTINGS.write_bytes(backup)
print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK — {TMP}")
sys.exit(0 if results and all(results) else 1)
