from core import conversions
from core.utils import human_size

from .base import SingleFileToolView


class PdfToExcelView(SingleFileToolView):
    title = "PDF a Excel"
    icon = "→X"
    description = "Extrae las tablas de un PDF a un libro .xlsx (una hoja por tabla)."
    run_label = "Extraer tablas"
    input_exts = [".pdf"]
    picker_label = "Arrastra el PDF con tablas"

    def run(self):
        src = self.require_file()
        if not src:
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}.xlsx")

        def work(progress):
            result, count = conversions.pdf_to_excel(src, output, progress)
            return (f"Se extrajeron {count} tabla(s) en {result.name} "
                    f"({human_size(result.stat().st_size)})")

        self.start_task(work)
