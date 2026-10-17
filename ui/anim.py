"""Animaciones livianas para Tk: interpolaciones con after(), easing ease-out
cubic, ~60 fps y cancelación de lo pendiente.

Todo corre en el hilo de la interfaz y cada cuadro hace muy poco trabajo, así
que nunca bloquea. Con `set_enabled(False)` ("Reducir animaciones") cada
animación salta directamente a su estado final.
"""
from __future__ import annotations

import time
import tkinter as tk

FRAME_MS = 16
ENABLED = True
SCROLL_QUIET_S = 0.15     # los efectos de hover esperan esto tras el último desplazamiento
_pending: dict[tuple[int, str], str] = {}
_scroll_until = 0.0


def set_enabled(enabled: bool) -> None:
    global ENABLED
    ENABLED = enabled


def note_scroll() -> None:
    """Lo llama el motor de desplazamiento en cada movimiento: mientras dura (y
    150 ms después) no arranca ningún efecto de hover."""
    global _scroll_until
    _scroll_until = time.perf_counter() + SCROLL_QUIET_S


def is_scrolling() -> bool:
    return time.perf_counter() < _scroll_until


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def cancel(widget, key: str) -> None:
    after_id = _pending.pop((id(widget), key), None)
    if after_id:
        try:
            widget.after_cancel(after_id)
        except tk.TclError:
            pass


def animate(widget, key: str, duration_ms: int, step, done=None) -> None:
    """Llama a step(t) con t de 0 a 1 (ya suavizado) durante `duration_ms`.
    Una animación nueva con la misma clave reemplaza a la anterior."""
    cancel(widget, key)
    if not ENABLED or duration_ms <= 0:
        _safe(step, 1.0)
        if done:
            done()
        return
    start = time.perf_counter()

    def tick():
        _pending.pop((id(widget), key), None)
        t = min(1.0, (time.perf_counter() - start) * 1000 / duration_ms)
        if not _safe(step, ease_out_cubic(t)):
            return
        if t < 1.0:
            try:
                _pending[(id(widget), key)] = widget.after(FRAME_MS, tick)
            except tk.TclError:
                pass
        elif done:
            done()

    tick()


def _safe(step, t) -> bool:
    try:
        step(t)
        return True
    except tk.TclError:  # el widget se destruyó a mitad de la animación
        return False


# --------------------------------------------------------------------------- colores
# Los colores pueden ser un hex o un par (claro, oscuro) del tema. Las mezclas se
# calculan con el hex del modo actual y el último cuadro de cada animación deja el
# valor original (el par), así un cambio de tema posterior lo recolorea bien.

def _hex(color) -> str:
    if isinstance(color, (tuple, list)):
        from ui import theme
        return theme.resolve(color)
    return color


def _rgb(color) -> tuple[int, int, int]:
    color = _hex(color).lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def mix(start, end, t: float) -> str:
    a, b = _rgb(start), _rgb(end)
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def darken(color, amount: float = 0.1) -> str:
    return mix(color, "#000000", amount)


def solid_bg(widget):
    """Color de fondo real detrás de un widget con fg_color "transparent"."""
    current = widget
    while current is not None:
        try:
            color = current.cget("fg_color")
        except (tk.TclError, ValueError, AttributeError):
            try:
                color = current.cget("bg")
            except tk.TclError:
                color = None
        if isinstance(color, (tuple, list)):
            return tuple(color)
        if color and color != "transparent" and color.startswith("#"):
            return color
        current = current.master
    return "#FFFFFF"


def fade(widget, attr: str, start, end, duration_ms: int = 120, key: str | None = None):
    animate(widget, key or attr, duration_ms,
            lambda t: widget.configure(**{attr: end if t >= 1 else mix(start, end, t)}))


# --------------------------------------------------------------------------- botones

def hover_fade(button, normal=None, hover=None, duration_ms: int = 120) -> None:
    """Reemplaza el hover instantáneo de un CTkButton por un fundido suave y agrega
    una breve respuesta al presionar. No arranca mientras se está desplazando."""
    if getattr(button, "_fx_hover", False):
        return
    normal = normal or button.cget("fg_color")
    hover = hover or button.cget("hover_color")
    if normal == "transparent":
        normal = solid_bg(button.master)
    if not (str(_hex(normal)).startswith("#") and str(_hex(hover)).startswith("#")) \
            or normal == hover:
        return
    button._fx_hover = True
    button.configure(hover=False, fg_color=normal)
    state = {"color": normal, "normal": normal, "hover": hover}

    def go(target, duration=duration_ms):
        start = state["color"]

        def step(t):
            state["color"] = target if t >= 1 else mix(start, target, t)
            button.configure(fg_color=state["color"])

        animate(button, "hover", duration, step)

    def enabled():
        try:
            return button.cget("state") != "disabled"
        except tk.TclError:
            return False

    button.bind("<Enter>", lambda _e: enabled() and not is_scrolling() and go(state["hover"]),
                add="+")
    button.bind("<Leave>", lambda _e: state["color"] != state["normal"] and go(state["normal"]),
                add="+")
    button.bind("<ButtonPress-1>", lambda _e: enabled() and go(darken(state["hover"], 0.12), 60),
                add="+")
    button.bind("<ButtonRelease-1>", lambda _e: go(state["hover"], 90), add="+")
    button._fx_state = state


def set_button_colors(button, normal, hover=None) -> None:
    """Cambia los colores de un botón con fundido ya aplicado (p. ej. al activarlo)."""
    state = getattr(button, "_fx_state", None)
    if state is None:
        button.configure(fg_color=normal, **({"hover_color": hover} if hover else {}))
        return
    state["normal"] = normal
    if hover:
        state["hover"] = hover
    fade(button, "fg_color", state["color"], normal, 150, key="hover")
    state["color"] = normal


def enhance(root) -> None:
    """Aplica el fundido a todos los CTkButton de un árbol de widgets (excepto los
    internos de selectores segmentados y los de color fijo)."""
    import customtkinter as ctk

    stack = [root]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        if isinstance(widget, ctk.CTkButton) and not isinstance(widget.master, ctk.CTkSegmentedButton):
            try:
                if widget.cget("hover"):
                    hover_fade(widget)
            except (tk.TclError, ValueError):
                pass
