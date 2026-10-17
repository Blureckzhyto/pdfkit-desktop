"""Rutas a assets/ e imágenes pre-renderizadas de la interfaz."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import customtkinter as ctk


def asset_path(name: str) -> Path:
    """Ruta a un archivo de assets/, válida en código fuente y en el .exe congelado."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / name


def _scaling() -> float:
    """Escala DPI de la ventana (1.0 = 100 %, 1.5 = 150 %, ...)."""
    try:
        return max(ctk.ScalingTracker.window_dpi_scaling_dict.values(), default=1.0)
    except Exception:
        return 1.0


@lru_cache(maxsize=None)
def _open(path: str):
    from PIL import Image

    with Image.open(path) as opened:
        return opened.convert("RGBA")


def _variant(stem: str):
    """PIL de `<stem>@1x.png` / `<stem>@2x.png`: se elige la variante que no necesita
    agrandarse para la escala de la pantalla (sin reescalar en los casos 1x y 2x)."""
    one, two = asset_path(f"{stem}@1x.png"), asset_path(f"{stem}@2x.png")
    source = two if (_scaling() > 1.0 and two.exists()) or not one.exists() else one
    return _open(str(source)) if source.exists() else None


def scaled_image(stem: str, size: tuple[int, int], dark_stem: str | None = None
                 ) -> ctk.CTkImage | None:
    """CTkImage del recurso; si existe `dark_stem`, es la versión del modo oscuro
    (customtkinter la cambia sola al cambiar el tema)."""
    image = _variant(stem)
    if image is None:
        return None
    dark = _variant(dark_stem) if dark_stem else None
    return ctk.CTkImage(light_image=image, dark_image=dark or image, size=size)


def pil_image(stem: str, dark: bool):
    """Imagen PIL del recurso para el modo pedido (para dibujar en lienzos tk)."""
    base, _, size = stem.rpartition("_")
    return (_variant(f"{base}_dark_{size}") if dark else None) or _variant(stem)


def icon(name: str, size: int) -> ctk.CTkImage | None:
    """Icono pre-renderizado de assets/icons (`tool_merge`, `ui_undo`, ...), con su
    variante clara para el modo oscuro (`<nombre>_dark_<tamaño>`) si existe."""
    return scaled_image(f"icons/{name}_{size}", (size, size), f"icons/{name}_dark_{size}")


def logo(stem: str, size: tuple[int, int]) -> ctk.CTkImage | None:
    return scaled_image(f"logo/{stem}", size, f"logo/{stem}_dark")


def load_image(name: str, height: int) -> ctk.CTkImage | None:
    """CTkImage de `height` px de alto, manteniendo la proporción (None si falta)."""
    path = asset_path(name)
    if not path.exists():
        return None
    image = _open(str(path))
    width = max(1, round(height * image.width / image.height))
    return ctk.CTkImage(light_image=image, dark_image=image, size=(width, height))
