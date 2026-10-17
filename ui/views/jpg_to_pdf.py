from core import pdf_tools
from core.image_tools import IMAGE_EXTS
from core.utils import human_size
from ui.components import FilePicker

from .base import ToolView


class JpgToPdfView(ToolView):
    title = "JPG a PDF"
    icon = "J→"
    description = "Combina una o varias imágenes en un solo PDF (una imagen por página)."
    run_label = "Crear PDF"

    def build_body(self, body):
        self.picker = FilePicker(body, exts=IMAGE_EXTS, multiple=True, reorderable=True,
                                 label="Arrastra las imágenes (JPG, PNG, WEBP, HEIC…)")
        self.picker.pack(fill="both", expand=True)

    def run(self):
        files = self.picker.get_files()
        if not files:
            self.show_error("Agrega al menos una imagen.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{files[0].stem}.pdf")

        def work(progress):
            result = pdf_tools.images_to_pdf(files, output, progress)
            return (f"Se creó {result.name} a partir de {len(files)} imagen(es) "
                    f"({human_size(result.stat().st_size)})")

        self.start_task(work)
