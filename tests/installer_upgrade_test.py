"""Instalador 1.3.7 (carpeta) sobre una instalación de una versión de un solo archivo (≤1.3.6).

NO toca la instalación del usuario: compila variantes de installer.iss con OTRO AppId y
otro nombre ("PDFKit Prueba"), instala por usuario en una carpeta temporal, verifica y
desinstala esa copia de prueba con su propio desinstalador.

    python tests\\installer_upgrade_test.py [exe_de_un_solo_archivo_1.3.6]

Comprueba: la versión vieja queda reemplazada en el mismo lugar (PDFKit.exe + _internal\\),
una sola entrada en "Agregar o quitar programas" con la versión nueva, accesos directos
(menú Inicio y Escritorio) apuntando al PDFKit.exe nuevo con su icono, que la app abre
desde el acceso directo del Escritorio (y cuánto tarda, en frío y en tibio) y que la
desinstalación no deja nada.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import measure_startup  # noqa: E402

ISCC = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Inno Setup 6" / "ISCC.exe"
TEST_ID = "{{3B1F6C2A-9D4E-4F7A-8C21-5E0D7A9B4C66}"
TEST_NAME = "PDFKit Prueba"
OLD_EXE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tests" / "_capturas" / "PDFKit_1.3.6_onefile.exe"
WORK = Path(tempfile.mkdtemp(prefix="pdfkit_instalador_", dir=ROOT / "tests" / "_capturas"))
APP_DIR = WORK / "app"
results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def variant(text: str, version: str, out_name: str, old_layout: bool) -> str:
    text = text.replace("AppId={{7E64A9D1-52F3-4C08-B1A4-9D0E6C2F5B83}", f"AppId={TEST_ID}")
    text = text.replace('#define MyAppName "PDFKit"', f'#define MyAppName "{TEST_NAME}"')
    text = re.sub(r'#define MyAppVersion "[^"]+"', f'#define MyAppVersion "{version}"', text)
    text = text.replace("OutputDir=installer", f"OutputDir={WORK}")
    text = text.replace("OutputBaseFilename=PDFKit_Setup", f"OutputBaseFilename={out_name}")
    text = text.replace('Source: "README.md"', f'Source: "{ROOT / "README.md"}"')
    text = text.replace("SetupIconFile=assets\\icon.ico", f"SetupIconFile={ROOT / 'assets' / 'icon.ico'}")
    text = text.replace('Source: "dist\\PDFKit\\', f'Source: "{ROOT / "dist" / "PDFKit"}\\')
    if old_layout:   # como era el instalador de 1.3.6: un solo archivo
        start, end = text.index("[InstallDelete]"), text.index("[Icons]")
        text = (text[:start] + f'[Files]\nSource: "{OLD_EXE}"; DestDir: "{{app}}"; DestName: "PDFKit.exe"; '
                f'Flags: ignoreversion\nSource: "{ROOT / "README.md"}"; DestDir: "{{app}}"; Flags: ignoreversion\n\n'
                + text[end:])
    return text


def build(version, name, old_layout):
    iss = WORK / f"{name}.iss"
    iss.write_text(variant((ROOT / "installer.iss").read_text(encoding="utf-8"), version, name, old_layout),
                   encoding="utf-8")
    proc = subprocess.run([str(ISCC), "/Q", str(iss)], capture_output=True, text=True, cwd=ROOT)
    return WORK / f"{name}.exe", proc


def install(setup):
    return subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                           f"/DIR={APP_DIR}", f"/LOG={WORK / (setup.stem + '.log')}"], timeout=900).returncode


def uninstall_entries():
    found = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                key = winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0,
                                     winreg.KEY_READ | view)
            except OSError:
                continue
            for i in range(winreg.QueryInfoKey(key)[0]):
                sub = winreg.EnumKey(key, i)
                if sub.startswith(TEST_ID[1:]):
                    with winreg.OpenKey(key, sub) as entry:
                        version = winreg.QueryValueEx(entry, "DisplayVersion")[0]
                    found.append((hive, view, sub, version))
    return {(e[2], e[3]) for e in found}


def shortcut(path: Path):
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{path}');"
                          "$s.TargetPath; $s.IconLocation"], capture_output=True, text=True).stdout.split("\n")
    return [line.strip() for line in out if line.strip()]


def desktop() -> Path:
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                         capture_output=True, text=True).stdout.strip()
    return Path(out)


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
settings = Path.home() / ".pdfkit" / "settings.json"
backup = settings.read_bytes() if settings.exists() else None
try:
    old_setup, p1 = build("1.3.6", "prueba_136", old_layout=True)
    new_setup, p2 = build("1.3.7", "prueba_137", old_layout=False)
    check("compilan los dos instaladores de prueba", old_setup.exists() and new_setup.exists(),
          (p1.stdout + p1.stderr + p2.stdout + p2.stderr)[-300:])

    check("instala la versión de un solo archivo (1.3.6)", install(old_setup) == 0)
    old_size = (APP_DIR / "PDFKit.exe").stat().st_size if (APP_DIR / "PDFKit.exe").exists() else 0
    check("1.3.6: un solo PDFKit.exe grande, sin _internal",
          old_size > 100_000_000 and not (APP_DIR / "_internal").exists(), f"{old_size / 1e6:.0f} MB")

    check("instala 1.3.7 encima", install(new_setup) == 0)
    exe = APP_DIR / "PDFKit.exe"
    new_size = exe.stat().st_size if exe.exists() else 0
    check("el PDFKit.exe viejo quedó reemplazado por el de la carpeta (chico)", 0 < new_size < 50_000_000,
          f"{new_size / 1e6:.1f} MB")
    internal = APP_DIR / "_internal"
    check("carpeta Licencias con la AGPL y las de terceros", (APP_DIR / "Licencias" / "LICENSE.txt").exists()
          and (APP_DIR / "Licencias" / "THIRD_PARTY_LICENSES.md").exists()
          and len(list((APP_DIR / "Licencias" / "terceros").rglob("*"))) > 50)
    check("la carpeta _internal está completa", internal.is_dir()
          and len(list(internal.rglob("*"))) > 1000 and (internal / "assets" / "splash.png").exists())
    entries = uninstall_entries()
    check("una sola entrada en Agregar o quitar programas, con la versión nueva",
          len(entries) == 1 and next(iter(entries))[1] == "1.3.7", str(entries))

    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / TEST_NAME
    links = list(start_menu.glob("*.lnk")) if start_menu.exists() else []
    desk = desktop() / f"{TEST_NAME}.lnk"
    for name, link in (("menú Inicio", links[0] if links else None), ("Escritorio", desk)):
        target = shortcut(link) if link and link.exists() else []
        check(f"acceso directo en {name} -> PDFKit.exe nuevo, con su icono",
              len(target) == 2 and Path(target[0]) == exe and str(exe).lower() in target[1].lower(), str(target))

    # abrir desde el acceso directo del Escritorio (como el usuario)
    if desk.exists():
        os.startfile(str(desk))
        found = None
        end = time.time() + 30
        while time.time() < end and not found:
            hwnds = []
            measure_startup._main_window  # noqa: B018  (asegura que el módulo cargó)
            import ctypes
            from ctypes import wintypes

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def callback(hwnd, _):
                title = ctypes.create_unicode_buffer(64)
                ctypes.windll.user32.GetWindowTextW(hwnd, title, 64)
                if title.value == "PDFKit" and ctypes.windll.user32.IsWindowVisible(hwnd):
                    hwnds.append(hwnd)
                return True

            ctypes.windll.user32.EnumWindows(callback, 0)
            found = hwnds[0] if hwnds else None
            time.sleep(0.2)
        check("abre desde el acceso directo del Escritorio", found is not None)
        if found:
            ctypes.windll.user32.PostMessageW(found, 0x0010, 0, 0)
            time.sleep(3)

    # arranque de la copia instalada: el primero tras instalar (frío) y los siguientes (tibio)
    times = [measure_startup.launch(exe) for _ in range(4)]
    for n, (first, visible, usable) in enumerate(times):
        log.append(f"  INFO  arranque {'frío' if n == 0 else 'tibio'} {n + 1}: aviso {first:.2f} s · "
                   f"ventana {visible:.2f} s · usable {usable:.2f} s")
    check("ventana en menos de 2 s y usable en menos de 4 s (tibio)",
          all(t[1] and t[1] < 2 and t[2] and t[2] < 4 for t in times[1:]), str(times[1:]))

    # desinstalar la copia de prueba (solo la de prueba: otro AppId)
    uninstaller = APP_DIR / "unins000.exe"
    subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=600)
    end = time.time() + 60
    while time.time() < end and (exe.exists() or uninstall_entries()):
        time.sleep(1)
    check("la desinstalación de prueba no deja la app, ni entradas, ni accesos directos",
          not exe.exists() and not internal.exists() and not uninstall_entries() and not desk.exists()
          and not (start_menu.exists() and any(start_menu.iterdir())))
finally:
    if backup is not None:
        settings.write_bytes(backup)
    shutil.rmtree(WORK, ignore_errors=True)

print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK")
sys.exit(0 if results and all(results) else 1)
