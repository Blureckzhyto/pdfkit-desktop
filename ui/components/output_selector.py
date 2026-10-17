"""Selector de carpeta de salida que recuerda la última ruta usada."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui import theme


class OutputSelector(ctk.CTkFrame):
    SETTINGS_KEY = "output_dir"

    def __init__(self, master, settings):
        super().__init__(master, fg_color="transparent")
        self.settings = settings
        initial = settings.get(self.SETTINGS_KEY)
        if not initial or not Path(initial).is_dir():
            downloads = Path.home() / "Downloads"
            initial = str(downloads if downloads.is_dir() else Path.home())

        ctk.CTkLabel(self, text="CARPETA DE SALIDA", width=140, anchor="w",
                     font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(side="left")
        self.entry = ctk.CTkEntry(self, **dict(theme.ENTRY, font=(theme.FONT_MONO, 13)))
        self.entry.insert(0, initial)
        self.entry.pack(side="left", fill="x", expand=True, padx=(4, 6))
        theme.attach_focus_ring(self.entry)
        ctk.CTkButton(self, text="Elegir carpeta", width=110, command=self._browse,
                      **theme.BTN_SECONDARY).pack(side="left")
        # nombre del archivo de salida (vacío = automático, como el original)
        ctk.CTkLabel(self, text="NOMBRE", anchor="w", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(18, 8))
        self.name_entry = ctk.CTkEntry(self, width=220, placeholder_text="Automático",
                                       **theme.ENTRY)
        self.name_entry.pack(side="left")
        theme.attach_focus_ring(self.name_entry)

    def clear_name(self) -> None:
        """Vuelve al nombre automático (tras guardar, para que el siguiente archivo no
        reciba por error el mismo nombre)."""
        self.name_entry.delete(0, "end")
        # CTkEntry solo vuelve a mostrar el texto de ejemplo al perder el foco; si el campo
        # no lo tiene ahora (p. ej. el nombre se escribió por código), se muestra ya
        if self.focus_get() is not self.name_entry._entry:
            self.name_entry._activate_placeholder()

    def get_name(self) -> str:
        """Nombre elegido para el archivo de salida (sin validar), o "" si es automático."""
        return self.name_entry.get().strip()

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.entry.get() or str(Path.home()))
        if chosen:
            self.entry.delete(0, "end")
            self.entry.insert(0, chosen)
            self.settings.set(self.SETTINGS_KEY, chosen)

    def get(self) -> Path:
        raw = self.entry.get().strip()
        if not raw:
            raise ValueError("Elige una carpeta de salida primero.")
        path = Path(raw).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        self.settings.set(self.SETTINGS_KEY, str(path))
        return path
