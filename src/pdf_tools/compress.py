"""PDF compression functionality using PyMuPDF."""

from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image


class Quality(str, Enum):
    """Compression quality presets."""

    LOW = "low"        # Aggressive compression – smallest file, some visible loss
    MEDIUM = "medium"  # Balanced compression – good quality, noticeably smaller
    HIGH = "high"      # Gentle compression – near-lossless, moderately smaller


class CompressionMode(str, Enum):
    """Compression mode presets."""

    NORMAL = "normal"
    SCANNED = "scanned"


# JPEG quality factor (0–100) and target DPI for each preset
_QUALITY_SETTINGS: dict[Quality, dict] = {
    Quality.LOW: {"jpeg_quality": 35, "dpi": 96},
    Quality.MEDIUM: {"jpeg_quality": 60, "dpi": 150},
    Quality.HIGH: {"jpeg_quality": 85, "dpi": 200},
}


@dataclass
class CompressionResult:
    """Statistics returned after a compression run."""

    input_path: Path
    output_path: Path
    input_size: int
    output_size: int
    pages: int
    errors: list[str] = field(default_factory=list)

    @property
    def saved_bytes(self) -> int:
        return self.input_size - self.output_size

    @property
    def reduction_percent(self) -> float:
        if self.input_size == 0:
            return 0.0
        return (self.saved_bytes / self.input_size) * 100


def _recompress_image(
    image_bytes: bytes,
    orig_xres: int,
    orig_yres: int,
    target_dpi: int,
    jpeg_quality: int,
) -> Optional[bytes]:
    """Return recompressed image bytes, or *None* if no change is worthwhile."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return None

    # Convert palette or transparency modes to a form Pillow can save as JPEG
    if img.mode in ("P", "PA"):
        img = img.convert("RGBA")
    if img.mode in ("RGBA", "LA"):
        # JPEG does not support alpha; composite onto white background
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Downsample only when the image resolution exceeds the target DPI
    effective_xres = orig_xres if orig_xres > 0 else 72
    effective_yres = orig_yres if orig_yres > 0 else 72

    if effective_xres > target_dpi or effective_yres > target_dpi:
        scale = min(target_dpi / effective_xres, target_dpi / effective_yres)
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return buf.getvalue()


def _pixmap_to_jpeg(pix: fitz.Pixmap, jpeg_quality: int) -> bytes:
    mode = "L" if pix.n == 1 else "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return buf.getvalue()


def _compress_scanned_pdf(
    source_doc: fitz.Document,
    target_dpi: int,
    jpeg_quality: int,
    errors: list[str],
) -> fitz.Document:
    scale = max(72, target_dpi) / 72.0
    matrix = fitz.Matrix(scale, scale)
    output_doc = fitz.open()

    for page_index in range(source_doc.page_count):
        page = source_doc[page_index]
        try:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            jpeg_bytes = _pixmap_to_jpeg(pix, jpeg_quality)
            output_page = output_doc.new_page(
                width=page.rect.width,
                height=page.rect.height,
            )
            output_page.insert_image(output_page.rect, stream=jpeg_bytes)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Page {page_index + 1}: {exc}")
            output_doc.insert_pdf(source_doc, from_page=page_index, to_page=page_index)

    return output_doc


def _save_document(
    doc: fitz.Document,
    input_path: Path,
    output_path: Path,
    save_kwargs: dict[str, int | bool],
) -> None:
    same_path = input_path.resolve() == output_path.resolve()
    if same_path:
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=output_path.parent, suffix=".tmp.pdf"
        )
        os.close(tmp_fd)
        try:
            doc.save(tmp_name, **save_kwargs)
            os.replace(tmp_name, str(output_path))
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        finally:
            doc.close()
        return

    try:
        doc.save(str(output_path), **save_kwargs)
    finally:
        doc.close()


def compress(
    input_path: str | Path,
    output_path: str | Path,
    quality: Quality | str = Quality.MEDIUM,
    *,
    recompress_images: bool = True,
    mode: CompressionMode | str = CompressionMode.NORMAL,
) -> CompressionResult:
    """Compress *input_path* and write the result to *output_path*.

    Parameters
    ----------
    input_path:
        Path to the source PDF file.
    output_path:
        Path where the compressed PDF will be saved.  The parent directory
        must already exist.
    quality:
        Compression preset – ``"low"``, ``"medium"`` (default), or ``"high"``.
    recompress_images:
        When ``True`` (default) embedded images are recompressed according to
        the chosen quality preset, which typically yields the biggest savings.
    mode:
        Compression mode: ``normal`` (default) uses existing structural/image
        stream compression, ``scanned`` rebuilds pages from recompressed page
        images to safely handle scanned PDFs.

    Returns
    -------
    CompressionResult
        Metadata about the compression run (file sizes, page count, …).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")

    quality = Quality(quality)
    mode = CompressionMode(mode)
    settings = _QUALITY_SETTINGS[quality]
    jpeg_quality: int = settings["jpeg_quality"]
    target_dpi: int = settings["dpi"]

    input_size = input_path.stat().st_size
    errors: list[str] = []

    doc = fitz.open(str(input_path))
    pages = doc.page_count

    if mode is CompressionMode.SCANNED and recompress_images:
        scanned_doc = _compress_scanned_pdf(doc, target_dpi, jpeg_quality, errors)
        doc.close()
        doc = scanned_doc
    elif recompress_images:
        for page_index in range(pages):
            page = doc[page_index]
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    orig_xres = base_image.get("xres", 0)
                    orig_yres = base_image.get("yres", 0)

                    recompressed = _recompress_image(
                        image_bytes, orig_xres, orig_yres, target_dpi, jpeg_quality
                    )
                    if recompressed is not None and len(recompressed) < len(image_bytes):
                        doc.update_stream(xref, recompressed)
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        f"Page {page_index + 1}, image xref {xref}: {exc}"
                    )

    _save_document(
        doc,
        input_path,
        output_path,
        {
            "garbage": 4,
            "deflate": True,
            "clean": True,
            "deflate_images": True,
            "deflate_fonts": True,
        },
    )

    output_size = output_path.stat().st_size

    return CompressionResult(
        input_path=input_path,
        output_path=output_path,
        input_size=input_size,
        output_size=output_size,
        pages=pages,
        errors=errors,
    )
