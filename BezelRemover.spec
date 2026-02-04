# PyInstaller spec for Bezel Remover (self-contained with bundled FFmpeg).
# Build on macOS: pyinstaller BezelRemover.spec  -> dist/Bezel Remover.app
# Build on Windows: pyinstaller BezelRemover.spec -> dist/Bezel Remover/
#
# Before building: put FFmpeg binaries in extra/ffmpeg_macos/ or extra/ffmpeg_win/
# See PACKAGING.md for download links and exact paths.

import sys
from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.building.osx import BUNDLE

# Bundle FFmpeg for this platform (binaries go to sys._MEIPASS/bin at runtime).
# datas expects (source_dir, target_dir) tuples; files from source_dir are copied into target_dir.
if sys.platform == "darwin":
    ffmpeg_datas = [("extra/ffmpeg_macos", "bin")]
elif sys.platform == "win32":
    ffmpeg_datas = [("extra/ffmpeg_win", "bin")]
else:
    ffmpeg_datas = []

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=ffmpeg_datas,
    hiddenimports=["customtkinter", "PIL", "darkdetect", "packaging"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# One-folder build: EXE gets only scripts; COLLECT bundles binaries + datas (incl. FFmpeg)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Bezel Remover",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No terminal window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Bezel Remover",
)

# On macOS, wrap COLLECT in a .app bundle (icon from extra/icon.icns)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Bezel Remover.app",
        icon="extra/icon.icns",
        bundle_identifier=None,
    )
