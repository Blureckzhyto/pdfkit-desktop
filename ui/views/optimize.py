"""Reparar PDF y OCR PDF."""
from __future__ import annotations

import customtkinter as ctk

from core import ocr, page_tools
from ui import theme
from ui.components import attach_textbox

from .base import SingleFileToolView

OCR_LANGUAGES = {"Español": "spa", "Inglés": "eng", "Ambos (español + inglés)": "spa+eng"}


class RepairView(SingleFileToolView):
    title = "Reparar PDF"
    description = ("Recupera un PDF dañado o que no abre bien: se reconstruye su estructura y "
                   "se guarda una copia limpia.")
    run_label = "Reparar PDF"
    picker_label = "Arrastra el PDF dañado"
    compact_picker = True

    def build_options(self, body):
        self.results = ctk.CTkTextbox(body, height=160, **theme.TEXTBOX)
        self.results.pack(fill="both", expand=True, pady=(12, 0))
        attach_textbox(self.results)
        self._set_results("Aquí vas a ver los problemas que se encontraron y corrigieron.")

    def _set_results(self, text):
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", text)
        self.results.configure(state="disabled")

    def run(self):
        src = self.require_file()
        out_dir = self.get_output_dir() if src else None
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_reparado.pdf")

        def work(progress):
            return page_tools.repair_pdf(src, output, progress)

        def done(result):
            path, warnings, pages = result
            if warnings:
                lines = [f"Problemas encontrados y corregidos ({len(warnings)}):", ""]
                lines += [f"• {w}" for w in warnings]
                summary = f"{len(warnings)} problema(s) corregido(s)"
            else:
                lines = ["No se encontraron problemas: se guardó una copia limpia."]
                summary = "sin problemas detectados"
            self._set_results("\n".join(lines))
            self._task_done(f"Se guardó {path.name} ({pages} página(s), {summary})")

        self.start_task(work, on_success=done)


class OcrView(SingleFileToolView):
    title = "OCR PDF"
    description = ("Convierte un PDF escaneado en un PDF con texto que se puede buscar, "
                   "seleccionar y copiar.")
    run_label = "Aplicar OCR"
    picker_label = "Arrastra el PDF escaneado"
    compact_picker = True

    def build_options(self, body):
        card = self.options_card(body)
        row = self.option_row(card, "IDIOMA")
        self.language = ctk.CTkOptionMenu(row, values=list(OCR_LANGUAGES), width=230,
                                          **theme.OPTIONMENU)
        self.language.set("Español")
        self.language.pack(side="left")
        row = self.option_row(card, "PÁGINAS CON TEXTO")
        self.skip_text = ctk.CTkCheckBox(row, text="Saltear las páginas que ya tienen texto",
                                         **theme.CHECKBOX)
        self.skip_text.select()
        self.skip_text.pack(side="left")
        self.hint(card, "El texto se agrega como una capa invisible sobre cada página: la imagen "
                        "original no cambia. Puede tardar unos segundos por página.",
                  pady=(10, 14))

    def run(self):
        src = self.require_file()
        out_dir = self.get_output_dir() if src else None
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_ocr.pdf")
        lang = OCR_LANGUAGES[self.language.get()]
        skip = bool(self.skip_text.get())

        def work(progress):
            result, done, skipped = ocr.ocr_pdf(src, output, lang=lang, skip_text_pages=skip,
                                                progress=progress)
            message = f"PDF con texto buscable: {result.name} · {done} página(s) procesada(s)"
            if skipped:
                message += f" · {skipped} ya tenían texto"
            return message

        self.start_task(work)
