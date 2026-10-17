"""Recortar PDF: vista previa con bordes arrastrables o márgenes exactos en mm."""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from core import page_tools, pdf_tools
from core.page_tools import MM_TO_PT
from ui import theme
from ui.components import run_task

from .base import SingleFileToolView

PREVIEW_DPI = 72
EDGES = ("top", "bottom", "left", "right")
EDGE_LABELS = {"top": "SUPERIOR", "bottom": "INFERIOR", "left": "IZQUIERDO", "right": "DERECHO"}
MIN_SIDE_PT = 20      # lo mínimo que puede quedar de la página
GRAB = 8              # tolerancia en píxeles para agarrar un borde
PAGE_SHADE = "#1F2133"  # sombreado de la zona descartada: va sobre la página, igual en los dos temas
APPLY = ["Página actual", "Todas las páginas"]


class CropView(SingleFileToolView):
    title = "Recortar PDF"
    description = "Arrastra los bordes rojos o escribe los márgenes exactos en milímetros."
    run_label = "Recortar PDF"
    picker_label = "Arrastra el PDF a recortar"
    compact_picker = True

    def build_options(self, body):
        self.src = None
        self.sizes: list[tuple[float, float]] = []
        self.current = 0
        self.margins = dict.fromkeys(EDGES, 0.0)   # en puntos
        self._cache: dict[int, Image.Image] = {}
        self._view = None
        self._photo = None
        self._drag_edge = None
        self._token = 0
        self._fit_job = None

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.pack(fill="both", expand=True, pady=(12, 0))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        preview = ctk.CTkFrame(main, **theme.CARD)
        preview.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        nav = ctk.CTkFrame(preview, fg_color="transparent")
        nav.pack(pady=(8, 4))
        ctk.CTkButton(nav, text="◀", width=30, height=28, command=lambda: self._goto(self.current - 1),
                      **theme.BTN_SECONDARY).pack(side="left")
        self.page_label = ctk.CTkLabel(nav, text="Página – de –", width=140, font=theme.FONT_BODY,
                                       text_color=theme.TEXT_PRIMARY)
        self.page_label.pack(side="left", padx=4)
        ctk.CTkButton(nav, text="▶", width=30, height=28, command=lambda: self._goto(self.current + 1),
                      **theme.BTN_SECONDARY).pack(side="left")
        self.canvas = tk.Canvas(preview, bg=theme.resolve(theme.CANVAS_BG), highlightthickness=0,
                                height=260)
        theme.on_mode_change(preview, self._mode_changed)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.canvas.bind("<Configure>", lambda _e: self._schedule_fit())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_drag_edge", None))

        panel = ctk.CTkFrame(main, width=270, **theme.CARD)
        panel.grid(row=0, column=1, sticky="ns")
        ctk.CTkLabel(panel, text="MÁRGENES (MM)", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", padx=16, pady=(14, 6))
        self.entries: dict[str, ctk.CTkEntry] = {}
        for edge in EDGES:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(row, text=EDGE_LABELS[edge].capitalize(), width=90, anchor="w",
                         font=theme.FONT_BODY, text_color=theme.TEXT_PRIMARY).pack(side="left")
            entry = ctk.CTkEntry(row, width=90, font=(theme.FONT_MONO, 13),
                                 **{k: v for k, v in theme.ENTRY.items() if k != "font"})
            entry.insert(0, "0")
            entry.pack(side="left")
            theme.attach_focus_ring(entry)
            entry.bind("<KeyRelease>", lambda _e, edge=edge: self._entry_changed(edge), add="+")
            self.entries[edge] = entry
        ctk.CTkLabel(panel, text="APLICAR A", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", padx=16, pady=(14, 6))
        self.apply_to = ctk.CTkSegmentedButton(panel, values=APPLY, **theme.SEGMENTED)
        self.apply_to.set("Todas las páginas")
        self.apply_to.pack(anchor="w", padx=16)
        ctk.CTkButton(panel, text="Restablecer", width=120, height=30, command=self._reset,
                      **theme.BTN_SECONDARY).pack(anchor="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(panel, text="La zona sombreada es la que se descarta.", wraplength=230,
                     justify="left", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=16, pady=(4, 14))
        self._message("Carga un PDF para ver la vista previa.")

    def _message(self, text):
        self._message_text = text
        self.canvas.delete("all")
        self.canvas.create_text(16, 16, anchor="nw", text=text, font=theme.FONT_BODY,
                                fill=theme.resolve(theme.TEXT_MUTED))

    def _mode_changed(self):
        self.canvas.configure(bg=theme.resolve(theme.CANVAS_BG))
        if self._view:
            self._redraw()
        else:
            self._message(getattr(self, "_message_text", ""))

    # ------------------------------------------------------------------ carga y vista previa

    def on_file(self, path):
        self._token += 1
        token = self._token
        self.src, self.sizes, self.current = None, [], 0
        self._cache.clear()
        self._message("Leyendo el PDF…")

        def loaded(sizes):
            if token == self._token:
                self.src, self.sizes = path, sizes
                self._show_page()

        run_task(self, lambda _p: page_tools.page_sizes_pt(path), loaded,
                 lambda exc: (self._message(""), self.show_error(str(exc))))

    def _goto(self, index):
        if self.src and 0 <= index < len(self.sizes):
            self.current = index
            self._show_page()

    def _show_page(self):
        self.page_label.configure(text=f"Página {self.current + 1} de {len(self.sizes)}")
        if self.current in self._cache:
            self._fit()
            return
        self._token += 1
        token, src, index = self._token, self.src, self.current
        self._message("Renderizando…")

        def rendered(img):
            self._cache[index] = img
            if token == self._token and index == self.current:
                self._fit()

        run_task(self, lambda _p: pdf_tools.render_page_image(src, index, dpi=PREVIEW_DPI),
                 rendered, lambda exc: self.show_error(str(exc)))

    def _schedule_fit(self):
        if self._fit_job:
            self.after_cancel(self._fit_job)
        self._fit_job = self.after(60, self._fit)

    def _fit(self):
        self._fit_job = None
        img = self._cache.get(self.current) if self.src else None
        if img is None:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        factor = min((cw - 24) / img.width, (ch - 24) / img.height)
        if factor <= 0:
            return
        size = (max(1, int(img.width * factor)), max(1, int(img.height * factor)))
        self._photo = ImageTk.PhotoImage(img.resize(size, Image.LANCZOS))
        pw, ph = self.sizes[self.current]
        self._view = {"ox": (cw - size[0]) / 2, "oy": (ch - size[1]) / 2,
                      "s": size[0] / pw, "pw": pw, "ph": ph}
        self._clamp_margins()
        self._redraw()

    # ------------------------------------------------------------------ dibujo

    def _crop_px(self):
        v, m = self._view, self.margins
        return (v["ox"] + m["left"] * v["s"], v["oy"] + m["top"] * v["s"],
                v["ox"] + (v["pw"] - m["right"]) * v["s"], v["oy"] + (v["ph"] - m["bottom"]) * v["s"])

    def _redraw(self):
        if not self._view:
            return
        v = self._view
        self.canvas.delete("all")
        self.canvas.create_image(v["ox"], v["oy"], anchor="nw", image=self._photo)
        px0, py0 = v["ox"], v["oy"]
        px1, py1 = v["ox"] + v["pw"] * v["s"], v["oy"] + v["ph"] * v["s"]
        x0, y0, x1, y1 = self._crop_px()
        accent = theme.resolve(theme.ACCENT)
        shade = dict(fill=PAGE_SHADE, stipple="gray50", outline="")
        for box in ((px0, py0, px1, y0), (px0, y1, px1, py1), (px0, y0, x0, y1), (x1, y0, px1, y1)):
            if box[2] - box[0] > 0.5 and box[3] - box[1] > 0.5:
                self.canvas.create_rectangle(*box, **shade)
        self.canvas.create_rectangle(x0, y0, x1, y1, outline=accent, width=2)
        for cx, cy in (((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1), (x0, (y0 + y1) / 2),
                       (x1, (y0 + y1) / 2)):
            self.canvas.create_rectangle(cx - 5, cy - 5, cx + 5, cy + 5, fill=accent,
                                         outline="#FFFFFF")

    # ------------------------------------------------------------------ bordes

    def _edge_at(self, x, y):
        if not self._view:
            return None
        x0, y0, x1, y1 = self._crop_px()
        inside_x, inside_y = x0 - GRAB <= x <= x1 + GRAB, y0 - GRAB <= y <= y1 + GRAB
        candidates = []
        if inside_x:
            candidates += [(abs(y - y0), "top"), (abs(y - y1), "bottom")]
        if inside_y:
            candidates += [(abs(x - x0), "left"), (abs(x - x1), "right")]
        distance, edge = min(candidates, default=(GRAB + 1, None))
        return edge if distance <= GRAB else None

    def _on_motion(self, event):
        edge = self._drag_edge or self._edge_at(event.x, event.y)
        cursor = {"top": "sb_v_double_arrow", "bottom": "sb_v_double_arrow",
                  "left": "sb_h_double_arrow", "right": "sb_h_double_arrow"}.get(edge, "")
        self.canvas.configure(cursor=cursor)

    def _on_press(self, event):
        self._drag_edge = self._edge_at(event.x, event.y)

    def _on_drag(self, event):
        if not self._drag_edge:
            return
        v, edge = self._view, self._drag_edge
        x_pt, y_pt = (event.x - v["ox"]) / v["s"], (event.y - v["oy"]) / v["s"]
        value = {"top": y_pt, "bottom": v["ph"] - y_pt, "left": x_pt, "right": v["pw"] - x_pt}[edge]
        self.margins[edge] = value
        self._clamp_margins(edge)
        self._sync_entries()
        self._redraw()

    def _clamp_margins(self, edge=None):
        if not self._view:
            return
        v, m = self._view, self.margins
        for name in EDGES:
            m[name] = max(0.0, m[name])
        for a, b, total in (("top", "bottom", v["ph"]), ("left", "right", v["pw"])):
            excess = m[a] + m[b] - (total - MIN_SIDE_PT)
            if excess > 0:  # recorta primero el borde que se está moviendo
                moving = edge if edge in (a, b) else b
                m[moving] = max(0.0, m[moving] - excess)

    def _sync_entries(self):
        for edge, entry in self.entries.items():
            if self.focus_get() is not entry:
                entry.delete(0, "end")
                entry.insert(0, f"{self.margins[edge] / MM_TO_PT:.1f}".rstrip("0").rstrip("."))

    def _entry_changed(self, edge):
        raw = self.entries[edge].get().strip().replace(",", ".")
        try:
            value = float(raw) if raw else 0.0
        except ValueError:
            return
        self.margins[edge] = value * MM_TO_PT
        self._clamp_margins(edge)
        self._redraw()

    def _reset(self):
        self.margins = dict.fromkeys(EDGES, 0.0)
        self._sync_entries()
        self._redraw()

    # ------------------------------------------------------------------ guardar

    def run(self):
        if not self.src:
            self.show_error("Carga un PDF primero.")
            return
        for edge, entry in self.entries.items():
            raw = entry.get().strip().replace(",", ".") or "0"
            try:
                if float(raw) < 0:
                    raise ValueError
            except ValueError:
                self.show_error(f"El margen {EDGE_LABELS[edge].lower()} no es un número válido.")
                return
        margins_mm = tuple(self.margins[e] / MM_TO_PT for e in EDGES)
        if not any(margins_mm):
            self.show_error("Todavía no recortaste nada: arrastra un borde o escribe un margen.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        src = self.src
        pages = [self.current] if self.apply_to.get() == "Página actual" else None
        output = self.output_file(out_dir, f"{src.stem}_recortado.pdf")

        def work(progress):
            result, count = page_tools.crop_pages(src, output, margins_mm, pages, progress)
            return f"Se recortó {count} página(s): {result.name}"

        self.start_task(work)
