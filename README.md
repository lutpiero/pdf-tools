# pdf-tools

A **standalone, cross-platform PDF tool** with both a command-line interface and a desktop GUI, with the first GUI release documented for Windows and Linux.

---

## Features

- **Compress** PDF files — reduces file size by:
  - Recompressing embedded images (JPEG, configurable quality)
  - Deflating all content streams and fonts
  - Removing unused/unreachable PDF objects (garbage collection)
- Three **quality presets**: `low`, `medium` (default), `high`
- Optional **skip-image** flag for structure-only compression
- Safe **in-place** overwrite support (`--force`)
- Clear **before/after size** summary in the terminal
- **PDF to Word** — converts PDF to `.docx`, preserving headings, paragraphs,
  spacing, images, and tables as closely as possible
  - Best-effort background **watermark removal** option
  - **OCR support** (`--ocr`) for scanned / image-only PDFs via
    [EasyOCR](https://github.com/JaidedAI/EasyOCR) — extracts searchable text
    from scanned pages while keeping existing text layers untouched
- Simple **desktop GUI** built with Tkinter for Windows and Linux

---

## Installation

### From source (requires Python ≥ 3.9)

```bash
git clone https://github.com/lutpiero/pdf-tools.git
cd pdf-tools
pip install .
```

The `pdf-tools` and `pdf-tools-gui` commands are now available in your PATH.

To enable **OCR support** for scanned PDFs, install the optional `ocr` extra:

```bash
pip install "pdf-tools[ocr]"
```

> The GUI runs on Tkinter. If your Python distribution does not include Tkinter,
> install the matching Tk package for your OS/distribution.
>
> Install **PyMuPDF** via `pip install pymupdf`. Do **not** install the unrelated
> `fitz` package from PyPI.

### Standalone executable (no Python required)

The Windows GUI executable is built automatically by the
**Build Windows GUI executable** GitHub Actions workflow on every push and can
also be built manually from the **Actions** tab (`workflow_dispatch`).

To download it:

1. Open the workflow run in the repository **Actions** tab.
2. Download the `pdf-tools-gui-windows` artifact.
3. Extract the artifact and run `pdf-tools-gui.exe`.

You can also build locally with [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --name pdf-tools src/pdf_tools/cli.py
pyinstaller --onefile --windowed --name pdf-tools-gui src/pdf_tools/gui.py
# The executables are written to the dist/ directory
```

---

## Usage

### Desktop GUI

Launch the graphical desktop app with either command:

```bash
pdf-tools-gui
```

or:

```bash
pdf-tools gui
```

The GUI provides two tabs:

**Compress tab** — lets you:

- choose an input PDF
- pick an output file
- select compression quality
- choose compression mode (`normal` or `scanned`)
- optionally skip image recompression
- optionally overwrite an existing output file
- read friendly success, warning, and error messages in the window

**PDF to Word tab** — lets you:

- choose an input PDF
- pick an output `.docx` file (defaults to `<stem>.docx` next to the input)
- optionally enable best-effort background watermark removal
- optionally overwrite an existing output file
- read friendly success and error messages in the window

> If Tkinter is not installed with your Python distribution, install your
> OS/distribution Tk package and run the GUI command again.

### Command line

```
pdf-tools <command> [options]
```

### `compress` — reduce PDF file size

```
pdf-tools compress [OPTIONS] INPUT [OUTPUT]
```

| Argument / Option | Description |
|---|---|
| `INPUT` | Path to the source PDF file |
| `OUTPUT` *(optional)* | Path for the compressed output. Defaults to `<stem>_compressed.pdf` next to the input |
| `-q`, `--quality` | Preset: `low` · `medium` (default) · `high` |
| `--mode` | Compression mode: `normal` (default) · `scanned` (safe for scanned/image-based PDFs) |
| `--no-images` | Skip image recompression (structural optimisation only) |
| `-f`, `--force` | Overwrite the output file if it already exists |

#### Examples

```bash
# Basic compression (medium quality, auto-named output)
pdf-tools compress report.pdf

# Specify output path
pdf-tools compress report.pdf report_small.pdf

# Aggressive compression (smallest file)
pdf-tools compress report.pdf report_small.pdf --quality low

# Near-lossless compression (best quality)
pdf-tools compress report.pdf --quality high

# Safe scanned-document compression mode
pdf-tools compress scanned.pdf scanned_small.pdf --mode scanned

# Skip image recompression
pdf-tools compress report.pdf --no-images

# Overwrite in place
pdf-tools compress report.pdf report.pdf --force
```

#### Sample output

```
Compressing 'report.pdf' → 'report_compressed.pdf'  [quality: medium]
Pages   : 12
Before  : 4.8 MB
After   : 1.1 MB
Saved   : 3.7 MB (77.4% smaller)
```

---

### `to-word` — convert PDF to Microsoft Word

```
pdf-tools to-word [OPTIONS] INPUT [OUTPUT]
```

Converts a PDF to a `.docx` file, preserving headings, paragraphs, spacing,
images, and tables as closely as possible using
[pdf2docx](https://pdf2docx.readthedocs.io/).

| Argument / Option | Description |
|---|---|
| `INPUT` | Path to the source PDF file |
| `OUTPUT` *(optional)* | Path for the `.docx` output. Defaults to `<stem>.docx` next to the input |
| `--ocr` | Enable OCR for scanned / image-only pages using EasyOCR. Pages that already contain an embedded text layer are converted using that text directly. Requires `pip install "pdf-tools[ocr]"` |
| `--strip-watermarks` | Best-effort removal of large semi-transparent background shapes (common watermark pattern) before conversion |
| `-f`, `--force` | Overwrite the output file if it already exists |

#### Examples

```bash
# Basic conversion (auto-named output)
pdf-tools to-word report.pdf

# Specify output path
pdf-tools to-word report.pdf report.docx

# Extract text from a scanned PDF using OCR
pdf-tools to-word scan.pdf scan.docx --ocr

# Remove background watermarks before conversion
pdf-tools to-word watermarked.pdf clean.docx --strip-watermarks

# Overwrite an existing output file
pdf-tools to-word report.pdf report.docx --force
```

#### Sample output

```
Converting 'report.pdf' → 'report.docx'
Pages   : 12
Output  : report.docx
```

#### Notes on formatting fidelity

- **Headings, paragraphs, and spacing** are detected from the PDF structure
  and mapped to Word styles where possible.
- **Images** are extracted and embedded in the DOCX.
- **Tables** are reconstructed from both lattice (bordered) and stream
  (space-aligned) layouts.
- Complex multi-column or heavily styled PDFs may not convert perfectly —
  this is a known limitation of PDF-to-Word conversion in general.
- **Scanned PDFs**: without `--ocr`, scanned (image-only) pages will not
  produce searchable text.  Pass `--ocr` to enable EasyOCR extraction.
  When `--ocr` is used, the output is text-focused and may not preserve
  complex layout formatting from the scanned original.  The tool
  automatically detects mixed PDFs — pages with an existing text layer are
  converted using that text directly, while scanned pages are processed with
  OCR.  A warning is printed when a scanned PDF is detected without `--ocr`.
- **Watermarks**: the `--strip-watermarks` flag removes large semi-transparent
  path shapes before conversion.  Fully opaque watermarks or text-based
  watermarks are not affected.

---

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=pdf_tools
```

---

## Roadmap

- [x] PDF compression
- [x] PDF to Word conversion
- [ ] PDF editing (text, annotations)
- [ ] PDF highlighting
