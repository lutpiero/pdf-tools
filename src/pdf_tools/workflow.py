"""Shared workflows for CLI and GUI entry points."""

from __future__ import annotations

from pathlib import Path

from pdf_tools.compress import CompressionMode, CompressionResult, Quality, compress


def format_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def default_output_path(input_path: str | Path) -> Path:
    """Return ``<stem>_compressed.<suffix>`` next to the input file."""
    input_path = Path(input_path)
    return input_path.with_name(f"{input_path.stem}_compressed{input_path.suffix}")


def prepare_compression_paths(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    force: bool = False,
) -> tuple[Path, Path]:
    """Validate and normalize compression input/output paths."""
    source = Path(input_path)
    destination = Path(output_path) if output_path else default_output_path(source)

    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")
    if not source.is_file():
        raise ValueError(f"Input path is not a file: {source}")
    if not destination.parent.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {destination.parent}"
        )
    if source.resolve() == destination.resolve() and not force:
        raise ValueError(
            "Output path is the same as the input file. "
            "Choose a different output file or enable overwrite."
        )
    if destination.exists() and not force:
        raise FileExistsError(
            f"Output file already exists: {destination}. Enable overwrite to replace it."
        )

    return source, destination


def compress_pdf(
    input_path: str | Path,
    output_path: str | Path | None = None,
    quality: Quality | str = Quality.MEDIUM,
    *,
    recompress_images: bool = True,
    mode: CompressionMode | str = CompressionMode.NORMAL,
    force: bool = False,
) -> CompressionResult:
    """Run PDF compression after applying shared path validation."""
    source, destination = prepare_compression_paths(
        input_path,
        output_path,
        force=force,
    )
    return compress(
        source,
        destination,
        quality=quality,
        recompress_images=recompress_images,
        mode=mode,
    )
