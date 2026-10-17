"""Notificaciones (toasts) que entran deslizándose abajo a la derecha."""
from __future__ import annotations

import customtkinter as ctk

from ui import anim, theme
from ui.assets import icon

DURATION_MS = 4000
MARGIN = 24
SLIDE = 48
MAX_VISIBLE = 3
ACCENTS = {"success": theme.SUCCESS, "error": theme.ERROR, "warning": theme.WARNING,
           "info": theme.INFO}


class ToastManager:
    def __init__(self, root):
        self.root = root
        self.toasts: list[ctk.CTkFrame] = []

    def show(self, kind: str, message: str, action=None, duration: int = DURATION_MS):
        """`action` = (texto del botón, función): p. ej. ("Deshacer", deshacer). Al usarlo
        el aviso se cierra. Devuelve el aviso."""
        while len(self.toasts) >= MAX_VISIBLE:
            self._dismiss(self.toasts[0], animated=False)
        toast = ctk.CTkFrame(self.root, fg_color=theme.SURFACE, corner_radius=12,
                             border_width=1, border_color=theme.BORDER_STRONG)
        # height chico: el alto por defecto de CTkFrame (200 px) agrandaría todo el aviso
        bar = ctk.CTkFrame(toast, width=4, height=8, corner_radius=2,
                           fg_color=ACCENTS.get(kind, theme.INFO))
        bar.pack(side="left", fill="y", padx=(8, 0), pady=10)
        image = icon(f"state_{kind}", 20)
        ctk.CTkLabel(toast, text="", image=image, width=24).pack(side="left", padx=(10, 6))
        ctk.CTkLabel(toast, text=message, font=theme.FONT_BODY, text_color=theme.TEXT_PRIMARY,
                     wraplength=320, justify="left", anchor="w").pack(side="left", pady=12)
        if action is not None:
            label, callback = action

            def run_action():
                self._dismiss(toast)
                callback()

            toast.action_button = ctk.CTkButton(toast, text=label, width=86, height=30,
                                                command=run_action, **theme.BTN_SECONDARY)
            toast.action_button.pack(side="left", padx=(12, 0))
        close = ctk.CTkButton(toast, text="", image=icon("ui_close", 18), width=28, height=28,
                              corner_radius=8, fg_color=theme.SURFACE, hover_color=theme.BG_HOVER,
                              command=lambda: self._dismiss(toast))
        close.pack(side="left", padx=(8, 8))
        toast._x = SLIDE
        self.toasts.append(toast)
        self._layout(new=toast)
        toast._timer = self.root.after(duration, lambda: self._dismiss(toast))
        return toast

    def _layout(self, new=None) -> None:
        self.root.update_idletasks()
        y = -MARGIN
        for toast in reversed(self.toasts):
            toast._y = y
            toast.place(relx=1.0, rely=1.0, x=-MARGIN + toast._x, y=y, anchor="se")
            toast.lift()
            y -= toast.winfo_reqheight() + 12
        if new is not None:
            def step(t):
                new._x = round(SLIDE * (1 - t))
                new.place_configure(x=-MARGIN + new._x)
            anim.animate(new, "slide", 220, step)

    def _dismiss(self, toast, animated: bool = True) -> None:
        if toast not in self.toasts:
            return
        self.toasts.remove(toast)
        try:
            self.root.after_cancel(toast._timer)
        except Exception:
            pass

        def destroy():
            try:
                toast.destroy()
            except Exception:
                pass
            self._layout()

        if not animated:
            destroy()
            return

        def step(t):
            toast.place_configure(x=-MARGIN + round(SLIDE * 2 * t))

        anim.animate(toast, "slide", 160, step, done=destroy)
