"""Prueba de core: miniaturas por página (carga diferida de Ordenar páginas)."""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from core import page_tools

TMP = Path(tempfile.mkdtemp(prefix="pliegue_core131_"))
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


doc = TMP / "mixto.pdf"
c = canvas.Canvas(str(doc))
for size in [(595, 842), (842, 595), (300, 900)] * 10:
    c.setPageSize(size)
    c.drawString(40, 40, "x")
    c.showPage()
c.save()

t0 = time.perf_counter()
thumbs = page_tools.render_page_thumbnails(doc, [0, 1, 2, 29], (112, 150))
elapsed = (time.perf_counter() - t0) * 1000
check("devuelve solo las páginas pedidas", sorted(thumbs) == [0, 1, 2, 29])
check("vertical cabe en 112×150", thumbs[0].width <= 112 and thumbs[0].height <= 150
      and max(thumbs[0].size) >= 149, str(thumbs[0].size))
check("horizontal cabe en 112×150", thumbs[1].width <= 112 and thumbs[1].height <= 150
      and thumbs[1].width >= 111, str(thumbs[1].size))
check("muy alta cabe en 112×150", thumbs[2].height <= 150 and thumbs[2].height >= 149, str(thumbs[2].size))
check("rápido (en proceso)", elapsed < 1500, f"{elapsed:.0f} ms para 4 páginas")
all_thumbs = page_tools.render_thumbnails(doc, 30)
check("render_thumbnails (todas) sigue funcionando", len(all_thumbs) == 30)

enc = TMP / "cifrado.pdf"
w = PdfWriter()
for p in PdfReader(str(doc)).pages[:2]:
    w.add_page(p)
w.encrypt("clave")
with open(enc, "wb") as fh:
    w.write(fh)
try:
    page_tools.render_page_thumbnails(enc, [0])
    check("PDF protegido: error claro", False, "no falló")
except ValueError as exc:
    check("PDF protegido: error claro", "contraseña" in str(exc).lower() or "proteg" in str(exc).lower(),
          str(exc)[:80])

print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK")
sys.exit(0 if all(results) else 1)
