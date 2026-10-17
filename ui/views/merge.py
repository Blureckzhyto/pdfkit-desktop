from core import pdf_tools
from core.utils import human_size
from ui.components import FilePicker

from .base import ToolView


class MergeView(ToolView):
    title = "Unir PDF"
    icon = "+"
    description = "Combina varios PDF en uno solo. Usa ↑ ↓ para definir el orden."
    run_label = "Unir PDFs"

    def build_body(self, body):
        self.picker = FilePicker(body, exts=[".pdf"], multiple=True, reorderable=True,
                                 label="Arrastra los PDF a unir")
        self.picker.pack(fill="both", expand=True)

    def run(self):
        files = self.picker.get_files()
        if len(files) < 2:
            self.show_error("Agrega al menos dos archivos PDF.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{files[0].stem}_unido.pdf")

        def work(progress):
            result = pdf_tools.merge_pdfs(files, output, progress)
            return (f"Se unieron {len(files)} archivos en {result.name} "
                    f"({human_size(result.stat().st_size)})")

        self.start_task(work)
