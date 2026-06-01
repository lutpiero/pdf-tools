# pdf-tools

A **standalone, cross-platform CLI tool** to compress (and, in future releases, edit and highlight) PDF files.

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

---

## Installation

### From source (requires Python ≥ 3.9)

```bash
git clone https://github.com/lutpiero/pdf-tools.git
cd pdf-tools
pip install .
```

The `pdf-tools` command is now available in your PATH.

### Standalone executable (no Python required)

You can bundle the tool into a single executable for Windows, macOS, or Linux using [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --name pdf-tools src/pdf_tools/cli.py
# The executable is written to dist/pdf-tools (or dist\pdf-tools.exe on Windows)
```

---

## Usage

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
