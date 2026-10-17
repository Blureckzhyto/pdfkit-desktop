"""Andamiaje compartido de las vistas: encabezado, cuerpo, barra de ejecución y
barra de estado."""
from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from core.utils import named_output
from ui import anim, theme
from ui.assets import icon as load_icon
from ui.components import FilePicker, OutputSelector, run_task

PAD = theme.PAD
STATUS_ICONS = {"success": "✓  ", "error": "✕  ", "warning": "⚠  ", "info": ""}


class ToolView(ctk.CTkFrame):
    title = "Herramienta"
    icon = ""
    description = ""
    run_label = "Procesar"
    uses_output_dir = True

    def __init__(self, master, app):
        super().__init__(master, fg_color=theme.BG_PRIMARY, corner_radius=0)
        self.app = app
        self._running = False
        self._progress_value = 0.0
        # la app indica nombre, color de categoría, símbolo y clave de la herramienta
        name, color, symbol, key = getattr(app, "building_meta", None) or (
            self.title, theme.ACCENT, self.icon, None)
        self.title = name

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PAD, pady=(28, 4))
        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(anchor="w")
        tool_icon = load_icon(f"tool_{key}", 20) if key else None
        if tool_icon or symbol:
            ctk.CTkLabel(title_row, text="" if tool_icon else symbol, image=tool_icon,
                         width=40, height=40, corner_radius=12, fg_color=theme.tint(color, 0.12),
                         text_color=color, font=(theme.FONT_SEMIBOLD, 14)
                         ).pack(side="left", padx=(0, 14))
        self.title_label = ctk.CTkLabel(title_row, text=name, font=theme.FONT_TITLE,
                                        text_color=theme.TEXT_PRIMARY)
        self.title_label.pack(side="left")
        self.fade_in_labels = [(self.title_label, theme.TEXT_PRIMARY)]
        if self.description:
            description = ctk.CTkLabel(header, text=self.description, font=theme.FONT_BODY,
                                       text_color=theme.TEXT_SECONDARY, justify="left",
                                       wraplength=860)
            description.pack(anchor="w", pady=(6, 0))
            self.fade_in_labels.append((description, theme.TEXT_SECONDARY))

        # barra de estado: ancho completo, al pie del panel
        status_bar = ctk.CTkFrame(self, fg_color=theme.BG_SECONDARY, corner_radius=0)
        status_bar.pack(fill="x", side="bottom")
        ctk.CTkFrame(status_bar, height=1, corner_radius=0,
                     fg_color=theme.BORDER).pack(fill="x", side="top")
        self.status_bar = status_bar
        self.status = ctk.CTkLabel(status_bar, text="Listo.", anchor="w", justify="left",
                                   wraplength=860, font=theme.FONT_STATUS,
                                   text_color=theme.TEXT_MUTED, fg_color="transparent")
        self.status.pack(fill="x", padx=PAD, pady=7)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", side="bottom", padx=PAD, pady=(6, 16))
        if self.uses_output_dir:
            self.output_selector = OutputSelector(bottom, app.settings)
            self.output_selector.pack(fill="x", pady=(0, 12))
        else:
            self.output_selector = None
        run_row = ctk.CTkFrame(bottom, fg_color="transparent")
        run_row.pack(fill="x")
        self.run_button = ctk.CTkButton(run_row, text=self.run_label, height=40, width=160,
                                        command=self.run, **theme.BTN_PRIMARY)
        self.run_button.pack(side="left")
        self.progress = ctk.CTkProgressBar(run_row, **theme.PROGRESS)
        self.set_progress(0)
        self.progress.pack(side="left", fill="x", expand=True, padx=(16, 0), pady=4)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=PAD, pady=8)
        self.build_body(self.body)

    # ------------------------------------------------------------------ a implementar

    def build_body(self, body) -> None:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------ estado

    def _set_status(self, kind: str, message: str, toast: bool = True) -> None:
        background, color = theme.STATUS_STYLES[kind]
        self.status_bar.configure(fg_color=background)
        self.status.configure(text=STATUS_ICONS[kind] + message, text_color=color)
        toasts = getattr(self.app, "toasts", None)
        if toast and kind != "info" and toasts is not None and self.winfo_ismapped():
            toasts.show(kind, message)

    def show_error(self, message: str) -> None:
        self._set_status("error", message)

    def show_success(self, message: str) -> None:
        self._set_status("success", message)

    def show_warning(self, message: str) -> None:
        self._set_status("warning", message)

    def show_info(self, message: str) -> None:
        self._set_status("info", message)

    def get_output_dir(self) -> Path | None:
        try:
            return self.output_selector.get()
        except (ValueError, OSError) as exc:
            self.show_error(str(exc))
            return None

    def output_name(self) -> str:
        """Nombre que el usuario escribió para el archivo de salida ("" = automático)."""
        return self.output_selector.get_name() if self.output_selector else ""

    def output_file(self, out_dir: Path, default_name: str) -> Path:
        """Ruta del archivo de salida: el nombre elegido (con la extensión de
        `default_name`) o el nombre automático; nunca pisa un archivo existente."""
        return named_output(out_dir, default_name, self.output_name())

    def set_progress(self, value: float) -> None:
        """Avanza la barra con una interpolación suave (vuelve a 0 sin animación)."""
        value = max(0.0, min(1.0, value))
        start = self._progress_value
        self._progress_value = value

        def step(t):
            current = start + (value - start) * t
            # con valor 0 customtkinter igual dibuja el extremo redondeado como un punto
            self.progress.configure(progress_color=theme.ACCENT if current > 0.001
                                    else theme.PROGRESS["fg_color"])
            self.progress.set(current)

        anim.animate(self.progress, "value", 0 if value <= start and value == 0 else 260, step)

    def set_run_label(self, label: str) -> None:
        self.run_label = label
        if not self._running:
            self.run_button.configure(text=label)

    # ------------------------------------------------------------------ tareas en segundo plano

    def start_task(self, work, on_success=None) -> None:
        """`work(progress)` corre en otro hilo; su resultado va a `on_success`
        (por defecto `_task_done`, que espera un mensaje de éxito). Los
        manejadores propios deben llamar a `_task_done` para restablecer el estado."""
        if self._running:
            return
        self._running = True
        self.run_button.configure(state="disabled", text="Procesando…")
        self.set_progress(0)
        self.show_info("Procesando…")
        run_task(self, work, on_success or self._task_done, self._task_failed,
                 self._task_progress)

    def _task_progress(self, fraction: float, message: str | None) -> None:
        self.set_progress(fraction)
        if message:
            self.show_info(message)

    def _task_done(self, message, toast: bool = True) -> None:
        """`toast=False` cuando enseguida se va a mostrar una advertencia (un solo aviso)."""
        self._running = False
        self.run_button.configure(state="normal", text=self.run_label)
        self.set_progress(1)
        self._set_status("success", str(message), toast=toast)
        if self.output_selector:   # el nombre elegido valía para este archivo; el siguiente, automático
            self.output_selector.clear_name()

    def _task_failed(self, exc: Exception) -> None:
        self._running = False
        self.run_button.configure(state="normal", text=self.run_label)
        self.set_progress(0)
        self.show_error(str(exc) or f"Error al procesar el archivo ({type(exc).__name__}).")


