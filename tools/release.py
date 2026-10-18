"""Prepara y (con --publicar) publica una versión de Pliegue en GitHub Releases.

    python tools\\release.py                 # prepara: SHA-256, docs/version.json, notas (no publica nada)
    python tools\\release.py --compilar      # además compila antes (build.bat + Inno Setup)
    python tools\\release.py --publicar      # etiqueta vX.Y.Z y release con gh, sube los archivos

Pasos: (1) usa installer\\Pliegue_Setup.exe (o lo compila con --compilar) y comprueba que sea
de la versión de ui/app.py; (2) calcula su SHA-256 y escribe build\\release\\SHA256SUMS.txt;
(3) actualiza docs/version.json y regenera la página; (4) arma las notas (español e inglés)
desde CHANGELOG.md; (5) con --publicar: commit de docs/, etiqueta, push y `gh release create`.
Nunca publica sin --publicar.

Transición de nombre (PDFKit -> Pliegue, desde 1.4.0): el mismo instalador se sube también
como PDFKit_Setup.exe, así los enlaces viejos a .../releases/latest/download/PDFKit_Setup.exe
siguen funcionando. Los dos nombres van en SHA256SUMS.txt.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import project  # noqa: E402

INSTALLER = ROOT / "installer" / "Pliegue_Setup.exe"
LEGACY_NAMES = ["PDFKit_Setup.exe"]          # mismos bytes, para los enlaces de antes de 1.4.0
OUT = ROOT / "build" / "release"
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def version() -> str:
    return re.search(r'VERSION = "([^"]+)"', (ROOT / "ui" / "app.py").read_text(encoding="utf-8")).group(1)


def installer_version(path: Path) -> str:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"(Get-Item '{path}').VersionInfo.ProductVersion"], capture_output=True, text=True)
    return out.stdout.strip()


def notes(ver: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(ver)}\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not match:
        raise SystemExit(f"CHANGELOG.md no tiene la sección ## {ver}")
    body = match.group(1).strip()
    url = f"https://github.com/{project.GITHUB_USER}/{project.REPO}"
    return (f"{body}\n\n---\n\n"
            f"**Descarga · Download:** `Pliegue_Setup.exe` (Windows 10/11, 64 bits). "
            f"`PDFKit_Setup.exe` es el mismo archivo, para los enlaces anteriores · "
            f"`PDFKit_Setup.exe` is the same file, kept for old links.\n\n"
            f"Si Windows muestra «Windows protegió su PC»: *Más información* → *Ejecutar de todas formas*. "
            f"/ If Windows shows \"Windows protected your PC\": *More info* → *Run anyway*.\n\n"
            f"**SHA-256:** ver / see `SHA256SUMS.txt`.\n\n"
            f"Código fuente con licencia AGPL-3.0 · Source code under AGPL-3.0: {url}\n")


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not project.GITHUB_USER:
        raise SystemExit("Falta core/project.py: GITHUB_USER")
    ver = version()
    if "--compilar" in argv:
        run(["cmd", "/c", str(ROOT / "build.bat")])
        run([str(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Inno Setup 6" / "ISCC.exe"), "installer.iss"])
    if not INSTALLER.exists():
        raise SystemExit(f"No existe {INSTALLER}: usa --compilar")
    found = installer_version(INSTALLER)
    if found != ver:
        raise SystemExit(f"El instalador es la versión {found!r}, pero ui/app.py dice {ver}: vuelve a compilar")

    OUT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(INSTALLER.read_bytes()).hexdigest()
    size_mb = round(INSTALLER.stat().st_size / 1_000_000)
    assets = [INSTALLER]
    for name in LEGACY_NAMES:
        copy = OUT / name
        shutil.copyfile(INSTALLER, copy)
        if hashlib.sha256(copy.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"La copia {name} no coincide con el instalador")
        assets.append(copy)
    sums = OUT / "SHA256SUMS.txt"
    sums.write_text("".join(f"{digest}  {a.name}\n" for a in assets), encoding="utf-8", newline="\n")
    (OUT / "notas.md").write_text(notes(ver), encoding="utf-8", newline="\n")
    info = {"version": ver, "size_mb": size_mb, "sha256": digest,
            "date": datetime.date.today().isoformat(),
            "url": f"https://github.com/{project.GITHUB_USER}/{project.REPO}/releases/download/v{ver}/{INSTALLER.name}"}
    (ROOT / "docs" / "version.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    run([sys.executable, str(ROOT / "tools" / "build_site.py")])
    print(f"\nVersión {ver} · {size_mb} MB · SHA-256 {digest}")
    print("Archivos:", ", ".join(a.name for a in assets), "+ SHA256SUMS.txt")
    print(f"Notas: {OUT / 'notas.md'}")

    if "--publicar" not in argv:
        print("\nNo se publicó nada (usa --publicar).")
        return 0
    tag = f"v{ver}"
    run(["git", "add", "docs"])
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode:
        run(["git", "commit", "-m", f"Página: versión {ver}"])
    run(["git", "tag", "-a", tag, "-m", f"Pliegue {ver}"])
    run(["git", "push", "origin", "HEAD", tag])
    run([GH, "release", "create", tag, *[str(a) for a in assets], str(sums), "--title", f"Pliegue {ver}",
         "--notes-file", str(OUT / "notas.md"), "--latest"])
    print(f"\nPublicado: https://github.com/{project.GITHUB_USER}/{project.REPO}/releases/tag/{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
