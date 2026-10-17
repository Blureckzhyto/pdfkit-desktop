"""Sistema de diseño suave y amigable: tema claro y oscuro.

Cada color es un par (claro, oscuro) que customtkinter entiende directamente:
al cambiar el modo con `set_mode()`, todos los widgets de customtkinter se
recolorean solos, sin reconstruir nada. Lo que no es de customtkinter (lienzos
tk.Canvas, tk.Text, imágenes dibujadas a mano) usa `resolve()` para obtener el
hex del modo actual y se redibuja desde `on_mode_change()`.

Las paletas LIGHT y DARK tienen exactamente los mismos nombres. Las familias
tipográficas se resuelven al iniciar (`configure_fonts`), cuando Tk ya puede
confirmar que la fuente incluida está disponible; por eso los kits que llevan
fuente se reconstruyen en ese momento. Los nombres antiguos (BG_INPUT,
ACCENT_DIM, TEXT_ACCENT, ...) siguen como alias.
"""
from __future__ import annotations

import sys

import customtkinter as ctk


def _mix(color: str, amount: float, base: str) -> str:
    c = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(base[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(bv + (cv - bv) * amount):02X}" for cv, bv in zip(c, b))


_D_BG, _D_SURFACE, _D_ACCENT = "#16171D", "#1D1F27", "#EF5B60"

# --- paletas -----------------------------------------------------------------------
LIGHT = dict(
    BG_PRIMARY="#FFFFFF",           # panel principal
    BG_SECONDARY="#F7F7FB",         # barra lateral, barra de estado
    SURFACE="#FFFFFF",              # tarjetas, campos, botones secundarios
    BG_HOVER="#F1F1F7",
    CARD_HOVER="#FBFBFD",
    SIDEBAR_BG="#F7F7FB",
    SIDEBAR_TEXT="#A3A6B8",         # títulos de categoría
    SIDEBAR_ITEM="#3D4054",         # ítems
    SIDEBAR_HOVER="#EDEDF4",
    SIDEBAR_ACTIVE_BG="#FDECEC",
    SIDEBAR_ACTIVE_HOVER="#FBE0E0",
    SIDEBAR_ACTIVE="#E5484D",
    SIDEBAR_ACCENT="#E5484D",
    TEXT_PRIMARY="#1F2133",
    TEXT_SECONDARY="#666A7E",
    TEXT_MUTED="#A0A3B4",
    ACCENT="#E5484D",
    ACCENT_HOVER="#D93D42",
    ACCENT_PRESSED="#C7353A",
    ACCENT_LIGHT="#FDECEC",
    FOCUS_RING="#F5B5B7",           # anillo de foco: tinte del rojo principal
    SELECTED_TINT="#FBD9DA",        # opción elegida en selectores segmentados
    SELECTED_TINT_HOVER="#F8C9CB",
    DROP_PULSE="#FAD1D2",           # punto máximo del pulso al arrastrar un archivo
    SUCCESS="#2B8A4E",
    SUCCESS_BG="#EAF6EE",
    WARNING="#C56A0A",
    WARNING_BG="#FFF4E5",
    ERROR="#D6373D",
    ERROR_BG="#FDECEC",
    INFO="#2563C9",
    INFO_BG="#EAF1FD",
    BORDER="#EEEEF3",
    BORDER_STRONG="#DEDFE8",
    INPUT_BORDER="#E3E4EC",
    CANVAS_BG="#F0F1F6",            # fondo de los lienzos donde se ven las páginas
    PAGE_SHADOW="#E2E3EA",          # sombra bajo la página en el editor
    TEXT_ON_ACCENT="#FFFFFF",
    # fondo de los botones principales: un rojo más oscuro que ACCENT para que el texto
    # blanco llegue a 4.5:1 (WCAG AA); el logo y los demás acentos no cambian
    PRIMARY_BG="#D33A3F",           # 4.72:1 con blanco
    PRIMARY_HOVER="#C23338",        # 5.49:1
    SWITCH_KNOB="#FFFFFF",
)

DARK = dict(
    BG_PRIMARY=_D_BG,
    BG_SECONDARY=_D_SURFACE,
    SURFACE=_D_SURFACE,
    BG_HOVER="#262935",
    CARD_HOVER="#23252F",
    SIDEBAR_BG=_D_SURFACE,
    SIDEBAR_TEXT="#6F7385",
    SIDEBAR_ITEM="#C9CCD8",
    SIDEBAR_HOVER="#262935",
    SIDEBAR_ACTIVE_BG=_mix(_D_ACCENT, 0.16, _D_SURFACE),
    SIDEBAR_ACTIVE_HOVER=_mix(_D_ACCENT, 0.22, _D_SURFACE),
    SIDEBAR_ACTIVE="#F47A7E",       # algo más claro que el acento: contraste AA sobre su fondo
    SIDEBAR_ACCENT=_D_ACCENT,
    TEXT_PRIMARY="#ECEDF2",
    TEXT_SECONDARY="#A3A7B7",
    TEXT_MUTED="#6F7385",
    ACCENT=_D_ACCENT,
    ACCENT_HOVER="#F26C71",
    ACCENT_PRESSED="#D94E53",
    ACCENT_LIGHT=_mix(_D_ACCENT, 0.16, _D_SURFACE),
    FOCUS_RING=_mix(_D_ACCENT, 0.55, _D_BG),
    SELECTED_TINT=_mix(_D_ACCENT, 0.26, _D_SURFACE),
    SELECTED_TINT_HOVER=_mix(_D_ACCENT, 0.34, _D_SURFACE),
    DROP_PULSE=_mix(_D_ACCENT, 0.30, _D_SURFACE),
    SUCCESS="#4CC38A",
    SUCCESS_BG=_mix("#4CC38A", 0.14, _D_BG),
    WARNING="#F0A44B",
    WARNING_BG=_mix("#F0A44B", 0.14, _D_BG),
    ERROR="#FF7276",
    ERROR_BG=_mix("#FF7276", 0.14, _D_BG),
    INFO="#78AEFF",
    INFO_BG=_mix("#78AEFF", 0.14, _D_BG),
    BORDER="#2E3140",
    BORDER_STRONG="#3C4053",
    INPUT_BORDER="#373B4C",
    CANVAS_BG="#101116",
    PAGE_SHADOW="#08090C",
    TEXT_ON_ACCENT="#FFFFFF",
    PRIMARY_BG="#C9373C",           # 5.13:1 con blanco
    PRIMARY_HOVER="#BC3237",        # 5.75:1
    SWITCH_KNOB="#ECEDF2",
)

assert LIGHT.keys() == DARK.keys()
globals().update({name: (LIGHT[name], DARK[name]) for name in LIGHT})

# categorías: el icono va en el color pleno sobre un mosaico con un tinte del color
CAT_ORDENAR = "#E5484D"
CAT_OPTIMIZAR = "#30A46C"
CAT_CONVERTIR_A = "#F08C1A"
CAT_CONVERTIR_DESDE = "#8E4EC6"
CAT_EDITAR = "#2F7FE0"
CAT_SEGURIDAD = "#0FA3B1"
CAT_IMAGENES = "#5E7387"

# alias de nombres anteriores
BG_INPUT = SURFACE  # noqa: F821  (definidos arriba con globals().update)
ACCENT_DIM = BORDER_STRONG  # noqa: F821
TEXT_ACCENT = ACCENT  # noqa: F821

PAD = 32   # margen del contenido
GAP = 24   # separación entre bloques

# --- tipografía -----------------------------------------------------------------
FONT = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"
FONT_MONO = "Consolas"


# --- modo claro / oscuro ----------------------------------------------------------

def is_dark() -> bool:
    return ctk.AppearanceModeTracker.appearance_mode == 1


def resolve(color):
    """Hex del modo actual a partir de un par (claro, oscuro); un hex suelto no cambia."""
    if isinstance(color, (tuple, list)):
        return color[1 if is_dark() else 0]
    return color


def set_mode(mode: str) -> None:
    """'light' u 'dark': recolorea al instante todos los widgets de customtkinter y
    llama a los avisos registrados con `on_mode_change`."""
    ctk.set_appearance_mode(mode)


def apply(mode: str = "light") -> None:
    set_mode(mode)


def on_mode_change(widget, callback) -> None:
    """Llama a `callback()` cada vez que cambia el modo, mientras `widget` exista."""
    def handler(_mode=None):
        try:
            if widget.winfo_exists():
                callback()
        except Exception:
            pass

    ctk.AppearanceModeTracker.add(handler)

    def destroyed(event):
        # en los widgets de customtkinter el evento llega desde su lienzo interno
        if event.widget in (widget, getattr(widget, "_canvas", None)):
            ctk.AppearanceModeTracker.remove(handler)

    widget.bind("<Destroy>", destroyed, add="+")


def system_prefers_dark() -> bool:
    """Lee la preferencia de Windows para las apps (Configuración > Personalización > Colores)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def tint(color: str, amount: float = 0.12, dark_amount: float = 0.18):
    """Mosaico de categoría: `amount` del color sobre blanco en claro y `dark_amount`
    sobre la superficie oscura (el icono sigue en el color pleno)."""
    return (_mix(color, amount, "#FFFFFF"), _mix(color, dark_amount, DARK["SURFACE"]))


def configure_fonts(regular: str, semibold: str) -> None:
    global FONT, FONT_SEMIBOLD
    FONT, FONT_SEMIBOLD = regular, semibold
    _build()


def _build() -> None:
    """(Re)construye los tamaños de fuente y los kits de widgets."""
    g = globals()
    g.update(
        FONT_TITLE=(FONT_SEMIBOLD, 22),
        FONT_HEADING=(FONT_SEMIBOLD, 15),
        FONT_SECTION=(FONT_SEMIBOLD, 12),    # rótulos de opciones
        FONT_BODY=(FONT, 14),
        FONT_BUTTON=(FONT_SEMIBOLD, 14),
        FONT_STATUS=(FONT, 13),
        FONT_SMALL=(FONT, 12),
        FONT_MONO_SMALL=(FONT_MONO, 12),     # solo rutas y tamaños de archivo
    )
    p = g
    g.update(
        CARD=dict(corner_radius=14, fg_color=p["SURFACE"], border_width=1, border_color=p["BORDER"]),
        BTN_PRIMARY=dict(corner_radius=10, fg_color=p["PRIMARY_BG"], hover_color=p["PRIMARY_HOVER"],
                         text_color=p["TEXT_ON_ACCENT"], font=g["FONT_BUTTON"]),
        BTN_SECONDARY=dict(corner_radius=10, fg_color=p["SURFACE"], hover_color=p["BG_HOVER"],
                           border_width=1, border_color=p["INPUT_BORDER"],
                           text_color=p["TEXT_PRIMARY"], font=(FONT_SEMIBOLD, 13)),
        ENTRY=dict(corner_radius=10, fg_color=p["SURFACE"], border_width=1,
                   border_color=p["INPUT_BORDER"], text_color=p["TEXT_PRIMARY"],
                   placeholder_text_color=p["TEXT_MUTED"], font=(FONT, 14)),
        TEXTBOX=dict(corner_radius=12, fg_color=p["SURFACE"], border_width=1,
                     border_color=p["BORDER"], text_color=p["TEXT_PRIMARY"],
                     font=g["FONT_MONO_SMALL"]),
        # customtkinter no permite otro color de texto para la opción elegida: se marca
        # con un tinte del rojo que mantiene buen contraste con el texto
        SEGMENTED=dict(corner_radius=10, fg_color=p["BG_HOVER"], selected_color=p["SELECTED_TINT"],
                       selected_hover_color=p["SELECTED_TINT_HOVER"],
                       unselected_color=p["SURFACE"], unselected_hover_color=p["BG_HOVER"],
                       text_color=p["TEXT_PRIMARY"], font=(FONT, 13)),
        OPTIONMENU=dict(corner_radius=10, fg_color=p["BG_HOVER"], button_color=p["BG_HOVER"],
                        button_hover_color=p["BORDER_STRONG"], text_color=p["TEXT_PRIMARY"],
                        font=(FONT, 13), dropdown_fg_color=p["SURFACE"],
                        dropdown_hover_color=p["BG_HOVER"], dropdown_text_color=p["TEXT_PRIMARY"],
                        dropdown_font=(FONT, 13)),
        SLIDER=dict(progress_color=p["ACCENT"], button_color=p["ACCENT"],
                    button_hover_color=p["ACCENT_HOVER"], fg_color=p["BORDER_STRONG"]),
        PROGRESS=dict(corner_radius=4, height=6, progress_color=p["ACCENT"], fg_color=p["BG_HOVER"]),
        SCROLLFRAME=dict(corner_radius=14, fg_color=p["SURFACE"], border_width=1,
                         border_color=p["BORDER"]),
        CHECKBOX=dict(corner_radius=6, border_width=2, fg_color=p["ACCENT"],
                      hover_color=p["ACCENT_HOVER"], border_color=p["BORDER_STRONG"],
                      checkmark_color=p["TEXT_ON_ACCENT"], text_color=p["TEXT_PRIMARY"],
                      font=(FONT, 13)),
        TABVIEW=dict(corner_radius=14, border_width=1, border_color=p["BORDER"],
                     fg_color=p["SURFACE"], segmented_button_fg_color=p["BG_HOVER"],
                     segmented_button_selected_color=p["SELECTED_TINT"],
                     segmented_button_selected_hover_color=p["SELECTED_TINT_HOVER"],
                     segmented_button_unselected_color=p["SURFACE"],
                     segmented_button_unselected_hover_color=p["BG_HOVER"],
                     segmented_button_font=(FONT, 13), text_color=p["TEXT_PRIMARY"]),
        SCROLLBAR=dict(button_color=p["BORDER_STRONG"], button_hover_color=p["TEXT_MUTED"]),
    )
    g["SLIDER_ON_CARD"] = g["SLIDER"]


_build()

STATUS_STYLES = {  # estado -> (fondo, texto)
    "info": (BG_SECONDARY, TEXT_SECONDARY),  # noqa: F821
    "success": (SUCCESS_BG, SUCCESS),  # noqa: F821
    "warning": (WARNING_BG, WARNING),  # noqa: F821
    "error": (ERROR_BG, ERROR),  # noqa: F821
}


def spaced(text: str) -> str:
    """Mayúsculas con espaciado de letras (~1 px), para títulos de categoría."""
    return " ".join(text.upper())


def attach_focus_ring(entry) -> None:
    """Anillo de foco suave: borde de 2 px con un tinte del rojo principal."""
    entry.bind("<FocusIn>", lambda _e: entry.configure(border_color=FOCUS_RING, border_width=2),  # noqa: F821
               add="+")
    entry.bind("<FocusOut>", lambda _e: entry.configure(border_color=INPUT_BORDER,  # noqa: F821
                                                        border_width=1), add="+")
