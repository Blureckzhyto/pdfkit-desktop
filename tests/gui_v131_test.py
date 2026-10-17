"""Pruebas de la versión 1.3.1 bajo mainloop: tema claro/oscuro/sistema, auditoría de
colores en oscuro (todas las vistas), desplazamiento (rueda, aceleración, zona bajo el
cursor, Mayús+rueda, touchpad, arrastre de la barra agrupado por cuadro, pausa del
hover) y miniaturas diferidas. Guarda capturas del modo oscuro en shots_v131/."""
import json
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import ImageGrab
from reportlab.pdfgen import canvas as rl_canvas

SHOTS = Path(__file__).parent / "_capturas" / "shots_v131"
SHOTS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="pdfkit_gui131_"))
SETTINGS = Path.home() / ".pdfkit" / "settings.json"
backup = SETTINGS.read_bytes() if SETTINGS.exists() else None
# arranque sin preferencia guardada: debe usar "Sistema"
if backup is not None:
    data = json.loads(backup.decode("utf-8"))
    data.pop("theme", None)
    data["reduce_motion"] = False
    SETTINGS.write_text(json.dumps(data), encoding="utf-8")


def make_pdf(path, pages, size=(595, 842), text=None):
    c = rl_canvas.Canvas(str(path), pagesize=size)
    for i in range(pages):
        c.setFont("Helvetica-Bold", 40)
        c.drawString(72, size[1] - 120, text or f"Pagina {i + 1}")
        c.setFont("Helvetica", 16)
        c.drawString(72, size[1] - 170, "Texto de ejemplo para las pruebas del modo oscuro")
        c.showPage()
    c.save()


pdf50 = TMP / "cincuenta.pdf"
make_pdf(pdf50, 50)
pdf3 = TMP / "tres.pdf"
make_pdf(pdf3, 3)
pdf3b = TMP / "tres_b.pdf"
make_pdf(pdf3b, 3, text="Pagina CAMBIADA")

import customtkinter as ctk

from core.settings import Settings
from ui import anim, startup, theme
from ui.app import App
from ui.components import scrolling

errors = []
tk.Tk.report_callback_exception = lambda self, exc, val, tb: errors.append(f"{exc.__name__}: {val}")

app = App()
app.geometry("1320x840+40+40")
app.attributes("-topmost", True)
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def grab(name):
    app.update_idletasks()
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab(bbox=(x - 1, y - 31, x + app.winfo_width() + 1, y + app.winfo_height() + 1),
                   all_screens=True).save(SHOTS / f"{name}.png")


def settle(ms=350):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        app.update()


def view(key):
    app.show_view(key)
    v = app._views[key]
    if getattr(v, "output_selector", None):
        v.output_selector.entry.delete(0, "end")
        v.output_selector.entry.insert(0, str(TMP))
    settle(250)
    return v


def wheel(widget, delta, x=40, y=40, shift=False):
    rx, ry = widget.winfo_rootx() + x, widget.winfo_rooty() + y
    widget.event_generate("<MouseWheel>", delta=delta, x=x, y=y, rootx=rx, rooty=ry,
                          state=0x1 if shift else 0)


def lum(color):
    r, g, b = (v / 65535 for v in app.winfo_rgb(color))

    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# --------------------------------------------------------------- secuencia de pasos
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
    deadline = time.time() + 90

    def poll():
        if wait_for is None or wait_for() or time.time() > deadline:
            app.after(80, run_steps)
        else:
            app.after(100, poll)

    app.after(120, poll)


# =============================================================== TEMA
@step
def t_default_system():
    system_dark = theme.system_prefers_dark()
    check("tema por defecto: Sistema", app.theme_pref == "sistema"
          and app._theme_selector.get() == "Sistema")
    check("Sistema sigue a Windows al iniciar",
          ctk.get_appearance_mode() == ("Dark" if system_dark else "Light"),
          f"Windows oscuro={system_dark}")


@step
def t_dark():
    app.set_theme("oscuro", animate=False)
    settle()
    home = app._views["home"].grid_view
    check("Oscuro: modo de customtkinter", ctk.get_appearance_mode() == "Dark")
    check("Oscuro: se guarda en settings.json", Settings().get("theme") == "oscuro")
    check("Oscuro: barra de título oscura (DWMWA 20)", startup.titlebar_is_dark(app._hwnd()) is True)
    check("Oscuro: lienzo del inicio con fondo oscuro",
          home.canvas.cget("bg").upper() == theme.DARK["BG_PRIMARY"])
    check("Oscuro: tarjetas redibujadas con la superficie oscura",
          home.canvas.itemcget(home.cards[0]["bg"], "image") == str(home._card_image(*home.cards[0]["size"], 0)))
    check("Oscuro: barra lateral oscura",
          app._nav._parent_canvas.cget("bg").upper() == theme.DARK["SIDEBAR_BG"])
    check("Oscuro: logotipo con texto claro (variante oscura cargada)",
          app._wordmark is not None and app._wordmark._dark_image is not app._wordmark._light_image)
    grab("dark_home")


