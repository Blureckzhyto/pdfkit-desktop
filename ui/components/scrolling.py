"""Motor de desplazamiento compartido por todas las zonas con scroll de la app.

Por qué existe: CTkScrollbar llama a `update_idletasks()` en cada redibujo, o sea en
cada evento de arrastre y otra vez al recibir la nueva posición. Eso fuerza a Tk a
mover y repintar todo el contenido una o dos veces por cada píxel que se mueve el
mouse, y el contenido se queda atrás del cursor. Aquí:

* `ScrollBar`: la misma barra de customtkinter, sin ese repintado forzado y sin
  redibujarse si la posición no cambió.
* `Scroller`: aplica el arrastre de la barra como máximo una vez por cuadro (~16 ms),
  desplaza con la rueda ~120 px por muesca (con aceleración y, si las animaciones
  están activas, un suavizado corto), acumula los deltas pequeños del touchpad y
  avisa a `anim` para que los efectos de hover esperen a que termine el movimiento.
* Un único enrutador de la rueda por ventana: mueve la zona que está bajo el cursor
  (la más cercana que tenga algo que desplazar); Mayús + rueda desplaza en horizontal.
* `ScrollFrame`: reemplazo directo de CTkScrollableFrame que usa todo lo anterior.
"""
from __future__ import annotations

import time
import tkinter as tk

import customtkinter as ctk

from ui import anim, theme

WHEEL_PX = 120            # píxeles por muesca de la rueda (delta 120 en Windows)
ACCEL_WINDOW_S = 0.09     # muescas más seguidas que esto aceleran
ACCEL_STEP = 0.35
ACCEL_MAX = 2.6
SMOOTH_MS = 150
FRAME_MS = 16
NOTIFY_MS = 60            # aviso de "se desplazó" (carga diferida de miniaturas)

_registry: dict[str, "Scroller"] = {}


# --------------------------------------------------------------------------- barra

class ScrollBar(ctk.CTkScrollbar):
    def __init__(self, master, **kwargs):
        for key, value in theme.SCROLLBAR.items():
            kwargs.setdefault(key, value)
        super().__init__(master, **kwargs)
        # customtkinter fuerza aquí un repintado síncrono de toda la ventana
        self._canvas.update_idletasks = lambda: None
        self.scroller: Scroller | None = None

    def set(self, start_value, end_value):
        start, end = float(start_value), float(end_value)
        if abs(start - self._start_value) < 1e-7 and abs(end - self._end_value) < 1e-7:
            return
        super().set(start, end)

    def _mouse_scroll_event(self, event=None):
        if self.scroller is not None and event is not None:
            self.scroller.wheel(event.delta, self._orientation == "horizontal")
            return "break"
        return super()._mouse_scroll_event(event)


# --------------------------------------------------------------------------- motor

