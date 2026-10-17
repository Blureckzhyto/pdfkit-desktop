"""Números de página."""
from __future__ import annotations

import customtkinter as ctk

from core import page_tools
from ui import theme
from ui.components import ColorSwatches

from .base import SingleFileToolView

POSITIONS = {"Pie de página centrado": "bottom_center", "Pie derecho": "bottom_right",
             "Pie izquierdo": "bottom_left", "Encabezado centrado": "top_center"}
FORMATS = {"1": "n", "Página 1": "pagina_n", "1 / N": "n_de_total",
           "Página 1 de N": "pagina_n_de_total"}
SIZES = ["8", "9", "10", "11", "12", "14", "16", "18"]
COLORS = [("Negro", "#1A1A2E"), ("Gris", "#6B7080"), ("Rojo", "#E53935"), ("Azul", "#1E88E5")]
APPLY = ["Todas", "Rango"]


class PageNumbersView(SingleFileToolView):
    title = "Números de página"
    description = "Agrega la numeración a las páginas del PDF."
    run_label = "Numerar páginas"
    picker_label = "Arrastra el PDF a numerar"
    compact_picker = True

    def build_options(self, body):
        card = self.options_card(body)
        row = self.option_row(card, "POSICIÓN")
        self.position = ctk.CTkSegmentedButton(row, values=list(POSITIONS), **theme.SEGMENTED)
        self.position.set("Pie de página centrado")
        self.position.pack(side="left")

        row = self.option_row(card, "FORMATO")
        self.fmt = ctk.CTkOptionMenu(row, values=list(FORMATS), width=160, **theme.OPTIONMENU)
        self.fmt.set("1")
        self.fmt.pack(side="left", padx=(0, 24))
        ctk.CTkLabel(row, text="COMENZAR DESDE", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.start = ctk.CTkEntry(row, width=70, **theme.ENTRY)
        self.start.insert(0, "1")
        self.start.pack(side="left")
        theme.attach_focus_ring(self.start)

        row = self.option_row(card, "TAMAÑO")
        self.font_size = ctk.CTkOptionMenu(row, values=SIZES, width=80, **theme.OPTIONMENU)
        self.font_size.set("11")
        self.font_size.pack(side="left", padx=(0, 24))
        ctk.CTkLabel(row, text="COLOR", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.color = ColorSwatches(row, COLORS, initial="#1A1A2E")
        self.color.pack(side="left")

        row = self.option_row(card, "APLICAR A", last=True)
        self.apply_to = ctk.CTkSegmentedButton(row, values=APPLY, command=self._apply_changed,
                                               **theme.SEGMENTED)
        self.apply_to.set("Todas")
        self.apply_to.pack(side="left", padx=(0, 10))
        self.range_entry = ctk.CTkEntry(row, width=160, placeholder_text="2-10", **theme.ENTRY)
        self.range_entry.pack(side="left")
        theme.attach_focus_ring(self.range_entry)
        self._apply_changed("Todas")

    def _apply_changed(self, value):
        self.range_entry.configure(state="normal" if value == "Rango" else "disabled")

    def run(self):
        src = self.require_file()
        if not src:
            return
        try:
            start = int(self.start.get().strip())
            if start < 0:
                raise ValueError
        except ValueError:
            self.show_error("“Comenzar desde” tiene que ser un número entero, por ejemplo 1.")
            return
        pages_spec = None
        if self.apply_to.get() == "Rango":
            pages_spec = self.range_entry.get().strip()
            if not pages_spec:
                self.show_error("Ingresa el rango de páginas, por ejemplo 2-10.")
                return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_numerado.pdf")
        position, fmt = POSITIONS[self.position.get()], FORMATS[self.fmt.get()]
        size, color = float(self.font_size.get()), self.color.get()

        def work(progress):
            result, count = page_tools.add_page_numbers(src, output, position, start, fmt, size,
                                                        color, pages_spec, progress)
            return f"Se numeraron {count} página(s): {result.name}"

        self.start_task(work)
