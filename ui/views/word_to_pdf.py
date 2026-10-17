from core import conversions
from core.utils import human_size

from .base import SingleFileToolView


class WordToPdfView(SingleFileToolView):
    title = "Word a PDF"
    icon = "W→"
    description = "Convierte un documento .docx a PDF (usa Microsoft Word o LibreOffice)."
    run_label = "Convertir a PDF"
    input_exts = [".docx", ".doc"]
    picker_label = "Arrastra el documento de Word"

    def run(self):
        src = self.require_file()
        if not src:
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}.pdf")

        def work(progress):
            result = conversions.word_to_pdf(src, output, progress)
            return f"Se guardó {result.name} ({human_size(result.stat().st_size)})"

        self.start_task(work)
