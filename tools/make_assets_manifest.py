"""(Mantenimiento) Genera tools/assets_manifest.json a partir de los binarios que hay hoy en
assets/: descarga cada archivo oficial, comprueba su SHA-256 y busca dentro de él cada
archivo de assets/ por su propio SHA-256. Así `tools/fetch_assets.py` reproduce
EXACTAMENTE los mismos archivos en un clon nuevo.

    python tools\\make_assets_manifest.py

Solo hace falta volver a correrlo al actualizar Poppler, Tesseract, WeasyPrint o la
biblioteca de fuentes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ROOT / "build" / "asset_cache"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_font_library  # noqa: E402

SOURCES = {
    "poppler": {
        "url": "https://github.com/oschwartz10612/poppler-windows/releases/download/v26.02.0-0/Release-26.02.0-0.zip",
        "license": "GPL-2.0-or-later", "home": "https://poppler.freedesktop.org/",
    },
    "weasyprint": {
        "url": "https://github.com/Kozea/WeasyPrint/releases/download/v70.0/weasyprint-windows-onedir.zip",
        "license": "BSD-3-Clause", "home": "https://weasyprint.org/",
    },
    "tesseract": {
        "url": "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/"
               "tesseract-ocr-w64-setup-5.4.0.20240606.exe",
        "license": "Apache-2.0", "home": "https://github.com/tesseract-ocr/tesseract",
    },
    "7zip": {   # solo para abrir el instalador NSIS de Tesseract (no se incluye en la app)
        "url": "https://www.7-zip.org/a/7z2501-x64.msi", "license": "LGPL-2.1-or-later",
        "home": "https://www.7-zip.org/",
    },
}
TESSDATA = {   # idiomas de OCR (modelos "fast")
    "eng.traineddata": "https://github.com/tesseract-ocr/tessdata_fast/raw/4.1.0/eng.traineddata",
    "spa.traineddata": "https://github.com/tesseract-ocr/tessdata_fast/raw/4.1.0/spa.traineddata",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / url.rstrip("/").split("/")[-1]
    if not path.exists():
        print("descargando", url, flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "pdfkit-desktop"})
        path.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    return path


def local_files(folder: str) -> dict[str, str]:
    base = ASSETS / folder
    return {p.relative_to(ASSETS).as_posix(): sha256(p.read_bytes()) for p in base.rglob("*") if p.is_file()}


def match(wanted: dict[str, str], members: dict[str, str]) -> tuple[list, list]:
    by_hash: dict[str, list[str]] = {}
    for name, digest in members.items():
        by_hash.setdefault(digest, []).append(name)
    files, missing = [], []
    for dest, digest in sorted(wanted.items()):
        options = by_hash.get(digest, [])
        if not options:
            missing.append(dest)
            continue
        same_name = [o for o in options if o.split("/")[-1] == dest.split("/")[-1]]
        files.append({"dest": dest, "member": (same_name or options)[0], "sha256": digest})
    return files, missing


def zip_members(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as z:
        return {n: sha256(z.read(n)) for n in z.namelist() if not n.endswith("/")}


def seven_zip() -> Path:
    msi = download(SOURCES["7zip"]["url"])
    target = CACHE / "7zip"
    exe = next(target.rglob("7z.exe"), None) if target.exists() else None
    if exe is None:
        subprocess.run(["msiexec", "/a", str(msi), "/qn", f"TARGETDIR={target}"], check=True)
        exe = next(target.rglob("7z.exe"))
    return exe


def main() -> int:
    manifest: dict = {"components": {}, "unmatched": []}
    for name in ("poppler", "weasyprint"):
        archive = download(SOURCES[name]["url"])
        files, missing = match(local_files(name), zip_members(archive))
        manifest["components"][name] = dict(SOURCES[name], kind="zip", sha256=sha256(archive.read_bytes()),
                                            files=files)
        manifest["unmatched"] += missing

    # Tesseract: instalador NSIS -> 7-Zip; los idiomas, de tessdata_fast
    installer = download(SOURCES["tesseract"]["url"])
    extracted = CACHE / "tesseract_setup"
    if not extracted.exists():
        subprocess.run([str(seven_zip()), "x", "-y", f"-o{extracted}", str(installer)], check=True,
                       capture_output=True)
    members = {p.relative_to(extracted).as_posix(): sha256(p.read_bytes())
               for p in extracted.rglob("*") if p.is_file()}
    wanted = local_files("tesseract")
    langs = {k: v for k, v in wanted.items() if k.split("/")[-1] in TESSDATA}
    files, missing = match({k: v for k, v in wanted.items() if k not in langs}, members)
    tessdata = []
    for dest, digest in langs.items():
        data = download(TESSDATA[dest.split("/")[-1]]).read_bytes()
        if sha256(data) == digest:
            tessdata.append({"dest": dest, "url": TESSDATA[dest.split("/")[-1]], "sha256": digest})
        else:
            missing.append(dest)
    manifest["components"]["tesseract"] = dict(SOURCES["tesseract"], kind="nsis",
                                               sha256=sha256(installer.read_bytes()), files=files,
                                               tessdata=tessdata)
    manifest["components"]["7zip"] = dict(SOURCES["7zip"], kind="tool",
                                          sha256=sha256(download(SOURCES["7zip"]["url"]).read_bytes()))
    manifest["unmatched"] += missing

    # biblioteca de fuentes: google/fonts en un commit fijo
    commit = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://api.github.com/repos/google/fonts/commits/main",
        headers={"User-Agent": "pdfkit-desktop"})))["sha"]
    fonts, missing = [], []
    for folder, (src, names, license_name) in fetch_font_library.FAMILIES.items():
        for name in names + ([license_name] if license_name != "apache" else []):
            dest = f"fonts/library/{folder}/{name}"
            local = ASSETS / dest
            url = f"https://raw.githubusercontent.com/google/fonts/{commit}/{src}/{name}"
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pdfkit-desktop"}),
                                          timeout=120).read()
            if local.exists() and sha256(local.read_bytes()) == sha256(data):
                fonts.append({"dest": dest, "url": url, "sha256": sha256(data)})
            else:
                missing.append(dest)
        if license_name == "apache":
            dest = f"fonts/library/{folder}/LICENSE-Apache-2.0.txt"
            fonts.append({"dest": dest, "url": fetch_font_library.APACHE,
                          "sha256": sha256((ASSETS / dest).read_bytes())})
    manifest["components"]["fonts_library"] = {
        "kind": "files", "home": "https://github.com/google/fonts", "commit": commit,
        "license": "OFL-1.1 / Apache-2.0 / UFL-1.0 (ver cada carpeta)", "files": fonts}
    manifest["unmatched"] += missing
    out = Path(__file__).with_name("assets_manifest.json")
    out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {k: len(v.get("files", [])) + len(v.get("tessdata", [])) for k, v in manifest["components"].items()}
    print("archivos por componente:", counts)
    print("sin origen oficial encontrado:", manifest["unmatched"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