class Scroller:
    """Desplazamiento de un tk.Canvas o tk.Text (`target`), con barras opcionales."""

    def __init__(self, target, vbar=None, hbar=None, on_scroll=None):
        self.target = target
        self.on_scroll = on_scroll
        self._is_text = isinstance(target, tk.Text)
        if not self._is_text:
            target.configure(yscrollincrement=1, xscrollincrement=1)
        self._pos = {"y": None, "x": None}        # posición fraccionaria actual (px)
        self._goal = {"y": None, "x": None}       # destino del suavizado (px)
        self._tween = {"y": None, "x": None}      # (inicio, desde, tiempo)
        self._anim_job = None
        self._drag = {}
        self._drag_job = None
        self._last_apply = 0.0
        self._last_notch = (0.0, 0)
        self._streak = 0
        self._notify_job = None
        self.moves = 0                             # movimientos aplicados (para pruebas)
        for bar, axis in ((vbar, "y"), (hbar, "x")):
            if bar is not None:
                self.bind_bar(bar, axis)
        self.alias(target)
        install(target)

    # ---------------------------------------------------------------- conexión
    def alias(self, widget) -> None:
        """La rueda sobre `widget` (o sus hijos) mueve este desplazamiento."""
        _registry[str(widget)] = self
        inner = getattr(widget, "_canvas", None)   # widgets de customtkinter: avisa su lienzo
        widget.bind("<Destroy>", lambda e, w=widget: e.widget in (w, inner)
                    and _registry.pop(str(w), None), add="+")
        if isinstance(widget, tk.Text):  # el texto se desplaza solo: se toma la rueda antes
            widget.bind("<MouseWheel>", lambda e: (_route(e), "break")[1])

    def bind_bar(self, bar, axis: str, connect: bool = True) -> None:
        bar.configure(command=lambda *args: self._bar_command(axis, *args))
        if isinstance(bar, ScrollBar):
            bar.scroller = self
        if connect:
            self.target.configure(**{f"{axis}scrollcommand": bar.set})

    # ---------------------------------------------------------------- geometría
    def _view(self, axis):
        return self.target.yview() if axis == "y" else self.target.xview()

    def _span(self, axis) -> float:
        """Tamaño total del contenido en píxeles."""
        size = self.target.winfo_height() if axis == "y" else self.target.winfo_width()
        first, last = self._view(axis)
        if not self._is_text:
            region = self.target.cget("scrollregion")
            if region:
                x0, y0, x1, y1 = (float(v) for v in region.split())
                return max(1.0, (y1 - y0) if axis == "y" else (x1 - x0))
        return max(1.0, size / max(1e-6, last - first))

    def _offset(self, axis) -> float:
        return self._view(axis)[0] * self._span(axis)

    def _max_offset(self, axis) -> float:
        size = self.target.winfo_height() if axis == "y" else self.target.winfo_width()
        return max(0.0, self._span(axis) - size)

    def _apply(self, axis, offset: float) -> None:
        span = self._span(axis)
        (self.target.yview_moveto if axis == "y" else self.target.xview_moveto)(offset / span)
        self.moves += 1
        self._moved()

    def can_scroll(self, horizontal: bool = False) -> bool:
        first, last = self._view("x" if horizontal else "y")
        return first > 0.0001 or last < 0.9999

    # ---------------------------------------------------------------- barra: un cuadro
    def _bar_command(self, axis, *args):
        if not args:
            return
        if args[0] == "moveto":
            self._stop(axis)
            self._drag[axis] = float(args[1]) * self._span(axis)
            if self._drag_job is None:
                wait = FRAME_MS - (time.perf_counter() - self._last_apply) * 1000
                self._drag_job = self.target.after(max(0, int(wait)), self._flush_drag)
        elif args[0] == "scroll":
            amount, unit = int(args[1]), args[2]
            size = self.target.winfo_height() if axis == "y" else self.target.winfo_width()
            self.scroll_by(axis, amount * (size * 0.9 if unit.startswith("page") else 40))

    def _flush_drag(self):
        self._drag_job = None
        self._last_apply = time.perf_counter()
        pending, self._drag = self._drag, {}
        for axis, offset in pending.items():
            self._pos[axis] = None
            try:
                self._apply(axis, max(0.0, min(offset, self._max_offset(axis))))
            except tk.TclError:
                return

    # ---------------------------------------------------------------- rueda
    def wheel(self, delta: int, horizontal: bool = False) -> None:
        axis = "x" if horizontal else "y"
        if not delta:
            return
        now = time.perf_counter()
        direction = 1 if delta > 0 else -1
        if abs(delta) >= 120:  # muesca de rueda: aceleración si vienen seguidas
            last_time, last_dir = self._last_notch
            self._streak = self._streak + 1 if (now - last_time < ACCEL_WINDOW_S
                                                and last_dir == direction) else 0
            self._last_notch = (now, direction)
            factor = min(ACCEL_MAX, 1 + ACCEL_STEP * self._streak)
        else:                  # touchpad: deltas chicos, 1 delta = 1 px, sin redondear a cero
            factor = 1.0
        self.scroll_by(axis, -delta / 120 * WHEEL_PX * factor)

    def scroll_by(self, axis: str, pixels: float) -> None:
        try:
            limit = self._max_offset(axis)
            current = self._goal[axis] if self._tween[axis] else self._current(axis)
        except tk.TclError:
            return
        goal = max(0.0, min(limit, current + pixels))
        if not anim.ENABLED:
            self._pos[axis] = goal
            self._apply(axis, goal)
            return
        self._goal[axis] = goal
        self._tween[axis] = (time.perf_counter(), self._current(axis))
        if self._anim_job is None:
            self._anim_job = self.target.after(0, self._tick)

    def _current(self, axis) -> float:
        pos = self._pos[axis]
        actual = self._offset(axis)
        # si otra cosa movió la vista (la barra, un salto), se parte de la posición real
        if pos is None or abs(pos - actual) > 2:
            pos = actual
        return pos

    def _tick(self):
        self._anim_job = None
        now = time.perf_counter()
        running = False
        for axis in ("y", "x"):
            tween = self._tween[axis]
            if not tween:
                continue
            start, origin = tween
            t = min(1.0, (now - start) * 1000 / SMOOTH_MS)
            pos = origin + (self._goal[axis] - origin) * anim.ease_out_cubic(t)
            self._pos[axis] = pos
            try:
                self._apply(axis, pos)
            except tk.TclError:
                return
            if t < 1.0:
                running = True
            else:
                self._tween[axis] = None
        if running:
            self._anim_job = self.target.after(FRAME_MS, self._tick)

    def _stop(self, axis):
        self._tween[axis] = None
        self._pos[axis] = None

    # ---------------------------------------------------------------- avisos
    def _moved(self):
        anim.note_scroll()
        if self.on_scroll is not None and self._notify_job is None:
            self._notify_job = self.target.after(NOTIFY_MS, self._notify)

    def _notify(self):
        self._notify_job = None
        try:
            self.on_scroll()
        except tk.TclError:
            pass


