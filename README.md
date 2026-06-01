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

### Standalone executable (no Python required)

You can bundle the tool into a single executable for Windows, macOS, or Linux using [PyInstaller](https://pyinstaller.org/):

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

The first GUI release focuses on PDF compression. It lets you:

- choose an input PDF
- pick an output file
- select compression quality
- optionally skip image recompression
- optionally overwrite an existing output file
- read friendly success, warning, and error messages in the window

> **Linux note:** if Tkinter is not installed with your Python distribution,
> install your distro's Tk package and run the GUI command again.

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
- [ ] PDF editing (text, annotations)
- [ ] PDF highlighting
