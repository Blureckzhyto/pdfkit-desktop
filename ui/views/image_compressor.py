import customtkinter as ctk

from core import image_tools
from core.image_tools import IMAGE_EXTS
from core.utils import human_size, rename_outputs
from ui import theme
from ui.components import FilePicker, attach_textbox

from .base import ToolView


class ImageCompressorView(ToolView):
    title = "Comprimir imágenes"
    icon = "%"
    description = "Reduce el peso de tus imágenes y compara el antes y el después."
    run_label = "Comprimir imágenes"

    def build_body(self, body):
        self.picker = FilePicker(body, exts=IMAGE_EXTS, multiple=True,
                                 label="Arrastra las imágenes a comprimir")
        self.picker.pack(fill="x")

        options = ctk.CTkFrame(body, **theme.CARD)
        options.pack(fill="x", pady=(12, 0))
        row = ctk.CTkFrame(options, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(row, text="CALIDAD", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 8))
        self.quality = ctk.CTkSlider(row, from_=10, to=95, number_of_steps=85,
                                     width=220, command=self._quality_changed,
                                     **theme.SLIDER)
        self.quality.set(70)
        self.quality.pack(side="left")
        self.quality_label = ctk.CTkLabel(row, text="70", width=34, font=theme.FONT_BODY,
                                          text_color=theme.TEXT_PRIMARY)
        self.quality_label.pack(side="left")
        ctk.CTkLabel(row, text="Menos calidad = archivos más livianos",
                     font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(14, 0))

        self.results = ctk.CTkTextbox(body, height=140, activate_scrollbars=True,
                                      **theme.TEXTBOX)
        self.results.pack(fill="both", expand=True, pady=(12, 0))
        attach_textbox(self.results)
        self._set_results("Aquí van a aparecer los resultados por archivo.")

    def _quality_changed(self, value):
        self.quality_label.configure(text=str(int(value)))

    def _set_results(self, text):
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", text)
        self.results.configure(state="disabled")

    def run(self):
        files = self.picker.get_files()
        if not files:
            self.show_error("Agrega al menos una imagen.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        quality = int(self.quality.get())
        name = self.output_name()

        def work(progress):
            results = image_tools.compress_images(files, out_dir, quality, progress)
            names = rename_outputs([out for out, _b, _a in results], name)
            return [(new, before, after) for new, (_o, before, after) in zip(names, results)]

        def done(results):
            lines = []
            total_before = total_after = 0
            for out, before, after in results:
                total_before += before
                total_after += after
                pct = (1 - after / before) * 100 if before else 0
                lines.append(f"{out.name}:  {human_size(before)} → {human_size(after)}"
                             f"  (−{pct:.0f}%)")
            self._set_results("\n".join(lines))
            saved = (1 - total_after / total_before) * 100 if total_before else 0
            self._task_done(
                f"Se comprimieron {len(results)} imagen(es): {human_size(total_before)}"
                f" → {human_size(total_after)} (ahorro del {saved:.0f}%)"
            )

        self.start_task(work, on_success=done)
