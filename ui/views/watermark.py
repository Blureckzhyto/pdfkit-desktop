"""Marca de agua de texto o imagen."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core import edit_sign
from ui import theme
from ui.components import ColorSwatches, FilePicker

from .base import ToolView

MODES = ["TEXTO", "IMAGEN"]
POSITIONS = {"Centro diagonal": "diagonal", "Centro horizontal": "horizontal",
             "Esquina inferior derecha": "corner"}
PAGE_MODES = ["Todas las páginas", "Rango de páginas"]
SIZES = ["24", "36", "48", "60", "72", "96", "120"]
COLORS = [("Gris", "#888888"), ("Rojo", "#FF2D2D"), ("Negro", "#000000"),
          ("Azul", "#1E5EFF")]
IMAGE_TYPES = [("Imágenes PNG", "*.png"), ("Imágenes", "*.png *.jpg *.jpeg"),
               ("Todos los archivos", "*.*")]


class WatermarkView(ToolView):
    title = "Marca de agua"
    icon = "WM"
    description = "Estampa un texto o una imagen sobre las páginas del PDF."
    run_label = "Aplicar marca de agua"

    def build_body(self, body):
        self.image_path: Path | None = None
        self.picker = FilePicker(body, exts=[".pdf"], multiple=False, compact=True,
                                 label="Arrastra el PDF")
        self.picker.pack(fill="x")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(10, 8))
        self._section(row, "TIPO")
        self.mode = ctk.CTkSegmentedButton(row, values=MODES, command=self._mode_changed,
                                           **theme.SEGMENTED)
        self.mode.set("TEXTO")
        self.mode.pack(side="left")

        self.mode_host = ctk.CTkFrame(body, fg_color="transparent")
        self.mode_host.pack(fill="x")

        # --- texto
        self.text_frame = ctk.CTkFrame(self.mode_host, **theme.CARD)
        r1 = self._row(self.text_frame)
        self._section(r1, "TEXTO")
        self.text_entry = ctk.CTkEntry(r1, width=300, **theme.ENTRY)
        self.text_entry.insert(0, "CONFIDENCIAL")
        self.text_entry.pack(side="left", padx=(0, 16))
        theme.attach_focus_ring(self.text_entry)
        self._section(r1, "TAMAÑO")
        self.text_size = ctk.CTkOptionMenu(r1, values=SIZES, width=70, **theme.OPTIONMENU)
        self.text_size.set("60")
        self.text_size.pack(side="left")
        r2 = self._row(self.text_frame, last=True)
        self._section(r2, "COLOR")
        self.color = ColorSwatches(r2, COLORS, initial="#888888")
        self.color.pack(side="left")

        # --- imagen
        self.image_frame = ctk.CTkFrame(self.mode_host, **theme.CARD)
        r1 = self._row(self.image_frame)
        ctk.CTkButton(r1, text="ELEGIR IMAGEN…", width=140, command=self._choose_image,
                      **theme.BTN_SECONDARY).pack(side="left")
        self.image_label = ctk.CTkLabel(r1, text="Ningún archivo (ideal: PNG transparente)",
                                        font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY)
        self.image_label.pack(side="left", padx=10)
        r2 = self._row(self.image_frame, last=True)
        self._section(r2, "ESCALA")
        self.scale = ctk.CTkSlider(r2, from_=10, to=100, number_of_steps=90, width=200,
                                   command=self._scale_changed, **theme.SLIDER_ON_CARD)
        self.scale.set(40)
        self.scale.pack(side="left")
        self.scale_label = ctk.CTkLabel(r2, text="40% del ancho de página", font=theme.FONT_BODY,
                                        text_color=theme.TEXT_PRIMARY)
        self.scale_label.pack(side="left", padx=8)

        # --- común
        common = ctk.CTkFrame(body, **theme.CARD)
        common.pack(fill="x", pady=(8, 0))
        r1 = self._row(common)
        self._section(r1, "OPACIDAD")
        self.opacity = ctk.CTkSlider(r1, from_=10, to=80, number_of_steps=70, width=200,
                                     command=self._opacity_changed, **theme.SLIDER_ON_CARD)
        self.opacity.set(30)
        self.opacity.pack(side="left")
        self.opacity_label = ctk.CTkLabel(r1, text="30%", width=44, font=theme.FONT_BODY,
                                          text_color=theme.TEXT_PRIMARY)
        self.opacity_label.pack(side="left", padx=6)
        r2 = self._row(common)
        self._section(r2, "POSICIÓN")
        self.position = ctk.CTkSegmentedButton(r2, values=list(POSITIONS), **theme.SEGMENTED)
        self.position.set("Centro diagonal")
        self.position.pack(side="left")
        r3 = self._row(common, last=True)
        self._section(r3, "PÁGINAS")
        self.page_mode = ctk.CTkSegmentedButton(r3, values=PAGE_MODES,
                                                command=self._page_mode_changed,
                                                **theme.SEGMENTED)
        self.page_mode.set(PAGE_MODES[0])
        self.page_mode.pack(side="left", padx=(0, 10))
        self.range_entry = ctk.CTkEntry(r3, width=150, placeholder_text="1-3, 5", **theme.ENTRY)
        self.range_entry.pack(side="left")
        theme.attach_focus_ring(self.range_entry)
        self._page_mode_changed(PAGE_MODES[0])

        self.text_frame.pack(fill="x")

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=theme.FONT_SECTION, width=80, anchor="w",
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 6))

    def _row(self, parent, last=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(12, 12 if last else 0))
        return row

    def _mode_changed(self, mode):
        self.text_frame.pack_forget()
        self.image_frame.pack_forget()
        (self.text_frame if mode == "TEXTO" else self.image_frame).pack(fill="x")

    def _scale_changed(self, value):
        self.scale_label.configure(text=f"{int(value)}% del ancho de página")

    def _opacity_changed(self, value):
        self.opacity_label.configure(text=f"{int(value)}%")

    def _page_mode_changed(self, mode):
        state = "normal" if mode == "Rango de páginas" else "disabled"
        self.range_entry.configure(state=state)

    def _choose_image(self):
        path = filedialog.askopenfilename(filetypes=IMAGE_TYPES)
        if path:
            self.image_path = Path(path)
            name = self.image_path.name
            self.image_label.configure(text=name if len(name) <= 44 else name[:41] + "…",
                                       text_color=theme.TEXT_PRIMARY)

    def run(self):
        files = self.picker.get_files()
        if not files:
            self.show_error("Selecciona un PDF primero.")
            return
        src = files[0]
        pages_spec = None
        if self.page_mode.get() == "Rango de páginas":
            pages_spec = self.range_entry.get().strip()
            if not pages_spec:
                self.show_error("Ingresa el rango de páginas, por ejemplo 1-3, 5.")
                return
        text_mode = self.mode.get() == "TEXTO"
        text = self.text_entry.get().strip()
        if text_mode and not text:
            self.show_error("Escribe el texto de la marca de agua.")
            return
        if not text_mode and not self.image_path:
            self.show_error("Elige la imagen de la marca de agua.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_marca.pdf")
        opacity = self.opacity.get() / 100
        position = POSITIONS[self.position.get()]
        size, color = float(self.text_size.get()), self.color.get()
        image_path, scale = self.image_path, self.scale.get() / 100

        def work(progress):
            if text_mode:
                result, count = edit_sign.watermark_text(src, output, text, size, opacity,
                                                         color, position, pages_spec, progress)
            else:
                result, count = edit_sign.watermark_image(src, output, image_path, opacity,
                                                          scale, position, pages_spec, progress)
            return f"Se marcó {count} página(s): {result.name} en {out_dir}"

        self.start_task(work)
