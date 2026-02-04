Put FFmpeg binaries here before building the macOS app.

Required files (in this folder):
  ffmpeg
  ffprobe

Download:
  - Static build: https://evermeet.cx/ffmpeg/ (get ffmpeg and ffprobe)
  - Or from Homebrew: copy from $(brew --prefix)/bin/ffmpeg and ffprobe

Then run from project root:
  pyinstaller BezelRemover.spec

Output: dist/Bezel Remover.app
