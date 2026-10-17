"""PDF operations: merge, split, compress, render, image conversion, editing.

Every long-running function accepts an optional `progress(fraction, message)`
callback. All heavy third-party imports are done lazily so the app starts fast
and a missing optional dependency only breaks the tool that needs it.

No UI imports allowed in this module.
"""
from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

from .utils import hex_to_rgb01, unique_path


def _noop(fraction: float, message: str | None = None) -> None:
    pass


# --------------------------------------------------------------------------- info

def get_page_count(src: str | Path) -> int:
    from pypdf import PdfReader
    return len(PdfReader(str(src)).pages)


# --------------------------------------------------------------------------- merge

def merge_pdfs(paths: list[str | Path], output: str | Path, progress=None) -> Path:
    from pypdf import PdfWriter

    progress = progress or _noop
    if len(paths) < 2:
        raise ValueError("Select at least two PDF files to merge.")
    writer = PdfWriter()
    for i, p in enumerate(paths):
        try:
            writer.append(str(p))
        except Exception as exc:
            raise RuntimeError(f"Could not read '{Path(p).name}': {exc}") from exc
        progress((i + 1) / (len(paths) + 1), f"Added {Path(p).name}")
    progress(0.95, "Writing merged file…")
    with open(output, "wb") as fh:
        writer.write(fh)
    progress(1.0, None)
    return Path(output)


# --------------------------------------------------------------------------- split

