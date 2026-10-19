"""Dónde guarda Pliegue sus datos y cómo se mudan los de PDFKit (el nombre anterior).

Todo vive en %LOCALAPPDATA%\\Pliegue: settings.json, logs\\, font_index.json, font_cache\\.
Hasta 1.3.x la app se llamaba PDFKit y usaba %LOCALAPPDATA%\\PDFKit y ~\\.pdfkit\\settings.json;
`migrate()` copia esos datos a la carpeta nueva, comprueba cada archivo (SHA-256) y recién
entonces borra los viejos. Si algo no coincide, el original se conserva y se reintenta en el
próximo inicio. Sin datos viejos no hace nada.

Versión de la Microsoft Store (paquete MSIX): Windows le da una carpeta propia,
%LOCALAPPDATA%\\Packages\\<familia del paquete>\\LocalState, que se borra al desinstalar. Ahí van
sus datos, separados de los de la versión del instalador clásico (las dos pueden convivir).
Al primer inicio solo copia la configuración (settings.json) del Pliegue clásico o de PDFKit,
sin borrar nada: esos datos siguen siendo de la otra instalación.

Para las pruebas: PLIEGUE_DATA_DIR cambia la carpeta de datos y PLIEGUE_LEGACY_DIRS (rutas
separadas por ";", vacío = ninguna) las carpetas viejas a migrar, así nunca tocan los datos
reales del usuario. PLIEGUE_PACKAGE_FAMILY simula (o, vacío, anula) el paquete MSIX.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Pliegue"
FORMER_NAME = "PDFKit"
IMPORT_MARKER = ".configuracion_importada"   # versión de la Store: la importación ya se hizo
_PACKAGE: list = []                           # caché de package_family_name()


def _local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def package_family_name() -> str | None:
    """Familia del paquete MSIX si la app corre empaquetada (Microsoft Store); si no, None."""
    override = os.environ.get("PLIEGUE_PACKAGE_FAMILY")
    if override is not None:
        return override or None
    if not _PACKAGE:
        _PACKAGE.append(_query_package_family())
    return _PACKAGE[0]


def _query_package_family() -> str | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    try:
        query = ctypes.windll.kernel32.GetCurrentPackageFamilyName
    except AttributeError:
        return None
    query.argtypes = [ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR]
    query.restype = wintypes.LONG
    length = wintypes.UINT(0)
    if query(ctypes.byref(length), None) != 122:   # 15700 = APPMODEL_ERROR_NO_PACKAGE: sin paquete
        return None
    buffer = ctypes.create_unicode_buffer(length.value)
    return buffer.value if query(ctypes.byref(length), buffer) == 0 and buffer.value else None


def is_packaged() -> bool:
    return package_family_name() is not None


def data_dir() -> Path:
    override = os.environ.get("PLIEGUE_DATA_DIR")
    if override:
        return Path(override)
    family = package_family_name()
    if family:
        return _local_appdata() / "Packages" / family / "LocalState"
    return _local_appdata() / APP_NAME


def logs_dir() -> Path:
    return data_dir() / "logs"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def legacy_sources() -> list[tuple[Path, str]]:
    """(carpeta vieja, tipo): "datos" = %LOCALAPPDATA%\\PDFKit, "home" = ~\\.pdfkit. Empaquetada,
    primero %LOCALAPPDATA%\\Pliegue (la versión del instalador clásico)."""
    override = os.environ.get("PLIEGUE_LEGACY_DIRS")
    if override is not None:
        out = []
        for raw in filter(None, override.split(";")):
            path = Path(raw)
            out.append((path, "home" if path.name.lower() == ".pdfkit" else "datos"))
        return out
    out = [(_local_appdata() / FORMER_NAME, "datos"), (Path.home() / ".pdfkit", "home")]
    if is_packaged():
        out.insert(0, (_local_appdata() / APP_NAME, "datos"))
    return out


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate() -> list[str]:
    """Muda los datos de PDFKit a Pliegue. Devuelve lo que pasó (para el registro)."""
    if is_packaged():
        return _import_settings()
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


def _import_settings() -> list[str]:
    """Versión de la Store: copia una sola vez la configuración de otra instalación (Pliegue
    clásico o PDFKit) y no borra nada. Si falla, se reintenta en el próximo inicio."""
    target = data_dir()
    marker = target / IMPORT_MARKER
    if marker.exists():
        return []
    notes: list[str] = []
    try:
        dest = target / "settings.json"
        for source, _kind in legacy_sources():
            settings = source / "settings.json"
            if dest.exists() or not settings.is_file():
                continue
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(settings, dest)
            if _sha256(settings) != _sha256(dest):
                dest.unlink()
                raise OSError(f"la copia de {settings} no coincide")
            notes.append(f"Configuración importada de {settings} (el original se conserva)")
            break
        target.mkdir(parents=True, exist_ok=True)
        marker.write_text("", encoding="utf-8")
    except OSError as exc:
        notes.append(f"No se pudo importar la configuración de otra instalación: {exc}")
    return notes
