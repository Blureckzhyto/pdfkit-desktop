"""v1.3.6: contraste del texto blanco en los botones principales (≥4,5:1 en claro y oscuro,
sin tocar el rojo del logo ni los demás acentos) y el campo NOMBRE que vuelve a quedar
vacío (nombre automático) después de guardar bien, pero no después de un error."""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageGrab  # noqa: E402
from reportlab.pdfgen import canvas as rl_canvas  # noqa: E402

from ui import theme  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="pdfkit_v136_"))
SHOTS = Path(__file__).parent / "_capturas" / "shots_v136"
SHOTS.mkdir(parents=True, exist_ok=True)
SETTINGS = Path.home() / ".pdfkit" / "settings.json"
backup = SETTINGS.read_bytes() if SETTINGS.exists() else None
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def luminance(color):
    c = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ------------------------------------------------------------------ paleta
for mode, palette in (("claro", theme.LIGHT), ("oscuro", theme.DARK)):
    white = palette["TEXT_ON_ACCENT"]
    normal, hover = contrast(white, palette["PRIMARY_BG"]), contrast(white, palette["PRIMARY_HOVER"])
    check(f"{mode}: texto blanco sobre el botón principal ≥4,5", normal >= 4.5, f"{normal:.2f}")
    check(f"{mode}: también al pasar el mouse (más oscuro)", hover >= normal, f"{hover:.2f}")
check("el rojo de acento no cambia", (theme.LIGHT["ACCENT"], theme.DARK["ACCENT"]) == ("#E5484D", "#EF5B60"))
check("el rojo de la barra lateral (logo) no cambia",
      (theme.LIGHT["SIDEBAR_ACCENT"], theme.DARK["SIDEBAR_ACCENT"]) == ("#E5484D", "#EF5B60"))
check("botón principal: colores nuevos en el kit",
      theme.BTN_PRIMARY["fg_color"] == ("#D33A3F", "#C9373C")
      and theme.BTN_PRIMARY["hover_color"] == ("#C23338", "#BC3237"), str(theme.BTN_PRIMARY["fg_color"]))

# ------------------------------------------------------------------ interfaz
doc = TMP / "doc.pdf"
c = rl_canvas.Canvas(str(doc))
for i in range(2):
    c.drawString(72, 700, f"Pagina {i + 1}")
    c.showPage()
c.save()

from ui.app import App  # noqa: E402

app = App()
app.geometry("1320x840+40+40")
app.attributes("-topmost", True)
out = TMP / "salida"
out.mkdir()


def wait(cond, timeout=90):
    end = time.time() + timeout
    while not cond() and time.time() < end:
        app.update()
    return cond()


def settle(ms):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        app.update()


def grab(name):
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()),
                   all_screens=True).save(SHOTS / f"{name}.png")


def button_pixel(button):
    """Color real del botón en pantalla (centro de la franja izquierda, sin el texto)."""
    app.update()
    x = button.winfo_rootx() + 14
    y = button.winfo_rooty() + button.winfo_height() // 2
    r, g, b = ImageGrab.grab(bbox=(x, y, x + 1, y + 1), all_screens=True).getpixel((0, 0))[:3]
    return f"#{r:02X}{g:02X}{b:02X}"


def close(a, b, tol=6):
    return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= tol for i in (1, 3, 5))


def run():
    app.show_view("compress")
    v = app._views["compress"]
    v.output_selector.entry.delete(0, "end")
    v.output_selector.entry.insert(0, str(out))
    for mode in ("claro", "oscuro"):
        app.set_theme(mode, animate=False)
        settle(800)
        want = theme.resolve(theme.PRIMARY_BG)
        got = button_pixel(v.run_button)
        check(f"{mode}: el botón «{v.run_button.cget('text')}» se ve con el rojo nuevo", close(got, want),
              f"{got} ≈ {want}")
        check(f"{mode}: la barra de progreso y los casilleros siguen con el acento",
              theme.PROGRESS["progress_color"] == theme.ACCENT and theme.CHECKBOX["fg_color"] == theme.ACCENT)
        grab(f"boton_{mode}")

    # error: el nombre se conserva (el usuario lo va a necesitar al reintentar)
    v.picker.clear()
    v.output_selector.name_entry.insert(0, "Mi reporte")
    v.run()
    wait(lambda: not v._running)
    settle(200)
    check("tras un error el nombre se conserva", v.output_selector.get_name() == "Mi reporte",
          f"{v.status.cget('text')} · {v.output_selector.get_name()!r}")

    # éxito: usa el nombre y el campo vuelve a quedar vacío
    v.picker.add_files([str(doc)])
    v.run()
    wait(lambda: not v._running)
    settle(300)
    check("guardar usa el nombre elegido", (out / "Mi reporte.pdf").exists(), v.status.cget("text"))
    check("después de guardar bien, NOMBRE queda vacío", v.output_selector.get_name() == "")
    entry = v.output_selector.name_entry
    app.focus_set()
    settle(200)
    check("y vuelve a mostrar «Automático»", entry._entry.get() == "Automático", entry._entry.get())
    grab("nombre_vacio")

    # el siguiente archivo recibe el nombre automático
    v.run()
    wait(lambda: not v._running)
    settle(200)
    check("el siguiente archivo usa el nombre automático", (out / "doc_comprimido.pdf").exists(),
          str(sorted(p.name for p in out.iterdir())))
    app.set_theme("sistema", animate=False)
    settle(300)
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
