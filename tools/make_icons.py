"""Pre-renderiza los SVG de Lucide (tools/lucide_svg) a PNG en assets/icons/.

Genera cada icono a 1x y 2x de su tamaño de uso. Se ejecuta solo durante el
desarrollo (usa PyMuPDF para rasterizar el SVG); la app nunca lee SVG.
Nombres: <set>_<nombre>_<tamaño>@<1x|2x>.png; los de interfaz y estado tienen además una
variante para el modo oscuro: <set>_<nombre>_dark_<tamaño>@<1x|2x>.png
"""
import re
import shutil
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "tools" / "lucide_svg"
OUT = ROOT / "assets" / "icons"
sys.path.insert(0, str(ROOT))

TOOL_ICONS = ["merge", "split", "extract", "delete", "organize", "compress", "repair", "ocr",
              "jpg2pdf", "word2pdf", "pptx2pdf", "excel2pdf", "html2pdf", "pdf2jpg", "pdf2word",
              "pdf2pptx", "pdf2excel", "pdfa", "rotate", "numbers", "watermark", "crop", "edit",
              "forms", "sign", "protect", "unprotect", "redact", "compare", "imgconvert",
              "imgcompress"]
TOOL_SIZES = (20, 24)          # cabecera de la vista y tarjetas del inicio
UI_ICONS = ["home", "upload", "undo", "redo", "zoom-in", "zoom-out", "fit", "layers", "select",
            "text", "highlight", "draw", "image", "redact-tool", "rotate-left", "rotate-right",
            "trash", "close", "front", "back", "up", "down", "prev", "next", "bold", "italic",
            "align-left", "align-center", "align-right", "align-justify", "folder", "sparkles",
            "sun", "moon", "monitor"]
UI_SIZES = (18,)
STATE_ICONS = ["success", "error", "warning", "info"]


def render(name: str, color: str, size: int, scale: int, out_name: str) -> None:
    svg = (SVG / f"{name}.svg").read_text(encoding="utf-8")
    svg = svg.replace("currentColor", color)
    svg = re.sub(r'width="\d+"', 'width="24"', svg, count=1)
    svg = re.sub(r'height="\d+"', 'height="24"', svg, count=1)
    doc = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")
    px = size * scale
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(px / 24, px / 24), alpha=True)
    pix.save(str(OUT / out_name))
    doc.close()


def main():
    from ui import theme
    from ui.app import CATEGORIES

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    tool_colors = {key: color for _cat, color, tools in CATEGORIES for key, *_ in tools}
    count = 0
    for key in TOOL_ICONS:
        for size in TOOL_SIZES:
            for scale in (1, 2):
                render(key, tool_colors[key], size, scale, f"tool_{key}_{size}@{scale}x.png")
                count += 1
    light, dark = theme.LIGHT, theme.DARK
    for key in UI_ICONS:
        for size in UI_SIZES:
            for variant, color, dark_color in (
                    ("", light["TEXT_SECONDARY"], dark["TEXT_SECONDARY"]),
                    ("_active", light["ACCENT"], dark["ACCENT"]),
                    ("_white", "#FFFFFF", None)):
                for scale in (1, 2):
                    render(key, color, size, scale, f"ui_{key}{variant}_{size}@{scale}x.png")
                    count += 1
                    if dark_color:
                        render(key, dark_color, size, scale,
                               f"ui_{key}{variant}_dark_{size}@{scale}x.png")
                        count += 1
    for key in STATE_ICONS:
        name = key.upper()
        for scale in (1, 2):
            render(key, light[name], 20, scale, f"state_{key}_20@{scale}x.png")
            render(key, dark[name], 20, scale, f"state_{key}_dark_20@{scale}x.png")
            count += 2
    shutil.copy(SVG / "LICENSE-lucide.txt", OUT / "LICENSE-lucide.txt")
    print(f"{count} PNG generados en {OUT}")


if __name__ == "__main__":
    main()
