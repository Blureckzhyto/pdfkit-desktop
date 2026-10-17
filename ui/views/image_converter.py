import customtkinter as ctk

from core import image_tools
from core.image_tools import IMAGE_EXTS
from core.utils import rename_outputs
from ui import theme
from ui.components import FilePicker

from .base import ToolView


class ImageConverterView(ToolView):
    title = "Convertir imágenes"
    icon = "↔"
    description = "Convierte imágenes entre PNG, JPG, WEBP, BMP, TIFF y HEIC."
    run_label = "Convertir imágenes"

    def build_body(self, body):
        self.picker = FilePicker(body, exts=IMAGE_EXTS, multiple=True,
                                 label="Arrastra las imágenes a convertir")
        self.picker.pack(fill="x")

        options = ctk.CTkFrame(body, **theme.CARD)
        options.pack(fill="x", pady=(12, 0))
        row = ctk.CTkFrame(options, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(row, text="CONVERTIR A", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 10))
        self.format = ctk.CTkOptionMenu(row, values=list(image_tools.FORMATS),
                                        width=100, **theme.OPTIONMENU)
        self.format.set("PNG")
        self.format.pack(side="left")
        ctk.CTkLabel(row, text="CALIDAD", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(20, 8))
        self.quality = ctk.CTkSlider(row, from_=10, to=100, number_of_steps=90,
                                     width=180, command=self._quality_changed,
                                     **theme.SLIDER)
        self.quality.set(90)
        self.quality.pack(side="left")
        self.quality_label = ctk.CTkLabel(row, text="90", width=34, font=theme.FONT_BODY,
                                          text_color=theme.TEXT_PRIMARY)
        self.quality_label.pack(side="left")
        ctk.CTkLabel(options, text="La calidad aplica a las salidas JPG, WEBP y HEIC.",
                     font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=14,
                                                           pady=(0, 10))

    def _quality_changed(self, value):
        self.quality_label.configure(text=str(int(value)))

    def run(self):
        files = self.picker.get_files()
        if not files:
            self.show_error("Agrega al menos una imagen.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        fmt = self.format.get()
        quality = int(self.quality.get())
        name = self.output_name()

        def work(progress):
            outputs = image_tools.convert_images(files, out_dir, fmt, quality, progress)
            outputs = rename_outputs(outputs, name, files[0].stem if len(files) == 1 else None)
            return f"Se convirtieron {len(outputs)} imagen(es) a {fmt} en {out_dir}"

        self.start_task(work)
