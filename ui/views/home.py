"""Pantalla de inicio: tarjetas de herramientas agrupadas por categoría, 4 columnas.

Toda la grilla se dibuja en un solo tk.Canvas: fondos de tarjeta pre-renderizados
con bordes suavizados, mosaicos con su icono y textos son elementos del lienzo.
Antes cada tarjeta eran varios widgets (unas 150 ventanas hijas en total) y al
desplazar Windows tenía que mover y repintar cada una en cada cuadro; ahora
desplazar es solo mover elementos de un lienzo. Las imágenes se generan una vez
por tamaño y tema y quedan en caché: desplazar nunca reconstruye nada.
"""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from ui import anim, theme
from ui.assets import logo, pil_image
from ui.components.scrolling import ScrollBar, Scroller

COLUMNS = 4
CARD_H = 116
CARD_RADIUS = 14
TILE = 46
TILE_RADIUS = 12
ICON = 24
HOVER_FRAMES = 6          # pasos pre-renderizados del fundido de hover
HOVER_MS = 120
SUPERSAMPLE = 3           # bordes redondeados suavizados


def _rounded(size, radius, fill, background, outline=None) -> Image.Image:
    """Rectángulo redondeado suavizado y opaco: las esquinas ya llevan el color del fondo,
    así Tk copia la imagen tal cual en cada cuadro en vez de mezclar transparencias."""
    w, h = size
    k = SUPERSAMPLE
    img = Image.new("RGBA", (w * k, h * k), background)
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=radius * k,
                                          fill=fill, outline=outline, width=k if outline else 0)
    return img.resize((w, h), Image.LANCZOS)


