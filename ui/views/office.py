"""PowerPoint a PDF, HTML a PDF, PDF a PowerPoint y PDF a PDF/A."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import customtkinter as ctk

from core import convert_extra
from ui import theme
from ui.components import FilePicker

from .base import SingleFileToolView, ToolView


class PptxToPdfView(SingleFileToolView):
    title = "PowerPoint a PDF"
    description = "Convierte presentaciones .pptx (o .ppt) a PDF."
    run_label = "Convertir a PDF"
    input_exts = [".pptx", ".ppt"]
    picker_label = "Arrastra la presentación"
    compact_picker = True

    def build_options(self, body):
        card = self.options_card(body)
        self.hint(card, "Se usa Microsoft PowerPoint o LibreOffice si están instalados (mejor "
                        "calidad). Si no, se hace un renderizado básico de las diapositivas.",
                  pady=(14, 14))

    def run(self):
        src = self.require_file()
        out_dir = self.get_output_dir() if src else None
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}.pdf")

        def work(progress):
            return convert_extra.pptx_to_pdf(src, output, progress)

        def done(result):
            path, method, note = result
            self._task_done(f"Se guardó {path.name} (con {method})", toast=not note)
            if note:
                self.show_warning(f"Se guardó {path.name}. {note}")

        self.start_task(work, on_success=done)


class HtmlToPdfView(ToolView):
    title = "HTML a PDF"
    description = "Convierte una página web o un archivo .html en PDF."
    run_label = "Convertir a PDF"

    def build_body(self, body):
        self.picker = FilePicker(body, exts=[".html", ".htm"], multiple=False, compact=True,
                                 label="Arrastra un archivo HTML",
                                 on_change=lambda _f: self.url_entry.delete(0, "end"))
        self.picker.pack(fill="x")
        card = ctk.CTkFrame(body, **theme.CARD)
        card.pack(fill="x", pady=(12, 0))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(row, text="O PEGA UNA URL", font=theme.FONT_SECTION, width=130, anchor="w",
                     text_color=theme.TEXT_MUTED).pack(side="left")
        self.url_entry = ctk.CTkEntry(row, placeholder_text="https://ejemplo.com/pagina",
                                      **theme.ENTRY)
        self.url_entry.pack(side="left", fill="x", expand=True)
        theme.attach_focus_ring(self.url_entry)
        ctk.CTkLabel(card, text="Si escribes una URL, se usa en lugar del archivo (necesita "
                                "conexión a internet). El motor es WeasyPrint; si no puede con la "
                                "página, se reintenta con Microsoft Edge.",
                     font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY, wraplength=760,
                     justify="left", anchor="w").pack(fill="x", padx=16, pady=(8, 14))

    def run(self):
        url = self.url_entry.get().strip()
        files = self.picker.get_files()
        if url:
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url
            source = url
            stem = (urlparse(url).netloc or "pagina").replace(":", "_")
        elif files:
            source, stem = str(files[0]), files[0].stem
        else:
            self.show_error("Elige un archivo HTML o pega una URL.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{stem}.pdf")

        def work(progress):
            result, engine = convert_extra.html_to_pdf(source, output, progress)
            return f"Se guardó {result.name} (motor: {engine})"

        self.start_task(work)


class PdfToPptxView(SingleFileToolView):
    title = "PDF a PowerPoint"
    description = "Cada página del PDF se convierte en una diapositiva."
    run_label = "Convertir a PowerPoint"
    picker_label = "Arrastra el PDF a convertir"
    compact_picker = True

    def build_options(self, body):
        card = self.options_card(body)
        row = self.option_row(card, "CALIDAD (DPI)")
        self.dpi = ctk.CTkOptionMenu(row, values=["100", "150", "200"], width=90,
                                     **theme.OPTIONMENU)
        self.dpi.set("150")
        self.dpi.pack(side="left")
        self.hint(card, "El texto no será editable. Para texto editable, el PDF original debe "
                        "tener texto seleccionable.", pady=(10, 14))

    def run(self):
        src = self.require_file()
        out_dir = self.get_output_dir() if src else None
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}.pptx")
        dpi = int(self.dpi.get())

        def work(progress):
            result, slides = convert_extra.pdf_to_pptx(src, output, dpi, progress)
            return f"Se creó {result.name} con {slides} diapositiva(s)"

        self.start_task(work)


class PdfToPdfaView(SingleFileToolView):
    title = "PDF a PDF/A"
    description = "Convierte el PDF al formato de archivo a largo plazo PDF/A-1b."
    run_label = "Convertir a PDF/A"
    picker_label = "Arrastra el PDF a archivar"
    compact_picker = True

    def build_options(self, body):
        card = self.options_card(body)
        if convert_extra.find_ghostscript():
            text = ("Ghostscript detectado: se generará PDF/A-1b completo, conservando el "
                    "texto seleccionable.")
        else:
            text = ("Ghostscript no está instalado: se generará PDF/A-1b básico, con cada "
                    "página guardada como imagen (el texto deja de ser seleccionable). "
                    "Instala Ghostscript para conservar el texto.")
        self.hint(card, text, pady=(14, 14))

    def run(self):
        src = self.require_file()
        out_dir = self.get_output_dir() if src else None
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_pdfa.pdf")

        def work(progress):
            return convert_extra.pdf_to_pdfa(src, output, progress)

        def done(result):
            path, level = result
            self._task_done(f"Se guardó {Path(path).name} · {level}",
                            toast=level != convert_extra.LEVEL_BASIC)
            if level == convert_extra.LEVEL_BASIC:
                self.show_warning(f"Se guardó {Path(path).name} · {level}")

        self.start_task(work, on_success=done)
