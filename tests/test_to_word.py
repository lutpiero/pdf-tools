"""Tests for pdf_tools.to_word and the to-word CLI subcommand."""

from __future__ import annotations

import zipfile
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from pdf_tools import gui as gui_module
from pdf_tools.cli import main
from pdf_tools.to_word import (
    ConversionResult,
    convert_pdf_to_docx,
    default_word_output_path,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_simple_pdf(path: Path, pages: int = 2) -> Path:
    """Create a minimal multi-page PDF at *path* and return it."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            f"Page {i + 1}\n" + ("Sample text content. " * 20),
            fontsize=12,
        )
    doc.save(str(path), deflate=False)
    doc.close()
    return path


@pytest.fixture()
def tmp_pdf(tmp_path: Path) -> Path:
    return _make_simple_pdf(tmp_path / "sample.pdf")


@pytest.fixture()
def tmp_pdf_with_watermark(tmp_path: Path) -> Path:
    """Create a PDF that contains a large semi-transparent background shape."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Document with watermark", fontsize=14)
    # Draw a large semi-transparent rectangle spanning most of the page
    rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
    page.draw_rect(rect, color=(0.8, 0.8, 0.8), fill=(0.9, 0.9, 0.9), fill_opacity=0.1)
    path = tmp_path / "watermark.pdf"
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------------------
# convert_pdf_to_docx() – unit tests
# ---------------------------------------------------------------------------

class TestConvertPdfToDocx:
    def test_output_file_is_created(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        convert_pdf_to_docx(tmp_pdf, out)
        assert out.exists()

    def test_returns_conversion_result(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        result = convert_pdf_to_docx(tmp_pdf, out)
        assert isinstance(result, ConversionResult)

    def test_result_contains_correct_paths(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        result = convert_pdf_to_docx(tmp_pdf, out)
        assert result.input_path == tmp_pdf
        assert result.output_path == out

    def test_page_count_reported(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        result = convert_pdf_to_docx(tmp_pdf, out)
        assert result.pages == 2

    def test_default_output_path_used_when_none_given(self, tmp_pdf: Path):
        expected = tmp_pdf.with_suffix(".docx")
        if expected.exists():
            expected.unlink()
        result = convert_pdf_to_docx(tmp_pdf)
        assert result.output_path == expected
        expected.unlink()

    def test_force_allows_overwrite(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        out.write_bytes(b"old content")
        result = convert_pdf_to_docx(tmp_pdf, out, force=True)
        assert out.exists()
        assert result.output_path == out

    def test_existing_output_without_force_raises(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        out.write_bytes(b"old content")
        with pytest.raises(FileExistsError):
            convert_pdf_to_docx(tmp_pdf, out)

    def test_missing_input_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            convert_pdf_to_docx(tmp_path / "missing.pdf", tmp_path / "out.docx")

    def test_directory_as_input_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            convert_pdf_to_docx(tmp_path, tmp_path / "out.docx")

    def test_missing_output_dir_raises(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "nonexistent_dir" / "out.docx"
        with pytest.raises(FileNotFoundError):
            convert_pdf_to_docx(tmp_pdf, out)

    def test_strip_watermarks_flag(self, tmp_pdf_with_watermark: Path, tmp_path: Path):
        out = tmp_path / "out_no_wm.docx"
        result = convert_pdf_to_docx(tmp_pdf_with_watermark, out, strip_watermarks=True)
        assert out.exists()
        assert isinstance(result, ConversionResult)

    def test_output_is_valid_docx(self, tmp_pdf: Path, tmp_path: Path):
        """Verify the output is a valid ZIP-based .docx file."""
        out = tmp_path / "out.docx"
        convert_pdf_to_docx(tmp_pdf, out)
        assert zipfile.is_zipfile(out)


# ---------------------------------------------------------------------------
# CLI – to-word subcommand
# ---------------------------------------------------------------------------

class TestCLIToWord:
    def test_to_word_basic(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        rc = main(["to-word", str(tmp_pdf), str(out)])
        assert rc == 0
        assert out.exists()

    def test_to_word_default_output_name(self, tmp_pdf: Path):
        expected = tmp_pdf.with_suffix(".docx")
        if expected.exists():
            expected.unlink()
        rc = main(["to-word", str(tmp_pdf)])
        assert rc == 0
        assert expected.exists()
        expected.unlink()

    def test_to_word_strip_watermarks_flag(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        rc = main(["to-word", str(tmp_pdf), str(out), "--strip-watermarks"])
        assert rc == 0

    def test_to_word_force_overwrite(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        out.write_bytes(b"old")
        rc = main(["to-word", str(tmp_pdf), str(out), "--force"])
        assert rc == 0

    def test_to_word_no_force_existing_output_fails(self, tmp_pdf: Path, tmp_path: Path):
        out = tmp_path / "out.docx"
        out.write_bytes(b"old")
        rc = main(["to-word", str(tmp_pdf), str(out)])
        assert rc == 1

    def test_to_word_missing_input_fails(self, tmp_path: Path):
        rc = main(
            ["to-word", str(tmp_path / "missing.pdf"), str(tmp_path / "out.docx")]
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestDefaultWordOutputPath:
    def test_changes_extension_to_docx(self, tmp_path: Path):
        p = tmp_path / "document.pdf"
        assert default_word_output_path(p) == tmp_path / "document.docx"

    def test_preserves_directory(self, tmp_path: Path):
        p = tmp_path / "sub" / "file.pdf"
        result = default_word_output_path(p)
        assert result.parent == tmp_path / "sub"
        assert result.suffix == ".docx"


# ---------------------------------------------------------------------------
# GUI entry point smoke-tests (no display required)
# ---------------------------------------------------------------------------

class TestGUIWithToWord:
    def test_gui_main_returns_zero_when_launch_succeeds(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(gui_module, "launch_gui", lambda: None)
        assert gui_module.main() == 0

    def test_gui_main_returns_error_code_on_runtime_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        def fake_launch_gui() -> None:
            raise RuntimeError("missing tkinter")

        monkeypatch.setattr(gui_module, "launch_gui", fake_launch_gui)
        assert gui_module.main() == 1
        assert "missing tkinter" in capsys.readouterr().err
