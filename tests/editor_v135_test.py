"""v1.3.5: ediciones atómicas (verificación al previsualizar y al guardar), texto invisible
sin falsos avisos, errores.log y el bloqueo de Tk por __del__ en hilos de trabajo."""
import sys
import tempfile
import threading
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from core import errors, pdf_editor  # noqa: E402
from core import pdf_textops as tops  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="pliegue_v135_"))
results = []


def check(name, ok, info=""):
    results.append(ok)
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"  [{info}]" if info else ""), flush=True)


def make(path, invisible=False):
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 700, "CARRERA: INGENIERIA EN SISTEMAS")
    t = c.beginText(72, 600)
    t.setFont("Helvetica", 12)
    if invisible:
        t.setTextRenderMode(3)
    t.textLine("Texto oculto de una capa OCR")
    c.drawText(t)
    c.save()


def state_for(session, needle, new):
    line = next(l for l in session.analyze(0)["lines"] if needle in l["text"])
    return line, {"overrides": {line["id"]: {"text": new}}, "added": [], "z": None}


pdf = TMP / "a.pdf"
make(pdf)
s = pdf_editor.EditorSession(pdf)
line, st = state_for(s, "CARRERA", "CARRERA: INGENIERIA EN Prueba")
try:
    s.render_page(0, st, 1.5, verify=[line["id"]])
    check("edición normal: la verificación pasa", True)
except pdf_editor.EditFailed as exc:
    check("edición normal: la verificación pasa", False, str(exc))

# reinserción que no dibuja: se detecta en vista previa y al guardar (sin archivo a medias)
saved = (tops.Rewriter.emit_after, pdf_editor.EditorSession._draw_text)
tops.Rewriter.emit_after = lambda *_a, **_k: None
pdf_editor.EditorSession._draw_text = lambda self, page, unit, overlay: (list(unit["bbox"]), None)
try:
    try:
        s.render_page(0, st, 1.5, verify=[line["id"]])
        check("vista previa: texto que no quedó -> EditFailed", False)
    except pdf_editor.EditFailed as exc:
        check("vista previa: texto que no quedó -> EditFailed", line["id"] in exc.failures, str(exc))
    out = TMP / "no_debe_existir.pdf"
    try:
        s.save(out, {0: st}, [0], {})
        check("guardar: texto que no quedó -> EditFailed", False)
    except pdf_editor.EditFailed:
        check("guardar: texto que no quedó -> EditFailed y no se escribe nada", not out.exists())
    # sin verificar (render normal de otra página o sin ediciones nuevas) no se lanza
    image, _l, _n = s.render_page(0, st, 1.0)
    check("render sin verificación sigue funcionando", image.width > 0)
finally:
    tops.Rewriter.emit_after, pdf_editor.EditorSession._draw_text = saved

# excepción al reinsertar: sale de render_page (el editor la usa para volver al original)
saved_reg = (pdf_editor.EditorSession._register_font, pdf_editor.EditorSession._draw_text,
             tops.Rewriter.emit_after)


def boom(*_a, **_k):
    raise RuntimeError("falla forzada")


pdf_editor.EditorSession._register_font = boom
pdf_editor.EditorSession._draw_text = boom
tops.Rewriter.emit_after = boom
s._font_cache.clear()
try:
    s.render_page(0, st, 1.5, verify=[line["id"]])
    check("falla al reinsertar llega al editor", False)
except RuntimeError as exc:
    check("falla al reinsertar llega al editor", "forzada" in str(exc))
finally:
    (pdf_editor.EditorSession._register_font, pdf_editor.EditorSession._draw_text,
     tops.Rewriter.emit_after) = saved_reg
out = TMP / "bien.pdf"
s.save(out, {0: st}, [0], {})
with fitz.open(out) as d:
    check("después de una falla, guardar normal funciona", "Prueba" in d[0].get_text())
s.close()

# texto invisible (capa OCR, Tr 3): editarlo no es "desaparecer"
inv = TMP / "invisible.pdf"
make(inv, invisible=True)
s = pdf_editor.EditorSession(inv)
line, st = state_for(s, "oculto", "Texto oculto corregido")
try:
    s.render_page(0, st, 1.5, verify=[line["id"]])
    check("texto invisible editado: sin falso aviso", True)
except pdf_editor.EditFailed as exc:
    check("texto invisible editado: sin falso aviso", False, str(exc))
s.save(TMP / "inv_out.pdf", {0: st}, [0], {})
with fitz.open(TMP / "inv_out.pdf") as d:
    check("texto invisible editado se guarda", "corregido" in d[0].get_text())
s.close()

# errores.log: record() escribe la traza completa
errors.setup()
log_file = errors.logs_dir() / "errores.log"
size = log_file.stat().st_size if log_file.exists() else 0
try:
    raise ValueError("prueba de registro v135")
except ValueError:
    errors.record("Prueba del registro")
for h in errors.log.handlers:
    h.flush()
tail = log_file.read_bytes()[size:].decode("utf-8", "replace") if log_file.exists() else ""
check("errores.log guarda contexto y traza", "Prueba del registro" in tail and "Traceback" in tail
      and "prueba de registro v135" in tail)

# __del__ de Tk en un hilo de trabajo: no debe congelar la app
import tkinter as tk  # noqa: E402
import tkinter.font as tkfont  # noqa: E402

from ui import startup  # noqa: E402

startup._tk_cleanup_in_main_thread()
root = tk.Tk()
root.withdraw()
font = tkfont.Font(root=root, family="Arial", size=12)
name = font.name
lock = threading.Lock()
holder = {"font": font}
del font
done = threading.Event()


def worker():
    with lock:
        holder.clear()          # la última referencia muere en este hilo, con el candado tomado
        time.sleep(0.2)
    done.set()


threading.Thread(target=worker, daemon=True).start()
time.sleep(0.05)
start = time.time()
got = lock.acquire(timeout=10)   # el hilo principal espera el candado (como page_size)
check("__del__ de Tk en otro hilo no bloquea", got and time.time() - start < 5,
      f"{time.time() - start:.2f}s")
if got:
    lock.release()
done.wait(5)
check("la fuente queda pendiente de borrar", any(obj.name == name for _f, obj in startup._LATE
                                                 if hasattr(obj, "name")))
startup.flush_tk_cleanup()
check("se borra en el hilo principal", name not in tkfont.names(root))
root.destroy()

print(f"\n{sum(results)}/{len(results)} {'OK' if all(results) else 'FALLAS'} — {TMP}")
sys.exit(0 if all(results) else 1)
