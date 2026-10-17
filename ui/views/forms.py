"""Rellenar formulario PDF: lista los campos AcroForm y escribe los valores."""
from __future__ import annotations

import customtkinter as ctk

from core import edit_sign
from ui import theme
from ui.components import FilePicker, ScrollFrame, run_task

from .base import ToolView

NONE_OPTION = "(sin elegir)"


class FormView(ToolView):
    title = "Rellenar formulario"
    icon = "FM"
    description = "Completa los campos de un formulario PDF (AcroForm)."
    run_label = "Guardar formulario"

    def build_body(self, body):
        self.src = None
        self._getters: dict[str, callable] = {}
        self._token = 0
        self.picker = FilePicker(body, exts=[".pdf"], multiple=False, compact=True,
                                 label="Arrastra el PDF con el formulario",
                                 on_change=self._file_changed)
        self.picker.pack(fill="x")
        self.fields_frame = ScrollFrame(body, **theme.SCROLLFRAME)
        self.fields_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.fields_frame.grid_columnconfigure(1, weight=1)
        self._placeholder("Carga un PDF para ver sus campos rellenables.")

    def _clear(self):
        for child in self.fields_frame.winfo_children():
            child.destroy()
        self._getters = {}

    def _placeholder(self, text, color=theme.TEXT_SECONDARY):
        self._clear()
        ctk.CTkLabel(self.fields_frame, text=text, font=theme.FONT_BODY, text_color=color,
                     wraplength=680, justify="left").grid(row=0, column=0, columnspan=2,
                                                          sticky="w", padx=12, pady=12)

    def _file_changed(self, files):
        if not files:
            return
        src = files[0]
        self.src = None
        self._token += 1
        token = self._token
        self._placeholder("Leyendo campos…")
        self.show_info("Leyendo campos…")

        def loaded(fields):
            if token == self._token:
                self.src = src
                self._populate(fields)

        def failed(exc):
            if token == self._token:
                self._placeholder(str(exc), theme.ERROR)
                self.show_error(str(exc))

        run_task(self, lambda _p: edit_sign.get_form_fields(src), loaded, failed)

    def _populate(self, fields):
        self._clear()
        if not fields:
            self._placeholder(edit_sign.NO_FIELDS_MSG, theme.WARNING)
            self.show_warning(edit_sign.NO_FIELDS_MSG)
            return
        ctk.CTkLabel(self.fields_frame, text=f"{len(fields)} CAMPO(S)", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).grid(row=0, column=0, sticky="w",
                                                           padx=12, pady=(10, 6))
        for row, field in enumerate(fields, start=1):
            label = field["label"] + ("  (solo lectura)" if field["readonly"] else "")
            ctk.CTkLabel(self.fields_frame, text=label, font=theme.FONT_BODY,
                         text_color=theme.TEXT_PRIMARY, anchor="w", width=220,
                         wraplength=220, justify="left").grid(row=row, column=0, sticky="nw",
                                                              padx=(12, 10), pady=5)
            widget, getter = self._make_widget(field)
            widget.grid(row=row, column=1, sticky="ew" if field["type"] == "text" else "w",
                        padx=(0, 12), pady=5)
            if field["readonly"]:
                widget.configure(state="disabled")
            else:
                self._getters[field["name"]] = getter
        self.show_info(f"{len(fields)} campo(s) listos para completar.")

    def _make_widget(self, field):
        parent = self.fields_frame
        kind = field["type"]
        if kind == "text" and field["multiline"]:
            box = ctk.CTkTextbox(parent, height=64, **theme.TEXTBOX)
            box.insert("1.0", field["value"])
            return box, lambda: box.get("1.0", "end-1c")
        if kind == "text":
            entry = ctk.CTkEntry(parent, **theme.ENTRY)
            entry.insert(0, field["value"])
            theme.attach_focus_ring(entry)
            return entry, entry.get
        if kind == "checkbox":
            on_state, on_label = field["options"][0]
            var = ctk.StringVar(value=on_state if field["value"] == on_state else "/Off")
            box = ctk.CTkCheckBox(parent, text=on_label, variable=var, onvalue=on_state,
                                  offvalue="/Off", **theme.CHECKBOX)
            return box, var.get
        # radio y lista desplegable: menú con los textos visibles
        if kind == "radio":
            mapping = {label: state for state, label in field["options"]}
            empty_value = "/Off"
        else:
            mapping = {label: value for value, label in field["options"]}
            empty_value = ""
        labels = [NONE_OPTION] + list(mapping)
        mapping[NONE_OPTION] = empty_value
        menu = ctk.CTkOptionMenu(parent, values=labels, width=240, **theme.OPTIONMENU)
        current = next((label for label, value in mapping.items()
                        if value == field["value"] and label != NONE_OPTION), NONE_OPTION)
        menu.set(current)
        return menu, lambda: mapping[menu.get()]

    def run(self):
        files = self.picker.get_files()
        if not files:
            self.show_error("Selecciona un PDF primero.")
            return
        if not self.src:
            self.show_error("Espera a que se lean los campos del formulario.")
            return
        if not self._getters:
            self.show_error(edit_sign.NO_FIELDS_MSG)
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        values = {name: getter() for name, getter in self._getters.items()}
        src = self.src
        output = self.output_file(out_dir, f"{src.stem}_relleno.pdf")

        def work(progress):
            result = edit_sign.fill_form(src, output, values, progress)
            return f"Se guardó {result.name} con {len(values)} campo(s) en {out_dir}"

        self.start_task(work)
