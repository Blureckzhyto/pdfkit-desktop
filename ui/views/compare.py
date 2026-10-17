"""Comparar PDF: diferencias de texto lado a lado o informe visual."""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from core import compare
from ui import theme
from ui.components import FilePicker, ScrollBar, Scroller, attach_textbox

from .base import ToolView

MODES = ["TEXTO", "VISUAL"]
LINE_STYLES = {  # estado -> (fondo, texto, prefijo)
    "equal": (theme.SURFACE, theme.TEXT_PRIMARY, "  "),
    "removed": (theme.ERROR_BG, theme.ERROR, "− "),
    "added": (theme.SUCCESS_BG, theme.SUCCESS, "+ "),
    "empty": (theme.BG_SECONDARY, theme.TEXT_MUTED, "  "),
}


class CompareView(ToolView):
    title = "Comparar PDF"
    description = "Encuentra las diferencias entre dos versiones de un documento."
    run_label = "Comparar"

    def build_body(self, body):
        pickers = ctk.CTkFrame(body, fg_color="transparent")
        pickers.pack(fill="x")
        pickers.grid_columnconfigure((0, 1), weight=1, uniform="p")
        self.pickers = []
        for col, label in enumerate(("PDF A · ORIGINAL", "PDF B · MODIFICADO")):
            ctk.CTkLabel(pickers, text=label, font=theme.FONT_SECTION, text_color=theme.TEXT_MUTED
                         ).grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 6, 0))
            picker = FilePicker(pickers, exts=[".pdf"], multiple=False, compact=True,
                                label="Arrastra el PDF " + "AB"[col])
            picker.grid(row=1, column=col, sticky="ew", padx=(0, 6) if col == 0 else (6, 0))
            self.pickers.append(picker)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(10, 8))
        ctk.CTkLabel(row, text="MODO", font=theme.FONT_SECTION, text_color=theme.TEXT_MUTED
                     ).pack(side="left", padx=(0, 10))
        self.mode = ctk.CTkSegmentedButton(row, values=MODES, command=self._mode_changed,
                                           **theme.SEGMENTED)
        self.mode.set("TEXTO")
        self.mode.pack(side="left")
        self.mode_hint = ctk.CTkLabel(row, text="", font=theme.FONT_SMALL,
                                      text_color=theme.TEXT_SECONDARY)
        self.mode_hint.pack(side="left", padx=12)

        self.results_host = ctk.CTkFrame(body, fg_color="transparent")
        self.results_host.pack(fill="both", expand=True)
        self._build_text_results()
        self.visual_box = ctk.CTkTextbox(self.results_host, **theme.TEXTBOX)
        attach_textbox(self.visual_box)
        self._mode_changed("TEXTO")

    def _build_text_results(self):
        frame = ctk.CTkFrame(self.results_host, **theme.CARD)
        self.text_frame = frame
        frame.grid_columnconfigure((0, 1), weight=1, uniform="t")
        frame.grid_rowconfigure(1, weight=1)
        self.texts = []
        for col, label in enumerate(("A · ORIGINAL", "B · MODIFICADO")):
            ctk.CTkLabel(frame, text=label, font=theme.FONT_SECTION, text_color=theme.TEXT_MUTED
                         ).grid(row=0, column=col, sticky="w", padx=12, pady=(8, 2))
            text = tk.Text(frame, wrap="none", font=(theme.FONT_MONO, 12), relief="flat",
                           borderwidth=0, highlightthickness=1, padx=6, pady=4)
            text.grid(row=1, column=col, sticky="nsew", padx=(8, 4) if col == 0 else (4, 0),
                      pady=(0, 8))
            self.texts.append(text)
        self._paint_texts()
        theme.on_mode_change(frame, self._paint_texts)
        scroll = ScrollBar(frame)
        scroll.grid(row=1, column=2, sticky="ns", padx=(2, 4), pady=(0, 8))
        self._scrollbar = scroll
        # las dos columnas se desplazan juntas: el motor mueve la A y la B la sigue
        left, right = self.texts
        self.scroller = Scroller(left)
        self.scroller.alias(right)
        self.scroller.bind_bar(scroll, "y", connect=False)
        left.configure(yscrollcommand=self._on_text_scroll,
                       xscrollcommand=lambda first, _last: right.xview_moveto(first))
        right.configure(yscrollcommand=lambda *_a: None)
        self._fill_texts([("Elige los dos PDFs y presiona Comparar.", "empty", "", "empty")])

    def _paint_texts(self):
        r = theme.resolve
        for text in self.texts:
            text.configure(bg=r(theme.SURFACE), fg=r(theme.TEXT_PRIMARY),
                           highlightbackground=r(theme.BORDER), highlightcolor=r(theme.BORDER),
                           insertbackground=r(theme.TEXT_PRIMARY))
            for state, (bg, fg, _prefix) in LINE_STYLES.items():
                text.tag_configure(state, background=r(bg), foreground=r(fg))

    # desplazamiento sincronizado de las dos columnas
    def _on_text_scroll(self, first, last):
        self._scrollbar.set(first, last)
        self.texts[1].yview_moveto(first)

    def _fill_texts(self, rows):
        for text in self.texts:
            text.configure(state="normal")
            text.delete("1.0", "end")
        for left, left_state, right, right_state in rows:
            for text, line, state in ((self.texts[0], left, left_state),
                                      (self.texts[1], right, right_state)):
                prefix = LINE_STYLES[state][2]
                text.insert("end", prefix + line + "\n", state)
        for text in self.texts:
            text.configure(state="disabled")

    def _mode_changed(self, mode):
        self.text_frame.pack_forget()
        self.visual_box.pack_forget()
        if mode == "TEXTO":
            self.text_frame.pack(fill="both", expand=True)
            self.mode_hint.configure(text="Líneas quitadas en rojo, agregadas en verde.")
        else:
            self.visual_box.pack(fill="both", expand=True)
            self.mode_hint.configure(text="Genera un PDF con las páginas lado a lado y los "
                                          "cambios en rojo.")
            self._set_visual("El informe visual se guarda en la carpeta de salida.")

    def _set_visual(self, text):
        self.visual_box.configure(state="normal")
        self.visual_box.delete("1.0", "end")
        self.visual_box.insert("1.0", text)
        self.visual_box.configure(state="disabled")

    @staticmethod
    def _page_warning(pages_a, pages_b):
        if pages_a != pages_b:
            return (f"Los PDFs tienen distinta cantidad de páginas (A: {pages_a}, B: {pages_b}).")
        return None

    def run(self):
        files = [p.get_files() for p in self.pickers]
        if not all(files):
            self.show_error("Elige los dos PDFs a comparar.")
            return
        src_a, src_b = files[0][0], files[1][0]
        if self.mode.get() == "TEXTO":
            self._run_text(src_a, src_b)
        else:
            self._run_visual(src_a, src_b)

    def _run_text(self, src_a, src_b):
        def done(result):
            self._fill_texts(result["rows"] or [("(sin texto)", "empty", "(sin texto)", "empty")])
            if result["identical"]:
                message = "El texto de los dos PDFs es idéntico."
            else:
                message = (f"Diferencias: {result['removed']} línea(s) quitada(s) y "
                           f"{result['added']} agregada(s).")
            warning = self._page_warning(result["pages_a"], result["pages_b"])
            self._task_done(message, toast=not warning)
            if warning:
                self.show_warning(f"{message} {warning}")

        self.start_task(lambda progress: compare.compare_text(src_a, src_b, progress),
                        on_success=done)

    def _run_visual(self, src_a, src_b):
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"comparacion_{src_a.stem}_vs_{src_b.stem}.pdf")

        def done(result):
            changed = result["changed_pages"]
            lines = [f"Páginas comparadas: {result['compared']}",
                     f"Páginas con diferencias: {', '.join(map(str, changed)) if changed else 'ninguna'}",
                     f"Informe: {result['path']}"]
            warning = self._page_warning(result["pages_a"], result["pages_b"])
            if warning:
                lines.append(warning + " Solo se compararon las páginas en común.")
            self._set_visual("\n".join(lines))
            message = (f"{len(changed)} página(s) con diferencias · informe: {result['path'].name}"
                       if changed else f"No hay diferencias visuales · informe: {result['path'].name}")
            self._task_done(message, toast=not warning)
            if warning:
                self.show_warning(f"{message}. {warning}")

        self.start_task(lambda progress: compare.compare_visual(src_a, src_b, output,
                                                                progress=progress),
                        on_success=done)
