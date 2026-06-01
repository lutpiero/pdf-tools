"""Tkinter desktop GUI for pdf-tools."""

from __future__ import annotations

import sys
from pathlib import Path

from pdf_tools.compress import CompressionResult, Quality
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
            self.input_var = tk.StringVar()
            self.output_var = tk.StringVar()
            self.quality_var = tk.StringVar(value=Quality.MEDIUM.value)
            self.no_images_var = tk.BooleanVar(value=False)
            self.force_var = tk.BooleanVar(value=False)
            self.status_var = tk.StringVar(
                value="Choose a PDF file and click Compress PDF."
            )
            self._auto_output = True
            self._build()
            self.grid(sticky="nsew")
            self.columnconfigure(0, weight=1)
            self.master.columnconfigure(0, weight=1)
            self.master.rowconfigure(0, weight=1)

        def _build(self) -> None:
            self.master.title("pdf-tools")
            self.master.minsize(640, 360)

            ttk.Label(self, text="Input PDF").grid(row=0, column=0, sticky="w")
            ttk.Entry(self, textvariable=self.input_var).grid(
                row=1, column=0, sticky="ew", padx=(0, 8)
            )
            ttk.Button(self, text="Browse…", command=self._choose_input).grid(
                row=1, column=1, sticky="ew"
            )

            ttk.Label(self, text="Output PDF").grid(
                row=2, column=0, sticky="w", pady=(12, 0)
            )
            ttk.Entry(self, textvariable=self.output_var).grid(
                row=3, column=0, sticky="ew", padx=(0, 8)
            )
            ttk.Button(self, text="Save as…", command=self._choose_output).grid(
                row=3, column=1, sticky="ew"
            )

            ttk.Label(self, text="Quality").grid(row=4, column=0, sticky="w", pady=(12, 0))
            ttk.Combobox(
                self,
                textvariable=self.quality_var,
                values=[quality.value for quality in Quality],
                state="readonly",
            ).grid(row=5, column=0, sticky="w")

            ttk.Checkbutton(
                self,
                text="Skip image recompression",
                variable=self.no_images_var,
            ).grid(row=6, column=0, sticky="w", pady=(12, 0))
            ttk.Checkbutton(
                self,
                text="Overwrite output file if it exists",
                variable=self.force_var,
            ).grid(row=7, column=0, sticky="w")

            ttk.Button(self, text="Compress PDF", command=self._compress).grid(
                row=8, column=0, sticky="w", pady=(16, 12)
            )

            ttk.Label(self, textvariable=self.status_var, foreground="#555555").grid(
                row=9, column=0, columnspan=2, sticky="w"
            )

            result_box = tk.Text(self, height=9, wrap="word")
            result_box.grid(row=10, column=0, columnspan=2, sticky="nsew")
            result_box.configure(state="disabled")
            self.result_box = result_box

            self.rowconfigure(10, weight=1)
            self.input_var.trace_add("write", self._sync_output_from_input)

        def _choose_input(self) -> None:
            filename = filedialog.askopenfilename(
                title="Select PDF file",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
            if filename:
                self._auto_output = True
                self.input_var.set(filename)

        def _choose_output(self) -> None:
            initial = self.output_var.get() or self._suggest_output()
            filename = filedialog.asksaveasfilename(
                title="Save compressed PDF as",
                defaultextension=".pdf",
                initialfile=Path(initial).name if initial else "",
                initialdir=str(Path(initial).parent) if initial else "",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
            if filename:
                self._auto_output = False
                self.output_var.set(filename)

        def _suggest_output(self) -> str:
            input_path = self.input_var.get().strip()
            if not input_path:
                return ""
            return str(default_output_path(input_path))

        def _sync_output_from_input(self, *_args: object) -> None:
            if self._auto_output:
                self.output_var.set(self._suggest_output())

        def _set_result_text(self, text: str) -> None:
            self.result_box.configure(state="normal")
            self.result_box.delete("1.0", "end")
            self.result_box.insert("1.0", text)
            self.result_box.configure(state="disabled")

        def _compress(self) -> None:
            input_path = self.input_var.get().strip()
            output_path = self.output_var.get().strip() or None
            if not input_path:
                messagebox.showerror("Missing input", "Please choose an input PDF file.")
                return

            self.status_var.set("Compressing PDF…")
            self.master.update_idletasks()

            try:
                result = compress_pdf(
                    input_path,
                    output_path,
                    quality=self.quality_var.get(),
                    recompress_images=not self.no_images_var.get(),
                    force=self.force_var.get(),
                )
            except (OSError, ValueError, RuntimeError) as exc:
                self.status_var.set("Compression failed.")
                messagebox.showerror("Compression failed", str(exc))
                return

            self.status_var.set("Compression complete.")
            self._set_result_text(_build_summary(result))
            messagebox.showinfo("Compression complete", f"Saved to:\n{result.output_path}")

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
