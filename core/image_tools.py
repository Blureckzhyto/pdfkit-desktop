"""Image conversion and compression. No UI imports."""
from __future__ import annotations

from pathlib import Path

from .utils import unique_path

try:  # enables HEIC/HEIF open + save through Pillow
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False

# UI-facing format name -> (extension, Pillow format)
FORMATS = {
    "PNG": (".png", "PNG"),
    "JPG": (".jpg", "JPEG"),
    "JPEG": (".jpeg", "JPEG"),
    "WEBP": (".webp", "WEBP"),
    "BMP": (".bmp", "BMP"),
    "TIFF": (".tiff", "TIFF"),
    "HEIC": (".heic", "HEIF"),
}

IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".gif"]


def _noop(fraction: float, message: str | None = None) -> None:
    pass


def _flatten_alpha(im):
    """Composite transparency onto white (for formats without alpha)."""
    from PIL import Image
    rgba = im.convert("RGBA")
    background = Image.new("RGB", im.size, "white")
    background.paste(rgba, mask=rgba.split()[-1])
    return background


def convert_image(src: str | Path, out_dir: str | Path, fmt: str, quality: int = 90) -> Path:
    from PIL import Image

    fmt = fmt.upper()
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported target format: {fmt}")
    ext, pil_fmt = FORMATS[fmt]
    if pil_fmt == "HEIF" and not HEIF_SUPPORTED:
        raise RuntimeError("HEIC support requires the 'pillow-heif' package (pip install pillow-heif).")

    out = unique_path(Path(out_dir) / f"{Path(src).stem}{ext}")
    with Image.open(src) as im:
        has_alpha = "A" in im.getbands() or (im.mode == "P" and "transparency" in im.info)
        if pil_fmt in ("JPEG", "BMP") and has_alpha:
            im = _flatten_alpha(im)
        elif im.mode == "P":
            im = im.convert("RGBA" if has_alpha else "RGB")
        elif im.mode not in ("RGB", "RGBA", "L", "LA") and pil_fmt != "TIFF":
            im = im.convert("RGB")

        save_kwargs: dict = {}
        if pil_fmt == "JPEG":
            save_kwargs = {"quality": quality, "optimize": True}
        elif pil_fmt == "WEBP":
            save_kwargs = {"quality": quality}
        elif pil_fmt == "HEIF":
            save_kwargs = {"quality": quality}
        elif pil_fmt == "PNG":
            save_kwargs = {"optimize": True}
        elif pil_fmt == "TIFF":
            save_kwargs = {"compression": "tiff_lzw"}
        im.save(out, pil_fmt, **save_kwargs)
    return out


def convert_images(paths, out_dir, fmt, quality=90, progress=None) -> list[Path]:
    progress = progress or _noop
    outputs = []
    for i, p in enumerate(paths):
        try:
            outputs.append(convert_image(p, out_dir, fmt, quality))
        except Exception as exc:
            raise RuntimeError(f"Failed on '{Path(p).name}': {exc}") from exc
        progress((i + 1) / len(paths), f"Converted {Path(p).name}")
    return outputs


def compress_image(src: str | Path, out_dir: str | Path, quality: int = 70) -> tuple[Path, int, int]:
    """Recompress an image in (roughly) its own format.

    Returns (output_path, bytes_before, bytes_after).
    """
    from PIL import Image

    src = Path(src)
    before = src.stat().st_size
    with Image.open(src) as im:
        fmt = (im.format or "").upper()
        if fmt in ("JPEG", "MPO"):
            out = unique_path(Path(out_dir) / f"{src.stem}_compressed.jpg")
            if im.mode not in ("RGB", "L"):
                im = _flatten_alpha(im)
            im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
        elif fmt == "PNG":
            out = unique_path(Path(out_dir) / f"{src.stem}_compressed.png")
            if quality < 90:  # lossy color reduction buys the real savings for PNG
                im = im.quantize(256, method=Image.Quantize.FASTOCTREE)
            im.save(out, "PNG", optimize=True)
        elif fmt == "WEBP":
            out = unique_path(Path(out_dir) / f"{src.stem}_compressed.webp")
            im.save(out, "WEBP", quality=quality)
        elif fmt in ("HEIF", "HEIC"):
            if not HEIF_SUPPORTED:
                raise RuntimeError("HEIC support requires the 'pillow-heif' package.")
            out = unique_path(Path(out_dir) / f"{src.stem}_compressed.heic")
            im.save(out, "HEIF", quality=quality)
        else:  # BMP/TIFF/GIF etc. -> JPEG gives the meaningful size win
            out = unique_path(Path(out_dir) / f"{src.stem}_compressed.jpg")
            if im.mode not in ("RGB", "L"):
                im = _flatten_alpha(im)
            im.save(out, "JPEG", quality=quality, optimize=True)
    return out, before, out.stat().st_size


def compress_images(paths, out_dir, quality=70, progress=None) -> list[tuple[Path, int, int]]:
    progress = progress or _noop
    results = []
    for i, p in enumerate(paths):
        try:
            results.append(compress_image(p, out_dir, quality))
        except Exception as exc:
            raise RuntimeError(f"Failed on '{Path(p).name}': {exc}") from exc
        progress((i + 1) / len(paths), f"Compressed {Path(p).name}")
    return results
