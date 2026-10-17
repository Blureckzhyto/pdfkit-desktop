"""Ordenar páginas: grilla de miniaturas que se reordena arrastrando.

Las miniaturas se generan solo para las páginas cerca de la zona visible (y las
que se ven al desplazar), en segundo plano, y quedan en caché.
"""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk
from PIL import ImageTk

from core import page_tools
from ui import theme
from ui.components import ScrollBar, Scroller, run_task

from .base import SingleFileToolView

THUMB_BOX = (112, 150)    # tamaño máximo de cada miniatura
CELL_W, CELL_H = 140, 196
PAD = 12
DRAG_THRESHOLD = 6
BATCH = 12                # miniaturas por tarea en segundo plano
LOOKAHEAD = 1.0           # se cargan además las de una pantalla más arriba y abajo


class OrganizeView(SingleFileToolView):
    title = "Ordenar páginas"
    description = "Arrastra las miniaturas para cambiar el orden, o usa los botones."
    run_label = "Guardar nuevo orden"
    picker_label = "Arrastra el PDF a ordenar"
    compact_picker = True

    def build_options(self, body):
        self.src = None
        self.page_total = 0
        self.order: list[int] = []
        self.selected: int | None = None   # posición en self.order
        self._photos: dict[int, ImageTk.PhotoImage] = {}
        self._loading: set[int] = set()
        self._drag = None
        self._marker = None
        self._layout_job = None
        self._token = 0

        bar = ctk.CTkFrame(body, fg_color="transparent")
        bar.pack(fill="x", pady=(10, 6))
        for text, command in (("Mover arriba", lambda: self._move(-1)),
                              ("Mover abajo", lambda: self._move(1)),
                              ("Eliminar", self._delete),
                              ("Restablecer", self._reset_order)):
            ctk.CTkButton(bar, text=text, width=110, height=30, command=command,
                          **theme.BTN_SECONDARY).pack(side="left", padx=(0, 8))
        self.count_info = ctk.CTkLabel(bar, text="", font=theme.FONT_SMALL,
                                       text_color=theme.TEXT_SECONDARY)
        self.count_info.pack(side="right")

        frame = ctk.CTkFrame(body, **theme.CARD)
        frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(frame, highlightthickness=0, bg=theme.resolve(theme.CANVAS_BG))
        self.scrollbar = ScrollBar(frame)
        self.scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=4)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        self.scroller = Scroller(self.canvas, vbar=self.scrollbar, on_scroll=self._load_visible)
        self.canvas.bind("<Configure>", lambda _e: self._schedule_layout())
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        theme.on_mode_change(frame, self._mode_changed)
        self._placeholder("Carga un PDF para ver sus páginas.")

    def _placeholder(self, text):
        self._placeholder_text = text
        self.canvas.delete("all")
        self.canvas.create_text(20, 20, anchor="nw", text=text, font=theme.FONT_BODY,
                                fill=theme.resolve(theme.TEXT_MUTED))

    def _mode_changed(self):
        self.canvas.configure(bg=theme.resolve(theme.CANVAS_BG))
        if self.order:
            self._layout(self._marker)
        else:
            self._placeholder(self._placeholder_text)

    # ------------------------------------------------------------------ carga

    def on_file(self, path):
        self._token += 1
        token = self._token
        self.src, self.order, self.selected, self.page_total = None, [], None, 0
        self._photos.clear()
        self._loading.clear()
        self._placeholder("Leyendo el PDF…")
        self.count_info.configure(text="")

        def loaded(count):
            if token != self._token:
                return
            self.src, self.page_total = path, count
            self.order = list(range(count))
            self.canvas.yview_moveto(0)
            self.show_info(f"{count} página(s). Arrastra para reordenar.")
            self._layout()
            self._load_visible()

        def failed(exc):
            if token == self._token:
                self._placeholder("")
                self.show_error(str(exc))

        run_task(self, lambda _p: page_tools.get_page_count(path), loaded, failed)

    def _visible_positions(self):
        columns = self._columns()
        height = max(1, self.canvas.winfo_height())
        top = self.canvas.canvasy(0) - height * LOOKAHEAD
        bottom = self.canvas.canvasy(0) + height * (1 + LOOKAHEAD)
        first_row = max(0, int((top - PAD) // CELL_H))
        last_row = max(0, int((bottom - PAD) // CELL_H))
        return range(first_row * columns, min(len(self.order), (last_row + 1) * columns))

    def _load_visible(self):
        """Pide en segundo plano las miniaturas de lo visible (y una pantalla alrededor)."""
        if not self.src or self._loading:
            return
        missing = [self.order[p] for p in self._visible_positions() if self.order[p] not in self._photos]
        if not missing:
            return
        batch = missing[:BATCH]
        self._loading.update(batch)
        token, src = self._token, self.src

        def done(images):
            if token != self._token:
                return
            self._loading.difference_update(batch)
            for index, image in images.items():
                self._photos[index] = ImageTk.PhotoImage(image, master=self.canvas)
            self._layout(self._marker)
            self._load_visible()

        def failed(exc):
            if token == self._token:
                self._loading.difference_update(batch)
                self.show_error(str(exc))

        run_task(self, lambda _p: page_tools.render_page_thumbnails(src, batch, THUMB_BOX), done,
                 failed)

    # ------------------------------------------------------------------ grilla

    def _columns(self):
        return max(1, (self.canvas.winfo_width() - PAD) // CELL_W)

    def _cell_origin(self, position):
        columns = self._columns()
        return PAD + (position % columns) * CELL_W, PAD + (position // columns) * CELL_H

    def _schedule_layout(self):
        if self._layout_job:
            self.after_cancel(self._layout_job)
        self._layout_job = self.after(60, self._relayout)

    def _relayout(self):
        self._layout(self._marker)
        self._load_visible()

    def _layout(self, marker: int | None = None):
        self._layout_job = None
        self._marker = marker
        if not self.order:
            if self.src:
                self._placeholder("No quedan páginas. Usa Restablecer para recuperarlas.")
            return
        r = theme.resolve
        surface, accent, border = r(theme.SURFACE), r(theme.ACCENT), r(theme.BORDER)
        secondary, muted = r(theme.TEXT_SECONDARY), r(theme.TEXT_MUTED)
        self.canvas.delete("all")
        for position, original in enumerate(self.order):
            x, y = self._cell_origin(position)
            selected = position == self.selected
            self.canvas.create_rectangle(
                x, y, x + CELL_W - 12, y + CELL_H - 12, fill=surface,
                outline=accent if selected else border, width=2 if selected else 1)
            cx, cy = x + (CELL_W - 12) / 2, y + 10 + THUMB_BOX[1] / 2
            photo = self._photos.get(original)
            if photo is not None:
                self.canvas.create_image(cx, cy, image=photo)
            else:  # aún sin miniatura: hueco del tamaño de una página
                self.canvas.create_rectangle(cx - 40, cy - 56, cx + 40, cy + 56, outline=border,
                                             fill="")
                self.canvas.create_text(cx, cy, text="…", fill=muted, font=theme.FONT_BODY)
            self.canvas.create_text(x + (CELL_W - 12) / 2, y + CELL_H - 26,
                                    text=f"{position + 1}  ·  pág. {original + 1}",
                                    fill=accent if selected else secondary,
                                    font=theme.FONT_SMALL)
        if marker is not None:
            x, y = self._cell_origin(marker)
            self.canvas.create_line(x - 7, y, x - 7, y + CELL_H - 12, fill=accent, width=3)
        rows = (len(self.order) + self._columns() - 1) // self._columns()
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), PAD + rows * CELL_H))
        removed = self.page_total - len(self.order)
        self.count_info.configure(text=f"{len(self.order)} página(s)"
                                  + (f" · {removed} eliminada(s)" if removed else ""))

    def _position_at(self, x, y, insertion=False):
        columns = self._columns()
        col = int((x - PAD) // CELL_W)
        row = int((y - PAD) // CELL_H)
        if col < 0 or row < 0 or col >= columns:
            return None
        if insertion:  # punto de inserción: antes o después de la celda según la mitad
            offset = 1 if (x - PAD) % CELL_W > CELL_W / 2 else 0
            return min(len(self.order), row * columns + col + offset)
        position = row * columns + col
        return position if position < len(self.order) else None

    # ------------------------------------------------------------------ mouse

    def _xy(self, event):
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _on_press(self, event):
        x, y = self._xy(event)
        position = self._position_at(x, y)
        self.selected = position
        self._drag = {"from": position, "start": (event.x, event.y), "active": False} \
            if position is not None else None
        self._layout()

    def _on_drag(self, event):
        if not self._drag:
            return
        sx, sy = self._drag["start"]
        if abs(event.x - sx) + abs(event.y - sy) > DRAG_THRESHOLD:
            self._drag["active"] = True
        if self._drag["active"]:
            x, y = self._xy(event)
            self._layout(marker=self._position_at(x, y, insertion=True))

    def _on_release(self, event):
        drag, self._drag = self._drag, None
        if not drag or not drag["active"]:
            return
        x, y = self._xy(event)
        target = self._position_at(x, y, insertion=True)
        if target is None:
            self._layout()
            return
        source = drag["from"]
        page = self.order.pop(source)
        if target > source:
            target -= 1
        self.order.insert(target, page)
        self.selected = target
        self._layout()
        self._load_visible()

    # ------------------------------------------------------------------ botones

    def _move(self, delta):
        if self.selected is None:
            self.show_info("Selecciona una página primero.")
            return
        target = self.selected + delta
        if 0 <= target < len(self.order):
            self.order[self.selected], self.order[target] = self.order[target], self.order[self.selected]
            self.selected = target
            self._layout()

    def _delete(self):
        if self.selected is None:
            self.show_info("Selecciona una página primero.")
            return
        self.order.pop(self.selected)
        self.selected = min(self.selected, len(self.order) - 1) if self.order else None
        self._layout()
        self._load_visible()

    def _reset_order(self):
        if self.src:
            self.order = list(range(self.page_total))
            self.selected = None
            self._layout()
            self._load_visible()

    def run(self):
        if not self.src:
            self.show_error("Carga un PDF primero.")
            return
        if not self.order:
            self.show_error("No quedan páginas para guardar.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        src, order = self.src, list(self.order)
        output = self.output_file(out_dir, f"{src.stem}_ordenado.pdf")

        def work(progress):
            result = page_tools.reorder_pages(src, output, order, progress)
            return f"Se guardó {result.name} con {len(order)} página(s) en el nuevo orden"

        self.start_task(work)
