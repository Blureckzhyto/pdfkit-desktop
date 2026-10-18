"""Editar PDF: texto, resaltado, dibujo, imágenes, redacción, rotar y eliminar
páginas, con deshacer por página.

Las páginas se renderizan en segundo plano a RENDER_DPI con el Poppler incluido;
las anotaciones se guardan en píxeles de la página renderizada y
core.edit_sign.apply_edits las integra al PDF.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageTk

from core import edit_sign, pdf_tools
from ui import theme
from ui.assets import asset_path
from ui.components import ColorSwatches, FilePicker, ScrollBar, Scroller, run_task
from ui.components import box_geometry as boxes

from .base import ToolView

RENDER_DPI = 100
SCALE = RENDER_DPI / 72.0  # píxeles renderizados por punto PDF

TOOLS = ["TEXTO", "RESALTAR", "DIBUJAR", "IMAGEN", "REDACTAR"]
TEXT_COLORS = [("Blanco", "#FFFFFF"), ("Negro", "#000000"), ("Rojo", "#FF2D2D"),
               ("Azul", "#1E5EFF"), ("Gris", "#888888")]
HIGHLIGHT_COLORS = [("Amarillo", "#FFE600"), ("Verde", "#00FF88"), ("Rosa", "#FF4FD8"),
                    ("Celeste", "#4FC3FF")]
DRAW_COLORS = [("Rojo", "#FF2D2D"), ("Negro", "#000000"), ("Azul", "#1E5EFF"),
               ("Blanco", "#FFFFFF")]
FONT_SIZES = ["10", "12", "14", "18", "24"]
STROKE_WIDTHS = ["1", "2", "3", "5", "8"]
IMAGE_TYPES = [("Imágenes", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*")]
HINTS = {
    "TEXTO": "Clic en la página para colocar un cuadro de texto.",
    "RESALTAR": "Arrastra sobre el texto para resaltarlo.",
    "DIBUJAR": "Dibuja a mano alzada con el mouse.",
    "IMAGEN": "Clic en un espacio vacío para insertar una imagen · arrástrala para moverla · "
              "usa las esquinas para cambiar el tamaño.",
    "REDACTAR": "Arrastra para tapar contenido: al guardar, lo que quede debajo se borra "
                "de forma permanente.",
}
CURSORS = {"TEXTO": "xterm", "RESALTAR": "crosshair", "DIBUJAR": "pencil",
           "IMAGEN": "arrow", "REDACTAR": "crosshair"}


def _rotate_point(x, y, w, h, delta):
    """Punto de una página w×h tras girarla 90° (delta=90 horario, -90 antihorario)."""
    return (h - y, x) if delta == 90 else (y, w - x)


class EditView(ToolView):
    title = "Editar PDF"
    icon = "ED"
    description = "Texto, resaltado, dibujo, imágenes y redacción. Rota o elimina páginas."
    run_label = "Guardar PDF editado"
    tools = TOOLS
    page_actions = True       # rotar y eliminar página
    picker_label = "Arrastra el PDF a editar"
    output_suffix = "_editado"

    def build_body(self, body):
        self.src = None
        self.page_count = 0
        self.current = 0
        self.annotations: dict[int, list[dict]] = {}
        self.rotations: dict[int, int] = {}
        self.deleted: set[int] = set()
        self.history: dict[int, list[tuple]] = {}
        self._page_cache: dict[int, Image.Image] = {}
        self._image_cache: dict[str, Image.Image] = {}
        self._font_cache: dict[tuple, tkfont.Font] = {}
        self._photo_refs: list = []
        self._base_photo = None
        self._disp_size = (0, 0)
        self._render_token = 0
        self._drag = None

        self.picker = FilePicker(body, exts=[".pdf"], multiple=False, compact=True,
                                 label=self.picker_label, on_change=self._file_changed)
        self.picker.pack(fill="x")

        bar = ctk.CTkFrame(body, **theme.CARD)
        bar.pack(fill="x", pady=(8, 6))
        row1 = ctk.CTkFrame(bar, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(8, 4))
        self.tool = ctk.CTkSegmentedButton(row1, values=self.tools,
                                           command=self._tool_changed, **theme.SEGMENTED)
        self.tool.set(self.tools[0])
        self.tool.pack(side="left")
        actions = ctk.CTkFrame(row1, fg_color="transparent")
        actions.pack(side="right")
        self.delete_button = ctk.CTkButton(actions, text="ELIMINAR PÁGINA", width=140,
                                           height=28, command=self._toggle_delete,
                                           **theme.BTN_SECONDARY)
        if self.page_actions:
            ctk.CTkButton(actions, text="↺ 90°", width=60, height=28,
                          command=lambda: self._rotate(-90),
                          **theme.BTN_SECONDARY).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="↻ 90°", width=60, height=28,
                          command=lambda: self._rotate(90),
                          **theme.BTN_SECONDARY).pack(side="left", padx=2)
            self.delete_button.pack(side="left", padx=2)
        ctk.CTkButton(actions, text="DESHACER", width=86, height=28, command=self._undo,
                      **theme.BTN_SECONDARY).pack(side="left", padx=(2, 0))

        row2 = ctk.CTkFrame(bar, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(0, 8))
        nav = ctk.CTkFrame(row2, fg_color="transparent")
        nav.pack(side="right")
        ctk.CTkButton(nav, text="◀", width=30, height=28,
                      command=lambda: self._goto(self.current - 1),
                      **theme.BTN_SECONDARY).pack(side="left")
        self.page_label = ctk.CTkLabel(nav, text="Página – de –", width=130,
                                       font=theme.FONT_BODY, text_color=theme.TEXT_PRIMARY)
        self.page_label.pack(side="left", padx=4)
        ctk.CTkButton(nav, text="▶", width=30, height=28,
                      command=lambda: self._goto(self.current + 1),
                      **theme.BTN_SECONDARY).pack(side="left")
        self.options_host = ctk.CTkFrame(row2, fg_color="transparent")
        self.options_host.pack(side="left", fill="x", expand=True)
        self._option_frames = {
            "TEXTO": self._build_text_options(),
            "RESALTAR": self._build_highlight_options(),
            "DIBUJAR": self._build_draw_options(),
            "IMAGEN": self._build_hint_options("Inserta PNG o JPG; luego muévelo o redimensiónalo."),
            "REDACTAR": self._build_hint_options("Tapa en negro y elimina el contenido de debajo."),
        }

        canvas_frame = ctk.CTkFrame(body, **theme.CARD)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg=theme.resolve(theme.CANVAS_BG),
                                highlightthickness=0)
        vbar = ScrollBar(canvas_frame)
        hbar = ScrollBar(canvas_frame, orientation="horizontal")
        self.scroller = Scroller(self.canvas, vbar=vbar, hbar=hbar)
        vbar.pack(side="right", fill="y", padx=(0, 2), pady=4)
        hbar.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
        self.canvas.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        theme.on_mode_change(canvas_frame, self._mode_changed)
        self._tool_changed(self.tools[0], announce=False)

    def _mode_changed(self):
        self.canvas.configure(bg=theme.resolve(theme.CANVAS_BG))
        if self._base_photo is not None:
            self._paint_annotations()

    # ------------------------------------------------------------------ barra de opciones

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=theme.FONT_SECTION,
                     text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 6))

    def _build_text_options(self):
        frame = ctk.CTkFrame(self.options_host, fg_color="transparent")
        self._section(frame, "TAMAÑO")
        self.font_size = ctk.CTkOptionMenu(frame, values=FONT_SIZES, width=62, height=28,
                                           **theme.OPTIONMENU)
        self.font_size.set("14")
        self.font_size.pack(side="left", padx=(0, 12))
        self._section(frame, "COLOR")
        self.text_color = ColorSwatches(frame, TEXT_COLORS, initial="#000000")
        self.text_color.pack(side="left", padx=(0, 12))
        self.bold = ctk.CTkCheckBox(frame, text="NEGRITA", width=20, checkbox_width=18,
                                    checkbox_height=18, **theme.CHECKBOX)
        self.bold.pack(side="left")
        return frame

    def _build_highlight_options(self):
        frame = ctk.CTkFrame(self.options_host, fg_color="transparent")
        self._section(frame, "COLOR")
        self.highlight_color = ColorSwatches(frame, HIGHLIGHT_COLORS, initial="#FFE600")
        self.highlight_color.pack(side="left")
        return frame

    def _build_draw_options(self):
        frame = ctk.CTkFrame(self.options_host, fg_color="transparent")
        self._section(frame, "COLOR")
        self.draw_color = ColorSwatches(frame, DRAW_COLORS, initial="#FF2D2D")
        self.draw_color.pack(side="left", padx=(0, 12))
        self._section(frame, "GROSOR")
        self.stroke_width = ctk.CTkOptionMenu(frame, values=STROKE_WIDTHS, width=58,
                                              height=28, **theme.OPTIONMENU)
        self.stroke_width.set("2")
        self.stroke_width.pack(side="left")
        return frame

    def _build_hint_options(self, text):
        frame = ctk.CTkFrame(self.options_host, fg_color="transparent")
        ctk.CTkLabel(frame, text=text, font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(side="left")
        return frame

    def _tool_changed(self, tool, announce=True):
        for frame in self._option_frames.values():
            frame.pack_forget()
        self._option_frames[tool].pack(side="left")
        self.canvas.configure(cursor=CURSORS[tool])
        if self.src is not None:
            self._paint_annotations()
        if announce:
            self.show_info(HINTS[tool])

    # ------------------------------------------------------------------ documento

    def _reset(self):
        self._render_token += 1
        self.src = None
        self.page_count = 0
        self.current = 0
        self.annotations, self.rotations, self.deleted, self.history = {}, {}, set(), {}
        self._page_cache.clear()
        self._base_photo = None
        self._photo_refs.clear()
        self.canvas.delete("all")
        self.page_label.configure(text="Página – de –")

    def _file_changed(self, files):
        if not files:
            return
        src = files[0]
        self._reset()
        self.show_info("Abriendo PDF…")
        token = self._render_token

        def opened(count):
            if token != self._render_token:
                return
            self.src, self.page_count = src, count
            self._show_page()
            self.show_info(f"{count} página(s). {HINTS[self.tool.get()]}")

        def failed(exc):
            if token == self._render_token:
                text = str(exc)
                self.show_error(edit_sign.ENCRYPTED_MSG if "decrypt" in text.lower()
                                else f"No se pudo abrir el PDF: {text}")

        run_task(self, lambda _p: pdf_tools.get_page_count(src), opened, failed)

    def _goto(self, index):
        if self.src and 0 <= index < self.page_count and not self._drag:
            self.current = index
            self._show_page()

    def _show_page(self):
        self.canvas.delete("all")
        self._base_photo = None
        self.page_label.configure(text=f"Página {self.current + 1} de {self.page_count}")
        if self.current in self._page_cache:
            self._draw_base()
            return
        self._render_token += 1
        token, src, index = self._render_token, self.src, self.current
        self.canvas.create_text(24, 24, anchor="nw", text="Renderizando página…",
                                fill=theme.resolve(theme.TEXT_SECONDARY), font=theme.FONT_BODY)

        def rendered(img):
            self._page_cache[index] = img
            if token == self._render_token and index == self.current:
                self._draw_base()

        def failed(exc):
            if token == self._render_token:
                self.canvas.delete("all")
                self.show_error(str(exc))

        run_task(self, lambda _p: pdf_tools.render_page_image(src, index, dpi=RENDER_DPI),
                 rendered, failed)

    def _draw_base(self):
        img = self._page_cache[self.current]
        rotation = self.rotations.get(self.current, 0) % 360
        if rotation:
            img = img.rotate(-rotation, expand=True)
        self._disp_size = img.size
        self._base_photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._base_photo, tags="base")
        self.canvas.configure(scrollregion=(0, 0, img.width, img.height))
        self._paint_annotations()

    # ------------------------------------------------------------------ pintado

    def _tk_font(self, size_pt, bold):
        px = max(6, round(size_pt * SCALE))
        key = (px, bool(bold))
        if key not in self._font_cache:
            # tamaño negativo = píxeles: el texto en pantalla mide lo mismo que en el PDF
            self._font_cache[key] = tkfont.Font(family="Helvetica", size=-px,
                                                weight="bold" if bold else "normal")
        return self._font_cache[key]

    def _load_image(self, path):
        if path not in self._image_cache:
            with Image.open(path) as im:
                self._image_cache[path] = im.convert("RGBA")
        return self._image_cache[path]

    def _paint_annotations(self):
        self.canvas.delete("ann")
        self._photo_refs.clear()
        if self._base_photo is None:
            return
        anns = self.annotations.get(self.current, [])
        for ann in anns:
            self._paint(ann)
        if self.tool.get() == "IMAGEN":
            for ann in anns:
                if ann["type"] == "image":
                    boxes.draw_handles(self.canvas, (ann["x"], ann["y"], ann["w"], ann["h"]),
                                       theme.ACCENT, "ann")
        if self.current in self.deleted:
            w, h = self._disp_size
            self.canvas.create_rectangle(0, 0, w, h, fill="gray15", stipple="gray50",
                                         outline="", tags="ann")
            self.canvas.create_text(w / 2, h / 2, text="ESTA PÁGINA SE ELIMINARÁ",
                                    fill=theme.resolve(theme.ACCENT), font=(theme.FONT, 20, "bold"),
                                    tags="ann")
            self.delete_button.configure(text="RESTAURAR PÁGINA")
        else:
            self.delete_button.configure(text="ELIMINAR PÁGINA")

    def _paint(self, ann):
        kind = ann["type"]
        if kind == "text":
            self.canvas.create_text(ann["x"], ann["y"], text=ann["text"], anchor="nw",
                                    fill=ann["color"], tags="ann",
                                    font=self._tk_font(ann["size"], ann.get("bold")))
        elif kind == "highlight":
            self.canvas.create_rectangle(ann["x"], ann["y"], ann["x"] + ann["w"],
                                         ann["y"] + ann["h"], fill=ann["color"],
                                         stipple="gray50", outline="", tags="ann")
        elif kind == "redact":
            self.canvas.create_rectangle(ann["x"], ann["y"], ann["x"] + ann["w"],
                                         ann["y"] + ann["h"], fill="#000000",
                                         outline=theme.resolve(theme.ACCENT_DIM), tags="ann")
        elif kind == "draw":
            points = [coord for point in ann["points"] for coord in point]
            if len(points) >= 4:
                self.canvas.create_line(*points, fill=ann["color"],
                                        width=max(1, round(ann.get("width", 2) * SCALE)),
                                        capstyle="round", joinstyle="round", smooth=True,
                                        tags="ann")
        elif kind == "image":
            try:
                source = self._load_image(ann["path"])
            except Exception:
                return
            size = (max(1, round(ann["w"])), max(1, round(ann["h"])))
            photo = ImageTk.PhotoImage(source.resize(size, Image.LANCZOS))
            self._photo_refs.append(photo)
            self.canvas.create_image(ann["x"], ann["y"], anchor="nw", image=photo, tags="ann")

    # ------------------------------------------------------------------ historial

    def _push(self, action):
        self.history.setdefault(self.current, []).append(action)

    def _add(self, ann):
        self.annotations.setdefault(self.current, []).append(ann)
        self._push(("add", ann))
        self._paint_annotations()

    def _undo(self):
        stack = self.history.get(self.current)
        if not stack:
            self.show_info("No hay nada para deshacer en esta página.")
            return
        action = stack.pop()
        kind = action[0]
        if kind == "add":
            self.annotations[self.current].remove(action[1])
        elif kind == "geom":
            action[1].update(action[2])
        elif kind == "rotate":
            self._apply_rotation(-action[1])
            return
        elif kind == "delete":
            self.deleted.symmetric_difference_update({self.current})
        self._paint_annotations()
        self.show_info("Se deshizo la última acción.")

    # ------------------------------------------------------------------ mouse

    def _canvas_xy(self, event):
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _clamp_point(self, x, y):
        w, h = self._disp_size
        return min(max(0, x), w), min(max(0, y), h)

    def _editable(self) -> bool:
        if not self.src:
            self.show_info("Abre un PDF primero.")
            return False
        if self._base_photo is None:
            return False
        if self.current in self.deleted:
            self.show_info("Esta página está marcada para eliminarse: restáurala o usa DESHACER.")
            return False
        return True

    def _image_hit(self, x, y):
        for ann in reversed(self.annotations.get(self.current, [])):
            if ann["type"] == "image":
                mode = boxes.hit_test((ann["x"], ann["y"], ann["w"], ann["h"]), x, y)
                if mode:
                    return ann, mode
        return None, None

    def _on_press(self, event):
        if not self._editable():
            return
        x, y = self._canvas_xy(event)
        w, h = self._disp_size
        tool = self.tool.get()
        if tool == "IMAGEN":
            ann, mode = self._image_hit(x, y)
            if ann:
                self._drag = {"kind": "image", "ann": ann, "mode": mode, "start_xy": (x, y),
                              "start_box": (ann["x"], ann["y"], ann["w"], ann["h"])}
            elif x <= w and y <= h:
                self._insert_image(x, y)
            return
        if x > w or y > h:
            return
        if tool == "TEXTO":
            self._insert_text(x, y)
        elif tool in ("RESALTAR", "REDACTAR"):
            fill = self.highlight_color.get() if tool == "RESALTAR" else "#000000"
            item = self.canvas.create_rectangle(x, y, x, y, fill=fill, outline="",
                                                stipple="gray50" if tool == "RESALTAR" else "")
            self._drag = {"kind": "rect", "start": (x, y), "item": item}
        elif tool == "DIBUJAR":
            self._drag = {"kind": "stroke", "points": [(x, y)], "item": None}

    def _on_drag(self, event):
        if not self._drag:
            return
        x, y = self._clamp_point(*self._canvas_xy(event))
        drag = self._drag
        if drag["kind"] == "rect":
            x0, y0 = drag["start"]
            self.canvas.coords(drag["item"], x0, y0, x, y)
        elif drag["kind"] == "stroke":
            drag["points"].append((x, y))
            if drag["item"]:
                self.canvas.delete(drag["item"])
            points = [coord for point in drag["points"] for coord in point]
            drag["item"] = self.canvas.create_line(
                *points, fill=self.draw_color.get(), smooth=True, capstyle="round",
                joinstyle="round", width=max(1, round(float(self.stroke_width.get()) * SCALE)))
        elif drag["kind"] == "image":
            ann = drag["ann"]
            if drag["mode"] == "move":
                sx, sy, bw, bh = drag["start_box"]
                box = (sx + x - drag["start_xy"][0], sy + y - drag["start_xy"][1], bw, bh)
            else:
                box = boxes.resize(drag["start_box"], drag["mode"], x, y)
            ann["x"], ann["y"], ann["w"], ann["h"] = boxes.clamp(box, *self._disp_size)
            self._paint_annotations()

    def _on_release(self, event):
        if not self._drag:
            return
        drag, self._drag = self._drag, None
        x, y = self._clamp_point(*self._canvas_xy(event))
        if drag["kind"] == "rect":
            self.canvas.delete(drag["item"])
            x0, y0 = drag["start"]
            w, h = abs(x - x0), abs(y - y0)
            if w > 3 and h > 3:
                ann = {"x": min(x, x0), "y": min(y, y0), "w": w, "h": h}
                if self.tool.get() == "RESALTAR":
                    ann.update(type="highlight", color=self.highlight_color.get())
                else:
                    ann.update(type="redact")
                self._add(ann)
        elif drag["kind"] == "stroke":
            if drag["item"]:
                self.canvas.delete(drag["item"])
            if len(drag["points"]) > 1:
                self._add({"type": "draw", "points": drag["points"],
                           "width": float(self.stroke_width.get()),
                           "color": self.draw_color.get()})
        elif drag["kind"] == "image":
            ann = drag["ann"]
            old = dict(zip(("x", "y", "w", "h"), drag["start_box"]))
            if any(abs(ann[k] - v) > 0.5 for k, v in old.items()):
                self._push(("geom", ann, old))

    def _text_dialog(self):
        dialog = ctk.CTkInputDialog(text="Texto a agregar:", title="Agregar texto",
                                    fg_color=theme.BG_PRIMARY, text_color=theme.TEXT_PRIMARY,
                                    entry_fg_color=theme.SURFACE,
                                    entry_border_color=theme.INPUT_BORDER,
                                    entry_text_color=theme.TEXT_PRIMARY,
                                    button_fg_color=theme.ACCENT,
                                    button_hover_color=theme.ACCENT_HOVER,
                                    button_text_color=theme.TEXT_ON_ACCENT)
        # customtkinter pone su propio ícono a los 200 ms: se reemplaza por el de Pliegue
        dialog.after(260, lambda: dialog.winfo_exists() and dialog.iconbitmap(
            str(asset_path("icon.ico"))))
        return dialog

    def _insert_text(self, x, y):
        text = self._text_dialog().get_input()
        if not text:
            return
        size = int(self.font_size.get())
        bold = bool(self.bold.get())
        ascent = self._tk_font(size, bold).metrics("ascent")
        self._add({"type": "text", "x": x, "y": y, "baseline": y + ascent, "text": text,
                   "size": size, "color": self.text_color.get(), "bold": bold})

    def _insert_image(self, x, y):
        path = filedialog.askopenfilename(filetypes=IMAGE_TYPES)
        if not path:
            return
        try:
            img = self._load_image(path)
        except Exception as exc:
            self.show_error(f"No se pudo abrir la imagen: {exc}")
            return
        fit = min(1.0, 240 / max(img.size))
        box = boxes.clamp((x, y, img.width * fit, img.height * fit), *self._disp_size)
        self._add(dict(zip(("x", "y", "w", "h"), box), type="image", path=path))

    # ------------------------------------------------------------------ páginas

    def _rotate(self, delta):
        if not self._editable():
            return
        self._apply_rotation(delta)
        self._push(("rotate", delta))

    def _apply_rotation(self, delta):
        w, h = self._disp_size  # tamaño antes de esta rotación
        for ann in self.annotations.get(self.current, []):
            self._remap(ann, w, h, delta)
        self.rotations[self.current] = (self.rotations.get(self.current, 0) + delta) % 360
        self._draw_base()

    @staticmethod
    def _remap(ann, w, h, delta):
        """Reubica una anotación tras girar la página. Textos e imágenes siguen
        derechos; las zonas rectangulares y los trazos giran con el contenido."""
        kind = ann["type"]
        if kind == "text":
            offset = ann["baseline"] - ann["y"]
            ann["x"], ann["y"] = _rotate_point(ann["x"], ann["y"], w, h, delta)
            ann["baseline"] = ann["y"] + offset
        elif kind == "image":
            cx, cy = _rotate_point(ann["x"] + ann["w"] / 2, ann["y"] + ann["h"] / 2, w, h, delta)
            ann["x"], ann["y"] = cx - ann["w"] / 2, cy - ann["h"] / 2
        elif kind in ("highlight", "redact"):
            corners = [_rotate_point(ann["x"], ann["y"], w, h, delta),
                       _rotate_point(ann["x"] + ann["w"], ann["y"] + ann["h"], w, h, delta)]
            ann["x"] = min(c[0] for c in corners)
            ann["y"] = min(c[1] for c in corners)
            ann["w"], ann["h"] = ann["h"], ann["w"]
        elif kind == "draw":
            ann["points"] = [_rotate_point(x, y, w, h, delta) for x, y in ann["points"]]

    def _toggle_delete(self):
        if not self.src:
            self.show_info("Abre un PDF primero.")
            return
        self.deleted.symmetric_difference_update({self.current})
        self._push(("delete",))
        self._paint_annotations()
        if self.current in self.deleted:
            self.show_info(f"La página {self.current + 1} se eliminará al guardar.")
        else:
            self.show_info(f"Página {self.current + 1} restaurada.")

    # ------------------------------------------------------------------ guardar

    def run(self):
        if not self.src:
            self.show_error("Abre un PDF primero.")
            return
        has_rotation = any(r % 360 for r in self.rotations.values())
        if not any(self.annotations.values()) and not has_rotation and not self.deleted:
            self.show_error("Todavía no hay cambios para guardar.")
            return
        out_dir = self.get_output_dir()
        if not out_dir:
            return
        output = self.output_file(out_dir, f"{self.src.stem}{self.output_suffix}.pdf")
        annotations = {p: [dict(a) for a in anns] for p, anns in self.annotations.items() if anns}
        rotations = dict(self.rotations)
        deleted = set(self.deleted)
        src = self.src
        redacted = sum(1 for anns in annotations.values() for a in anns if a["type"] == "redact")

        def work(progress):
            result = edit_sign.apply_edits(src, output, annotations, rotations, deleted,
                                           SCALE, progress)
            message = f"Se guardó {result.name} en {out_dir}"
            if redacted:
                message += f" · {redacted} zona(s) redactada(s) de forma permanente"
            return message

        self.start_task(work)


class CensorView(EditView):
    """Censurar PDF: el mismo editor reducido a la redacción permanente."""
    title = "Censurar PDF"
    description = ("Tapa en negro datos sensibles. Al guardar, el texto, las imágenes y los "
                   "trazos de debajo se borran de verdad (no solo se ocultan).")
    run_label = "Guardar PDF censurado"
    tools = ["REDACTAR"]
    page_actions = False
    picker_label = "Arrastra el PDF a censurar"
    output_suffix = "_censurado"