# --------------------------------------------------------------------------- enrutador

def install(widget) -> None:
    """Un único manejador de la rueda por ventana principal."""
    root = widget._root()
    if getattr(root, "_wheel_router", False):
        return
    root._wheel_router = True
    root.bind_all("<MouseWheel>", _route, add="+")


def _route(event):
    if event.state & 0x4:      # Ctrl + rueda: lo maneja cada vista (zoom del editor)
        return None
    horizontal = bool(event.state & 0x1)
    try:
        widget = event.widget.winfo_containing(event.x_root, event.y_root) or event.widget
    except (KeyError, tk.TclError, AttributeError):
        widget = event.widget
    while widget is not None:
        scroller = _registry.get(str(widget))
        if scroller is not None:
            try:
                if scroller.can_scroll(horizontal):
                    scroller.wheel(event.delta, horizontal)
                    return "break"
            except tk.TclError:
                return None
        elif isinstance(widget, tk.Text):   # texto con desplazamiento propio (CTkTextbox)
            return None
        widget = getattr(widget, "master", None)
    return None


def attach_textbox(textbox: ctk.CTkTextbox) -> Scroller:
    """Rueda con el mismo comportamiento para un CTkTextbox (resultados, informes)."""
    scroller = Scroller(textbox._textbox)
    scroller.alias(textbox)
    return scroller


# --------------------------------------------------------------------------- marco

class ScrollFrame(ctk.CTkScrollableFrame):
    """CTkScrollableFrame con el motor de arriba: misma apariencia y misma API."""

    def __init__(self, master, on_scroll=None, **kwargs):
        bar_colors = {
            "button_color": kwargs.pop("scrollbar_button_color", theme.SCROLLBAR["button_color"]),
            "button_hover_color": kwargs.pop("scrollbar_button_hover_color",
                                             theme.SCROLLBAR["button_hover_color"]),
        }
        super().__init__(master, **kwargs)
        old = self._scrollbar
        bar_colors["fg_color"] = old.cget("fg_color")
        # desconectar antes de destruir: crear la barra nueva procesa tareas pendientes
        # del lienzo, que si no llamarían a la barra vieja
        self._parent_canvas.configure(yscrollcommand="", xscrollcommand="")
        old.destroy()
        self._scrollbar = ScrollBar(self._parent_frame, orientation=self._orientation, **bar_colors)
        self._create_grid()
        vertical = self._orientation == "vertical"
        self.scroller = Scroller(self._parent_canvas, vbar=self._scrollbar if vertical else None,
                                 hbar=None if vertical else self._scrollbar, on_scroll=on_scroll)
        self._size = None
        self._region_job = None
        # CTkScrollableFrame recalcula la región en cada <Configure>, también al moverse
        self.bind("<Configure>", self._content_configured)

    def _content_configured(self, event):
        size = (event.width, event.height)
        if size == self._size or self._region_job is not None:
            return
        self._size = size
        self._region_job = self.after_idle(self._update_region)

    def _update_region(self):
        self._region_job = None
        try:
            self._parent_canvas.configure(scrollregion=self._parent_canvas.bbox("all"))
        except tk.TclError:
            pass

    def _mouse_wheel_all(self, event):
        """El enrutador global se encarga de la rueda."""
        return None
