"""Descarga los componentes de terceros que la app incluye y que NO están en el
repositorio (son grandes y tienen sus propias licencias):

* assets/poppler        Poppler 26.02.0 para Windows (oschwartz10612/poppler-windows) — GPL
* assets/tesseract      Tesseract OCR 5.4.0 (UB-Mannheim) + idiomas eng/spa (tessdata_fast 4.1.0) — Apache-2.0
* assets/weasyprint     WeasyPrint 70.0, ejecutable para Windows (Kozea) — BSD-3-Clause
* assets/fonts/library  30 familias libres de github.com/google/fonts (commit fijo) — OFL/Apache/UFL

    python tools\\fetch_assets.py            (descarga lo que falte)
    python tools\\fetch_assets.py --verificar (solo comprueba lo que ya está)

Todo sale de las fuentes oficiales (ver tools/assets_manifest.json) y se verifica con
SHA-256: el archivo descargado y cada archivo extraído. Si algo no coincide, se detiene
sin dejar archivos a medias. Para abrir el instalador de Tesseract usa 7-Zip, que se
descarga de 7-zip.org y se extrae con `msiexec /a` (no se instala nada en Windows).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ROOT / "build" / "asset_cache"
MANIFEST = json.loads(Path(__file__).with_name("assets_manifest.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, expected: str | None = None) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / url.rstrip("/").split("/")[-1]
    if path.exists() and (expected is None or sha256(path) == expected):
        return path
    print(f"  descargando {url}", flush=True)
    tmp = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "pdfkit-desktop"})
    with urllib.request.urlopen(request, timeout=300) as response, open(tmp, "wb") as out:
        shutil.copyfileobj(response, out)
    if expected is not None and sha256(tmp) != expected:
        tmp.unlink()
        raise SystemExit(f"SHA-256 distinto para {url}: el archivo descargado no es el esperado.")
    tmp.replace(path)
    return path


def place(entries, read) -> None:
    """Escribe cada archivo en assets/ después de comprobar su SHA-256."""
    staged = []
    for entry in entries:
        data = read(entry)
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise SystemExit(f"SHA-256 distinto para {entry['dest']}")
        staged.append((ASSETS / entry["dest"], data))
    for path, data in staged:   # nada se escribe si algún archivo no coincidía
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def missing(entries) -> list:
    return [e for e in entries if not (ASSETS / e["dest"]).exists() or sha256(ASSETS / e["dest"]) != e["sha256"]]


def fetch_zip(name: str) -> None:
    comp = MANIFEST["components"][name]
    todo = missing(comp["files"])
    if not todo:
        return
    archive = download(comp["url"], comp["sha256"])
    with zipfile.ZipFile(archive) as z:
        place(todo, lambda e: z.read(e["member"]))


def seven_zip() -> Path:
    comp = MANIFEST["components"]["7zip"]
    msi = download(comp["url"], comp["sha256"])
    target = CACHE / "7zip"
    exe = next(target.rglob("7z.exe"), None) if target.exists() else None
    if exe is None:
        subprocess.run(["msiexec", "/a", str(msi), "/qn", f"TARGETDIR={target}"], check=True)
        exe = next(target.rglob("7z.exe"))
    return exe


def fetch_tesseract() -> None:
    comp = MANIFEST["components"]["tesseract"]
    todo = missing(comp["files"])
    if todo:
        installer = download(comp["url"], comp["sha256"])
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([str(seven_zip()), "x", "-y", f"-o{tmp}", str(installer)], check=True,
                           capture_output=True)
            place(todo, lambda e: (Path(tmp) / e["member"]).read_bytes())
    for entry in missing(comp["tessdata"]):
        data = download(entry["url"], entry["sha256"]).read_bytes()
        place([entry], lambda _e: data)


def fetch_files(name: str) -> None:
    for entry in missing(MANIFEST["components"][name]["files"]):
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "pdfkit-desktop"})
        data = urllib.request.urlopen(request, timeout=120).read()
        place([entry], lambda _e: data)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    components = MANIFEST["components"]
    if "--verificar" in argv:
        bad = []
        for name, comp in components.items():
            bad += [e["dest"] for e in missing(comp.get("files", []) + comp.get("tessdata", []))]
        print("todo en orden" if not bad else f"{len(bad)} archivo(s) faltan o no coinciden: {bad[:10]}")
        return 1 if bad else 0
    steps = [("Poppler", lambda: fetch_zip("poppler")), ("WeasyPrint", lambda: fetch_zip("weasyprint")),
             ("Tesseract", fetch_tesseract), ("biblioteca de fuentes", lambda: fetch_files("fonts_library"))]
    for label, step in steps:
        print(f"{label}…", flush=True)
        step()
    (ASSETS / "fonts" / "library" / "README.txt").write_text(
        "Fuentes libres incluidas con PDFKit (sin modificar), descargadas de\n"
        "https://github.com/google/fonts. Cada carpeta incluye su licencia\n"
        "(SIL Open Font License 1.1, Apache 2.0 o Ubuntu Font Licence 1.0).\n"
        "El editor de PDF las usa cuando la fuente original de un documento no\n"
        "está instalada en Windows.\n", encoding="utf-8")
    print("Listo: todos los componentes verificados con SHA-256.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
