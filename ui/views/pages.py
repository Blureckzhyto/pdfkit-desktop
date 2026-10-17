"""Extraer páginas y Eliminar páginas: un PDF + un rango de páginas."""
from __future__ import annotations

import customtkinter as ctk

from core import page_tools
from core.edit_sign import parse_page_spec
from ui import theme
from ui.components import run_task

from .base import SingleFileToolView


class _RangeView(SingleFileToolView):
    compact_picker = True
    range_placeholder = "1, 3, 5-8"
    range_hint = ""

    def build_options(self, body):
        self.page_count = None
        card = self.options_card(body)
        row = self.option_row(card, "PÁGINAS")
        self.range_entry = ctk.CTkEntry(row, width=260, placeholder_text=self.range_placeholder,
                                        **theme.ENTRY)
        self.range_entry.pack(side="left")
        theme.attach_focus_ring(self.range_entry)
        self.count_label = ctk.CTkLabel(row, text="", font=theme.FONT_SMALL,
                                        text_color=theme.TEXT_SECONDARY)
        self.count_label.pack(side="left", padx=12)
        self.hint(card, self.range_hint, pady=(6, 14))

    def on_file(self, path):
        self.page_count = None
        self.count_label.configure(text="Leyendo…")

        def done(count):
            self.page_count = count
            self.count_label.configure(text=f"El documento tiene {count} página(s)")

        run_task(self, lambda _p: page_tools.get_page_count(path), done,
                 lambda exc: (self.count_label.configure(text=""), self.show_error(str(exc))))

    def read_range(self) -> str | None:
        spec = self.range_entry.get().strip()
        if not spec:
            self.show_error("Ingresa las páginas, por ejemplo 1, 3, 5-8.")
            return None
        if self.page_count:
            try:
                parse_page_spec(spec, self.page_count)
            except ValueError as exc:
                self.show_error(str(exc))
                return None
        return spec


class ExtractPagesView(_RangeView):
    title = "Extraer páginas"
    description = "Elige páginas sueltas o rangos y guárdalos en un PDF nuevo."
    run_label = "Extraer páginas"
    picker_label = "Arrastra el PDF del que quieres extraer páginas"
    range_hint = ("Separa con comas; usa guiones para rangos. Las páginas se guardan en el "
                  "orden que escribas (por ejemplo, 5, 1-3).")

    def run(self):
        src = self.require_file()
        spec = self.read_range() if src else None
        out_dir = self.get_output_dir() if spec else None
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_extraido.pdf")

        def work(progress):
            result, count = page_tools.extract_pages(src, output, spec, progress)
            return f"Se extrajeron {count} página(s) a {result.name}"

        self.start_task(work)


class DeletePagesView(_RangeView):
    title = "Eliminar páginas"
    description = "Quita las páginas que no necesitas y guarda el resto en un PDF nuevo."
    run_label = "Eliminar páginas"
    picker_label = "Arrastra el PDF del que quieres quitar páginas"
    range_hint = "Separa con comas; usa guiones para rangos (por ejemplo, 2, 4-6)."

    def run(self):
        src = self.require_file()
        spec = self.read_range() if src else None
        out_dir = self.get_output_dir() if spec else None
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_sin_paginas.pdf")

        def work(progress):
            result, removed, remaining = page_tools.delete_pages(src, output, spec, progress)
            return f"Se eliminaron {removed} página(s); quedan {remaining} en {result.name}"

        self.start_task(work)
