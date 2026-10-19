"""Logotipos del listado de la Microsoft Store (Partner Center -> Descripciones de Store ->
Logotipos de Store), desde assets/logo_icon.png y assets/logo_wordmark.png:

  store_listing/logos/icono-1x1-300.png      icono de la app 1:1 (300x300)
  store_listing/logos/caja-1x1-2160.png      arte de caja 1:1 (2160x2160)
  store_listing/logos/poster-2x3-1440x2160.png  póster 2:3 (1440x2160)
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "store_listing" / "logos"
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
from make_logo_assets import _resize, _square, _trim  # noqa: E402

BACKGROUND_TOP, BACKGROUND_BOTTOM = (255, 255, 255), (253, 236, 236)   # blanco a rosa muy claro


def gradient(size: tuple[int, int]) -> Image.Image:
    w, h = size
    column = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM)))
    return column.resize((w, h)).convert("RGBA")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = _square(_trim(Image.open(ROOT / "assets" / "logo_icon.png").convert("RGBA")))
    word = _trim(Image.open(ROOT / "assets" / "logo_wordmark.png").convert("RGBA"))

    _resize(icon, (300, 300)).save(OUT / "icono-1x1-300.png", optimize=True)

    box = gradient((2160, 2160))
    side = 1100
    box.alpha_composite(_resize(icon, (side, side)), ((2160 - side) // 2, (2160 - side) // 2))
    box.convert("RGB").save(OUT / "caja-1x1-2160.png", optimize=True)

    poster = gradient((1440, 2160))
    side = 760
    poster.alpha_composite(_resize(icon, (side, side)), ((1440 - side) // 2, 560))
    # solo el texto del wordmark (sin su icono): se recorta a la derecha del icono
    text = word.crop((round(word.height * 1.08), 0, word.width, word.height))
    text = _trim(text)
    tw = 820
    th = round(text.height * tw / text.width)
    poster.alpha_composite(_resize(text, (tw, th)), ((1440 - tw) // 2, 560 + side + 120))
    poster.convert("RGB").save(OUT / "poster-2x3-1440x2160.png", optimize=True)
    print("Logotipos:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
