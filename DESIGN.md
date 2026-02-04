# Bezel Remover — User-Friendly Wrapper Design

## Goal

Non-technical users need to:
1. Pick a video file (8640×3840).
2. Optionally set how much to remove (bezel width) or use a sensible default.
3. Click one button to process.
4. Get a new video file in the same folder, with no command line or FFmpeg knowledge.

---

## Wrapper Approach: Desktop App (Recommended)

| Approach | Pros | Cons |
|----------|------|------|
| **Desktop app (Python + GUI)** | Drag-and-drop, progress bar, works offline, single .exe/.app possible | Requires building/packaging for each OS |
| Web app (local server) | Familiar browser UI | User must "open a page" and keep it open; more moving parts |
| Simple script + batch/shortcut | No extra UI code | Still exposes paths, errors, terminal |
| Installer that adds "Right-click → Bezel remove" | Feels native | Complex to implement; still need a UI for options |

**Choice: Desktop app** — One window, "Select video" → "Remove bezels" → "Done." Easiest to explain and support.

---

## UX Principles for Non-Technical Users

1. **One main action** — One clear "Process" or "Remove bezels" button. No modes or tabs unless necessary.
2. **Sensible defaults** — Bezel width pre-filled (e.g. 30 px). Advanced options hidden or in a "More options" section.
3. **No paths** — User picks input file via file picker; output goes to same folder with a clear name (e.g. `original_name_bezel_removed.mp4`).
4. **Visible progress** — Progress bar or "Step X of Y" so users know it’s working and not stuck.
5. **Plain-language messages** — "Video ready: filename.mp4" instead of "Process completed (0)."
6. **Errors in plain language** — "Couldn't open the video. Is it a supported format?" with optional "Details" for support.
7. **FFmpeg invisible** — No mention of FFmpeg in the UI; bundle or detect it and show one-time setup if needed.

---

## Suggested UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Bezel Remover for Videowall                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Video file:  [________________________] [Browse...]       │
│                                                             │
│  Bezel width (pixels):  [ 30 ]   (default is fine for most) │
│                                                             │
│  [        Remove bezels and save        ]                   │
│                                                             │
│  Progress:  [████████████░░░░░░░░] 45%                      │
│  Status: Encoding...                                         │
│                                                             │
│  ✓ Done. Saved as: video_bezel_removed.mp4                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- **Browse** opens a file picker (filter: video files).
- **Bezel width** has a default (e.g. 30); optional "What’s this?" tooltip or short help.
- **Process** runs the pipeline and disables the button until finished.
- **Progress** updates from FFmpeg (parsed from stderr or -progress pipe).
- **Result** shows the output filename and path (e.g. click to reveal in folder).

---

## Technical Wrapper Choices

- **Language/framework:** Python 3 + CustomTkinter for a modern look and good defaults on Windows/macOS/Linux.
- **Distribution:** 
  - **Option A:** `pyinstaller` (or similar) to build a single executable so users don’t install Python or FFmpeg.
  - **Option B:** Installer that installs Python + deps + FFmpeg and adds a shortcut to the GUI (better if you control the machines).
- **FFmpeg:** Bundled with the app (in a subfolder) when building the executable, or installed system-wide and detected at startup; show a clear message if missing ("Bezel Remover needs a small helper program. Install it from …").

---

## Optional Enhancements (Later)

- **Drag-and-drop** — Drop a video file onto the window to set the input.
- **Preset:** "Sony 75\" portrait ×4" that locks resolution and default bezel.
- **Batch:** "Add folder" → process all 8640×3840 videos in that folder.
- **Preview:** One frame before/after crop (optional, for power users).

---

## Summary

- **Best way to wrap the tool for non-technical users:** a **desktop app** with a simple window: choose file, optional bezel width, one "Remove bezels" button, progress bar, and a clear "Done — saved as …" message.
- **Implementation:** Python + CustomTkinter + a small core module that runs the FFmpeg split/crop/reassemble pipeline and reports progress.
- **Distribution:** Single executable (e.g. PyInstaller) with FFmpeg bundled, or an installer that installs Python + FFmpeg and runs the GUI script.
