"""Fila de muestras de color cuadradas + selector personalizado."""
from __future__ import annotations

from tkinter import colorchooser

import customtkinter as ctk

from ui import theme


class ColorSwatches(ctk.CTkFrame):
    """`colors` = [(nombre, "#hex"), ...]. El botón "+" abre el selector del sistema."""

    def __init__(self, master, colors: list[tuple[str, str]], initial: str | None = None,
                 on_change=None, allow_custom: bool = True):
        super().__init__(master, fg_color="transparent")
        self.on_change = on_change
        self.value = (initial or colors[0][1]).upper()
        self._buttons: dict[str, ctk.CTkButton] = {}
        for _name, hex_color in colors:
            self._add_swatch(hex_color.upper())
        if allow_custom:
            ctk.CTkButton(self, text="+", width=24, height=24, command=self._pick_custom,
                          **theme.BTN_SECONDARY).pack(side="left", padx=(4, 0))
        self._refresh()

    def _add_swatch(self, hex_color: str) -> None:
        button = ctk.CTkButton(self, text="", width=22, height=22, corner_radius=0,
                               fg_color=hex_color, hover_color=hex_color, border_width=1,
                               border_color=theme.BORDER,
                               command=lambda c=hex_color: self.set(c, notify=True))
        button.pack(side="left", padx=2)
        self._buttons[hex_color] = button

    def _pick_custom(self) -> None:
        chosen = colorchooser.askcolor(color=self.value, title="Elegir color")
        if chosen and chosen[1]:
            hex_color = chosen[1].upper()
            if hex_color not in self._buttons:
                self._add_swatch(hex_color)
            self.set(hex_color, notify=True)

    def _refresh(self) -> None:
        for hex_color, button in self._buttons.items():
            selected = hex_color == self.value
            button.configure(border_width=3 if selected else 1,
                             border_color=theme.TEXT_PRIMARY if selected else theme.BORDER)

    def set(self, hex_color: str, notify: bool = False) -> None:
        self.value = hex_color.upper()
        if self.value not in self._buttons:
            self._add_swatch(self.value)
        self._refresh()
        if notify and self.on_change:
            self.on_change(self.value)

    def get(self) -> str:
        return self.value
