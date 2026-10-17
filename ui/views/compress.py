import customtkinter as ctk

from core import pdf_tools
from core.utils import human_size
from ui import theme

from .base import SingleFileToolView

LEVELS = {"Calidad baja (más liviano)": "low", "Media (recomendada)": "medium",
          "Calidad alta": "high"}


class CompressView(SingleFileToolView):
    title = "Comprimir PDF"
    icon = "↓"
    description = "Reduce el peso de un PDF recomprimiendo sus imágenes y flujos."
    run_label = "Comprimir PDF"
    input_exts = [".pdf"]
    picker_label = "Arrastra el PDF a comprimir"

    def build_options(self, body):
        options = ctk.CTkFrame(body, **theme.CARD)
        options.pack(fill="x", pady=(12, 0))
        row = ctk.CTkFrame(options, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(row, text="CALIDAD", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 10))
        self.level = ctk.CTkSegmentedButton(row, values=list(LEVELS), **theme.SEGMENTED)
        self.level.set("Media (recomendada)")
        self.level.pack(side="left")

    def run(self):
        src = self.require_file()
        if not src:
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        quality = LEVELS[self.level.get()]
        output = self.output_file(out_dir, f"{src.stem}_comprimido.pdf")

        def work(progress):
            before = src.stat().st_size
            result = pdf_tools.compress_pdf(src, output, quality, progress)
            after = result.stat().st_size
            saved = (1 - after / before) * 100 if before else 0
            if saved <= 0:
                return (f"Se guardó como {result.name} ({human_size(after)}) — este PDF "
                        "ya estaba bien optimizado.")
            return (f"{result.name}: {human_size(before)} → {human_size(after)} "
                    f"(ahorro del {saved:.0f}%)")

        self.start_task(work)
