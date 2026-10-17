import customtkinter as ctk

from core import pdf_tools
from core.utils import human_size, rename_outputs
from ui import theme
from ui.components import attach_textbox

from .base import SingleFileToolView

MODES = ["Rangos de páginas", "Cada N páginas", "Tamaño máximo (MB)"]
HINTS = {
    "Rangos de páginas": "ej.: 1-3, 5, 8-10 — cada rango genera su propio PDF",
    "Cada N páginas": "ej.: 2 — un PDF nuevo cada 2 páginas",
    "Tamaño máximo (MB)": "Cada parte queda por debajo del límite; los archivos se llaman nombre_parte01.pdf, parte02…",
}
LABELS = {
    "Rangos de páginas": "Rangos:",
    "Cada N páginas": "Páginas por archivo:",
    "Tamaño máximo (MB)": "Tamaño máximo por parte (MB):",
}
PLACEHOLDERS = {"Rangos de páginas": "1-3, 5, 8-10", "Cada N páginas": "2",
                "Tamaño máximo (MB)": "24"}
DEFAULT_MAX_MB = "24"


class SplitView(SingleFileToolView):
    title = "Dividir PDF"
    icon = "/"
    description = "Divide un PDF en varios archivos."
    run_label = "Dividir PDF"
    input_exts = [".pdf"]
    picker_label = "Arrastra el PDF a dividir"

    def build_options(self, body):
        options = ctk.CTkFrame(body, **theme.CARD)
        options.pack(fill="x", pady=(12, 0))
        row = ctk.CTkFrame(options, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(row, text="DIVIDIR POR", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 10))
        self.mode = ctk.CTkSegmentedButton(row, values=MODES, command=self._mode_changed,
                                           **theme.SEGMENTED)
        self.mode.set(MODES[0])
        self.mode.pack(side="left")
        self.value_label = ctk.CTkLabel(row, text=LABELS[MODES[0]], font=theme.FONT_BODY,
                                        text_color=theme.TEXT_PRIMARY)
        self.value_label.pack(side="left", padx=(14, 6))
        self.value_entry = ctk.CTkEntry(row, width=180,
                                        placeholder_text=PLACEHOLDERS[MODES[0]],
                                        **theme.ENTRY)
        self.value_entry.pack(side="left")
        theme.attach_focus_ring(self.value_entry)
        self.hint = ctk.CTkLabel(options, text=HINTS[MODES[0]], font=theme.FONT_SMALL,
                                 text_color=theme.TEXT_SECONDARY)
        self.hint.pack(anchor="w", padx=14, pady=(0, 10))

        self.results = ctk.CTkTextbox(body, height=140, activate_scrollbars=True,
                                      **theme.TEXTBOX)
        self.results.pack(fill="both", expand=True, pady=(12, 0))
        attach_textbox(self.results)
        self._set_results("Aquí van a aparecer los archivos generados.")

    def _mode_changed(self, mode):
        self.hint.configure(text=HINTS[mode])
        self.value_label.configure(text=LABELS[mode])
        self.value_entry.delete(0, "end")
        self.value_entry.configure(placeholder_text=PLACEHOLDERS[mode])
        if mode == "Tamaño máximo (MB)":
            self.value_entry.insert(0, DEFAULT_MAX_MB)

    def _set_results(self, text):
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", text)
        self.results.configure(state="disabled")

    def run(self):
        src = self.require_file()
        if not src:
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        mode = self.mode.get()
        value = self.value_entry.get().strip()
        name = self.output_name()
        if not value:
            self.show_error("Ingresa un valor para el modo de división elegido.")
            return

        def work(progress):
            oversized: list[int] = []
            if mode == "Rangos de páginas":
                outputs = pdf_tools.split_by_ranges(src, value, out_dir, progress)
            elif mode == "Cada N páginas":
                try:
                    n = int(value)
                except ValueError:
                    raise ValueError("Las páginas por archivo deben ser un número entero.")
                outputs = pdf_tools.split_every_n(src, n, out_dir, progress)
            else:
                try:
                    mb = float(value.replace(",", "."))
                except ValueError:
                    raise ValueError("El tamaño máximo debe ser un número de megabytes.")
                outputs, oversized = pdf_tools.split_by_size(src, mb, out_dir, progress)
            return rename_outputs(outputs, name, src.stem), oversized, value

        def done(result):
            outputs, oversized, limit = result
            lines = [f"{p.name}  —  {human_size(p.stat().st_size)}" for p in outputs]
            self._set_results("\n".join(lines))
            self._task_done(f"Se crearon {len(outputs)} archivo(s) en {out_dir}", toast=not oversized)
            if oversized:
                names = ", ".join(outputs[n - 1].name for n in oversized)
                self.show_warning(
                    f"Se crearon {len(outputs)} archivo(s), pero hay páginas que por sí "
                    f"solas superan {limit} MB, así que estas partes exceden el límite: {names}"
                )

        self.start_task(work, on_success=done)
