"""Tests for pdf_tools.to_word and the to-word CLI subcommand."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
import pytest

from pdf_tools import gui as gui_module
from pdf_tools.cli import main
from pdf_tools.to_word import (
    ConversionResult,
    convert_pdf_to_docx,
    default_word_output_path,
    is_scanned_pdf,
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


def _make_scanned_pdf(path: Path, pages: int = 1) -> Path:
    """Create a PDF with no embedded text layer (simulates a scanned document)."""
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()  # empty pages – no text, no images
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def tmp_pdf(tmp_path: Path) -> Path:
    return _make_simple_pdf(tmp_path / "sample.pdf")


@pytest.fixture()
def tmp_scanned_pdf(tmp_path: Path) -> Path:
    return _make_scanned_pdf(tmp_path / "scanned.pdf")


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

    def test_to_word_ocr_flag_accepted(
        self,
        tmp_scanned_pdf: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """--ocr flag should be accepted and invoke the OCR conversion path."""
        out = tmp_path / "out.docx"
        mock_ocr = MagicMock()
        monkeypatch.setattr("pdf_tools.to_word._ocr_pdf_to_docx", mock_ocr)
        rc = main(["to-word", str(tmp_scanned_pdf), str(out), "--ocr"])
        assert rc == 0
        mock_ocr.assert_called_once()

    def test_to_word_scanned_warns_without_ocr_flag(
        self,
        tmp_scanned_pdf: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        """A scanned PDF should trigger a warning when --ocr is not provided."""
        out = tmp_path / "out.docx"
        main(["to-word", str(tmp_scanned_pdf), str(out)])
        captured = capsys.readouterr()
        assert "scanned" in captured.err.lower()
        assert "--ocr" in captured.err

    def test_to_word_ocr_import_error_returns_1(
        self,
        tmp_scanned_pdf: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A missing easyocr dependency should return exit code 1 with a message."""
        out = tmp_path / "out.docx"

        def raise_import_error(*_a, **_kw):
            raise ImportError("easyocr not installed")

        monkeypatch.setattr("pdf_tools.to_word._ocr_pdf_to_docx", raise_import_error)
        rc = main(["to-word", str(tmp_scanned_pdf), str(out), "--ocr"])
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
# is_scanned_pdf() tests
# ---------------------------------------------------------------------------

class TestIsScannedPdf:
    def test_text_pdf_is_not_scanned(self, tmp_pdf: Path):
        assert is_scanned_pdf(tmp_pdf) is False

    def test_empty_page_pdf_is_scanned(self, tmp_scanned_pdf: Path):
        assert is_scanned_pdf(tmp_scanned_pdf) is True

    def test_accepts_path_string(self, tmp_pdf: Path):
        assert is_scanned_pdf(str(tmp_pdf)) is False

    def test_custom_threshold(self, tmp_path: Path):
        """A page with very short text is scanned under a high threshold."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hi", fontsize=12)  # only 2 chars
        path = tmp_path / "short.pdf"
        doc.save(str(path))
        doc.close()
        # Default threshold is 10 chars – this page should be classified scanned.
        assert is_scanned_pdf(path, text_threshold=10) is True
        # With a lower threshold it is classified as having text.
        assert is_scanned_pdf(path, text_threshold=1) is False


# ---------------------------------------------------------------------------
# _ocr_pdf_to_docx() unit tests (easyocr mocked)
# ---------------------------------------------------------------------------

class TestOcrPdfToDocx:
    """Tests for the OCR conversion path using mocked EasyOCR."""

    def _make_fake_reader(self, ocr_results=None):
        """Return a fake EasyOCR Reader class."""
        if ocr_results is None:
            ocr_results = [([0, 0, 100, 20], "OCR extracted text", 0.99)]

        class FakeReader:
            def __init__(self, *args, **kwargs):
                pass

            def readtext(self, _img):
                return ocr_results

        return FakeReader

    def test_ocr_creates_docx_for_scanned_pdf(
        self,
        tmp_scanned_pdf: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        out = tmp_path / "ocr_out.docx"
        monkeypatch.setitem(
            __import__("sys").modules,
            "easyocr",
            MagicMock(Reader=self._make_fake_reader()),
        )
        from pdf_tools.to_word import _ocr_pdf_to_docx

        _ocr_pdf_to_docx(tmp_scanned_pdf, out)
        assert out.exists()
        assert zipfile.is_zipfile(out)

    def test_ocr_creates_docx_for_text_pdf(
        self,
        tmp_pdf: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Text-layer pages should still produce a valid DOCX via the OCR path."""
        out = tmp_path / "ocr_text.docx"
        monkeypatch.setitem(
            __import__("sys").modules,
            "easyocr",
            MagicMock(Reader=self._make_fake_reader()),
        )
        from pdf_tools.to_word import _ocr_pdf_to_docx

        _ocr_pdf_to_docx(tmp_pdf, out)
        assert out.exists()
        assert zipfile.is_zipfile(out)

    def test_ocr_raises_import_error_when_easyocr_missing(
        self,
        tmp_scanned_pdf: Path,
        tmp_path: Path,
    ):
        out = tmp_path / "ocr_out.docx"
        # Setting sys.modules["easyocr"] to None causes Python's import
        # machinery to raise ImportError on `import easyocr`.
        with patch.dict("sys.modules", {"easyocr": None}):
            from pdf_tools.to_word import _ocr_pdf_to_docx

            with pytest.raises(ImportError, match="easyocr"):
                _ocr_pdf_to_docx(tmp_scanned_pdf, out)

    def test_convert_pdf_to_docx_with_use_ocr(
        self,
        tmp_scanned_pdf: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """convert_pdf_to_docx(use_ocr=True) should delegate to _ocr_pdf_to_docx."""
        out = tmp_path / "out.docx"
        mock_ocr = MagicMock()
        monkeypatch.setattr("pdf_tools.to_word._ocr_pdf_to_docx", mock_ocr)
        result = convert_pdf_to_docx(tmp_scanned_pdf, out, use_ocr=True)
        mock_ocr.assert_called_once()
        assert isinstance(result, ConversionResult)


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
