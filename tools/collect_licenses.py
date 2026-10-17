"""Reúne los textos de licencia de todo lo que se distribuye con PDFKit en licenses/ y
genera THIRD_PARTY_LICENSES.md (lo usa el instalador: carpeta "Licencias").

    python tools\\collect_licenses.py

* Paquetes de Python: las dependencias (y sus dependencias) de requirements.txt, con la
  licencia que declara cada paquete y los archivos LICENSE/COPYING/NOTICE que trae.
* Python, Tcl/Tk y el cargador de PyInstaller.
* Componentes incluidos en assets/ (Poppler, Tesseract, WeasyPrint, fuentes, iconos).
"""
from __future__ import annotations

import importlib.metadata as md
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "licenses"
BUILD_ONLY = {"pyinstaller", "pefile", "weasyprint"}   # weasyprint: la app usa el ejecutable de assets/
LICENSE_FILE = re.compile(r"(licen[cs]e|copying|notice|authors)", re.I)
MANIFEST = json.loads((ROOT / "tools" / "assets_manifest.json").read_text(encoding="utf-8"))


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements() -> list[str]:
    names = []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            names.append(re.split(r"[\[<>=;! ]", line, 1)[0])
    return names


def closure(names: list[str]) -> dict[str, md.Distribution]:
    seen: dict[str, md.Distribution] = {}
    todo = [n for n in names if norm(n) not in BUILD_ONLY]
    while todo:
        name = todo.pop()
        key = norm(name)
        if key in seen:
            continue
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            continue
        seen[key] = dist
        for req in dist.requires or []:
            if "extra ==" in req and "cv" not in req:   # solo los extras que se usan (camelot[cv])
                continue
            if "sys_platform" in req and "win32" not in req and "nt" not in req:
                continue
            todo.append(re.split(r"[\[<>=;! (]", req, 1)[0])
    return seen


OVERRIDES = {   # comprobado en los archivos de licencia de cada paquete
    "customtkinter": "MIT (archivo LICENSE; los metadatos dicen CC0 por error)",
    "pillow-heif": "BSD-3-Clause (código); el binario para Windows es GPL-2.0 por libheif/x265 "
                   "(ver LICENSES_bundled.txt)",
    "pymupdf": "AGPL-3.0 (o licencia comercial de Artifex)",
}


def license_of(dist: md.Distribution) -> str:
    meta = dist.metadata
    if norm(meta["Name"]) in OVERRIDES:
        return OVERRIDES[norm(meta["Name"])]
    expression = (meta.get("License-Expression") or "").strip()
    if expression:
        return expression
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or []
                   if c.startswith("License ::") and "OSI Approved" != c.split("::")[-1].strip()]
    text = (meta.get("License") or "").strip().splitlines()
    short = text[0][:80] if text and len(text[0]) < 80 else ""
    return " / ".join(dict.fromkeys(classifiers)) or short or "ver archivos de licencia"


def home_of(dist: md.Distribution) -> str:
    meta = dist.metadata
    for url in meta.get_all("Project-URL") or []:
        label, _, link = url.partition(",")
        if any(k in label.lower() for k in ("source", "repository", "code", "github")):
            return link.strip()
    return (meta.get("Home-page") or f"https://pypi.org/project/{meta['Name']}/").strip()


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pdfkit-desktop"}),
                                  timeout=60).read()


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    rows = []
    for key, dist in sorted(closure(requirements()).items()):
        name, version = dist.metadata["Name"], dist.version
        target = OUT / "python" / f"{name}-{version}"
        copied = 0
        for file in dist.files or []:
            if LICENSE_FILE.search(file.name) and ".dist-info" in str(file) or (
                    LICENSE_FILE.search(file.name) and "licenses" in str(file).lower()):
                src = Path(file.locate())
                if src.is_file() and src.stat().st_size < 2_000_000:
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, target / src.name)
                    copied += 1
        if not copied:   # sin archivo: se deja el texto declarado en los metadatos
            target.mkdir(parents=True, exist_ok=True)
            (target / "LICENSE-metadata.txt").write_text(dist.metadata.get("License") or license_of(dist),
                                                          encoding="utf-8")
        rows.append((name, version, license_of(dist), home_of(dist)))

    def put(folder: str, name: str, data: bytes) -> None:
        (OUT / folder).mkdir(parents=True, exist_ok=True)
        (OUT / folder / name).write_bytes(data)

    base = Path(sys.base_prefix)
    put("python-runtime", "LICENSE.txt", (base / "LICENSE.txt").read_bytes())
    tcl = next((base / "tcl").glob("t*8.6/license.terms"), None)
    if tcl:
        put("tcl-tk", "license.terms", tcl.read_bytes())
    import PyInstaller

    put("pyinstaller-bootloader", "COPYING.txt", (Path(PyInstaller.__file__).parent.parent /
                                                  "pyinstaller-6.21.0.dist-info" / "licenses" / "COPYING.txt").read_bytes()
        if (Path(PyInstaller.__file__).parent.parent / "pyinstaller-6.21.0.dist-info" / "licenses" / "COPYING.txt").exists()
        else fetch("https://raw.githubusercontent.com/pyinstaller/pyinstaller/v6.21.0/COPYING.txt"))
    put("poppler", "COPYING", fetch("https://gitlab.freedesktop.org/poppler/poppler/-/raw/poppler-26.02.0/COPYING"))
    put("poppler", "COPYING3", fetch("https://gitlab.freedesktop.org/poppler/poppler/-/raw/poppler-26.02.0/COPYING3"))
    put("weasyprint", "LICENSE", fetch("https://raw.githubusercontent.com/Kozea/WeasyPrint/v70.0/LICENSE"))
    put("tesseract", "LICENSE", (ROOT / "assets" / "tesseract" / "LICENSE-tesseract.txt").read_bytes())
    put("lucide-icons", "LICENSE", (ROOT / "assets" / "icons" / "LICENSE-lucide.txt").read_bytes())
    for font in ("PlusJakartaSans", "Inter", "DancingScript"):
        put("fonts-app", f"{font}-OFL.txt", (ROOT / "assets" / "fonts" / f"{font}-OFL.txt").read_bytes())
    library = ROOT / "assets" / "fonts" / "library"
    for folder in sorted(p for p in library.iterdir() if p.is_dir()):
        for lic in folder.glob("*.txt"):
            put(f"fonts-library/{folder.name}", lic.name, lic.read_bytes())

    python_rows = "\n".join(f"| {n} | {v} | {lic} | {home} |" for n, v, lic, home in rows)
    families = sorted(p.name for p in library.iterdir() if p.is_dir())
    md_text = (ROOT / "tools" / "THIRD_PARTY_LICENSES.template.md").read_text(encoding="utf-8")
    md_text = md_text.replace("{{PYTHON_ROWS}}", python_rows).replace("{{FONT_FAMILIES}}", ", ".join(families))
    md_text = md_text.replace("{{FONTS_COMMIT}}", MANIFEST["components"]["fonts_library"]["commit"])
    (ROOT / "THIRD_PARTY_LICENSES.md").write_text(md_text, encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{len(rows)} paquetes de Python · licenses/ = {size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
