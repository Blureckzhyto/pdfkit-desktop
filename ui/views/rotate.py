"""Rotar PDF: rotación por página o para todas, sin abrir el editor."""
from __future__ import annotations

import customtkinter as ctk

from core import page_tools
from ui import theme
from ui.components import ScrollFrame, run_task

from .base import SingleFileToolView

ANGLES = ["0°", "90°", "180°", "270°"]


class RotateView(SingleFileToolView):
    title = "Rotar PDF"
    description = "Elige la rotación de cada página, o aplica la misma a todas."
    run_label = "Guardar rotación"
    picker_label = "Arrastra el PDF a rotar"
    compact_picker = True

    def build_options(self, body):
        self.src = None
        self.current: list[int] = []
        self.menus: list[ctk.CTkOptionMenu] = []
        self._token = 0
        bar = ctk.CTkFrame(body, **theme.CARD)
        bar.pack(fill="x", pady=(12, 8))
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(row, text="TODAS LAS PÁGINAS", font=theme.FONT_SECTION, width=150,
                     anchor="w", text_color=theme.TEXT_MUTED).pack(side="left")
        self.all_angle = ctk.CTkOptionMenu(row, values=ANGLES, width=90, **theme.OPTIONMENU)
        self.all_angle.set("90°")
        self.all_angle.pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Aplicar a todas", width=130, height=30,
                      command=self._apply_all, **theme.BTN_SECONDARY).pack(side="left")
        ctk.CTkButton(row, text="Restablecer", width=110, height=30,
                      command=self._reset, **theme.BTN_SECONDARY).pack(side="left", padx=8)
        self.list_frame = ScrollFrame(body, **theme.SCROLLFRAME)
        self.list_frame.pack(fill="both", expand=True)
        self._message("Carga un PDF para ver sus páginas.")

    def _message(self, text):
        for child in self.list_frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(self.list_frame, text=text, font=theme.FONT_BODY,
                     text_color=theme.TEXT_MUTED).pack(anchor="w", padx=12, pady=12)

    def on_file(self, path):
        self._token += 1
        token = self._token
        self.src = None
        self._message("Leyendo páginas…")

        def loaded(rotations):
            if token != self._token:
                return
            self.src, self.current = path, rotations
            self._build_rows()
            self.show_info(f"{len(rotations)} página(s).")

        run_task(self, lambda _p: page_tools.get_rotations(path), loaded,
                 lambda exc: (self._message(""), self.show_error(str(exc))))

    def _build_rows(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.menus = []
        for i, angle in enumerate(self.current):
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=f"Página {i + 1}", width=110, anchor="w", font=theme.FONT_BODY,
                         text_color=theme.TEXT_PRIMARY).pack(side="left")
            ctk.CTkLabel(row, text=f"actual: {angle}°", width=110, anchor="w",
                         font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY).pack(side="left")
            menu = ctk.CTkOptionMenu(row, values=ANGLES, width=90, **theme.OPTIONMENU)
            menu.set(f"{angle}°")
            menu.pack(side="left")
            self.menus.append(menu)

    def _apply_all(self):
        for menu in self.menus:
            menu.set(self.all_angle.get())

    def _reset(self):
        for menu, angle in zip(self.menus, self.current):
            menu.set(f"{angle}°")

    def run(self):
        if not self.src:
            self.show_error("Carga un PDF primero.")
            return
        rotations = {i: int(menu.get().rstrip("°")) for i, menu in enumerate(self.menus)}
        if all(rotations[i] == angle for i, angle in enumerate(self.current)):
            self.show_error("No cambiaste la rotación de ninguna página.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        src = self.src
        output = self.output_file(out_dir, f"{src.stem}_rotado.pdf")

        def work(progress):
            result, changed = page_tools.rotate_pages(src, output, rotations, progress)
            return f"Se guardó {result.name} · {changed} página(s) rotada(s)"

        self.start_task(work)