@step
def t_light():
    app.set_theme("claro", animate=False)
    settle()
    home = app._views["home"].grid_view
    check("Claro: modo de customtkinter", ctk.get_appearance_mode() == "Light")
    check("Claro: barra de título clara", startup.titlebar_is_dark(app._hwnd()) is False)
    check("Claro: lienzo del inicio claro", home.canvas.cget("bg").upper() == theme.LIGHT["BG_PRIMARY"])
    check("Claro: se guarda en settings.json", Settings().get("theme") == "claro")
    grab("light_home")


@step
def t_system_live():
    real = theme.system_prefers_dark
    app.set_theme("sistema", animate=False)
    settle()
    want = "Dark" if real() else "Light"
    check("Sistema: aplica la preferencia de Windows", ctk.get_appearance_mode() == want)
    # Windows cambia de modo con la app abierta: se sigue en vivo (sondeo cada 1,5 s)
    theme.system_prefers_dark = lambda: not real()
    app._fake_until = time.time() + 4
    flipped = "Light" if want == "Dark" else "Dark"
    app._sys_restore = real
    app._sys_flipped = flipped
    return lambda: ctk.get_appearance_mode() == flipped


@step
def t_system_live_check():
    check("Sistema: sigue en vivo el cambio de Windows", ctk.get_appearance_mode() == app._sys_flipped)
    theme.system_prefers_dark = app._sys_restore
    app.set_theme("oscuro", animate=False)
    check("Oscuro: no sigue a Windows",
          (app._poll_system_theme() or True) and ctk.get_appearance_mode() == "Dark")


@step
def t_crossfade():
    app.lift()
    app.focus_force()
    settle(200)
    before = len([w for w in app.winfo_children() if isinstance(w, tk.Toplevel)])
    app.set_theme("claro", animate=True)
    covers = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
    app._covers_during = len(covers) - before
    return lambda: not [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]


@step
def t_crossfade_check():
    check("cambio de tema con fundido (captura que se desvanece)",
          ctk.get_appearance_mode() == "Light" and app._covers_during in (0, 1),
          f"capas={app._covers_during}")
    check("el fundido no deja ventanas abiertas",
          not [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)])
    app.set_theme("oscuro", animate=False)


# =============================================================== AUDITORÍA EN OSCURO
PAPER_OK = set()


def allowed(widget, v):
    w = widget
    while w is not None:
        cls = type(w).__name__
        if cls == "ColorSwatches":
            return True
        if getattr(v, "pad", None) is w or w in (getattr(v, "type_preview", None),
                                                 getattr(v, "image_preview", None)):
            return True
        w = getattr(w, "master", None)
    return False


def audit(v, label):
    bad = []
    stack = [v]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if allowed(w, v):
            continue
        if isinstance(w, (ctk.CTkBaseClass, ctk.CTkScrollableFrame)):
            for attr in ("fg_color", "bg_color", "border_color"):
                try:
                    c = w.cget(attr)
                except Exception:
                    continue
                c = theme.resolve(c)
                if isinstance(c, str) and c.startswith("#") and lum(c) > 0.55:
                    bad.append(f"{type(w).__name__}.{attr}={c}")
        elif isinstance(w, (tk.Canvas, tk.Text, tk.Frame, tk.Label)):
            try:
                c = w.cget("bg")
            except tk.TclError:
                continue
            if lum(c) > 0.55:
                bad.append(f"{type(w).__name__}({w}).bg={c}")
    check(f"oscuro sin colores claros fijos: {label}", not bad, "; ".join(sorted(set(bad))[:4]))


ALL_KEYS = [k for _c, _col, tools in app.categories for k, *_ in tools]


@step
def t_audit_all_views():
    app.set_theme("oscuro", animate=False)
    for key in ["home"] + ALL_KEYS:
        v = view(key)
        audit(v, key)
        grab(f"dark_{key}")
    app.show_view("home")


