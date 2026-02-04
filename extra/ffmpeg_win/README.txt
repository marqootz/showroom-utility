Put FFmpeg binaries here before building the Windows app.

Required files (in this folder):
  ffmpeg.exe
  ffprobe.exe

Download:
  - https://www.gyan.dev/ffmpeg/builds/ (e.g. ffmpeg-release-essentials.zip)
  - Extract and copy bin/ffmpeg.exe and bin/ffprobe.exe into this folder

Then run from project root (on Windows):
  pyinstaller BezelRemover.spec

Output: dist/Bezel Remover/