def parse_ranges(spec: str, page_count: int) -> list[list[int]]:
    """'1-3, 5, 7-9' -> [[0,1,2], [4], [6,7,8]] (0-based). Raises ValueError."""
    groups: list[list[int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                a_s, b_s = part.split("-", 1)
                a, b = int(a_s), int(b_s)
            else:
                a = b = int(part)
        except ValueError:
            raise ValueError(f"'{part}' is not a valid page range (use e.g. 1-3,5,7-9).")
        if a < 1 or b > page_count or a > b:
            raise ValueError(f"Range '{part}' is out of bounds — the document has {page_count} pages.")
        groups.append(list(range(a - 1, b)))
    if not groups:
        raise ValueError("Enter at least one page range, e.g. 1-3,5.")
    return groups


def _write_pages(src_reader, indices: list[int], out_path: Path) -> None:
    from pypdf import PdfWriter
    writer = PdfWriter()
    for idx in indices:
        writer.add_page(src_reader.pages[idx])
    with open(out_path, "wb") as fh:
        writer.write(fh)


def split_by_ranges(src: str | Path, spec: str, out_dir: str | Path, progress=None) -> list[Path]:
    from pypdf import PdfReader

    progress = progress or _noop
    reader = PdfReader(str(src))
    groups = parse_ranges(spec, len(reader.pages))
    stem = Path(src).stem
    outputs = []
    for i, indices in enumerate(groups):
        label = f"{indices[0] + 1}" if len(indices) == 1 else f"{indices[0] + 1}-{indices[-1] + 1}"
        out = unique_path(Path(out_dir) / f"{stem}_pages_{label}.pdf")
        _write_pages(reader, indices, out)
        outputs.append(out)
        progress((i + 1) / len(groups), f"Wrote {out.name}")
    return outputs


def split_every_n(src: str | Path, n: int, out_dir: str | Path, progress=None) -> list[Path]:
    from pypdf import PdfReader

    progress = progress or _noop
    if n < 1:
        raise ValueError("Pages per file must be at least 1.")
    reader = PdfReader(str(src))
    total = len(reader.pages)
    stem = Path(src).stem
    outputs = []
    chunks = [list(range(i, min(i + n, total))) for i in range(0, total, n)]
    for i, indices in enumerate(chunks):
        out = unique_path(Path(out_dir) / f"{stem}_part{i + 1}.pdf")
        _write_pages(reader, indices, out)
        outputs.append(out)
        progress((i + 1) / len(chunks), f"Wrote {out.name}")
    return outputs


def split_by_size(src: str | Path, max_mb: float, out_dir: str | Path,
                  progress=None) -> tuple[list[Path], list[int]]:
    """Split into parts that each stay under max_mb megabytes.

    Grows each part page by page, re-writing the candidate part and measuring
    it, until adding one more page would push it past the limit. A single page
    larger than the limit is kept whole in its own part.

    Returns (parts, oversized) where `oversized` lists the 1-based part numbers
    whose lone page exceeds the limit.
    """
    from pypdf import PdfReader, PdfWriter

    progress = progress or _noop
    if max_mb <= 0:
        raise ValueError("Maximum size must be greater than 0 MB.")
    max_bytes = int(max_mb * 1024 * 1024)
    reader = PdfReader(str(src))
    total = len(reader.pages)
    stem = Path(src).stem

    parts: list[Path] = []
    oversized: list[int] = []
    part_num = 1
    start = 0
    while start < total:
        end = start
        while end < total:
            writer = PdfWriter()
            for i in range(start, end + 1):
                writer.add_page(reader.pages[i])
            buf = BytesIO()
            writer.write(buf)
            size = buf.tell()
            if size > max_bytes:
                if end == start:
                    end += 1  # single page exceeds limit, include it anyway
                    oversized.append(part_num)
                break
            else:
                end += 1

        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        out_path = unique_path(Path(out_dir) / f"{stem}_parte{part_num:02d}.pdf")
        with open(out_path, "wb") as fh:
            writer.write(fh)
        parts.append(out_path)
        progress(end / total, f"Wrote {out_path.name} (pages {start + 1}–{end} of {total})")
        part_num += 1
        start = end
    return parts, oversized


# --------------------------------------------------------------------------- compress

# quality level -> (JPEG quality, max image dimension in px)
COMPRESS_LEVELS = {"low": (50, 1000), "medium": (70, 1600), "high": (85, 2400)}


def compress_pdf(src: str | Path, output: str | Path, quality: str = "medium", progress=None) -> Path:
    """Recompress embedded images as JPEG and repack streams with pikepdf."""
    import pikepdf

    progress = progress or _noop
    jpeg_q, max_dim = COMPRESS_LEVELS[quality]
    with pikepdf.open(str(src)) as pdf:
        pages = list(pdf.pages)
        for i, page in enumerate(pages):
            try:
                images = dict(page.images)
            except Exception:
                images = {}
            for _name, raw in images.items():
                try:
                    _recompress_image(pikepdf, raw, jpeg_q, max_dim)
                except Exception:
                    continue  # never fail the whole file over one image
            progress(0.9 * (i + 1) / len(pages), f"Optimizing page {i + 1}/{len(pages)}")
        progress(0.95, "Repacking streams…")
        pdf.save(
            str(output),
            compress_streams=True,
            recompress_flate=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
    progress(1.0, None)
    return Path(output)


def _recompress_image(pikepdf, raw, jpeg_q: int, max_dim: int) -> None:
    from PIL import Image

    if "/SMask" in raw or "/Mask" in raw:
        return  # keep transparency untouched
    pdfimage = pikepdf.PdfImage(raw)
    pil = pdfimage.as_pil_image()
    if pil.width < 64 or pil.height < 64:
        return
    downsampled = max(pil.size) > max_dim
    if pil.mode not in ("RGB", "L"):
        pil = pil.convert("RGB")
    if downsampled:
        pil.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = BytesIO()
    pil.save(buf, "JPEG", quality=jpeg_q, optimize=True)
    data = buf.getvalue()
    try:
        old_len = len(raw.read_raw_bytes())
    except Exception:
        old_len = None
    if old_len is not None and len(data) >= old_len and not downsampled:
        return  # re-encoding did not help
    raw.write(data, filter=pikepdf.Name("/DCTDecode"))
    raw.ColorSpace = pikepdf.Name("/DeviceRGB" if pil.mode == "RGB" else "/DeviceGray")
    raw.Width, raw.Height = pil.width, pil.height
    raw.BitsPerComponent = 8
    for key in ("/DecodeParms", "/Decode"):
        if key in raw:
            del raw[key]


# --------------------------------------------------------------------------- PDF <-> images

def get_poppler_path() -> str | None:
    """Bundled Poppler (assets/poppler) first; POPPLER_PATH env var, then the
    system PATH as fallbacks."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller exe
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent
    poppler = base / "assets" / "poppler"
    if poppler.exists():
        return str(poppler)
    return os.environ.get("POPPLER_PATH") or None


POPPLER_PATH = get_poppler_path()


def _raise_poppler_hint(exc: Exception) -> None:
    text = f"{type(exc).__name__}: {exc}"
    if "poppler" in text.lower() or "pdfinfo" in text.lower() or "page count" in text.lower():
        raise RuntimeError(
            "Poppler was not found. This tool needs Poppler for Windows: download it "
            "(e.g. github.com/oschwartz10612/poppler-windows/releases), extract it, and add "
            "its 'Library\\bin' folder to your PATH — or set the POPPLER_PATH environment "
            "variable to that folder. Then restart PDFKit."
        ) from exc
    raise RuntimeError(f"Could not render the PDF: {exc}") from exc


def render_page_image(src: str | Path, page_index: int, dpi: int = 100):
    """Render one page to a PIL image (used for previews/editing)."""
    from pdf2image import convert_from_path

    try:
        return convert_from_path(
            str(src), dpi=dpi, first_page=page_index + 1, last_page=page_index + 1,
            poppler_path=POPPLER_PATH,
        )[0]
    except Exception as exc:
        _raise_poppler_hint(exc)


def pdf_to_images(src: str | Path, out_dir: str | Path, dpi: int = 150, progress=None) -> list[Path]:
    progress = progress or _noop
    total = get_page_count(src)
    stem = Path(src).stem
    outputs = []
    for i in range(total):
        img = render_page_image(src, i, dpi=dpi)
        out = unique_path(Path(out_dir) / f"{stem}_page{i + 1}.jpg")
        img.convert("RGB").save(out, "JPEG", quality=92)
        outputs.append(out)
        progress((i + 1) / total, f"Page {i + 1}/{total}")
    return outputs


def images_to_pdf(paths: list[str | Path], output: str | Path, progress=None) -> Path:
    import img2pdf
    from PIL import Image

    progress = progress or _noop
    if not paths:
        raise ValueError("Select at least one image.")
    pages: list[bytes] = []
    for i, p in enumerate(paths):
        with Image.open(p) as im:
            fmt = (im.format or "").upper()
            has_alpha = "A" in im.getbands() or (im.mode == "P" and "transparency" in im.info)
            if fmt == "JPEG" and not has_alpha:
                pages.append(Path(p).read_bytes())
            else:
                if has_alpha:
                    background = Image.new("RGB", im.size, "white")
                    background.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
                    im = background
                elif im.mode != "RGB":
                    im = im.convert("RGB")
                buf = BytesIO()
                im.save(buf, "PNG")
                pages.append(buf.getvalue())
        progress(0.8 * (i + 1) / len(paths), f"Preparing {Path(p).name}")
    progress(0.9, "Building PDF…")
    Path(output).write_bytes(img2pdf.convert(pages))
    progress(1.0, None)
    return Path(output)


# --------------------------------------------------------------------------- edit

def apply_edits(
    src: str | Path,
    output: str | Path,
    annotations: dict[int, list[dict]],
    rotations: dict[int, int],
    deleted: set[int],
    scale: float,
    progress=None,
) -> Path:
    """Bake edits into a new PDF.

    `annotations[page]` is a list of dicts with coordinates in *rendered pixels*
    (top-left origin) at `scale` pixels per PDF point, measured on the page as
    displayed (i.e. after existing /Rotate plus any extra rotation is applied).
    Types:
      {"type": "text",      "x", "y", "text", "size" (pt), "color" (#hex)}
      {"type": "highlight", "x", "y", "w", "h", "color"}
      {"type": "draw",      "points": [(x, y), ...], "width" (pt), "color"}
      {"type": "image",     "path", "x", "y", "w", "h"}
    """
    from pypdf import PdfReader, PdfWriter

    progress = progress or _noop
    reader = PdfReader(str(src))
    writer = PdfWriter()
    total = len(reader.pages)
    kept = 0
    for i, page in enumerate(reader.pages):
        if i in deleted:
            progress((i + 1) / total, f"Skipping deleted page {i + 1}")
            continue
        extra = rotations.get(i, 0) % 360
        if extra:
            page.rotate(extra)
        if page.rotation:
            # Bake /Rotate into the content so overlay coordinates match the
            # page exactly as it was rendered on screen.
            page.transfer_rotation_to_content()
        anns = annotations.get(i) or []
        if anns:
            page.merge_page(_build_overlay(page, anns, scale))
        writer.add_page(page)
        kept += 1
        progress((i + 1) / total, f"Processing page {i + 1}/{total}")
    if kept == 0:
        raise ValueError("All pages are marked for deletion — nothing to save.")
    with open(output, "wb") as fh:
        writer.write(fh)
    progress(1.0, None)
    return Path(output)


def _build_overlay(page, anns: list[dict], scale: float):
    from pypdf import PdfReader
    from reportlab.lib.colors import Color
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    mb = page.mediabox
    w, h = float(mb.width), float(mb.height)
    ox, oy = float(mb.left), float(mb.bottom)

    def px(v: float) -> float:
        return v / scale

    def x_pt(x: float) -> float:
        return ox + px(x)

    def y_pt(y: float) -> float:  # top-left pixel origin -> bottom-left points
        return oy + h - px(y)

    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(w, h))
    for a in anns:
        kind = a["type"]
        if kind == "text":
            r, g, b = hex_to_rgb01(a["color"])
            c.setFillColorRGB(r, g, b)
            c.setFont("Helvetica", a["size"])
            c.drawString(x_pt(a["x"]), y_pt(a["y"]), a["text"])
        elif kind == "highlight":
            r, g, b = hex_to_rgb01(a["color"])
            c.setFillColor(Color(r, g, b, alpha=0.35))
            c.rect(x_pt(a["x"]), y_pt(a["y"] + a["h"]), px(a["w"]), px(a["h"]), stroke=0, fill=1)
        elif kind == "draw":
            pts = a["points"]
            if len(pts) < 2:
                continue
            r, g, b = hex_to_rgb01(a["color"])
            c.setStrokeColorRGB(r, g, b)
            c.setLineWidth(a.get("width", 2))
            c.setLineCap(1)
            c.setLineJoin(1)
            path = c.beginPath()
            path.moveTo(x_pt(pts[0][0]), y_pt(pts[0][1]))
            for x, y in pts[1:]:
                path.lineTo(x_pt(x), y_pt(y))
            c.drawPath(path, stroke=1, fill=0)
        elif kind == "image":
            c.drawImage(
                ImageReader(a["path"]),
                x_pt(a["x"]), y_pt(a["y"] + a["h"]), px(a["w"]), px(a["h"]),
                mask="auto",
            )
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]
