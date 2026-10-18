"""Verificación obligatoria antes de publicar una versión: corre la autoprueba del editor
DENTRO del exe compilado (no desde el código: hay fallas que solo pasan en el exe).

    python tools\\release_check.py [dist\\Pliegue\\Pliegue.exe] [otro.pdf[::texto de la línea] ...]

Siempre prueba un PDF generado sin formularios (Helvetica, sin fuente incrustada); los
PDF que se pasen se prueban sobre copias. Cada uno: edición + Enter en el editor real,
vista previa, guardado y relectura del texto y la fuente; falla forzada al reinsertar
(queda el original y se avisa); reinserción que no dibuja; Enter con el texto vacío; y
con clics y teclas reales (v1.3.7): doble clic recién abierto con la ventana sin foco,
escribir y Retroceso sobre un texto elegido, Supr con «Deshacer», Supr sobre un agregado.
Termina con código 1 si algo falla. La configuración del usuario no se modifica.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _simple_pdf(path: Path) -> None:
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 700, "CARRERA: INGENIERIA EN SISTEMAS")
    c.setFont("Helvetica", 12)
    c.drawString(72, 660, "Texto de prueba normal")
    c.save()


def main(argv: list[str]) -> int:
    exe = Path(argv[0]) if argv and argv[0].lower().endswith(".exe") else ROOT / "dist" / "Pliegue" / "Pliegue.exe"
    pdfs = [a for a in argv if not a.lower().endswith(".exe")]
    if not exe.exists():
        print(f"No existe {exe}: primero ejecuta build.bat")
        return 1
    work = Path(tempfile.mkdtemp(prefix="pliegue_release_"))
    simple = work / "simple.pdf"
    _simple_pdf(simple)
    report = work / "autoprueba.json"
    # datos de la app en una carpeta temporal: no toca la configuración ni los registros reales
    env = dict(os.environ, PLIEGUE_DATA_DIR=str(work / "datos"), PLIEGUE_LEGACY_DIRS="")
    code = subprocess.run([str(exe), "--autotest", str(report), str(simple), *pdfs], env=env,
                          timeout=1800).returncode
    if not report.exists():
        print(f"El exe no escribió el reporte (código {code}). Avance: {report.with_suffix('.log')}")
        return 1
    data = json.loads(report.read_text(encoding="utf-8"))
    print(f"Pliegue {data['version']} ({'exe' if data['congelado'] else 'código'}) — {report}")
    for r in data["resultados"]:
        detail = r.get("error") or r.get("estado") or r.get("texto", "")
        print(f"  {'OK   ' if r.get('ok') else 'FALLA'} {r['pdf']:<28} {r['modo']:<34} {detail}")
    for kind in ("errores", "errores_hilos"):
        for trace in data[kind]:
            print(f"  [{kind}] {trace.strip().splitlines()[-1]}")
    print("RESULTADO:", "OK" if data["ok"] else "FALLA")
    return 0 if data["ok"] and code == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
