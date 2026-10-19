"""v1.3.7: foco y borrado en el editor, con clics y teclas reales del sistema (SendInput).

Usa los mismos casos que la autoprueba del exe (ui/selftest.py · _input_checks) y agrega
uno más estricto: la ventana al frente es de OTRO proceso y se hace doble clic apenas
aparece la página."""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from reportlab.pdfgen import canvas as rl_canvas  # noqa: E402

from ui import selftest  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="pliegue_v137_"))
SETTINGS = __import__("core.paths").paths.settings_file()
backup = SETTINGS.read_bytes() if SETTINGS.exists() else None
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def skipped(name, reason):
    """Otra app se puso en el camino: no se mandó el clic o la tecla (no cuenta como falla)."""
    log.append(f"  OMITIDA  {name}  [{reason}]")


pdf = TMP / "simple.pdf"
c = rl_canvas.Canvas(str(pdf), pagesize=(595, 842))
c.setFont("Helvetica-Bold", 16)
c.drawString(72, 700, "CARRERA: INGENIERIA EN SISTEMAS")
c.setFont("Helvetica", 12)
c.drawString(72, 660, "Texto de prueba normal")
c.save()

from ui.app import App  # noqa: E402

app = App()
app.geometry("1320x840+40+40")
app.attributes("-topmost", True)


def run():
    d = selftest._Driver(app)
    v = d.v
    # ventana de otro proceso al frente; doble clic real apenas se ve la página
    # otra app de verdad: un Python aparte (dentro del exe, sys.executable es Pliegue.exe)
    python = sys.executable if not getattr(sys, "frozen", False) else (shutil.which("py") or "py")
    other = subprocess.Popen([python] + (["-3.11"] if python.lower().endswith("py.exe") else []) + ["-c",
                              "import tkinter as t; r=t.Tk(); r.title('otra app'); "
                              "r.geometry('240x90+1100+60'); r.attributes('-topmost', True); "
                              "r.after(100, r.focus_force); r.after(8000, r.destroy); r.mainloop()"])
    time.sleep(1.5)
    ok = d.open(pdf, TMP, "proceso", settle_ms=0)
    line = selftest._pick_line(v._model(), "CARRERA")
    x, y = selftest._screen_point(v, line)
    import ctypes

    foreground_is_app = ctypes.windll.user32.GetForegroundWindow() == int(app.wm_frame(), 16)
    check("PDF abierto", ok)
    try:
        selftest._mouse(x, y, clicks=2)
        d.wait(lambda: v.ed_editor is not None, 3)
        d.settle(300)
        check("al empezar, la ventana de Pliegue no estaba activa", not foreground_is_app)
        check("doble clic con otra app al frente: abre el editor al primer intento",
              v.ed_editor is not None and v.ed_editor[1] == line["id"])
        check("el editor tiene el foco del teclado", v.ed_editor is not None and app.focus_get() is v.ed_editor[0])
        if v.ed_editor:
            selftest._key("Escape")
            d.settle(300)
    except selftest.OtherAppInTheWay as exc:
        skipped("doble clic con otra app al frente", exc)
    other.kill()

    for r in selftest._input_checks(app, pdf, TMP, "CARRERA"):
        if r.get("omitida"):
            skipped(r["modo"], r["omitida"])
            continue
        detail = {k: val for k, val in r.items() if k not in ("pdf", "modo", "ok")}
        check(r["modo"], r.get("ok"), str(detail)[:300])
    app.destroy()


app.after(800, run)
app.after(240000, app.destroy)
try:
    app.mainloop()
finally:
    if backup is not None:
        SETTINGS.write_bytes(backup)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK — {TMP}")
sys.exit(0 if results and all(results) else 1)
