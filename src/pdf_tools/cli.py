"""Command-line interface for pdf-tools."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdf_tools import __version__
from pdf_tools.compress import Quality, compress


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024  # type: ignore[assignment]
    return f"{num_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# Sub-command: compress
# ---------------------------------------------------------------------------

def _cmd_compress(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else _default_output(input_path)

    if output_path == input_path and not args.force:
        print(
            "Error: output path is the same as input path.  "
            "Use --force to overwrite in place.",
            file=sys.stderr,
        )
        return 1

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    if output_path.exists() and not args.force:
        print(
            f"Error: output file already exists: {output_path}.  "
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    print(f"Compressing '{input_path}' → '{output_path}'  [quality: {args.quality}]")

    try:
        result = compress(
            input_path,
            output_path,
            quality=args.quality,
            recompress_images=not args.no_images,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result.errors:
        print("Warnings during compression:")
        for err in result.errors:
            print(f"  • {err}")

    in_s = _format_size(result.input_size)
    out_s = _format_size(result.output_size)
    pct = result.reduction_percent

    print(f"Pages   : {result.pages}")
    print(f"Before  : {in_s}")
    print(f"After   : {out_s}")
    if pct >= 0:
        print(f"Saved   : {_format_size(result.saved_bytes)} ({pct:.1f}% smaller)")
    else:
        print(
            f"Note    : output is {_format_size(-result.saved_bytes)} "
            f"larger ({-pct:.1f}%) – the source was already well-compressed."
        )

    return 0


def _default_output(input_path: Path) -> Path:
    """Return ``<stem>_compressed.<suffix>`` next to the input file."""
    return input_path.with_name(f"{input_path.stem}_compressed{input_path.suffix}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-tools",
        description="A cross-platform PDF compression and manipulation toolkit.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # -- compress sub-command --
    compress_parser = subparsers.add_parser(
        "compress",
        help="Reduce the file size of a PDF.",
        description="Compress a PDF by deflating streams and optionally recompressing images.",
    )
    compress_parser.add_argument("input", metavar="INPUT", help="Path to the source PDF.")
    compress_parser.add_argument(
        "output",
        metavar="OUTPUT",
        nargs="?",
        default=None,
        help=(
            "Path for the compressed output PDF.  "
            "Defaults to <input-stem>_compressed.pdf in the same directory."
        ),
    )
    compress_parser.add_argument(
        "-q",
        "--quality",
        choices=[q.value for q in Quality],
        default=Quality.MEDIUM.value,
        help=(
            "Compression quality preset: "
            "low (smallest file, more loss), "
            "medium (balanced, default), "
            "high (near-lossless, moderate savings)."
        ),
    )
    compress_parser.add_argument(
        "--no-images",
        action="store_true",
        default=False,
        help="Skip image recompression (only apply structural optimisations).",
    )
    compress_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="Overwrite the output file if it already exists.",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "compress":
        return _cmd_compress(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
