"""Genera assets/splash.png: la pantalla de carga que muestra el exe (PyInstaller --splash)
desde el primer instante, mientras Python arranca. Logo + "Cargando…"."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 420, 240


def main() -> None:
    card = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(card)
    draw.rectangle((0, 0, W - 1, H - 1), outline="#E3E5EC")
    wordmark = Image.open(ROOT / "assets" / "logo_wordmark.png").convert("RGBA")
    width = 250
    wordmark = wordmark.resize((width, round(wordmark.height * width / wordmark.width)), Image.LANCZOS)
    card.paste(wordmark, ((W - width) // 2, 62), wordmark)
    font_path = ROOT / "assets" / "fonts" / "PlusJakartaSans-Regular.ttf"
    if not font_path.exists():
        font_path = ROOT / "assets" / "fonts" / "Inter-Regular.ttf"
    font = ImageFont.truetype(str(font_path), 15)
    text = "Cargando…"
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((W - (box[2] - box[0])) // 2, 172), text, font=font, fill="#6B7084")
    out = ROOT / "assets" / "splash.png"
    card.save(out)
    print(out)


if __name__ == "__main__":
    main()