class HomeGrid(ctk.CTkFrame):
    def __init__(self, master, categories, on_open):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.categories = categories
        self.on_open = on_open
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0,
                                bg=theme.resolve(theme.BG_PRIMARY))
        self.scrollbar = ScrollBar(self, button_color=theme.BORDER,
                                   button_hover_color=theme.BORDER_STRONG)
        self.scrollbar.pack(side="right", fill="y", padx=(4, 0))
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroller = Scroller(self.canvas, vbar=self.scrollbar, on_scroll=self._scrolled)
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}
        self.cards: list[dict] = []
        self._hover = None
        self._width = None
        self._layout_job = None
        self._recheck_job = None
        self.canvas.bind("<Configure>", self._configured)
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Leave>", lambda _e: self._set_hover(None))
        self.canvas.bind("<Button-1>", self._click)
        theme.on_mode_change(self, self._mode_changed)

    # ------------------------------------------------------------------ imágenes (caché)

    def _scale(self) -> float:
        return ctk.ScalingTracker.get_widget_scaling(self)

    def _card_image(self, width, height, frame):
        key = ("card", theme.is_dark(), width, height, frame)
        if key not in self._cache:
            t = frame / (HOVER_FRAMES - 1)
            fill = anim.mix(theme.SURFACE, theme.CARD_HOVER, t)
            border = anim.mix(theme.BORDER, theme.BORDER_STRONG, t)
            self._cache[key] = ImageTk.PhotoImage(
                _rounded((width, height), round(CARD_RADIUS * self._scale()), fill,
                         theme.resolve(theme.BG_PRIMARY), border),
                master=self.canvas)
        return self._cache[key]

    def _tile_image(self, tool_key, color):
        dark = theme.is_dark()
        key = ("tile", dark, tool_key)
        if key not in self._cache:
            s = self._scale()
            size = round(TILE * s)
            # el mosaico es chico: puede llevar esquinas transparentes (se ve igual con hover)
            tile = _rounded((size, size), round(TILE_RADIUS * s),
                            theme.resolve(theme.tint(color, 0.12)), (0, 0, 0, 0))
            icon = pil_image(f"icons/tool_{tool_key}_{ICON}", dark)
            if icon is not None:
                px = round(ICON * s)
                if icon.size != (px, px):
                    icon = icon.resize((px, px), Image.LANCZOS)
                tile.alpha_composite(icon, ((size - px) // 2, (size - px) // 2))
            self._cache[key] = ImageTk.PhotoImage(tile, master=self.canvas)
        return self._cache[key]

    def _dot_image(self, color):
        key = ("dot", theme.is_dark(), color, round(self._scale() * 10))
        if key not in self._cache:
            d = round(10 * self._scale())
            img = Image.new("RGBA", (d * 4, d * 4), theme.resolve(theme.BG_PRIMARY))
            ImageDraw.Draw(img).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=color)
            self._cache[key] = ImageTk.PhotoImage(img.resize((d, d), Image.LANCZOS),
                                                  master=self.canvas)
        return self._cache[key]

    # ------------------------------------------------------------------ dibujo

    def _configured(self, event):
        if event.width != self._width and self._layout_job is None:
            self._layout_job = self.after_idle(self._layout)

    def _mode_changed(self):
        self.canvas.configure(bg=theme.resolve(theme.BG_PRIMARY))
        self._layout()

    def _layout(self):
        self._layout_job = None
        c = self.canvas
        width = c.winfo_width()
        if width < 50:
            return
        self._width = width
        s = self._scale()
        c.delete("all")
        self.cards = []
        self._hover = None
        pad, gap = 12 * s, 24 * s
        col_w = (width - 2 * pad) / COLUMNS
        card_w, card_h = max(40, int(col_w - gap)), round(CARD_H * s)
        heading_font = (theme.FONT_SEMIBOLD, -round(15 * s))
        name_font = (theme.FONT_SEMIBOLD, -round(14 * s))
        text_color = theme.resolve(theme.TEXT_PRIMARY)
        card = self._card_image(card_w, card_h, 0)
        from ui.app import category_title

        y = 4 * s
        for index, (category, color, tools) in enumerate(self.categories):
            if index:
                y += gap
            head_h = 24 * s
            c.create_image(pad + 5 * s, y + head_h / 2, image=self._dot_image(color))
            c.create_text(pad + 20 * s, y + head_h / 2, text=category_title(category), anchor="w",
                          font=heading_font, fill=text_color)
            y += head_h + 4 * s
            for n, (key, _symbol, name, _cls) in enumerate(tools):
                row, col = divmod(n, COLUMNS)
                x0 = round(pad + col * col_w + gap / 2)
                y0 = round(y + row * (card_h + gap) + gap / 2)
                bg = c.create_image(x0, y0, image=card, anchor="nw")
                c.create_image(x0 + round(18 * s), y0 + round(18 * s),
                               image=self._tile_image(key, color), anchor="nw")
                c.create_text(x0 + 18 * s, y0 + 88 * s, text=name, anchor="w", font=name_font,
                              fill=text_color)
                self.cards.append({"key": key, "box": (x0, y0, x0 + card_w, y0 + card_h),
                                   "bg": bg, "frame": 0, "size": (card_w, card_h)})
            rows = (len(tools) + COLUMNS - 1) // COLUMNS
            y += rows * (card_h + gap)
        c.configure(scrollregion=(0, 0, width, round(y + 4 * s)))
        self._recheck()

    # ------------------------------------------------------------------ hover y clic

    def _card_at(self, x, y):
        cx, cy = self.canvas.canvasx(x), self.canvas.canvasy(y)
        for card in self.cards:
            x0, y0, x1, y1 = card["box"]
            if x0 <= cx < x1 and y0 <= cy < y1:
                return card
        return None

    def _show_frame(self, card, frame):
        card["frame"] = frame
        self.canvas.itemconfigure(card["bg"], image=self._card_image(*card["size"], frame))

    def _fade(self, card, target):
        start = card["frame"]

        def step(t):
            frame = round(start + (target - start) * t)
            if frame != card["frame"]:
                self._show_frame(card, frame)

        anim.animate(self.canvas, f"card_{card['key']}", HOVER_MS, step)

    def _set_hover(self, card, fade=True):
        if card is self._hover:
            return
        previous, self._hover = self._hover, card
        if previous is not None:
            if fade:
                self._fade(previous, 0)
            else:
                anim.cancel(self.canvas, f"card_{previous['key']}")
                self._show_frame(previous, 0)
        if card is not None:
            self._fade(card, HOVER_FRAMES - 1)
        self.canvas.configure(cursor="hand2" if card else "")

    def _motion(self, event):
        if anim.is_scrolling():
            return
        self._set_hover(self._card_at(event.x, event.y))

    def _scrolled(self):
        # durante el desplazamiento no arranca ningún fundido: se quita el hover al
        # instante y se vuelve a calcular cuando el movimiento termina
        if self._hover is not None:
            self._set_hover(None, fade=False)
        if self._recheck_job is not None:
            self.after_cancel(self._recheck_job)
        self._recheck_job = self.after(int(anim.SCROLL_QUIET_S * 1000) + 30, self._recheck)

    def _recheck(self):
        self._recheck_job = None
        if anim.is_scrolling():
            self._recheck_job = self.after(60, self._recheck)
            return
        try:
            px, py = self.canvas.winfo_pointerxy()
            x, y = px - self.canvas.winfo_rootx(), py - self.canvas.winfo_rooty()
        except tk.TclError:
            return
        inside = 0 <= x < self.canvas.winfo_width() and 0 <= y < self.canvas.winfo_height()
        self._set_hover(self._card_at(x, y) if inside else None)

    def _click(self, event):
        card = self._card_at(event.x, event.y)
        if card is not None:
            self.on_open(card["key"])


class HomeView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=theme.BG_PRIMARY, corner_radius=0)
        self.app = app
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD, pady=(28, 14))
        self._logo = logo("icon_home", (64, 64))
        if self._logo:
            ctk.CTkLabel(header, text="", image=self._logo).pack(side="left", padx=(0, 18))
        self.title_label = ctk.CTkLabel(header, text="¿Qué quieres hacer hoy con tus PDF?",
                                        font=(theme.FONT_SEMIBOLD, 26), text_color=theme.TEXT_PRIMARY)
        self.title_label.pack(side="left")
        self.fade_in_labels = [(self.title_label, theme.TEXT_PRIMARY)]

        self.grid_view = HomeGrid(self, app.categories, lambda key: self.app.show_view(key))
        self.grid_view.pack(fill="both", expand=True, padx=(theme.PAD - 12, 8), pady=(0, 16))