@step
def t_contrast():
    d = theme.DARK
    pairs = [("texto principal", d["TEXT_PRIMARY"], d["BG_PRIMARY"]),
             ("texto secundario", d["TEXT_SECONDARY"], d["BG_PRIMARY"]),
             ("texto en tarjeta", d["TEXT_PRIMARY"], d["SURFACE"]),
             ("éxito", d["SUCCESS"], d["SUCCESS_BG"]), ("advertencia", d["WARNING"], d["WARNING_BG"]),
             ("error", d["ERROR"], d["ERROR_BG"]), ("info", d["INFO"], d["INFO_BG"]),
             ("ítem activo de la barra", d["SIDEBAR_ACTIVE"], d["SIDEBAR_ACTIVE_BG"]),
             ("texto en barra de estado", d["TEXT_SECONDARY"], d["BG_SECONDARY"])]
    low = [f"{n} {contrast(a, b):.1f}" for n, a, b in pairs if contrast(a, b) < 4.5]
    check("contraste WCAG AA (≥4,5) de los textos en oscuro", not low, ", ".join(low))
    ui = contrast(d["ACCENT"], d["BG_PRIMARY"])
    check("acento sobre el fondo oscuro: ≥3 (componentes)", ui >= 3, f"{ui:.1f}")
    log.append(f"  INFO  texto blanco sobre botón rojo: oscuro "
               f"{contrast(d['TEXT_ON_ACCENT'], d['ACCENT']):.1f}, claro "
               f"{contrast(theme.LIGHT['TEXT_ON_ACCENT'], theme.LIGHT['ACCENT']):.1f}")


# ---- vistas con contenido en oscuro: editor, comparar, ordenar, zona de arrastre, avisos
@step
def t_editor_dark():
    v = view("edit")
    v.picker.add_files([str(pdf3)])
    return lambda: v.ed_image is not None and v._model()


@step
def t_editor_dark_shot():
    v = app._views["edit"]
    uid = v._model()["lines"][0]["id"]
    v._select(uid)
    v._toggle_layers()
    settle(300)
    check("editor oscuro: lienzo y miniaturas con fondo del tema",
          v.ed_canvas.cget("bg").upper() == theme.DARK["CANVAS_BG"]
          and v.ed_thumb_canvas.cget("bg").upper() == theme.DARK["SURFACE"])
    audit(v, "editor con PDF, selección y capas")
    grab("dark_editor_seleccion")
    v._toggle_layers()


@step
def t_compare_dark():
    v = view("compare")
    v.pickers[0].add_files([str(pdf3)])
    v.pickers[1].add_files([str(pdf3b)])
    v.run()
    return lambda: not v._running


@step
def t_compare_dark_shot():
    v = app._views["compare"]
    tag_bg = v.texts[0].tag_cget("removed", "background")
    check("comparar oscuro: colores de diferencias del tema", tag_bg.upper() == theme.DARK["ERROR_BG"],
          tag_bg)
    grab("dark_compare_resultados")
    app.set_theme("claro", animate=False)
    settle(150)
    check("comparar: los colores cambian con el tema sin reconstruir",
          v.texts[0].tag_cget("removed", "background").upper() == theme.LIGHT["ERROR_BG"])
    app.set_theme("oscuro", animate=False)


@step
def t_progress_toast_error():
    v = view("merge")
    v.picker.add_files([str(pdf3), str(pdf3b)])
    v._progress_value = 0
    v.set_progress(0.6)
    v.show_error("Este es un mensaje de error de ejemplo.")
    app.toasts.show("success", "Se guardó el archivo de ejemplo.")
    v.picker._drag_over = True
    v.picker._pulse = 0.6
    v.picker._draw_zone()
    settle(450)
    audit(v, "unir con lista, progreso y error")
    check("toast con superficie oscura",
          all(theme.resolve(t.cget("fg_color")) == theme.DARK["SURFACE"] for t in app.toasts.toasts))
    grab("dark_progreso_error_toast_zona")
    v.picker._drag_over = False
    v.picker._draw_zone()


@step
def t_dialog():
    dialog = view("redact")._text_dialog()   # el mismo diálogo que abre la herramienta Texto
    app._dialog = dialog
    return lambda: dialog.winfo_viewable()


@step
def t_dialog_shot():
    d = app._dialog
    settle(500)
    x, y = d.winfo_rootx(), d.winfo_rooty()
    ImageGrab.grab(bbox=(x - 1, y - 31, x + d.winfo_width() + 1, y + d.winfo_height() + 1),
                   all_screens=True).save(SHOTS / "dark_dialogo.png")
    check("diálogo con la paleta oscura de la app",
          theme.resolve(d.cget("fg_color")) == theme.DARK["BG_PRIMARY"])
    d.destroy()


