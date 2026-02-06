"""
Bezel Remover for Videowall — desktop app for non-technical users.
Pick a video (8640×3840), set bezel width, click Process. Output saved next to the original.
"""

import sys
import threading
from pathlib import Path
from typing import Optional

# When running as a .app (frozen), redirect stderr to a log so launch failures are visible
if getattr(sys, "frozen", False):
    try:
        _log_dir = Path.home() / "Library" / "Logs"
        _log_dir.mkdir(parents=True, exist_ok=True)
        _log_file = _log_dir / "Bezel Remover.log"
        sys.stderr = open(_log_file, "a", encoding="utf-8")
        sys.stderr.write("\n--- session ---\n")
        sys.stderr.flush()
    except Exception:
        pass

import customtkinter as ctk

from bezel_processor import (
    get_ffmpeg_path,
    output_path,
    run as run_bezel_removal,
)


# UI defaults (portrait row: top = left edge, bottom = right edge; Sony EZ20L ~16mm top, 21mm bottom)
CTK_FONT_FAMILY = "Helvetica"
DEFAULT_TOP_BEZEL_PX = 16
DEFAULT_BOTTOM_BEZEL_PX = 21
WINDOW_MIN_WIDTH = 520
# Min height: header (72) + main padding (48) + settings card (~220) + gap (10) + progress card (title + bar + status + result + log ~220)
WINDOW_MIN_HEIGHT = 850

# Styling (Figma-to-HTML–style: dark header, light body, white cards, purple primary)
COLOR_HEADER_BG = "#1A1A1A"
COLOR_MAIN_BG = "#F2F2F2"
COLOR_CARD_BG = "#FFFFFF"
COLOR_PRIMARY = "#9933CC"
COLOR_BUTTON_DISABLED_BG = "#A0A0A0"
COLOR_BUTTON_DISABLED_TEXT = "#888888"
COLOR_SECONDARY_BG = "#E6E6E6"
COLOR_SECONDARY_TEXT = "#333333"
COLOR_TEXT_TITLE = "#000000"
COLOR_TEXT_MUTED = "#666666"
COLOR_INPUT_BG = "#F0F0F0"  # Match for entry fields and dropdown
CARD_CORNER_RADIUS = 10
CARD_PAD = 24


class BezelRemoverApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Bezel Remover for Videowall")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.geometry("560x480")

        ctk.set_appearance_mode("light")
        self.configure(fg_color=COLOR_MAIN_BG)

        # Bring window to front when launched from Finder (macOS)
        self.after(100, self._bring_to_front)

        self.input_path: Optional[Path] = None
        self._processing = False
        self._progress_thread: Optional[threading.Thread] = None
        self._last_log_message: Optional[str] = None

        self._build_ui()

    def _build_ui(self):
        # —— Header (full-width dark bar) ——
        header = ctk.CTkFrame(
            self, fg_color=COLOR_HEADER_BG, corner_radius=0, height=72
        )
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=CARD_PAD, pady=12)
        ctk.CTkLabel(
            header_inner,
            text="Bezel Remover for Videowall",
            font=(CTK_FONT_FAMILY, 20, "bold"),
            text_color="white",
        ).pack(anchor="w")
        ctk.CTkLabel(
            header_inner,
            text="Remove bezel pixels from videowall video. Output saved next to the original.",
            font=(CTK_FONT_FAMILY, 12),
            text_color="white",
        ).pack(anchor="w")

        # —— Main content area (light grey) ——
        main = ctk.CTkFrame(self, fg_color=COLOR_MAIN_BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=CARD_PAD, pady=CARD_PAD)

        # —— Card 1: settings (white, rounded) ——
        card = ctk.CTkFrame(
            main,
            fg_color=COLOR_CARD_BG,
            corner_radius=CARD_CORNER_RADIUS,
            border_width=1,
            border_color="#E0E0E0",
        )
        card.pack(fill="x", pady=(0, 10))
        pad = {"padx": 16, "pady": 10}
        pad_header = {"padx": 16, "pady": (10, 0)}
        pad_secondary = {"padx": 16, "pady": (0, 10)}
        row = 0

        # Video file (no space between header and path line)
        ctk.CTkLabel(
            card, text="Video file", font=(CTK_FONT_FAMILY, 14, "bold"), text_color=COLOR_TEXT_TITLE
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad_header)
        row += 1
        self._path_var = ctk.StringVar(value="No file selected")
        self._path_label = ctk.CTkLabel(
            card,
            textvariable=self._path_var,
            anchor="w",
            wraplength=360,
            text_color=COLOR_TEXT_MUTED,
            font=(CTK_FONT_FAMILY, 12),
        )
        self._path_label.grid(row=row, column=0, sticky="ew", **pad_secondary)
        self._browse_btn = ctk.CTkButton(
            card,
            text="Browse…",
            command=self._browse,
            fg_color=COLOR_SECONDARY_BG,
            text_color=COLOR_SECONDARY_TEXT,
            hover_color="#D0D0D0",
            corner_radius=8,
        )
        self._browse_btn.grid(row=row, column=1, **pad_secondary)
        row += 1

        # Divider above bezel section
        div = ctk.CTkFrame(card, height=1, fg_color="#E0E0E0")
        div.grid(row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=(12, 4))
        row += 1
        ctk.CTkLabel(
            card, text="Bezels", font=(CTK_FONT_FAMILY, 14, "bold"), text_color=COLOR_TEXT_TITLE
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad_header)
        row += 1
        ctk.CTkLabel(
            card,
            text="Default values match the Bravia displays in the Showroom; leave unchanged unless needed.",
            text_color="#CC0000",
            font=(CTK_FONT_FAMILY, 12),
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad_secondary)
        row += 1

        # Top bezel (physical top = left edge in portrait row); no space between header and secondary
        ctk.CTkLabel(
            card, text="Top bezel (px)", font=(CTK_FONT_FAMILY, 12, "bold"), text_color=COLOR_TEXT_TITLE
        ).grid(row=row, column=0, sticky="w", **pad_header)
        self._top_bezel_var = ctk.StringVar(value=str(DEFAULT_TOP_BEZEL_PX))
        self._top_bezel_entry = ctk.CTkEntry(
            card, textvariable=self._top_bezel_var, width=80, corner_radius=8, border_color="#E0E0E0", fg_color=COLOR_INPUT_BG
        )
        self._top_bezel_entry.grid(row=row, column=1, sticky="e", **pad_header)
        row += 1
        ctk.CTkLabel(
            card,
            text="Left edge of each panel (e.g. 16 for 16mm)",
            text_color=COLOR_TEXT_MUTED,
            font=(CTK_FONT_FAMILY, 12),
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad_secondary)
        row += 1

        # Bottom bezel (physical bottom = right edge in portrait row); no space between header and secondary
        ctk.CTkLabel(
            card, text="Bottom bezel (px)", font=(CTK_FONT_FAMILY, 12, "bold"), text_color=COLOR_TEXT_TITLE
        ).grid(row=row, column=0, sticky="w", **pad_header)
        self._bottom_bezel_var = ctk.StringVar(value=str(DEFAULT_BOTTOM_BEZEL_PX))
        self._bottom_bezel_entry = ctk.CTkEntry(
            card, textvariable=self._bottom_bezel_var, width=80, corner_radius=8, border_color="#E0E0E0", fg_color=COLOR_INPUT_BG
        )
        self._bottom_bezel_entry.grid(row=row, column=1, sticky="e", **pad_header)
        row += 1
        ctk.CTkLabel(
            card,
            text="Right edge of each panel (e.g. 21 for 21mm)",
            text_color=COLOR_TEXT_MUTED,
            font=(CTK_FONT_FAMILY, 12),
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad_secondary)
        row += 1

        # Divider below bezel section
        div2 = ctk.CTkFrame(card, height=1, fg_color="#E0E0E0")
        div2.grid(row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 12))
        row += 1

        # Target file size (quality vs size; longer videos get lower bitrate to stay under target)
        ctk.CTkLabel(
            card, text="Target file size", font=(CTK_FONT_FAMILY, 14, "bold"), text_color=COLOR_TEXT_TITLE
        ).grid(row=row, column=0, sticky="w", **pad_header)
        self._target_size_var = ctk.StringVar(value="200 MB")
        self._target_size_menu = ctk.CTkOptionMenu(
            card,
            values=["100 MB", "200 MB", "500 MB", "Best quality"],
            variable=self._target_size_var,
            width=140,
            corner_radius=8,
            fg_color=COLOR_INPUT_BG,
            dropdown_fg_color=COLOR_INPUT_BG,
            button_color=COLOR_SECONDARY_BG,
            button_hover_color="#D0D0D0",
            text_color=COLOR_TEXT_TITLE,
            dropdown_text_color=COLOR_TEXT_TITLE,
        )
        self._target_size_menu.grid(row=row, column=1, sticky="e", **pad_header)
        row += 1
        ctk.CTkLabel(
            card,
            text="Shorter videos get higher quality within the limit; Best quality uses fixed bitrate.",
            text_color=COLOR_TEXT_MUTED,
            font=(CTK_FONT_FAMILY, 12),
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad_secondary)
        row += 1

        # Process button (primary: purple)
        self._process_btn = ctk.CTkButton(
            card,
            text="Remove bezels and save",
            command=self._process,
            font=(CTK_FONT_FAMILY, 14),
            height=40,
            fg_color=COLOR_PRIMARY,
            hover_color="#7B2C9E",
            text_color="white",
            corner_radius=8,
        )
        self._process_btn.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        card.columnconfigure(0, weight=1)

        # —— Card 2: progress & log (white, rounded) ——
        card2 = ctk.CTkFrame(
            main,
            fg_color=COLOR_CARD_BG,
            corner_radius=CARD_CORNER_RADIUS,
            border_width=1,
            border_color="#E0E0E0",
        )
        card2.pack(fill="both", expand=True)
        row2 = 0
        ctk.CTkLabel(
            card2, text="Progress", font=(CTK_FONT_FAMILY, 14, "bold"), text_color=COLOR_TEXT_TITLE
        ).grid(row=row2, column=0, columnspan=2, sticky="w", **pad)
        row2 += 1
        self._progress_var = ctk.DoubleVar(value=0.0)
        self._progress_bar = ctk.CTkProgressBar(
            card2, variable=self._progress_var, progress_color=COLOR_PRIMARY
        )
        self._progress_bar.grid(row=row2, column=0, columnspan=2, sticky="ew", **pad)
        row2 += 1
        self._status_var = ctk.StringVar(value="")
        self._status_label = ctk.CTkLabel(
            card2,
            textvariable=self._status_var,
            anchor="w",
            text_color=COLOR_TEXT_MUTED,
            font=(CTK_FONT_FAMILY, 12),
        )
        self._status_label.grid(row=row2, column=0, columnspan=2, sticky="w", **pad)
        row2 += 1
        self._result_var = ctk.StringVar(value="")
        self._result_label = ctk.CTkLabel(
            card2,
            textvariable=self._result_var,
            anchor="w",
            wraplength=420,
            font=(CTK_FONT_FAMILY, 12),
            text_color=COLOR_TEXT_TITLE,
        )
        self._result_label.grid(row=row2, column=0, columnspan=2, sticky="w", **pad)
        row2 += 1
        self._log_text = ctk.CTkTextbox(card2, height=72, font=(CTK_FONT_FAMILY, 11), state="disabled", wrap="word")
        self._log_text.grid(row=row2, column=0, columnspan=2, sticky="nsew", **pad)
        row2 += 1
        card2.columnconfigure(0, weight=1)
        card2.rowconfigure(row2 - 1, weight=1)

        # FFmpeg check (bundled or PATH)
        if not get_ffmpeg_path():
            self._status_var.set("FFmpeg not found. Please install FFmpeg.")
            self._process_btn.configure(
                state="disabled",
                fg_color=COLOR_BUTTON_DISABLED_BG,
                text_color=COLOR_BUTTON_DISABLED_TEXT,
            )

    def _bring_to_front(self):
        """Raise window and focus (helps when launched from Finder)."""
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _browse(self):
        path = ctk.filedialog.askopenfilename(
            title="Select video file",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.input_path = Path(path)
            self._path_var.set(self.input_path.name)
            self._result_var.set("")
            self._progress_var.set(0.0)
            self._status_var.set("")

    def _process(self):
        if self._processing:
            return
        if not self.input_path or not self.input_path.is_file():
            self._status_var.set("Please select a video file first.")
            return
        try:
            top_bezel_px = int(self._top_bezel_var.get().strip())
            bottom_bezel_px = int(self._bottom_bezel_var.get().strip())
        except ValueError:
            self._status_var.set("Top and bottom bezel must be numbers (e.g. 16, 21).")
            return
        if top_bezel_px < 0 or bottom_bezel_px < 0 or top_bezel_px + bottom_bezel_px > 1000:
            self._status_var.set("Bezel values must be >= 0 and their sum < 1000.")
            return

        target_size_mb = None
        choice = self._target_size_var.get().strip()
        if choice == "100 MB":
            target_size_mb = 100.0
        elif choice == "200 MB":
            target_size_mb = 200.0
        elif choice == "500 MB":
            target_size_mb = 500.0
        # "Best quality" -> None

        out = output_path(self.input_path)
        self._processing = True
        self._process_btn.configure(
            state="disabled",
            fg_color=COLOR_BUTTON_DISABLED_BG,
            text_color=COLOR_BUTTON_DISABLED_TEXT,
        )
        self._progress_var.set(0.0)
        self._status_var.set("Starting...")
        self._result_var.set("")
        self._last_log_message = None
        try:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", "end")
            self._log_text.configure(state="disabled")
        except Exception:
            pass
        self._append_log("Starting…")

        def progress_callback(percent: float, message: str):
            self.after(0, lambda p=percent, m=message: self._update_progress(p, m))

        ffmpeg_path = get_ffmpeg_path()

        def run_safe():
            err = None
            res = None
            try:
                res = run_bezel_removal(
                    self.input_path,
                    output_path_arg=out,
                    top_bezel_px=top_bezel_px,
                    bottom_bezel_px=bottom_bezel_px,
                    target_size_mb=target_size_mb,
                    ffmpeg_path=ffmpeg_path,
                    progress_callback=progress_callback,
                )
            except Exception as e:
                err = e
            self.after(0, lambda r=res, e=err: self._finish(result=r, error=e))

        threading.Thread(target=run_safe, daemon=True).start()

    def _append_log(self, line: str):
        if not line:
            return
        try:
            self._log_text.configure(state="normal")
            self._log_text.insert("end", line.rstrip() + "\n")
            self._log_text.see("end")
            self._log_text.configure(state="disabled")
        except Exception:
            pass

    def _update_progress(self, percent: float, message: str):
        self._progress_var.set(percent / 100.0)
        # Status line: message and percent when meaningful
        if percent is not None and 0 < percent < 100:
            self._status_var.set(f"{message}  {round(percent)}%")
        else:
            self._status_var.set(message)
        # Log: append when message changes (avoid duplicate lines for every %)
        if message != self._last_log_message:
            self._last_log_message = message
            self._append_log(message)

    def _finish(self, result=None, error=None):
        self._processing = False
        self._process_btn.configure(
            state="normal",
            fg_color=COLOR_PRIMARY,
            text_color="white",
        )
        if error:
            msg = str(error)
            # Only show generic message for the specific "no binary" error; show real error otherwise
            if "FFmpeg not found. Please install FFmpeg" in msg:
                msg = "FFmpeg is not installed or not in PATH. Please install FFmpeg."
            elif "Input video must be" in msg and "This video is" in msg:
                msg = msg  # Keep exact message: "Input video must be 8640×3840. This video is W×H."
            elif "FileNotFoundError" in type(error).__name__:
                msg = "Could not find the video file. Is the path correct?"
            elif "FFmpeg pass" in msg and "failed" in msg:
                msg = "Encoding failed. " + msg
            else:
                msg = "Something went wrong. " + msg
            self._status_var.set("Error")
            self._result_var.set(msg)
            self._result_label.configure(text_color="#C53030")
            self._append_log("Error.")
            self._append_log(msg)
        else:
            self._progress_var.set(1.0)
            self._status_var.set("Done.")
            out_name = Path(result).name if result else "video"
            self._result_var.set(f"Saved as: {out_name}")
            self._result_label.configure(text_color="#2D7D46")
            self._append_log("Done.")
            self._append_log(f"Saved as: {out_name}")


def main():
    try:
        app = BezelRemoverApp()
        app.mainloop()
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            tk.messagebox.showerror("Bezel Remover Error", str(e))
            root.destroy()
        except Exception:
            pass
        print(err, file=__import__("sys").stderr)
        raise


if __name__ == "__main__":
    main()
