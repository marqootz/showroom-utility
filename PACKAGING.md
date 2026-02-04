# Packaging Bezel Remover (self-contained with FFmpeg)

This app can be built as a **self-contained** bundle (macOS `.app` or Windows folder) with FFmpeg included. End users do not need to install Python or FFmpeg.

## Prerequisites

- Python 3.10+ with venv and dependencies installed (`pip install -r requirements.txt` and `pip install pyinstaller`). If `pyinstaller` isn't on your PATH after installing, use `python -m PyInstaller` instead of `pyinstaller`.
- FFmpeg binaries for the platform you are building on (see below)

## 1. Add FFmpeg to the bundle

The build expects FFmpeg in a platform-specific folder. Put the **binary files** directly in that folder (not in a subfolder).

### macOS

1. Create or use folder: **`extra/ffmpeg_macos/`**
2. Put these files inside it:
   - **`ffmpeg`** (executable, no extension)
   - **`ffprobe`** (executable, no extension)

**Where to get them:**

- **Static build:** [evermeet.cx/ffmpeg](https://evermeet.cx/ffmpeg/) — download the `ffmpeg` and `ffprobe` packages, then copy the binaries from each package into `extra/ffmpeg_macos/`.
- **Homebrew:** Copy from your Homebrew prefix:
  ```bash
  cp $(brew --prefix ffmpeg)/bin/ffmpeg  extra/ffmpeg_macos/
  cp $(brew --prefix ffmpeg)/bin/ffprobe extra/ffmpeg_macos/
  ```

### Windows

1. Create or use folder: **`extra/ffmpeg_win/`**
2. Put these files inside it:
   - **`ffmpeg.exe`**
   - **`ffprobe.exe`**

**Where to get them:**

- [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) — e.g. **ffmpeg-release-essentials.zip**. Extract the archive and copy `bin/ffmpeg.exe` and `bin/ffprobe.exe` into `extra/ffmpeg_win/`.

## 2. Build

**PyInstaller does not cross-compile.** You must build on the OS you are targeting:
- Build **on macOS** → **`dist/Bezel Remover.app`** (and a `dist/Bezel Remover/` folder; the .app is what you distribute).
- Build **on Windows** → **`dist/Bezel Remover/`** with **`Bezel Remover.exe`** inside it (no .app on Windows).

From the project root (with venv activated):

```bash
source .venv/bin/activate   # or on Windows: .venv\Scripts\activate
pyinstaller BezelRemover.spec
```

- **macOS:** Use **`dist/Bezel Remover.app`**. The “Bezel Remover” file inside `dist/Bezel Remover/` is the Unix executable for the one-folder layout; the **.app** is the proper double-clickable app.
- **Windows:** Use **`dist/Bezel Remover/Bezel Remover.exe`**. Zip the whole folder to distribute.

## 3. Verify

Run the built app and use “Browse” to select a test video. If FFmpeg was bundled correctly, “Remove bezels and save” will work without having FFmpeg on the system PATH.

## If the macOS .app doesn't launch

1. **Run from Terminal** to see the error (double-clicking hides it):
   ```bash
   "/path/to/Bezel Remover.app/Contents/MacOS/Bezel Remover"
   ```
   Replace `/path/to` with the actual path (e.g. `~/LOCAL_DEV/videowall/dist/Bezel Remover.app`). Any Python traceback will appear in the terminal.

2. **Gatekeeper (unsigned app):** The first time you open the .app, macOS may block it. Right-click the .app → **Open** → **Open** again to confirm. Or go to **System Settings → Privacy & Security** and allow the app.

3. **Rebuild** after code changes: `pyinstaller -y BezelRemover.spec`

## How bundled FFmpeg is found

At runtime the app checks whether it is running from a PyInstaller bundle (`sys.frozen` and `sys._MEIPASS`). If so, it looks for `ffmpeg` (or `ffmpeg.exe` on Windows) in **`sys._MEIPASS/bin/`**. That directory is populated at build time from `extra/ffmpeg_macos/` or `extra/ffmpeg_win/` via the spec’s `Tree(..., prefix="bin")`. If no bundled binary is found, it falls back to the system PATH.

## One-file build (optional)

For a single executable (e.g. one `.exe` on Windows), you can change the spec to a one-file EXE (include `a.binaries` and `a.datas` in `EXE(...)` and remove `COLLECT`). The same `sys._MEIPASS/bin/` lookup works; FFmpeg is extracted to a temp folder at launch. One-file builds start a bit slower and still need the FFmpeg binaries in `extra/ffmpeg_*` when building.
