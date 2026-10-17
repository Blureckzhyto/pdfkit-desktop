"""Genera los recursos del logo a partir de los archivos originales (que no se
modifican): assets/logo_icon.png y assets/logo_wordmark.png.

  assets/icon.ico                      16…256 px, LANCZOS, enfoque leve en 16–32 px
  assets/logo/icon_window_{32,256}.png icono de ventana y barra de tareas (iconphoto)
  assets/logo/wordmark_sidebar@{1,2}x.png   barra lateral (34 px de alto)
  assets/logo/wordmark_sidebar_dark@{1,2}x.png   lo mismo para el modo oscuro: el texto
                                       gris carbón "PDF" pasa a #ECEDF2; el rojo no cambia
  assets/logo/icon_home@{1,2}x.png          pantalla de inicio (64 px)
"""
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUT = ASSETS / "logo"
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
SHARPEN_UP_TO = 32
SIDEBAR_WORDMARK_H = 34
HOME_ICON = 64
CHARCOAL = (35, 35, 45)       # color del texto "PDF" del logotipo original
DARK_MODE_TEXT = (0xEC, 0xED, 0xF2)


def _light_text(img: Image.Image) -> Image.Image:
    """Variante para fondo oscuro: los píxeles gris carbón (también los bordes suavizados,
    que solo difieren en el alfa) toman el color claro; todo lo demás queda igual."""
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a and abs(r - CHARCOAL[0]) + abs(g - CHARCOAL[1]) + abs(b - CHARCOAL[2]) < 60:
                px[x, y] = (*DARK_MODE_TEXT, a)
    return out


def _trim(img: Image.Image) -> Image.Image:
    """Recorta el margen transparente (alfa > 3) sin tocar el dibujo."""
    return img.crop(img.getchannel("A").point(lambda v: 255 if v > 3 else 0).getbbox())


def _square(img: Image.Image, margin: float = 0.02) -> Image.Image:
    side = round(max(img.size) * (1 + 2 * margin))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def _resize(img: Image.Image, size: tuple[int, int], sharpen: bool = False) -> Image.Image:
    out = img.resize(size, Image.LANCZOS)
    if sharpen:  # solo color: enfocar el alfa crearía un halo
        rgb = out.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.6, percent=70, threshold=0))
        rgb.putalpha(out.getchannel("A"))
        out = rgb
    return out


def _by_height(img: Image.Image, height: int) -> Image.Image:
    return _resize(img, (round(img.width * height / img.height), height))


def main():
    OUT.mkdir(exist_ok=True)
    icon = _square(_trim(Image.open(ASSETS / "logo_icon.png").convert("RGBA")))
    frames = [_resize(icon, (s, s), sharpen=s <= SHARPEN_UP_TO) for s in ICO_SIZES]
    frames[-1].save(ASSETS / "icon.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES],
                    append_images=frames[:-1])
    for s in (32, 256):
        _resize(icon, (s, s), sharpen=s <= SHARPEN_UP_TO).save(OUT / f"icon_window_{s}.png")
    for scale in (1, 2):
        _resize(icon, (HOME_ICON * scale,) * 2).save(OUT / f"icon_home@{scale}x.png")
    wordmark = _trim(Image.open(ASSETS / "logo_wordmark.png").convert("RGBA"))
    wordmark_dark = _light_text(wordmark)
    for scale in (1, 2):
        _by_height(wordmark, SIDEBAR_WORDMARK_H * scale).save(OUT / f"wordmark_sidebar@{scale}x.png")
        _by_height(wordmark_dark, SIDEBAR_WORDMARK_H * scale).save(
            OUT / f"wordmark_sidebar_dark@{scale}x.png")
    print("Recursos del logo generados:", ", ".join(sorted(p.name for p in OUT.iterdir())), "+ icon.ico")


if __name__ == "__main__":
    main()