# =============================================================== DESPLAZAMIENTO
@step
def s_wheel_notch():
    app.show_view("home")
    settle(300)
    grid = app._views["home"].grid_view
    grid.canvas.yview_moveto(0)
    settle(100)
    start = grid.canvas.canvasy(0)
    wheel(grid.canvas, -120)
    settle(400)
    moved = grid.canvas.canvasy(0) - start
    check("rueda: ~120 px por muesca en el inicio", 110 <= moved <= 130, f"{moved:.0f} px")


@step
def s_wheel_accel():
    grid = app._views["home"].grid_view
    grid.canvas.yview_moveto(0)
    settle(250)
    start = grid.canvas.canvasy(0)
    for _ in range(4):
        wheel(grid.canvas, -120)
        app.update()
        time.sleep(0.03)
    settle(450)
    moved = grid.canvas.canvasy(0) - start
    check("rueda: muescas seguidas aceleran (más de 4 × 120 px)", moved > 4 * 120 + 40, f"{moved:.0f} px")


@step
def s_wheel_under_cursor():
    grid = app._views["home"].grid_view
    grid.canvas.yview_moveto(0)
    nav = app._nav
    nav._parent_canvas.yview_moveto(0)
    settle(250)
    home_before, nav_before = grid.canvas.canvasy(0), nav._parent_canvas.canvasy(0)
    item = app._nav_items["merge"]
    wheel(item, -120, x=20, y=10)
    settle(400)
    check("rueda: mueve la zona bajo el cursor (barra lateral, no el inicio)",
          nav._parent_canvas.canvasy(0) > nav_before and grid.canvas.canvasy(0) == home_before,
          f"barra {nav._parent_canvas.canvasy(0) - nav_before:.0f} px, inicio "
          f"{grid.canvas.canvasy(0) - home_before:.0f} px")
    nav._parent_canvas.yview_moveto(0)


@step
def s_touchpad():
    grid = app._views["home"].grid_view
    grid.canvas.yview_moveto(0)
    settle(200)
    start = grid.canvas.canvasy(0)
    for _ in range(12):
        wheel(grid.canvas, -10)
        app.update()
    settle(400)
    moved = grid.canvas.canvasy(0) - start
    check("touchpad: deltas pequeños no se redondean a cero (12 × 10 = 120 px)",
          100 <= moved <= 140, f"{moved:.0f} px")


@step
def s_reduce_motion():
    grid = app._views["home"].grid_view
    app._reduce.select()
    app._toggle_motion()
    grid.canvas.yview_moveto(0)
    settle(150)
    start = grid.canvas.canvasy(0)
    wheel(grid.canvas, -120)
    app.update_idletasks()
    moved = grid.canvas.canvasy(0) - start
    check("Reducir animaciones: la rueda salta sin suavizado", moved >= 110, f"{moved:.0f} px")
    app._reduce.deselect()
    app._toggle_motion()


@step
def s_hover_paused():
    grid = app._views["home"].grid_view
    grid.canvas.yview_moveto(0)
    settle(300)
    card = grid.cards[0]
    grid._set_hover(card)
    settle(200)
    wheel(grid.canvas, -120)
    app.update()
    scrolling_now = anim.is_scrolling()
    settle(60)
    check("hover en pausa durante el desplazamiento",
          scrolling_now and grid._hover is None and card["frame"] == 0)
    x0, y0, x1, y1 = card["box"]
    ev = type("E", (), {"x": 30, "y": int(y0 - grid.canvas.canvasy(0)) + 30})()
    grid._motion(ev)
    check("no arranca un fundido de hover mientras se desplaza", grid._hover is None)
    settle(500)
    check("terminado el desplazamiento ya no está en pausa", not anim.is_scrolling())


@step
def s_drag_coalesced():
    grid = app._views["home"].grid_view
    grid.canvas.yview_moveto(0)
    settle(250)
    sb, scroller = grid.scrollbar, grid.scroller
    sb._motion_center_offset = 0
    moves_before = scroller.moves
    h = sb._canvas.winfo_height()
    for i in range(40):
        sb._canvas.event_generate("<B1-Motion>", x=4, y=int(30 + (h - 60) * i / 39), when="tail")
    settle(200)
    applied = scroller.moves - moves_before
    check("arrastre de la barra: 40 movimientos del mouse → pocos redibujados (uno por cuadro)",
          1 <= applied <= 4, f"{applied} redibujado(s)")
    check("arrastre de la barra: llega a la posición final", grid.canvas.yview()[1] > 0.99,
          f"{grid.canvas.yview()}")
    grid.canvas.yview_moveto(0)


