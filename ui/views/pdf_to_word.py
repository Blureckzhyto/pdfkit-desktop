from core import conversions
from core.utils import human_size

from .base import SingleFileToolView


class PdfToWordView(SingleFileToolView):
    title = "PDF a Word"
    icon = "→W"
    description = "Convierte un PDF en un documento .docx editable (solo PDF con texto)."
    run_label = "Convertir a Word"
    input_exts = [".pdf"]
    picker_label = "Arrastra el PDF a convertir"

    def run(self):
        src = self.require_file()
        if not src:
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}.docx")

        def work(progress):
            result = conversions.pdf_to_word(src, output, progress)
            return f"Se guardó {result.name} ({human_size(result.stat().st_size)})"

        self.start_task(work)