class SingleFileToolView(ToolView):
    """Vista cuyo insumo principal es exactamente un archivo."""
    input_exts: list[str] = [".pdf"]
    picker_label: str | None = None
    compact_picker = False

    def build_body(self, body) -> None:
        self.picker = FilePicker(body, exts=self.input_exts, multiple=False,
                                 label=self.picker_label, compact=self.compact_picker,
                                 on_change=self._picked)
        self.picker.pack(fill="x")
        self.build_options(body)

    def _picked(self, files) -> None:
        if files:
            self.on_file(files[0])

    def on_file(self, path: Path) -> None:
        """Se llama al elegir un archivo (las subclases pueden leerlo en segundo plano)."""

    def build_options(self, body) -> None:
        pass

    def options_card(self, body, pady=(12, 0)):
        card = ctk.CTkFrame(body, **theme.CARD)
        card.pack(fill="x", pady=pady)
        return card

    def option_row(self, parent, label: str | None = None, last: bool = False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 14 if last else 0))
        if label:
            ctk.CTkLabel(row, text=label, font=theme.FONT_SECTION, width=130, anchor="w",
                         text_color=theme.TEXT_MUTED).pack(side="left")
        return row

    def hint(self, parent, text: str, pady=(4, 0)):
        label = ctk.CTkLabel(parent, text=text, font=theme.FONT_SMALL, justify="left",
                             text_color=theme.TEXT_SECONDARY, wraplength=760, anchor="w")
        label.pack(fill="x", padx=16, pady=pady)
        return label

    def require_file(self) -> Path | None:
        files = self.picker.get_files()
        if not files:
            self.show_error("Selecciona un archivo primero.")
            return None
        return files[0]
