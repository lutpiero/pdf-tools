"""Command-line interface for pdf-tools."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdf_tools import __version__
from pdf_tools.compress import Quality
from pdf_tools.workflow import compress_pdf, default_output_path, format_size


# ---------------------------------------------------------------------------
# Sub-command: compress
# ---------------------------------------------------------------------------

def _cmd_compress(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else default_output_path(input_path)

    print(f"Compressing '{input_path}' → '{output_path}'  [quality: {args.quality}]")

    try:
        result = compress_pdf(
            input_path,
            output_path,
            quality=args.quality,
            recompress_images=not args.no_images,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result.errors:
        print("Warnings during compression:")
        for err in result.errors:
            print(f"  • {err}")

    in_s = format_size(result.input_size)
    out_s = format_size(result.output_size)
    pct = result.reduction_percent

    print(f"Pages   : {result.pages}")
    print(f"Before  : {in_s}")
    print(f"After   : {out_s}")
    if pct >= 0:
        print(f"Saved   : {format_size(result.saved_bytes)} ({pct:.1f}% smaller)")
    else:
        print(
            f"Note    : output is {format_size(-result.saved_bytes)} "
            f"larger ({-pct:.1f}%) – the source was already well-compressed."
        )

    return 0


def _cmd_gui(_args: argparse.Namespace) -> int:
    try:
        from pdf_tools.gui import launch_gui

        launch_gui()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


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
    compress_parser.set_defaults(handler=_cmd_compress)

    gui_parser = subparsers.add_parser(
        "gui",
        help="Launch the desktop GUI.",
        description="Open the cross-platform desktop interface for pdf-tools.",
    )
    gui_parser.set_defaults(handler=_cmd_gui)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
