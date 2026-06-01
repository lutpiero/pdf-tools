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


def compress(
    input_path: str | Path,
    output_path: str | Path,
    quality: Quality | str = Quality.MEDIUM,
    *,
    recompress_images: bool = True,
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
    settings = _QUALITY_SETTINGS[quality]
    jpeg_quality: int = settings["jpeg_quality"]
    target_dpi: int = settings["dpi"]

    input_size = input_path.stat().st_size
    errors: list[str] = []

    doc = fitz.open(str(input_path))
    pages = doc.page_count

    if recompress_images:
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

    # Save with maximum structural and stream compression:
    # garbage=4  – full cross-reference rebuild + remove unreachable objects
    # deflate=True – apply flate (zlib) compression to all streams
    # clean=True  – sanitise content streams
    same_path = input_path.resolve() == output_path.resolve()
    if same_path:
        # PyMuPDF cannot save non-incrementally to the source file; write to a
        # temporary file in the same directory and then atomically replace.
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=output_path.parent, suffix=".tmp.pdf"
        )
        os.close(tmp_fd)
        try:
            doc.save(
                tmp_name,
                garbage=4,
                deflate=True,
                clean=True,
                deflate_images=True,
                deflate_fonts=True,
            )
            doc.close()
            os.replace(tmp_name, str(output_path))
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    else:
        doc.save(
            str(output_path),
            garbage=4,
            deflate=True,
            clean=True,
            deflate_images=True,
            deflate_fonts=True,
        )
        doc.close()

    output_size = output_path.stat().st_size

    return CompressionResult(
        input_path=input_path,
        output_path=output_path,
        input_size=input_size,
        output_size=output_size,
        pages=pages,
        errors=errors,
    )
