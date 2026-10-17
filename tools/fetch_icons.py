"""Descarga los SVG de Lucide (licencia ISC) que usa la app a tools/lucide_svg/.

Solo se usa durante el desarrollo; la app carga los PNG pre-renderizados por
tools/make_icons.py, nunca SVG en tiempo de ejecución.
"""
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "lucide_svg"

# nombre en la app -> nombre del icono en Lucide (alternativas si cambia el nombre)
ICONS = {
    # herramientas
    "merge": ["merge"], "split": ["split"], "extract": ["file-output"],
    "delete": ["file-minus"], "organize": ["layout-grid"], "compress": ["minimize-2"],
    "repair": ["wrench"], "ocr": ["scan-text"], "jpg2pdf": ["file-image"],
    "word2pdf": ["file-text"], "pptx2pdf": ["presentation"], "excel2pdf": ["sheet", "file-spreadsheet"],
    "html2pdf": ["code-xml", "code"], "pdf2jpg": ["image-down"], "pdf2word": ["file-pen-line", "file-pen"],
    "pdf2pptx": ["monitor-play"], "pdf2excel": ["table-2", "table"], "pdfa": ["archive"],
    "rotate": ["rotate-cw"], "numbers": ["list-ordered"], "watermark": ["stamp"],
    "crop": ["crop"], "edit": ["square-pen", "pen-square"], "forms": ["text-cursor-input"],
    "sign": ["signature"], "protect": ["lock"], "unprotect": ["lock-open", "unlock"],
    "redact": ["eraser"], "compare": ["git-compare"], "imgconvert": ["images"],
    "imgcompress": ["image-minus"],
    # interfaz
    "home": ["house", "home"], "upload": ["upload"], "undo": ["undo-2"], "redo": ["redo-2"],
    "zoom-in": ["zoom-in"], "zoom-out": ["zoom-out"], "fit": ["maximize-2"],
    "layers": ["layers"], "select": ["mouse-pointer-2"], "text": ["type"],
    "highlight": ["highlighter"], "draw": ["pencil"], "image": ["image-plus"],
    "redact-tool": ["square"], "rotate-left": ["rotate-ccw"], "rotate-right": ["rotate-cw"],
    "trash": ["trash-2"], "close": ["x"], "success": ["circle-check", "check-circle-2"],
    "error": ["circle-x", "x-circle"], "warning": ["triangle-alert", "alert-triangle"],
    "info": ["info"], "front": ["bring-to-front"], "back": ["send-to-back"],
    "up": ["arrow-up"], "down": ["arrow-down"], "prev": ["chevron-left"], "next": ["chevron-right"],
    "bold": ["bold"], "italic": ["italic"], "align-left": ["align-left", "text-align-start"],
    "align-center": ["align-center", "text-align-center"],
    "align-right": ["align-right", "text-align-end"],
    "align-justify": ["align-justify", "text-align-justify"], "folder": ["folder-open"],
    "sparkles": ["sparkles"], "sun": ["sun"], "moon": ["moon"], "monitor": ["monitor"],
}


def main():
    version = json.load(urllib.request.urlopen("https://registry.npmjs.org/lucide-static/latest"))["version"]
    base = f"https://cdn.jsdelivr.net/npm/lucide-static@{version}"
    OUT.mkdir(exist_ok=True)
    missing = []
    for name, candidates in ICONS.items():
        for candidate in candidates:
            try:
                data = urllib.request.urlopen(f"{base}/icons/{candidate}.svg").read()
            except Exception:
                continue
            (OUT / f"{name}.svg").write_bytes(data)
            break
        else:
            missing.append(name)
    (OUT / "LICENSE-lucide.txt").write_bytes(urllib.request.urlopen(f"{base}/LICENSE").read())
    (OUT / "VERSION.txt").write_text(f"lucide-static {version}\n", encoding="utf-8")
    print(f"lucide-static {version}: {len(ICONS) - len(missing)}/{len(ICONS)} iconos")
    if missing:
        print("faltan:", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()
