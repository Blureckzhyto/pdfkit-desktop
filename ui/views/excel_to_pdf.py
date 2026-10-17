from core import conversions
from core.utils import human_size

from .base import SingleFileToolView


class ExcelToPdfView(SingleFileToolView):
    title = "Excel a PDF"
    icon = "X→"
    description = "Convierte un libro .xlsx a PDF (ReportLab, o LibreOffice si está instalado)."
    run_label = "Convertir a PDF"
    input_exts = [".xlsx", ".xlsm"]
    picker_label = "Arrastra el libro de Excel"

    def run(self):
        src = self.require_file()
        if not src:
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}.pdf")

        def work(progress):
            result = conversions.excel_to_pdf(src, output, progress)
            return f"Se guardó {result.name} ({human_size(result.stat().st_size)})"

        self.start_task(work)
