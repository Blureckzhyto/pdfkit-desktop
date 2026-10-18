"""Dónde guarda Pliegue sus datos y cómo se mudan los de PDFKit (el nombre anterior).

Todo vive en %LOCALAPPDATA%\\Pliegue: settings.json, logs\\, font_index.json, font_cache\\.
Hasta 1.3.x la app se llamaba PDFKit y usaba %LOCALAPPDATA%\\PDFKit y ~\\.pdfkit\\settings.json;
`migrate()` copia esos datos a la carpeta nueva, comprueba cada archivo (SHA-256) y recién
entonces borra los viejos. Si algo no coincide, el original se conserva y se reintenta en el
próximo inicio. Sin datos viejos no hace nada.

Para las pruebas: PLIEGUE_DATA_DIR cambia la carpeta de datos y PLIEGUE_LEGACY_DIRS (rutas
separadas por ";", vacío = ninguna) las carpetas viejas a migrar, así nunca tocan los datos
reales del usuario.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

APP_NAME = "Pliegue"
FORMER_NAME = "PDFKit"


def _local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def data_dir() -> Path:
    override = os.environ.get("PLIEGUE_DATA_DIR")
    return Path(override) if override else _local_appdata() / APP_NAME


def logs_dir() -> Path:
    return data_dir() / "logs"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def legacy_sources() -> list[tuple[Path, str]]:
    """(carpeta vieja, tipo): "datos" = %LOCALAPPDATA%\\PDFKit, "home" = ~\\.pdfkit."""
    override = os.environ.get("PLIEGUE_LEGACY_DIRS")
    if override is not None:
        out = []
        for raw in filter(None, override.split(";")):
            path = Path(raw)
            out.append((path, "home" if path.name.lower() == ".pdfkit" else "datos"))
        return out
    return [(_local_appdata() / FORMER_NAME, "datos"), (Path.home() / ".pdfkit", "home")]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate() -> list[str]:
    """Muda los datos de PDFKit a Pliegue. Devuelve lo que pasó (para el registro)."""
    notes: list[str] = []
    target = data_dir()
    for source, kind in legacy_sources():
        if not source.is_dir():
            continue
        try:
            pairs = []
            for file in sorted(p for p in source.rglob("*") if p.is_file()):
                relative = file.relative_to(source)
                if kind == "home":       # ~/.pdfkit/settings.json -> Pliegue/settings.json
                    if relative.as_posix() != "settings.json":
                        continue
                dest = target / relative
                if dest.exists():        # lo nuevo manda: nunca se pisa
                    pairs.append((file, None))
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
                pairs.append((file, dest))
            bad = [str(src) for src, dest in pairs if dest is not None and _sha256(src) != _sha256(dest)]
            if bad:   # se deshacen las copias de esta vez: el próximo inicio copia de nuevo desde el original
                for _src, dest in pairs:
                    if dest is not None and dest.exists():
                        dest.unlink()
                notes.append(f"No se borró {source}: {len(bad)} archivo(s) no coinciden al copiarlos")
                continue
            copied = sum(1 for _s, d in pairs if d is not None)
            if kind == "home":
                settings = source / "settings.json"
                if settings.exists():
                    settings.unlink()
                if not any(source.iterdir()):
                    source.rmdir()
            else:
                shutil.rmtree(source)
            notes.append(f"Datos de {FORMER_NAME} migrados: {copied} archivo(s) de {source} a {target}")
        except OSError as exc:   # p. ej. la versión vieja sigue abierta: se reintenta la próxima vez
            notes.append(f"Migración incompleta desde {source}: {exc}")
    return notes
