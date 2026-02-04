# Bezel Remover for Videowall

Removes the pixels that fall in the physical bezel gaps of a 4-panel videowall (4× portrait panels: 2160×3840 each, horizontal row = 8640×3840). **Input layout is auto-detected:** wide input (e.g. 8640×3840) is treated as 4 vertical strips side-by-side; tall input (e.g. 3840×8640) is treated as 4 horizontal bands top-to-bottom, each band rotated 90° CCW for portrait. Output: one continuous video with bezel areas cropped out, saved next to the original with `_bezel_removed` in the name.

## For non-technical users (desktop app)

1. **Install Python** (if not already installed): [python.org/downloads](https://www.python.org/downloads/) — use Python 3.10 or newer.
2. **On macOS with Homebrew:** install Tk so the GUI works: `brew install python-tk@3.13` (use the version that matches your Python, e.g. `python-tk@3.12` for Python 3.12).
3. **Install FFmpeg**: [ffmpeg.org/download](https://ffmpeg.org/download.html) — make sure it’s on your PATH so the app can find it.
4. **Install the app** (one time, using a virtual environment so you don’t hit “externally managed” errors on macOS):
   - Open a terminal in this folder (`videowall`) and run:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
5. **Run the app** (each time, from the same folder):
   ```bash
   source .venv/bin/activate
   python app.py
   ```
   Or in one line: `source .venv/bin/activate && python app.py`

In the app:

- Click **Browse** and select your video (any resolution; it’s split into 4 strips at that resolution, bezel cropped, then reassembled).
- Leave **Top bezel** and **Bottom bezel** (e.g. 16 and 21 px for 16mm/21mm; portrait row: top = left edge, bottom = right edge) (or change it if you’ve measured your bezels).
- Click **Remove bezels and save**.
- When it’s done, the new video appears in the same folder as the original, with `_bezel_removed` in the filename.

## For developers / command line

- Core logic: `bezel_processor.run(input_path, output_path, top_bezel_px=16, bottom_bezel_px=21)`.
- See `DESIGN.md` for UX and wrapper design.
- **Input layout:** If width ≥ height (e.g. 8640×3840), panels are 4 vertical strips; if height > width (e.g. 3840×8640), panels are 4 horizontal bands, each rotated 90° CCW. Bezel: top = left edge of strip, bottom = right edge. Output width: `4 × (panel_width - top_bezel_px - bottom_bezel_px)` (e.g. 8492 for 16+21).

## Distributing to end users

You have three main options:

### Option 1: Standalone app (PyInstaller) — best for “double-click and run”

Users get a single app (`.app` on macOS, `.exe` on Windows). They do **not** need to install Python or use the terminal. They **do** need FFmpeg installed on their machine (or you bundle it; see below).

**Build (on your machine, once per OS):**

```bash
source .venv/bin/activate
pip install pyinstaller
# Self-contained (FFmpeg inside): put ffmpeg/ffprobe in extra/ffmpeg_macos or extra/ffmpeg_win, then:
pyinstaller BezelRemover.spec
# Or without bundling FFmpeg:
pyinstaller --windowed --name "Bezel Remover" app.py
```

Output: `dist/Bezel Remover.app` (macOS) or `dist/Bezel Remover.exe` (Windows). Share that folder (or zip it). On macOS, users can move the app to Applications; on Windows, they run the .exe.

- **One-file variant:** add `--onefile` so you get a single executable (slower to start, no extra folder).
- **Each OS needs its own build:** build on macOS for Mac users, on Windows for Windows users.

**Self-contained (FFmpeg inside the app):** You can bundle FFmpeg so users don't install anything. Put FFmpeg binaries in **`extra/ffmpeg_macos/`** (Mac) or **`extra/ffmpeg_win/`** (Windows), then run **`pyinstaller BezelRemover.spec`**. See **PACKAGING.md** for exact steps and download links. Otherwise:
- Tell users to install FFmpeg (e.g. [ffmpeg.org](https://ffmpeg.org/download.html) or `brew install ffmpeg` on Mac) and add it to PATH, or
- (Or bundle FFmpeg—see PACKAGING.md.)

### Option 2: Share the project folder + run script

Give users the whole `videowall` folder (or a zip). Include a short **run** script so they don’t have to remember commands.

**On macOS:** create `run.command` in the project:

```bash
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || { python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt; }
python app.py
```

Make it executable (`chmod +x run.command`). Users double-click `run.command`; first time it creates the venv and installs deps. They still need Python and FFmpeg (and on Mac, `python-tk`) installed.

**On Windows:** create `run.bat` that does the equivalent (e.g. `python -m venv .venv`, `call .venv\Scripts\activate`, `pip install -r requirements.txt`, `python app.py`).

### Option 3: Installer (advanced)

Use an installer builder (e.g. Inno Setup on Windows, or a .pkg on macOS) to install Python + venv + FFmpeg + the app and add a desktop/Start Menu shortcut. Best if you control the machines or need a “corporate” install; more work to set up and maintain.

---

**Summary:** For non-technical users, **Option 1 (PyInstaller)** plus clear instructions to install FFmpeg (or a build that bundles FFmpeg) gives the smoothest experience. **Option 2** is simpler for you (no build step) but requires users to have Python and FFmpeg already installed.
