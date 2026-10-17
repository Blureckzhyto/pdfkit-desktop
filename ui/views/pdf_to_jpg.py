import customtkinter as ctk

from core import pdf_tools
from core.utils import rename_outputs
from ui import theme

from .base import SingleFileToolView


class PdfToJpgView(SingleFileToolView):
    title = "PDF a JPG"
    icon = "→J"
    description = "Exporta cada página del PDF como imagen JPG. Requiere Poppler."
    run_label = "Convertir a JPG"
    input_exts = [".pdf"]
    picker_label = "Arrastra el PDF a convertir"

    def build_options(self, body):
        options = ctk.CTkFrame(body, **theme.CARD)
        options.pack(fill="x", pady=(12, 0))
        row = ctk.CTkFrame(options, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(row, text="RESOLUCIÓN (DPI)", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 10))
        self.dpi = ctk.CTkOptionMenu(row, values=["72", "100", "150", "200", "300"],
                                     width=100, **theme.OPTIONMENU)
        self.dpi.set("150")
        self.dpi.pack(side="left")
        ctk.CTkLabel(row, text="Más DPI = más nitidez y archivos más pesados",
                     font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(14, 0))

    def run(self):
        src = self.require_file()
        if not src:
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        dpi = int(self.dpi.get())
        name = self.output_name()

        def work(progress):
            outputs = pdf_tools.pdf_to_images(src, out_dir, dpi=dpi, progress=progress)
            outputs = rename_outputs(outputs, name, src.stem)
            return f"Se guardaron {len(outputs)} imagen(es) en {out_dir}"

        self.start_task(work)
