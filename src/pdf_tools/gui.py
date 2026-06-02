"""Tkinter desktop GUI for pdf-tools."""

from __future__ import annotations

import sys
from pathlib import Path

from pdf_tools.compress import CompressionMode, CompressionResult, Quality
from pdf_tools.to_word import ConversionResult, convert_pdf_to_docx, default_word_output_path
from pdf_tools.workflow import compress_pdf, default_output_path, format_size


def _build_summary(result: CompressionResult) -> str:
    """Return a friendly multi-line summary for the GUI."""
    lines = [
        f"Saved: {result.output_path}",
        f"Pages: {result.pages}",
        f"Before: {format_size(result.input_size)}",
        f"After: {format_size(result.output_size)}",
    ]
    if result.reduction_percent >= 0:
        lines.append(
            "Saved space: "
            f"{format_size(result.saved_bytes)} ({result.reduction_percent:.1f}% smaller)"
        )
    else:
        lines.append(
            "Output is larger by "
            f"{format_size(-result.saved_bytes)} ({-result.reduction_percent:.1f}%)"
        )
    if result.errors:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {error}" for error in result.errors)
    return "\n".join(lines)


def _build_word_summary(result: ConversionResult) -> str:
    """Return a friendly multi-line summary for a to-word conversion."""
    return "\n".join([
        f"Output : {result.output_path}",
        f"Pages  : {result.pages}",
    ])


