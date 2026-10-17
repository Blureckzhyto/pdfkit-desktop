"""Zona para soltar archivos + lista, usada por todas las herramientas.

La zona se dibuja sobre un tk.Canvas para lograr el borde punteado del estilo
Nothing; se redibuja al cambiar el tamaño, el tema o el estado de arrastre.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.utils import human_size
from ui import anim, theme

from .scrolling import ScrollFrame

try:
    from tkinterdnd2 import DND_FILES
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

ZONE_HEIGHT = 96
COMPACT_ZONE_HEIGHT = 58


class FilePicker(ctk.CTkFrame):
    """Selector de archivos por clic o arrastrar-y-soltar, con lista reordenable.

    `compact=True` (solo un archivo): zona más baja y sin lista; el archivo
    elegido se muestra dentro de la propia zona. Para vistas que necesitan el
    espacio vertical, como los editores con lienzo."""

    def __init__(self, master, exts: list[str], multiple: bool = True,
                 reorderable: bool = False, on_change=None, label: str | None = None,
                 compact: bool = False):
        super().__init__(master, fg_color="transparent")
        self.exts = [e.lower() for e in exts]
        self.multiple = multiple
        self.reorderable = reorderable
        self.on_change = on_change
        self.compact = compact and not multiple
        self.zone_height = COMPACT_ZONE_HEIGHT if self.compact else ZONE_HEIGHT
        self.files: list[Path] = []
        self._drag_over = False

        self._dnd_ok = _HAS_DND and getattr(self.winfo_toplevel(), "dnd_available", False)
        self.label_text = label or (
            "Arrastra tus archivos aquí" if multiple else "Arrastra tu archivo aquí")
        hint = "o haz clic para buscar" if self._dnd_ok else "haz clic para buscar"
        kinds = " · ".join(dict.fromkeys(e.lstrip(".").upper() for e in self.exts))
        self.hint_text = f"{kinds}  —  {hint}"

        self.zone = tk.Canvas(self, height=self.zone_height, highlightthickness=0, bd=0,
                              cursor="hand2")
        self.zone.pack(fill="x")
        self.zone.bind("<Configure>", lambda _e: self._draw_zone())
        self.zone.bind("<Button-1>", lambda _e: self.browse())
        if self._dnd_ok:
            self.after(150, self._register_dnd)

        # el canvas no entiende pares (claro, oscuro): redibujar al cambiar el tema
        ctk.AppearanceModeTracker.add(self._appearance_changed)
        self.bind("<Destroy>", self._on_destroy)

        self.list_frame = ScrollFrame(self, height=150, **theme.SCROLLFRAME)
        # se muestra solo cuando hay archivos

    def _on_destroy(self, _event=None):
        try:
            ctk.AppearanceModeTracker.remove(self._appearance_changed)
        except Exception:
            pass

    def _appearance_changed(self, _mode=None):
        try:
            self._draw_zone()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ dibujo de la zona

    @staticmethod
    def _round_rect(canvas, x0, y0, x1, y1, r, **kwargs):
        points = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
                  x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _draw_upload_icon(self, x, y, color):
        canvas = self.zone
        canvas.create_line(x, y + 7, x, y - 9, fill=color, width=2, arrow="last",
                           arrowshape=(7, 8, 4))
        canvas.create_line(x - 10, y + 4, x - 10, y + 11, x + 10, y + 11, x + 10, y + 4,
                           fill=color, width=2, capstyle="round", joinstyle="round")

    def _draw_zone(self) -> None:
        canvas = self.zone
        canvas.delete("all")
        r = theme.resolve
        canvas.configure(bg=r(theme.BG_PRIMARY))
        width = max(canvas.winfo_width(), 4)
        height = self.zone_height
        pulse = getattr(self, "_pulse", 0.0)
        fill = (anim.mix(theme.ACCENT_LIGHT, theme.DROP_PULSE, pulse) if self._drag_over
                else r(theme.BG_SECONDARY))
        outline = r(theme.ACCENT if self._drag_over else theme.BORDER_STRONG)
        self._round_rect(canvas, 1, 1, width - 2, height - 2, 14, fill=fill, outline="")
        # borde punteado de 2 px: dos contornos de 1 px (en Windows Tk dibuja
        # continuo cualquier guion más grueso que 1 px)
        for inset in (1, 2):
            self._round_rect(canvas, inset, inset, width - 1 - inset, height - 1 - inset,
                             14, fill="", outline=outline, dash=(6, 4))
        label, hint, label_color = self.label_text, self.hint_text, r(theme.TEXT_MUTED)
        if self.compact and self.files:
            path = self.files[0]
            try:
                size = human_size(path.stat().st_size)
            except OSError:
                size = "?"
            name = path.name if len(path.name) <= 60 else path.name[:57] + "…"
            label = f"{name}  —  {size}"
            hint = "clic o arrastra otro archivo para cambiarlo"
            label_color = r(theme.TEXT_PRIMARY)
        icon_color = r(theme.ACCENT if self._drag_over else theme.TEXT_MUTED)
        if self.compact:
            self._draw_upload_icon(28, height / 2, icon_color)
            canvas.create_text(width / 2, height / 2 - 9, text=label, fill=label_color,
                               font=(theme.FONT, 14))
            canvas.create_text(width / 2, height / 2 + 11, text=hint, fill=r(theme.TEXT_MUTED),
                               font=(theme.FONT, 12))
        else:
            self._draw_upload_icon(width / 2, 26, icon_color)
            canvas.create_text(width / 2, 56, text=label, fill=label_color,
                               font=(theme.FONT, 14))
            canvas.create_text(width / 2, 77, text=hint, fill=r(theme.TEXT_MUTED),
                               font=(theme.FONT, 12))

    # ------------------------------------------------------------------ arrastrar y soltar

    def _register_dnd(self) -> None:
        try:
            self.zone.drop_target_register(DND_FILES)
            self.zone.dnd_bind("<<Drop>>", self._on_drop)
            self.zone.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            self.zone.dnd_bind("<<DropLeave>>", self._on_drop_leave)
        except Exception:
            pass

    def _on_drop_enter(self, event):
        self._drag_over = True
        self._pulse_step(rising=True)
        return event.action

    def _pulse_step(self, rising):
        """Pulso suave del tinte mientras se arrastra un archivo encima."""
        if not self._drag_over:
            return
        if not anim.ENABLED:  # sin animaciones: tinte fijo (y sin bucle infinito)
            self._pulse = 0.5
            self._draw_zone()
            return

        def step(t):
            self._pulse = t if rising else 1 - t
            self._draw_zone()

        anim.animate(self.zone, "pulse", 650, step, done=lambda: self._pulse_step(not rising))

    def _stop_pulse(self):
        self._drag_over = False
        self._pulse = 0.0
        anim.cancel(self.zone, "pulse")
        self._draw_zone()

    def _on_drop_leave(self, _event):
        self._stop_pulse()

    def _on_drop(self, event) -> None:
        self._stop_pulse()
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        self.add_files(paths)

    # ------------------------------------------------------------------ archivos

    def browse(self) -> None:
        patterns = " ".join(f"*{e}" for e in self.exts)
        filetypes = [("Archivos compatibles", patterns), ("Todos los archivos", "*.*")]
        if self.multiple:
            picked = filedialog.askopenfilenames(filetypes=filetypes)
        else:
            one = filedialog.askopenfilename(filetypes=filetypes)
            picked = [one] if one else []
        if picked:
            self.add_files(picked)

    def add_files(self, paths) -> None:
        added = False
        for raw in paths:
            p = Path(str(raw).strip("{}"))
            if not p.is_file() or p.suffix.lower() not in self.exts:
                continue
            if not self.multiple:
                self.files = [p]
                added = True
                break
            if p not in self.files:
                self.files.append(p)
                added = True
        if added:
            self._refresh()
            if self.on_change:
                self.on_change(self.files)

    def clear(self) -> None:
        self.files = []
        self._refresh()
        if self.on_change:
            self.on_change(self.files)

    def get_files(self) -> list[Path]:
        return list(self.files)

    # ------------------------------------------------------------------ lista

    def _refresh(self) -> None:
        if self.compact:
            self._draw_zone()
            return
        for child in self.list_frame.winfo_children():
            child.destroy()
        if not self.files:
            self.list_frame.pack_forget()
            return
        self.list_frame.pack(fill="x", pady=(8, 0))
        for i, path in enumerate(self.files):
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            name = path.name if len(path.name) <= 55 else path.name[:52] + "…"
            try:
                size = human_size(path.stat().st_size)
            except OSError:
                size = "?"
            ctk.CTkLabel(row, text=f"{i + 1:>2}.", width=30, anchor="w",
                         font=theme.FONT_STATUS,
                         text_color=theme.TEXT_SECONDARY).pack(side="left")
            ctk.CTkLabel(row, text=name, anchor="w", font=theme.FONT_STATUS,
                         text_color=theme.TEXT_PRIMARY).pack(side="left",
                                                             fill="x", expand=True)
            ctk.CTkLabel(row, text=size, width=76, anchor="e", font=theme.FONT_MONO_SMALL,
                         text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(4, 8))
            if self.reorderable:
                ctk.CTkButton(row, text="↑", width=26, height=22,
                              command=lambda i=i: self._move(i, -1),
                              **theme.BTN_SECONDARY).pack(side="left", padx=1)
                ctk.CTkButton(row, text="↓", width=26, height=22,
                              command=lambda i=i: self._move(i, 1),
                              **theme.BTN_SECONDARY).pack(side="left", padx=1)
            remove_style = dict(theme.BTN_SECONDARY)
            remove_style["text_color"] = theme.ERROR
            ctk.CTkButton(row, text="✕", width=26, height=22,
                          command=lambda i=i: self._remove(i),
                          **remove_style).pack(side="left", padx=(1, 4))

    def _move(self, index: int, delta: int) -> None:
        target = index + delta
        if 0 <= target < len(self.files):
            self.files[index], self.files[target] = self.files[target], self.files[index]
            self._refresh()
            if self.on_change:
                self.on_change(self.files)

    def _remove(self, index: int) -> None:
        del self.files[index]
        self._refresh()
        if self.on_change:
            self.on_change(self.files)
