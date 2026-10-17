"""Small shared helpers. No UI imports."""
from __future__ import annotations

import re
from pathlib import Path


def human_size(num_bytes: float) -> str:
    """Format a byte count for humans: 532 B, 1.4 KB, 12.3 MB..."""
    num = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(num)} B"
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def unique_path(path: str | Path) -> Path:
    """Return `path` if free, otherwise `name (1).ext`, `name (2).ext`, ..."""
    path = Path(path)
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}


def clean_filename(name: str) -> str:
    """Nombre válido en Windows a partir de lo que escribió el usuario: los caracteres
    no permitidos se cambian por "_" y se quitan puntos y espacios del final."""
    name = _INVALID.sub("_", name or "").strip().rstrip(". ")
    if name.split(".")[0].lower() in _RESERVED:
        name = "_" + name
    return name[:180]


def named_output(out_dir: str | Path, default_name: str, custom: str | None = None) -> Path:
    """Ruta libre para el archivo de salida: el nombre elegido por el usuario (con la
    extensión que corresponde) o, si no eligió ninguno, `default_name`."""
    default = Path(default_name)
    stem = clean_filename(custom or "")
    if stem.lower().endswith(default.suffix.lower()):
        stem = stem[: -len(default.suffix)].rstrip(". ")
    name = stem + default.suffix if stem else default.name
    return unique_path(Path(out_dir) / name)


def rename_outputs(paths: list[Path], custom: str | None, old_stem: str | None = None) -> list[Path]:
    """Renombra archivos ya creados con el nombre elegido. Uno solo: ese nombre. Varios:
    el nombre + lo que distingue a cada uno (`_parte01`, `_page2`…) o un número."""
    stem = clean_filename(custom or "")
    if not stem or not paths:
        return list(paths)
    renamed = []
    keep_tail = old_stem and all(Path(p).stem.startswith(old_stem) for p in paths)
    for n, path in enumerate(paths, start=1):
        path = Path(path)
        if len(paths) == 1:
            new = stem
        elif keep_tail:
            new = stem + path.stem[len(old_stem):]
        else:
            new = f"{stem}_{n}"
        target = path if path.stem == new else unique_path(path.with_name(new + path.suffix))
        if target != path:
            path.rename(target)
        renamed.append(target)
    return renamed


def hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    """'#ff8800' -> (1.0, 0.53, 0.0), components in 0..1."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def file_size(path: str | Path) -> int:
    return Path(path).stat().st_size
