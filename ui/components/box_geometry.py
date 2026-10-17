"""Cajas arrastrables y redimensionables por las esquinas (x, y, ancho, alto)."""
from __future__ import annotations

HANDLE = 6  # mitad del lado del tirador, en píxeles de pantalla
CORNERS = ("nw", "ne", "sw", "se")


def corner_points(box) -> dict[str, tuple[float, float]]:
    x, y, w, h = box
    return {"nw": (x, y), "ne": (x + w, y), "sw": (x, y + h), "se": (x + w, y + h)}


def hit_test(box, px: float, py: float, handle: float = HANDLE + 2) -> str | None:
    """'nw'/'ne'/'sw'/'se' sobre un tirador, 'move' dentro de la caja, o None."""
    for name, (cx, cy) in corner_points(box).items():
        if abs(px - cx) <= handle and abs(py - cy) <= handle:
            return name
    x, y, w, h = box
    if x <= px <= x + w and y <= py <= y + h:
        return "move"
    return None


def resize(start_box, corner: str, px: float, py: float, min_w: float = 12):
    """Redimensiona manteniendo la proporción; la esquina opuesta queda fija."""
    x, y, w, h = start_box
    aspect = h / w if w else 1
    fixed_x = x + w if "w" in corner else x
    fixed_y = y + h if "n" in corner else y
    new_w = max(min_w, abs(px - fixed_x))
    new_h = new_w * aspect
    new_x = fixed_x - new_w if "w" in corner else fixed_x
    new_y = fixed_y - new_h if "n" in corner else fixed_y
    return (new_x, new_y, new_w, new_h)


def clamp(box, max_w: float, max_h: float):
    """Mantiene la caja dentro de (0, 0, max_w, max_h), achicándola si hace falta."""
    x, y, w, h = box
    if w > max_w or h > max_h:
        factor = min(max_w / w, max_h / h)
        w, h = w * factor, h * factor
    x = min(max(0, x), max_w - w)
    y = min(max(0, y), max_h - h)
    return (x, y, w, h)


def draw_handles(canvas, box, color, tag: str) -> None:
    from ui.theme import resolve

    color = resolve(color)
    x, y, w, h = box
    canvas.create_rectangle(x, y, x + w, y + h, outline=color, dash=(4, 3), tags=tag)
    for cx, cy in corner_points(box).values():
        canvas.create_rectangle(cx - HANDLE, cy - HANDLE, cx + HANDLE, cy + HANDLE,
                                fill=color, outline="", tags=tag)
