"""Firmar PDF: firma dibujada, escrita o desde imagen, ubicada sobre una miniatura
de la página con arrastre y tiradores en las esquinas."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageTk

from core import edit_sign, pdf_tools
from ui import theme
from ui.components import ColorSwatches, FilePicker, run_task
from ui.components import box_geometry as boxes

from .base import ToolView

PAD_W, PAD_H = 500, 150
THUMB_DPI = 80
SIG_COLORS = [("Negro", "#000000"), ("Azul", "#1E3A8A"), ("Rojo", "#FF2D2D")]
PAPER = "#FFFFFF"          # la firma se dibuja "en papel" en los dos temas (tinta oscura)
PAPER_HINT = "#888888"
TABS = ("DIBUJAR", "ESCRIBIR", "IMAGEN")
PREVIEW_SIZE = (500, 80)
IMAGE_TYPES = [("Imágenes", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*")]


class SignView(ToolView):
    title = "Firmar PDF"
    icon = "SG"
    description = "Dibuja, escribe o sube tu firma y ubícala sobre la página."
    run_label = "Firmar PDF"

    def build_body(self, body):
        self.src = None
        self.page_count = 0
        self.current = 0
        self._page_cache: dict[int, Image.Image] = {}
        self._render_token = 0
        self.strokes: list[list[tuple[float, float]]] = []
        self.uploaded = None          # (imagen, ancho natural en pt)
        self.sig = None               # firma activa: (imagen, ancho natural en pt)
        self.placement = None         # {"page": índice, "box": (x, y, w, h) en pt}
        self._drag = None
        self._view = None             # geometría de la miniatura en pantalla
        self._thumb_photo = None
        self._sig_photo = None
        self._fit_job = None
        self.fonts = edit_sign.signature_fonts()

        self.picker = FilePicker(body, exts=[".pdf"], multiple=False, compact=True,
                                 label="Arrastra el PDF a firmar",
                                 on_change=self._file_changed)
        self.picker.pack(fill="x")

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.pack(fill="both", expand=True, pady=(8, 0))
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(main, width=532, height=300, command=self._tab_changed,
                                   **theme.TABVIEW)
        self.tabs.grid(row=0, column=0, sticky="n", padx=(0, 12))
        for name in TABS:
            self.tabs.add(name)
        self._build_draw_tab(self.tabs.tab("DIBUJAR"))
        self._build_type_tab(self.tabs.tab("ESCRIBIR"))
        self._build_image_tab(self.tabs.tab("IMAGEN"))

        placement = ctk.CTkFrame(main, **theme.CARD)
        placement.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(placement, text="UBICACIÓN", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=8, pady=(8, 2))
        # fila compacta y centrada: entra aunque la ventana esté en su tamaño mínimo
        nav = ctk.CTkFrame(placement, fg_color="transparent")
        nav.pack(pady=(0, 4))
        ctk.CTkButton(nav, text="◀", width=28, height=26,
                      command=lambda: self._goto(self.current - 1),
                      **theme.BTN_SECONDARY).pack(side="left")
        self.page_label = ctk.CTkLabel(nav, text="– / –", width=70,
                                       font=theme.FONT_BODY, text_color=theme.TEXT_PRIMARY)
        self.page_label.pack(side="left", padx=2)
        ctk.CTkButton(nav, text="▶", width=28, height=26,
                      command=lambda: self._goto(self.current + 1),
                      **theme.BTN_SECONDARY).pack(side="left")
        # la ayuda se empaqueta antes que el lienzo para que no la aplaste
        hint = ctk.CTkLabel(placement, text="Clic para ubicar · arrastra para mover · "
                                            "esquinas para el tamaño",
                            font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY,
                            wraplength=320)
        hint.pack(side="bottom", fill="x", padx=8, pady=(4, 6))
        placement.bind("<Configure>",
                       lambda e: hint.configure(wraplength=max(120, e.width - 20)), add="+")
        self.canvas = tk.Canvas(placement, bg=theme.resolve(theme.CANVAS_BG),
                                highlightthickness=0, height=180)
        theme.on_mode_change(placement, self._mode_changed)
        self.canvas.pack(fill="both", expand=True, padx=1)
        self.canvas.bind("<Configure>", lambda _e: self._schedule_fit())
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _mode_changed(self):
        self.canvas.configure(bg=theme.resolve(theme.CANVAS_BG))
        self.pad.configure(highlightbackground=theme.resolve(theme.BORDER_STRONG),
                           highlightcolor=theme.resolve(theme.BORDER_STRONG))
        self._draw_signature()

    # ------------------------------------------------------------------ pestañas de firma

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 6))

    def _build_draw_tab(self, tab):
        self.pad = tk.Canvas(tab, width=PAD_W, height=PAD_H, bg=PAPER,
                             highlightthickness=1,
                             highlightbackground=theme.resolve(theme.BORDER_STRONG),
                             highlightcolor=theme.resolve(theme.BORDER_STRONG),
                             cursor="pencil")
        self.pad.pack(pady=(4, 8))
        self.pad.bind("<Button-1>", self._pad_press)
        self.pad.bind("<B1-Motion>", self._pad_drag)
        self.pad.bind("<ButtonRelease-1>", lambda _e: self._refresh_signature())
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x")
        self._section(row, "COLOR")
        self.draw_color = ColorSwatches(row, SIG_COLORS, on_change=self._redraw_pad)
        self.draw_color.pack(side="left")
        ctk.CTkButton(row, text="BORRAR", width=80, height=28, command=self._clear_pad,
                      **theme.BTN_SECONDARY).pack(side="right")

    def _build_type_tab(self, tab):
        self.name_entry = ctk.CTkEntry(tab, width=PAD_W, placeholder_text="Escribe tu nombre",
                                       **theme.ENTRY)
        self.name_entry.pack(pady=(4, 6))
        theme.attach_focus_ring(self.name_entry)
        self.name_entry.bind("<KeyRelease>", lambda _e: self._refresh_signature())
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        self._section(row, "FUENTE")
        font_names = list(self.fonts) or ["(sin fuentes)"]
        self.font_menu = ctk.CTkOptionMenu(row, values=font_names, width=180, height=28,
                                           command=lambda _v: self._refresh_signature(),
                                           **theme.OPTIONMENU)
        self.font_menu.set(font_names[0])
        self.font_menu.pack(side="left", padx=(0, 12))
        if not self.fonts:
            self.font_menu.configure(state="disabled")
        self._section(row, "TAMAÑO")
        self.size_slider = ctk.CTkSlider(row, from_=24, to=96, number_of_steps=72, width=130,
                                         command=lambda _v: self._refresh_signature(),
                                         **theme.SLIDER_ON_CARD)
        self.size_slider.set(48)
        self.size_slider.pack(side="left")
        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 6))
        self._section(row2, "COLOR")
        self.type_color = ColorSwatches(row2, SIG_COLORS,
                                        on_change=lambda _c: self._refresh_signature())
        self.type_color.pack(side="left")
        self.type_preview = ctk.CTkLabel(tab, text="Vista previa", width=PAD_W,
                                         height=PREVIEW_SIZE[1], fg_color=PAPER,
                                         corner_radius=0, text_color=PAPER_HINT,
                                         font=theme.FONT_SMALL)
        self.type_preview.pack()

    def _build_image_tab(self, tab):
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=(4, 6))
        ctk.CTkButton(row, text="ELEGIR IMAGEN…", width=140, height=30,
                      command=self._choose_image, **theme.BTN_SECONDARY).pack(side="left")
        self.image_name = ctk.CTkLabel(row, text="Ningún archivo", font=theme.FONT_SMALL,
                                       text_color=theme.TEXT_SECONDARY)
        self.image_name.pack(side="left", padx=10)
        self.image_preview = ctk.CTkLabel(tab, text="Vista previa", width=PAD_W,
                                          height=110, fg_color=PAPER, corner_radius=0,
                                          text_color=PAPER_HINT, font=theme.FONT_SMALL)
        self.image_preview.pack(pady=(0, 6))
        ctk.CTkLabel(tab, text="Recomendado: PNG con fondo transparente. Si la imagen tiene "
                               "fondo blanco, se vuelve transparente automáticamente.",
                     font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY,
                     wraplength=PAD_W, justify="left").pack(anchor="w")

    # dibujo
    def _pad_xy(self, event):
        return min(max(0, event.x), PAD_W), min(max(0, event.y), PAD_H)

    def _pad_press(self, event):
        x, y = self._pad_xy(event)
        self.strokes.append([(x, y)])
        r = 1.5
        self.pad.create_oval(x - r, y - r, x + r, y + r, fill=self.draw_color.get(),
                             outline="")

    def _pad_drag(self, event):
        if not self.strokes:
            return
        x, y = self._pad_xy(event)
        px, py = self.strokes[-1][-1]
        self.strokes[-1].append((x, y))
        self.pad.create_line(px, py, x, y, fill=self.draw_color.get(), width=2.5,
                             capstyle="round", smooth=True)

    def _redraw_pad(self, _color=None):
        self.pad.delete("all")
        for stroke in self.strokes:
            if len(stroke) > 1:
                points = [c for p in stroke for c in p]
                self.pad.create_line(*points, fill=self.draw_color.get(), width=2.5,
                                     capstyle="round", joinstyle="round", smooth=True)
            else:
                x, y = stroke[0]
                self.pad.create_oval(x - 1.5, y - 1.5, x + 1.5, y + 1.5,
                                     fill=self.draw_color.get(), outline="")
        self._refresh_signature()

    def _clear_pad(self):
        self.strokes = []
        self.pad.delete("all")
        self._refresh_signature()

    # imagen
    def _choose_image(self):
        path = filedialog.askopenfilename(filetypes=IMAGE_TYPES)
        if not path:
            return
        self.show_info("Preparando la imagen…")

        def loaded(result):
            self.uploaded = result
            name = path.replace("\\", "/").rsplit("/", 1)[-1]
            self.image_name.configure(text=name if len(name) <= 40 else name[:37] + "…")
            self._set_preview(self.image_preview, result[0], (PAD_W, 110))
            self._refresh_signature()
            self.show_info("Imagen lista. Haz clic sobre la página para ubicarla.")

        run_task(self, lambda _p: edit_sign.load_signature_image(path), loaded,
                 lambda exc: self.show_error(str(exc)))

    def _set_preview(self, label, img, max_size):
        if img is None:
            label.configure(image=None, text="Vista previa")
            label._preview_image = None
            return
        factor = min(max_size[0] / img.width, max_size[1] / img.height, 1.0)
        size = (max(1, int(img.width * factor)), max(1, int(img.height * factor)))
        preview = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        label.configure(image=preview, text="")
        label._preview_image = preview

    def _tab_changed(self):
        self._refresh_signature()

    def _refresh_signature(self):
        tab = self.tabs.get()
        try:
            if tab == "DIBUJAR":
                sig = edit_sign.render_drawn_signature(self.strokes, self.draw_color.get())
            elif tab == "ESCRIBIR":
                font = self.fonts.get(self.font_menu.get())
                sig = (edit_sign.render_text_signature(self.name_entry.get(), font,
                                                       self.type_color.get(),
                                                       int(self.size_slider.get()))
                       if font else None)
                self._set_preview(self.type_preview, sig[0] if sig else None, PREVIEW_SIZE)
            else:
                sig = self.uploaded
        except Exception as exc:
            self.show_error(str(exc))
            sig = None
        self.sig = sig
        if sig and self.placement:
            x, y, w, _h = self.placement["box"]
            aspect = sig[0].height / sig[0].width
            self.placement["box"] = boxes.clamp((x, y, w, w * aspect), *self._page_size_pt())
        self._draw_signature()

    # ------------------------------------------------------------------ páginas

    def _file_changed(self, files):
        if not files:
            return
        src = files[0]
        self._render_token += 1
        token = self._render_token
        self.src, self.page_count, self.current = None, 0, 0
        self._page_cache.clear()
        self.placement = None
        self._view = None
        self.canvas.delete("all")
        self.show_info("Abriendo PDF…")

        def opened(count):
            if token != self._render_token:
                return
            self.src, self.page_count = src, count
            self._show_page()
            self.show_info("Crea tu firma a la izquierda y haz clic sobre la página para "
                           "ubicarla.")

        def failed(exc):
            if token == self._render_token:
                text = str(exc)
                self.show_error(edit_sign.ENCRYPTED_MSG if "decrypt" in text.lower()
                                else f"No se pudo abrir el PDF: {text}")

        run_task(self, lambda _p: pdf_tools.get_page_count(src), opened, failed)

    def _goto(self, index):
        if self.src and 0 <= index < self.page_count and not self._drag:
            self.current = index
            self._show_page()

    def _show_page(self):
        self.page_label.configure(text=f"Pág. {self.current + 1}/{self.page_count}")
        self.canvas.delete("all")
        self._view = None
        if self.current in self._page_cache:
            self._fit()
            return
        self._render_token += 1
        token, src, index = self._render_token, self.src, self.current
        self.canvas.create_text(16, 16, anchor="nw", text="Renderizando…",
                                fill=theme.resolve(theme.TEXT_SECONDARY), font=theme.FONT_BODY)

        def rendered(img):
            self._page_cache[index] = img
            if token == self._render_token and index == self.current:
                self._fit()

        def failed(exc):
            if token == self._render_token:
                self.canvas.delete("all")
                self.show_error(str(exc))

        run_task(self, lambda _p: pdf_tools.render_page_image(src, index, dpi=THUMB_DPI),
                 rendered, failed)

    def _schedule_fit(self):
        if self._fit_job:
            self.after_cancel(self._fit_job)
        self._fit_job = self.after(60, self._fit)

    def _fit(self):
        self._fit_job = None
        img = self._page_cache.get(self.current) if self.src else None
        if img is None:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        factor = min((cw - 16) / img.width, (ch - 16) / img.height)
        if factor <= 0:
            return
        size = (max(1, int(img.width * factor)), max(1, int(img.height * factor)))
        self._thumb_photo = ImageTk.PhotoImage(img.resize(size, Image.LANCZOS))
        pt_per_px = 72.0 / THUMB_DPI
        self._view = {
            "ox": (cw - size[0]) / 2, "oy": (ch - size[1]) / 2,
            "s": factor / pt_per_px,  # píxeles de pantalla por punto PDF
            "pw": img.width * pt_per_px, "ph": img.height * pt_per_px,
        }
        self.canvas.delete("all")
        self.canvas.create_image(self._view["ox"], self._view["oy"], anchor="nw",
                                 image=self._thumb_photo)
        self._draw_signature()

    def _page_size_pt(self):
        if self._view:
            return self._view["pw"], self._view["ph"]
        return 10_000, 10_000

    # ------------------------------------------------------------------ ubicación

    def _box_to_px(self, box):
        v = self._view
        x, y, w, h = box
        return (v["ox"] + x * v["s"], v["oy"] + y * v["s"], w * v["s"], h * v["s"])

    def _box_to_pt(self, box):
        v = self._view
        x, y, w, h = box
        return ((x - v["ox"]) / v["s"], (y - v["oy"]) / v["s"], w / v["s"], h / v["s"])

    def _draw_signature(self):
        self.canvas.delete("sig")
        self._sig_photo = None
        if not (self._view and self.sig and self.placement
                and self.placement["page"] == self.current):
            return
        box_px = self._box_to_px(self.placement["box"])
        size = (max(1, round(box_px[2])), max(1, round(box_px[3])))
        self._sig_photo = ImageTk.PhotoImage(self.sig[0].resize(size, Image.LANCZOS))
        self.canvas.create_image(box_px[0], box_px[1], anchor="nw", image=self._sig_photo,
                                 tags="sig")
        boxes.draw_handles(self.canvas, box_px, theme.ACCENT, "sig")

    def _on_press(self, event):
        if not self._view:
            return
        if not self.sig:
            self.show_error("Primero crea tu firma: dibújala, escríbela o sube una imagen.")
            return
        on_this_page = self.placement and self.placement["page"] == self.current
        mode = (boxes.hit_test(self._box_to_px(self.placement["box"]), event.x, event.y)
                if on_this_page else None)
        if not mode:
            v = self._view
            x_pt, y_pt = (event.x - v["ox"]) / v["s"], (event.y - v["oy"]) / v["s"]
            if not (0 <= x_pt <= v["pw"] and 0 <= y_pt <= v["ph"]):
                return
            img, natural_w = self.sig
            w = min(natural_w, v["pw"] * 0.4)
            h = w * img.height / img.width
            box = boxes.clamp((x_pt - w / 2, y_pt - h / 2, w, h), v["pw"], v["ph"])
            self.placement = {"page": self.current, "box": box}
            self._draw_signature()
            mode = "move"
        self._drag = {"mode": mode, "start_xy": (event.x, event.y),
                      "start_px": self._box_to_px(self.placement["box"])}

    def _on_drag(self, event):
        if not self._drag:
            return
        drag = self._drag
        if drag["mode"] == "move":
            x, y, w, h = drag["start_px"]
            box_px = (x + event.x - drag["start_xy"][0], y + event.y - drag["start_xy"][1], w, h)
        else:
            box_px = boxes.resize(drag["start_px"], drag["mode"], event.x, event.y, min_w=16)
        self.placement["box"] = boxes.clamp(self._box_to_pt(box_px), *self._page_size_pt())
        self._draw_signature()

    def _on_release(self, _event):
        if self._drag:
            self._drag = None
            self.show_info(f"Firma en la página {self.placement['page'] + 1}. "
                           "Ajústala o presiona FIRMAR PDF.")

    # ------------------------------------------------------------------ firmar

    def run(self):
        files = self.picker.get_files()
        if not files or not self.src:
            self.show_error("Selecciona un PDF primero.")
            return
        if not self.sig:
            self.show_error("Crea tu firma primero: dibújala, escríbela o sube una imagen.")
            return
        if not self.placement:
            self.show_error("Haz clic sobre la página para ubicar la firma.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        src = self.src
        output = self.output_file(out_dir, f"{src.stem}_firmado.pdf")
        signature = self.sig[0].copy()
        page = self.placement["page"]
        box = tuple(self.placement["box"])

        def work(progress):
            result = edit_sign.sign_pdf(src, output, page, signature, box, progress)
            return f"Se firmó la página {page + 1}: {result.name} en {out_dir}"

        self.start_task(work)