def launch_gui() -> None:
    """Launch the graphical desktop application."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - depends on system Python
        raise RuntimeError(
            "Tkinter is not available in this Python installation."
        ) from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "A graphical display is not available. Run the GUI from a desktop session."
        ) from exc

    class PdfToolsApp(ttk.Frame):
        def __init__(self, master: tk.Tk) -> None:
            super().__init__(master, padding=16)
            self.master = master
            self._build()
            self.grid(sticky="nsew")
            self.columnconfigure(0, weight=1)
            self.master.columnconfigure(0, weight=1)
            self.master.rowconfigure(0, weight=1)

        def _build(self) -> None:
            self.master.title("pdf-tools")
            self.master.minsize(640, 420)

            notebook = ttk.Notebook(self)
            notebook.grid(row=0, column=0, sticky="nsew")
            self.rowconfigure(0, weight=1)
            self.columnconfigure(0, weight=1)

            compress_tab = ttk.Frame(notebook, padding=12)
            notebook.add(compress_tab, text="Compress")
            self._build_compress_tab(compress_tab)

            to_word_tab = ttk.Frame(notebook, padding=12)
            notebook.add(to_word_tab, text="PDF to Word")
            self._build_to_word_tab(to_word_tab)

        # ------------------------------------------------------------------
        # Compress tab
        # ------------------------------------------------------------------

        def _build_compress_tab(self, parent: ttk.Frame) -> None:
            self.c_input_var = tk.StringVar()
            self.c_output_var = tk.StringVar()
            self.quality_var = tk.StringVar(value=Quality.MEDIUM.value)
            self.mode_var = tk.StringVar(value=CompressionMode.NORMAL.value)
            self.no_images_var = tk.BooleanVar(value=False)
            self.force_var = tk.BooleanVar(value=False)
            self.c_status_var = tk.StringVar(
                value="Choose a PDF file and click Compress PDF."
            )
            self._c_auto_output = True

            parent.columnconfigure(0, weight=1)

            ttk.Label(parent, text="Input PDF").grid(row=0, column=0, sticky="w")
            ttk.Entry(parent, textvariable=self.c_input_var).grid(
                row=1, column=0, sticky="ew", padx=(0, 8)
            )
            ttk.Button(parent, text="Browse…", command=self._c_choose_input).grid(
                row=1, column=1, sticky="ew"
            )

            ttk.Label(parent, text="Output PDF").grid(
                row=2, column=0, sticky="w", pady=(12, 0)
            )
            ttk.Entry(parent, textvariable=self.c_output_var).grid(
                row=3, column=0, sticky="ew", padx=(0, 8)
            )
            ttk.Button(parent, text="Save as…", command=self._c_choose_output).grid(
                row=3, column=1, sticky="ew"
            )

            ttk.Label(parent, text="Quality").grid(row=4, column=0, sticky="w", pady=(12, 0))
            ttk.Combobox(
                parent,
                textvariable=self.quality_var,
                values=[quality.value for quality in Quality],
                state="readonly",
            ).grid(row=5, column=0, sticky="w")

            ttk.Label(parent, text="Mode").grid(row=4, column=1, sticky="w", pady=(12, 0))
            ttk.Combobox(
                parent,
                textvariable=self.mode_var,
                values=[mode.value for mode in CompressionMode],
                state="readonly",
            ).grid(row=5, column=1, sticky="w")

            ttk.Checkbutton(
                parent,
                text="Skip image recompression",
                variable=self.no_images_var,
            ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 0))
            ttk.Checkbutton(
                parent,
                text="Overwrite output file if it exists",
                variable=self.force_var,
            ).grid(row=7, column=0, columnspan=2, sticky="w")

            ttk.Button(parent, text="Compress PDF", command=self._compress).grid(
                row=8, column=0, sticky="w", pady=(16, 12)
            )

            ttk.Label(parent, textvariable=self.c_status_var).grid(
                row=9, column=0, columnspan=2, sticky="w"
            )

            c_result_box = tk.Text(parent, height=9, wrap="word")
            c_result_box.grid(row=10, column=0, columnspan=2, sticky="nsew")
            c_result_box.configure(state="disabled")
            self.c_result_box = c_result_box

            parent.rowconfigure(10, weight=1)
            self.c_input_var.trace_add("write", self._c_sync_output_from_input)

        def _c_choose_input(self) -> None:
            filename = filedialog.askopenfilename(
                title="Select PDF file",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
            if filename:
                self._c_auto_output = True
                self.c_input_var.set(filename)

        def _c_choose_output(self) -> None:
            initial = self.c_output_var.get() or self._c_suggest_output()
            filename = filedialog.asksaveasfilename(
                title="Save compressed PDF as",
                defaultextension=".pdf",
                initialfile=Path(initial).name if initial else "",
                initialdir=str(Path(initial).parent) if initial else "",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
            if filename:
                self._c_auto_output = False
                self.c_output_var.set(filename)

        def _c_suggest_output(self) -> str:
            input_path = self.c_input_var.get().strip()
            if not input_path:
                return ""
            return str(default_output_path(input_path))

        def _c_sync_output_from_input(self, *_args: object) -> None:
            if self._c_auto_output:
                self.c_output_var.set(self._c_suggest_output())

        def _c_set_result_text(self, text: str) -> None:
            self.c_result_box.configure(state="normal")
            self.c_result_box.delete("1.0", "end")
            self.c_result_box.insert("1.0", text)
            self.c_result_box.configure(state="disabled")

        def _compress(self) -> None:
            input_path = self.c_input_var.get().strip()
            output_path = self.c_output_var.get().strip() or None
            if not input_path:
                messagebox.showerror("Missing input", "Please choose an input PDF file.")
                return

            self.c_status_var.set("Compressing PDF…")
            self.master.update_idletasks()

            try:
                result = compress_pdf(
                    input_path,
                    output_path,
                    quality=self.quality_var.get(),
                    recompress_images=not self.no_images_var.get(),
                    mode=self.mode_var.get(),
                    force=self.force_var.get(),
                )
            except (OSError, ValueError, RuntimeError) as exc:
                self.c_status_var.set("Compression failed.")
                messagebox.showerror("Compression failed", str(exc))
                return

            self.c_status_var.set("Compression complete.")
            self._c_set_result_text(_build_summary(result))
            messagebox.showinfo("Compression complete", f"Saved to:\n{result.output_path}")

        # ------------------------------------------------------------------
        # PDF to Word tab
        # ------------------------------------------------------------------

        def _build_to_word_tab(self, parent: ttk.Frame) -> None:
            self.w_input_var = tk.StringVar()
            self.w_output_var = tk.StringVar()
            self.strip_watermarks_var = tk.BooleanVar(value=False)
            self.w_force_var = tk.BooleanVar(value=False)
            self.w_status_var = tk.StringVar(
                value="Choose a PDF file and click Convert to Word."
            )
            self._w_auto_output = True

            parent.columnconfigure(0, weight=1)

            ttk.Label(parent, text="Input PDF").grid(row=0, column=0, sticky="w")
            ttk.Entry(parent, textvariable=self.w_input_var).grid(
                row=1, column=0, sticky="ew", padx=(0, 8)
            )
            ttk.Button(parent, text="Browse…", command=self._w_choose_input).grid(
                row=1, column=1, sticky="ew"
            )

            ttk.Label(parent, text="Output Word file (.docx)").grid(
                row=2, column=0, sticky="w", pady=(12, 0)
            )
            ttk.Entry(parent, textvariable=self.w_output_var).grid(
                row=3, column=0, sticky="ew", padx=(0, 8)
            )
            ttk.Button(parent, text="Save as…", command=self._w_choose_output).grid(
                row=3, column=1, sticky="ew"
            )

            ttk.Checkbutton(
                parent,
                text="Strip background watermarks (best-effort)",
                variable=self.strip_watermarks_var,
            ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))
            ttk.Checkbutton(
                parent,
                text="Overwrite output file if it exists",
                variable=self.w_force_var,
            ).grid(row=5, column=0, columnspan=2, sticky="w")

            ttk.Button(
                parent, text="Convert to Word", command=self._to_word
            ).grid(row=6, column=0, sticky="w", pady=(16, 12))

            ttk.Label(parent, textvariable=self.w_status_var).grid(
                row=7, column=0, columnspan=2, sticky="w"
            )

            w_result_box = tk.Text(parent, height=9, wrap="word")
            w_result_box.grid(row=8, column=0, columnspan=2, sticky="nsew")
            w_result_box.configure(state="disabled")
            self.w_result_box = w_result_box

            parent.rowconfigure(8, weight=1)
            self.w_input_var.trace_add("write", self._w_sync_output_from_input)

        def _w_choose_input(self) -> None:
            filename = filedialog.askopenfilename(
                title="Select PDF file",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
            if filename:
                self._w_auto_output = True
                self.w_input_var.set(filename)

        def _w_choose_output(self) -> None:
            initial = self.w_output_var.get() or self._w_suggest_output()
            filename = filedialog.asksaveasfilename(
                title="Save Word file as",
                defaultextension=".docx",
                initialfile=Path(initial).name if initial else "",
                initialdir=str(Path(initial).parent) if initial else "",
                filetypes=[
                    ("Word documents", "*.docx"),
                    ("All files", "*.*"),
                ],
            )
            if filename:
                self._w_auto_output = False
                self.w_output_var.set(filename)

        def _w_suggest_output(self) -> str:
            input_path = self.w_input_var.get().strip()
            if not input_path:
                return ""
            return str(default_word_output_path(input_path))

        def _w_sync_output_from_input(self, *_args: object) -> None:
            if self._w_auto_output:
                self.w_output_var.set(self._w_suggest_output())

        def _w_set_result_text(self, text: str) -> None:
            self.w_result_box.configure(state="normal")
            self.w_result_box.delete("1.0", "end")
            self.w_result_box.insert("1.0", text)
            self.w_result_box.configure(state="disabled")

        def _to_word(self) -> None:
            input_path = self.w_input_var.get().strip()
            output_path = self.w_output_var.get().strip() or None
            if not input_path:
                messagebox.showerror("Missing input", "Please choose an input PDF file.")
                return

            self.w_status_var.set("Converting PDF to Word…")
            self.master.update_idletasks()

            try:
                result = convert_pdf_to_docx(
                    input_path,
                    output_path,
                    strip_watermarks=self.strip_watermarks_var.get(),
                    force=self.w_force_var.get(),
                )
            except (OSError, ValueError, RuntimeError) as exc:
                self.w_status_var.set("Conversion failed.")
                messagebox.showerror("Conversion failed", str(exc))
                return

            self.w_status_var.set("Conversion complete.")
            self._w_set_result_text(_build_word_summary(result))
            messagebox.showinfo("Conversion complete", f"Saved to:\n{result.output_path}")

    PdfToolsApp(root)
    root.mainloop()


def main() -> int:
    """Run the GUI entry point."""
    try:
        launch_gui()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
