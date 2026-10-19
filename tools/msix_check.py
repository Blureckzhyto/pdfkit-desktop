"""Lista de verificación de la versión de la Microsoft Store, contra el paquete MSIX INSTALADO
(una copia de prueba firmada: ver tools/build_msix.py --firmar-prueba).

    python tools\\msix_check.py [filtro]

Cada prueba corre dentro del paquete (Invoke-CommandInDesktopPackage): con su identidad, su
carpeta de instalación de solo lectura y la virtualización de archivos de Windows. Corre:
  - tests/msix_runtime_test.py (lo propio del paquete: identidad, datos, programas incluidos,
    PDF a JPG, OCR, HTML a PDF, PDF a Excel, fuentes, DPI, barra oscura, arrastrar y soltar);
  - todas las suites de tests/run_all.py;
  - la autoprueba del editor de tools/release_check.py (foco, Supr, Deshacer...).
Las suites usan carpetas de datos de prueba; los resultados quedan en build\\msix_prueba
(fuera de AppData: así se leen igual desde dentro y desde fuera del paquete).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))
from core import project  # noqa: E402
from release_check import _simple_pdf  # noqa: E402
from run_all import SUITES  # noqa: E402

WORK = ROOT / "build" / "msix_prueba"
TESTS = ROOT / "tests"


def powershell(script: str) -> str:
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode:
        raise SystemExit(f"PowerShell falló: {proc.stderr.strip()}")
    return proc.stdout.strip()


def package() -> dict:
    out = powershell(f"Get-AppxPackage -Name '{project.STORE_IDENTITY_NAME}' | "
                     "Select-Object PackageFamilyName, InstallLocation, Version | ConvertTo-Json")
    if not out:
        raise SystemExit("El paquete de Pliegue no está instalado (Add-AppxPackage de la copia firmada).")
    return json.loads(out)


def launch(pkg: dict, args: list[str], env: dict, name: str, timeout: int = 900) -> int | None:
    """Corre Pliegue.exe dentro del paquete y espera a que deje su código de salida."""
    folder = WORK / name
    folder.mkdir(parents=True, exist_ok=True)
    env_file, done = folder / "entorno.json", folder / "fin.txt"
    env_file.write_text(json.dumps(env), encoding="utf-8")
    done.unlink(missing_ok=True)
    full = ["--entorno", str(env_file), "--fin", str(done), *args]
    quoted = " ".join(f'"{a}"' if " " in a else a for a in full).replace("'", "''")
    exe = str(Path(pkg["InstallLocation"]) / "Pliegue.exe")
    powershell(f"Invoke-CommandInDesktopPackage -PackageFamilyName '{pkg['PackageFamilyName']}' "
               f"-AppId Pliegue -Command '{exe}' -Args '{quoted}'")
    limit = time.time() + timeout
    while time.time() < limit:
        if done.exists() and done.read_text(encoding="utf-8").strip():
            return int(done.read_text(encoding="utf-8").strip())
        time.sleep(1)
    return None


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pkg = package()
    print(f"Paquete {pkg['PackageFamilyName']} {pkg['Version']}\n  {pkg['InstallLocation']}\n")
    base_env = {"PYTHONIOENCODING": "utf-8"}
    bad = []
    suites = ["msix_runtime_test"] + SUITES
    wanted = [s for s in suites if not argv or any(a in s for a in argv)]
    for suite in wanted:
        out = WORK / suite / "salida.txt"
        env = dict(base_env)
        if suite != "msix_runtime_test":   # esta usa la carpeta de datos real del paquete
            env.update(PLIEGUE_DATA_DIR=str(WORK / suite / "datos"), PLIEGUE_LEGACY_DIRS="")
        start = time.time()
        code = launch(pkg, ["--run-script", str(TESTS / f"{suite}.py"), "--salida", str(out)], env, suite)
        text = out.read_text(encoding="utf-8", errors="replace").strip() if out.exists() else ""
        last = text.splitlines()[-1] if text else "(sin salida)"
        ok = code == 0
        bad += [] if ok else [suite]
        print(f"{'OK  ' if ok else 'FALLA'}  {suite:<26} {time.time() - start:5.0f} s  {last}", flush=True)
        if suite == "msix_runtime_test" or not ok:
            print("\n".join("      " + line for line in text.splitlines()[:-1] if line.strip()))

    total = len(wanted)
    if not argv or any(a in "autotest" for a in argv):
        total += 1
        folder = WORK / "autotest"
        folder.mkdir(parents=True, exist_ok=True)
        simple, report = folder / "simple.pdf", folder / "autoprueba.json"
        report.unlink(missing_ok=True)
        _simple_pdf(simple)
        env = dict(base_env, PLIEGUE_DATA_DIR=str(folder / "datos"), PLIEGUE_LEGACY_DIRS="")
        code = launch(pkg, ["--autotest", str(report), str(simple)], env, "autotest", timeout=1800)
        data = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
        if data is None:
            bad.append("autotest")
            print(f"FALLA  autoprueba del editor: sin reporte (código {code})")
        else:
            print(f"\nAutoprueba del editor — Pliegue {data['version']} ({'exe' if data['congelado'] else 'código'})")
            for r in data["resultados"]:
                detail = r.get("omitida") or r.get("error") or r.get("estado") or r.get("texto", "")
                mark = "OMITIDA" if r.get("omitida") else ("OK     " if r.get("ok") else "FALLA  ")
                print(f"  {mark} {r['modo']:<52} {str(detail)[:80]}")
            if not (data["ok"] and code == 0):
                bad.append("autotest")
    print(f"\n{total - len(bad)}/{total} OK" + (f" — fallaron: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
