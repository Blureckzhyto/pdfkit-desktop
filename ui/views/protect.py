"""Proteger / Desproteger PDF con contraseña."""
from __future__ import annotations

import customtkinter as ctk

from core import edit_sign
from ui import theme
from ui.components import FilePicker

from .base import ToolView

MODES = ["PROTEGER", "DESPROTEGER"]
RUN_LABELS = {"PROTEGER": "Proteger PDF", "DESPROTEGER": "Desproteger PDF"}
MASK = "•"


class ProtectView(ToolView):
    """Con `fixed_mode` la vista queda en un solo modo y sin selector (así se usa
    en la barra lateral: 'Proteger PDF' y 'Desproteger PDF')."""
    title = "Proteger / Desproteger"
    icon = "PW"
    description = "Agrega o quita la contraseña de un PDF."
    run_label = RUN_LABELS["PROTEGER"]
    fixed_mode: str | None = None

    def build_body(self, body):
        self.picker = FilePicker(body, exts=[".pdf"], multiple=False, compact=True,
                                 label="Arrastra el PDF")
        self.picker.pack(fill="x")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(10, 8))
        self.mode = ctk.CTkSegmentedButton(row, values=MODES, command=self._mode_changed,
                                           **theme.SEGMENTED)
        self.mode.set(self.fixed_mode or "PROTEGER")
        if not self.fixed_mode:
            ctk.CTkLabel(row, text="MODO", font=theme.FONT_SECTION,
                         text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 10))
            self.mode.pack(side="left")
        self.show_passwords = ctk.CTkCheckBox(row, text="Mostrar contraseñas",
                                              command=self._toggle_mask, **theme.CHECKBOX)
        self.show_passwords.pack(side="right" if not self.fixed_mode else "left")

        # --- proteger
        self.protect_frame = ctk.CTkFrame(body, **theme.CARD)
        self.protect_frame.grid_columnconfigure(1, weight=1)
        self.user_pw = self._password_row(
            self.protect_frame, 0, "CONTRASEÑA PARA ABRIR",
            "Opcional. Sin ella, cualquiera puede abrir el PDF.")
        self.owner_pw = self._password_row(
            self.protect_frame, 2, "CONTRASEÑA DE PROPIETARIO",
            "Controla los permisos. Si la dejas vacía se genera una al azar.")
        ctk.CTkLabel(self.protect_frame, text="PERMISOS", font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).grid(row=4, column=0, sticky="nw",
                                                           padx=14, pady=(10, 12))
        perms = ctk.CTkFrame(self.protect_frame, fg_color="transparent")
        perms.grid(row=4, column=1, sticky="w", padx=(0, 14), pady=(10, 12))
        self.allow_print = ctk.CTkCheckBox(perms, text="Permitir impresión", **theme.CHECKBOX)
        self.allow_copy = ctk.CTkCheckBox(perms, text="Permitir copia de texto", **theme.CHECKBOX)
        self.allow_modify = ctk.CTkCheckBox(perms, text="Permitir modificaciones",
                                            **theme.CHECKBOX)
        for box, checked in ((self.allow_print, True), (self.allow_copy, True),
                             (self.allow_modify, False)):
            box.pack(anchor="w", pady=2)
            if checked:
                box.select()

        # --- desproteger
        self.unprotect_frame = ctk.CTkFrame(body, **theme.CARD)
        self.unprotect_frame.grid_columnconfigure(1, weight=1)
        self.unlock_pw = self._password_row(
            self.unprotect_frame, 0, "CONTRASEÑA",
            "La contraseña para abrir o la de propietario del PDF. "
            "Se guarda una copia sin contraseña.")

        self._mode_changed(self.mode.get())

    def _password_row(self, parent, row, label, hint):
        ctk.CTkLabel(parent, text=label, font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).grid(row=row, column=0, sticky="w",
                                                           padx=14, pady=(12, 0))
        entry = ctk.CTkEntry(parent, width=300, show=MASK, **theme.ENTRY)
        entry.grid(row=row, column=1, sticky="w", padx=(0, 14), pady=(12, 0))
        theme.attach_focus_ring(entry)
        ctk.CTkLabel(parent, text=hint, font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY,
                     wraplength=520, justify="left").grid(row=row + 1, column=1, sticky="w",
                                                          padx=(0, 14), pady=(2, 0))
        return entry

    def _toggle_mask(self):
        show = "" if self.show_passwords.get() else MASK
        for entry in (self.user_pw, self.owner_pw, self.unlock_pw):
            entry.configure(show=show)

    def _mode_changed(self, mode):
        self.protect_frame.pack_forget()
        self.unprotect_frame.pack_forget()
        (self.protect_frame if mode == "PROTEGER" else self.unprotect_frame).pack(fill="x")
        self.set_run_label(RUN_LABELS[mode])

    def run(self):
        files = self.picker.get_files()
        if not files:
            self.show_error("Selecciona un PDF primero.")
            return
        src = files[0]
        if self.mode.get() == "PROTEGER":
            self._protect(src)
        else:
            self._unprotect(src)

    def _protect(self, src):
        user, owner = self.user_pw.get(), self.owner_pw.get()
        if not user and not owner:
            self.show_error("Ingresa al menos una contraseña.")
            return
        allow_print = bool(self.allow_print.get())
        allow_copy = bool(self.allow_copy.get())
        allow_modify = bool(self.allow_modify.get())
        restricted = not (allow_print and allow_copy and allow_modify)
        if user and owner and user == owner and restricted:
            self.show_error("La contraseña de propietario tiene que ser distinta de la de "
                            "apertura; si no, los permisos no tienen efecto.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_protegido.pdf")

        def work(progress):
            result, algorithm, generated = edit_sign.protect_pdf(
                src, output, user, owner, allow_print, allow_copy, allow_modify, progress)
            message = f"Se guardó {result.name} cifrado con {algorithm}"
            if generated:
                message += " · contraseña de propietario generada al azar"
            return message

        self.start_task(work)

    def _unprotect(self, src):
        password = self.unlock_pw.get()
        if not password:
            self.show_error("Ingresa la contraseña del PDF.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{src.stem}_desbloqueado.pdf")

        def work(progress):
            result = edit_sign.unprotect_pdf(src, output, password, progress)
            return f"Se guardó {result.name} sin contraseña en {out_dir}"

        self.start_task(work)


class ProtectPdfView(ProtectView):
    description = ("Agrega una contraseña de apertura y restringe impresión, copia o "
                   "modificaciones (cifrado AES-256).")
    fixed_mode = "PROTEGER"
    run_label = RUN_LABELS["PROTEGER"]


class UnprotectPdfView(ProtectView):
    description = "Quita la contraseña de un PDF del que la conoces y guarda una copia libre."
    fixed_mode = "DESPROTEGER"
    run_label = RUN_LABELS["DESPROTEGER"]
