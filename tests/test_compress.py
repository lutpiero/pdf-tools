"""Tests for pdf_tools.compress and pdf_tools.cli."""

from __future__ import annotations

import os
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from pdf_tools.compress import CompressionResult, Quality, compress
from pdf_tools import gui as gui_module
from pdf_tools.cli import main, _default_output, _format_size
from pdf_tools.workflow import compress_pdf, prepare_compression_paths


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_simple_pdf(path: Path, pages: int = 2, *, add_text: bool = True) -> Path:
    """Create a minimal multi-page PDF at *path* and return it."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        if add_text:
            page.insert_text(
                (72, 72),
                f"Page {i + 1}\n" + ("Sample text content. " * 20),
                fontsize=12,
            )
    doc.save(str(path), deflate=False)  # save uncompressed so we have room to compress
    doc.close()
    return path


@pytest.fixture()
def tmp_pdf(tmp_path: Path) -> Path:
    return _make_simple_pdf(tmp_path / "sample.pdf")


@pytest.fixture()
def tmp_pdf_with_image(tmp_path: Path) -> Path:
    """Create a PDF that embeds a small generated JPEG image."""
    from PIL import Image
    import io

    # Create a 200x200 pixel gradient image
    img = Image.new("RGB", (200, 200))
    pixels = img.load()
    for y in range(200):
        for x in range(200):
            pixels[x, y] = (x, y, (x + y) % 256)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    jpeg_bytes = buf.getvalue()

    pdf_path = tmp_path / "with_image.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF with embedded image", fontsize=14)
    page.insert_image(fitz.Rect(100, 100, 300, 300), stream=jpeg_bytes)
    doc.save(str(pdf_path), deflate=False)
    doc.close()
    return pdf_path


# ---------------------------------------------------------------------------
# compress() – unit tests
# ---------------------------------------------------------------------------

class TestCompress:
    def test_output_file_is_created(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        compress(tmp_pdf, out)
        assert out.exists()

    def test_returns_compression_result(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out)
        assert isinstance(result, CompressionResult)

    def test_result_contains_correct_paths(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out)
        assert result.input_path == tmp_pdf
        assert result.output_path == out

    def test_output_is_valid_pdf(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        compress(tmp_pdf, out)
        doc = fitz.open(str(out))
        assert doc.page_count > 0
        doc.close()

    def test_page_count_preserved(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out)
        assert result.pages == 2

    def test_quality_low(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out, quality=Quality.LOW)
        assert out.exists()
        assert result.output_size > 0

    def test_quality_high(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out, quality=Quality.HIGH)
        assert out.exists()
        assert result.output_size > 0

    def test_quality_string_accepted(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out, quality="low")
        assert isinstance(result, CompressionResult)

    def test_sizes_reported_correctly(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out)
        assert result.input_size == tmp_pdf.stat().st_size
        assert result.output_size == out.stat().st_size

    def test_saved_bytes_calculation(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out)
        assert result.saved_bytes == result.input_size - result.output_size

    def test_reduction_percent_type(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out)
        assert isinstance(result.reduction_percent, float)

    def test_no_image_recompression_flag(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out, recompress_images=False)
        assert out.exists()
        assert result.output_size > 0

    def test_image_recompression(self, tmp_pdf_with_image: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf_with_image, out, quality=Quality.LOW)
        assert out.exists()
        assert result.output_size > 0

    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            compress(tmp_path / "nonexistent.pdf", tmp_path / "out.pdf")

    def test_directory_as_input_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            compress(tmp_path, tmp_path / "out.pdf")

    def test_no_errors_for_clean_pdf(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        result = compress(tmp_pdf, out)
        assert result.errors == []


# ---------------------------------------------------------------------------
# CLI – unit tests
# ---------------------------------------------------------------------------

class TestCLI:
    def test_compress_basic(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        rc = main(["compress", str(tmp_pdf), str(out)])
        assert rc == 0
        assert out.exists()

    def test_compress_default_output_name(self, tmp_pdf: Path):
        out = tmp_pdf.with_name(f"{tmp_pdf.stem}_compressed{tmp_pdf.suffix}")
        if out.exists():
            out.unlink()
        rc = main(["compress", str(tmp_pdf)])
        assert rc == 0
        assert out.exists()
        out.unlink()

    def test_compress_quality_low(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        rc = main(["compress", str(tmp_pdf), str(out), "--quality", "low"])
        assert rc == 0

    def test_compress_quality_high(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        rc = main(["compress", str(tmp_pdf), str(out), "--quality", "high"])
        assert rc == 0

    def test_compress_no_images_flag(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        rc = main(["compress", str(tmp_pdf), str(out), "--no-images"])
        assert rc == 0

    def test_compress_force_overwrite(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        out.write_bytes(b"dummy")
        rc = main(["compress", str(tmp_pdf), str(out), "--force"])
        assert rc == 0

    def test_compress_no_force_existing_output_fails(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.pdf"
        out.write_bytes(b"dummy")
        rc = main(["compress", str(tmp_pdf), str(out)])
        assert rc == 1

    def test_compress_missing_input_fails(self, tmp_path: Path):
        rc = main(["compress", str(tmp_path / "missing.pdf"), str(tmp_path / "out.pdf")])
        assert rc == 1

    def test_compress_same_path_without_force_fails(self, tmp_pdf: Path):
        rc = main(["compress", str(tmp_pdf), str(tmp_pdf)])
        assert rc == 1

    def test_compress_same_path_with_force(self, tmp_pdf: Path):
        rc = main(["compress", str(tmp_pdf), str(tmp_pdf), "--force"])
        assert rc == 0

    def test_gui_subcommand_launches_gui(self, monkeypatch: pytest.MonkeyPatch):
        called = {"value": False}

        def fake_launch_gui() -> None:
            called["value"] = True

        monkeypatch.setattr(gui_module, "launch_gui", fake_launch_gui)
        rc = main(["gui"])
        assert rc == 0
        assert called["value"] is True

    def test_gui_subcommand_returns_error_code_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        def fake_launch_gui() -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(gui_module, "launch_gui", fake_launch_gui)
        rc = main(["gui"])
        assert rc == 1


class TestWorkflow:
    def test_prepare_compression_paths_uses_default_output(self, tmp_pdf: Path):
        source, destination = prepare_compression_paths(tmp_pdf)
        assert source == tmp_pdf
        assert destination == tmp_pdf.with_name("sample_compressed.pdf")

    def test_prepare_compression_paths_rejects_existing_output_without_force(
        self,
        tmp_pdf: Path,
        tmp_path: Path,
    ):
        output = tmp_path / "out.pdf"
        output.write_bytes(b"already-here")

        with pytest.raises(FileExistsError):
            prepare_compression_paths(tmp_pdf, output)

    def test_compress_pdf_reuses_validation_and_returns_result(
        self,
        tmp_pdf: Path,
        tmp_path: Path,
    ):
        output = tmp_path / "workflow.pdf"
        result = compress_pdf(tmp_pdf, output, quality="low")

        assert isinstance(result, CompressionResult)
        assert output.exists()


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_default_output_name(self, tmp_path: Path):
        p = tmp_path / "document.pdf"
        result = _default_output(p)
        assert result == tmp_path / "document_compressed.pdf"

    def test_format_size_bytes(self):
        assert _format_size(512) == "512.0 B"

    def test_format_size_kb(self):
        assert "KB" in _format_size(2048)

    def test_format_size_mb(self):
        assert "MB" in _format_size(2 * 1024 * 1024)

    def test_gui_build_summary(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "summary.pdf"
        result = compress(tmp_pdf, out)
        summary = gui_module._build_summary(result)
        assert "Saved:" in summary
        assert "Pages:" in summary