@step
def s_shift_wheel():
    v = view("compare")
    v._fill_texts([("x" * 400, "equal", "y" * 400, "equal")] * 5)
    settle(150)
    left, right = v.texts
    left.xview_moveto(0)
    settle(100)
    wheel(left, -120, shift=True)
    settle(400)
    check("Mayús+rueda: desplaza en horizontal (y la otra columna la sigue)",
          left.xview()[0] > 0 and abs(right.xview()[0] - left.xview()[0]) < 0.02,
          f"A={left.xview()[0]:.3f} B={right.xview()[0]:.3f}")


@step
def s_compare_sync_wheel():
    v = app._views["compare"]
    v._fill_texts([(f"línea {i}", "equal", f"línea {i}", "equal") for i in range(300)])
    settle(100)
    left, right = v.texts
    wheel(right, -120, x=30, y=30)
    settle(400)
    check("comparar: la rueda sobre la columna B desplaza las dos juntas",
          left.yview()[0] > 0 and abs(left.yview()[0] - right.yview()[0]) < 0.01,
          f"A={left.yview()[0]:.3f} B={right.yview()[0]:.3f}")


@step
def s_lazy_organize():
    v = view("organize")
    v.picker.add_files([str(pdf50)])
    app._t_org = time.perf_counter()
    return lambda: len(v.order) == 50 and len(v._photos) > 0 and not v._loading


@step
def s_lazy_organize_check():
    v = app._views["organize"]
    first = len(v._photos)
    check("ordenar: solo genera las miniaturas cercanas a lo visible", 0 < first < 50,
          f"{first} de 50 al abrir")
    v.canvas.yview_moveto(1.0)
    v.scroller._moved()
    return lambda: 49 in v._photos


@step
def s_lazy_organize_end():
    v = app._views["organize"]
    check("ordenar: al desplazar se cargan las del final (y quedan en caché)",
          49 in v._photos and 0 in v._photos, f"{len(v._photos)} en caché")
    grab("dark_ordenar_50_paginas")


@step
def s_lazy_editor():
    v = view("edit")
    v.picker.add_files([str(pdf50)])
    return lambda: v.ed_session is not None and v.ed_image is not None and v.ed_thumbs \
        and not v.ed_thumbs_loading


@step
def s_lazy_editor_check():
    v = app._views["edit"]
    check("editor: miniaturas diferidas", 0 < len(v.ed_thumbs) < 50, f"{len(v.ed_thumbs)} de 50")
    v.ed_thumb_canvas.yview_moveto(1.0)
    v.ed_thumb_scroller._moved()
    return lambda: 49 in v.ed_thumbs


@step
def s_lazy_editor_end():
    v = app._views["edit"]
    check("editor: al desplazar las miniaturas se cargan las siguientes", 49 in v.ed_thumbs)
    start = v.ed_canvas.canvasy(0)
    v._zoom_step(1)
    v._zoom_step(1)
    return lambda: v.ed_image is not None and v.ed_scale > 1.4


@step
def s_editor_wheel():
    v = app._views["edit"]
    settle(300)
    v.ed_canvas.yview_moveto(0)
    v.ed_canvas.xview_moveto(0)
    settle(100)
    wheel(v.ed_canvas, -120, x=200, y=200)
    settle(400)
    y = v.ed_canvas.canvasy(0)
    wheel(v.ed_canvas, -120, x=200, y=200, shift=True)
    settle(400)
    x = v.ed_canvas.canvasx(0)
    check("editor: rueda vertical y Mayús+rueda horizontal sobre la página", y > 100 and x > 50,
          f"y={y:.0f} x={x:.0f}")
    zoom = v.ed_zoom
    v.ed_canvas.event_generate("<MouseWheel>", delta=120, x=200, y=200, state=0x4)
    settle(200)
    check("editor: Ctrl+rueda sigue haciendo zoom", v.ed_zoom != zoom, f"{zoom} -> {v.ed_zoom}")


@step
def s_no_errors():
    check("sin excepciones en la interfaz", not errors, "; ".join(errors[:3]))


def finish():
    app.destroy()


app.after(900, run_steps)
app.after(600000, app.destroy)
try:
    app.mainloop()
finally:
    if backup is not None:
        SETTINGS.write_bytes(backup)
print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK — capturas en {SHOTS}")
sys.exit(0 if results and all(results) else 1)
