"""
Bezel removal for 4-panel videowall (portrait: 2160×3840 per panel, horizontal row = 8640×3840).
Supports two input layouts:
- Horizontal composite (8640×3840): panels are vertical strips side-by-side; split by width.
- Vertical stack (3840×8640): panels are horizontal bands top-to-bottom; split by height, rotate each band 90° CCW, then crop/hstack.
Uses two-pass H.264 encoding: high422, yuv422p10le, 10000k, tune animation.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union


# Expected input size: 4 panels × 2160 wide, 3840 tall
INPUT_WIDTH = 8640
INPUT_HEIGHT = 3840
PANEL_WIDTH = 2160
PANEL_COUNT = 4

# Output size: same aspect ratio as destination desktop (8640×3840) so it fills correctly
OUTPUT_WIDTH = 4320
OUTPUT_HEIGHT = 1920  # 4320/1920 = 8640/3840 = 2.25

# Two-pass encode settings (videowall-quality)
ENCODE_PIX_FMT = "yuv422p10le"
ENCODE_PROFILE = "high422"
ENCODE_LEVEL = "5.2"
ENCODE_PRESET = "medium"
ENCODE_BITRATE = "10000k"
ENCODE_BITRATE_MIN_K = 1000
ENCODE_BITRATE_MAX_K = 50000
ENCODE_TUNE = "animation"
AUDIO_BITRATE = "160k"
AUDIO_CHANNELS = 2


def video_bitrate_for_target_size_mb(target_size_mb: float, duration_sec: float) -> str:
    """
    Compute video bitrate (e.g. "5000k") so total file size stays at or under target_size_mb,
    given duration_sec. Reserves space for audio (160 kbps). Clamped to ENCODE_BITRATE_MIN/MAX.
    """
    if duration_sec <= 0:
        return ENCODE_BITRATE
    target_bits = target_size_mb * 8 * 1024 * 1024
    audio_bits = 160 * 1000 * duration_sec  # 160 kbps
    video_bps = (target_bits - audio_bits) / duration_sec
    video_kbps = int(round(video_bps / 1000))
    video_kbps = max(ENCODE_BITRATE_MIN_K, min(ENCODE_BITRATE_MAX_K, video_kbps))
    return f"{video_kbps}k"


def find_ffmpeg() -> Optional[str]:
    """Return path to ffmpeg binary (PATH only), or None if not found."""
    return shutil.which("ffmpeg")


def get_ffmpeg_path() -> Optional[str]:
    """
    Return path to ffmpeg for use by the app.
    When running as a PyInstaller bundle, looks in the bundle's bin/ first
    (.app Contents/Frameworks/bin or sys._MEIPASS/bin). Otherwise uses PATH (find_ffmpeg).
    """
    def _check_base(base: Path) -> Optional[str]:
        if not base.exists():
            return None
        if sys.platform == "win32":
            for name in ("ffmpeg.exe", "ffmpeg"):
                p = base / name
                if p.is_file():
                    return str(p.resolve())
        else:
            p = base / "ffmpeg"
            if p.is_file():
                return str(p.resolve())
        return None

    if getattr(sys, "frozen", False):
        _debug_lines: list[str] = []
        _debug_lines.append(f"frozen=True platform={sys.platform!r} executable={getattr(sys, 'executable', None)!r}")

        # macOS .app: executable is Contents/MacOS/AppName; FFmpeg is in Contents/Frameworks/bin
        if sys.platform == "darwin":
            # Prefer actual executable path (macOS API) in case sys.executable differs when launched from Finder
            exe_path: Optional[Path] = None
            try:
                import ctypes
                buf = ctypes.create_string_buffer(1024)
                bufsize = ctypes.c_uint(1024)
                if hasattr(ctypes, "CDLL"):
                    libc = ctypes.CDLL("/usr/lib/libc.dylib")
                    if hasattr(libc, "_NSGetExecutablePath"):
                        libc._NSGetExecutablePath(buf, ctypes.byref(bufsize))
                        exe_path = Path(buf.value.decode("utf-8")).resolve()
            except Exception as e:
                _debug_lines.append(f"_NSGetExecutablePath error: {e}")
            if exe_path is None and getattr(sys, "executable", None):
                try:
                    exe_path = Path(sys.executable).resolve()
                except Exception:
                    pass
            if exe_path:
                try:
                    contents = exe_path.parent.parent  # .../Contents
                    _debug_lines.append(f"exe_path={exe_path!r} exists={exe_path.exists()}")
                    _debug_lines.append(f"contents={contents!r} exists={contents.exists()}")
                    for rel in ("Frameworks/bin", "Frameworks/Bezel Remover/bin", "Resources/bin"):
                        candidate = contents / rel
                        r = _check_base(candidate)
                        _debug_lines.append(f"  {rel}: exists={candidate.exists()}, ffmpeg found={r is not None}")
                        if r:
                            return r
                except Exception as e:
                    _debug_lines.append(f"darwin lookup error: {e}")
        if hasattr(sys, "_MEIPASS"):
            meipass = Path(sys._MEIPASS)
            _debug_lines.append(f"sys._MEIPASS={sys._MEIPASS!r} exists={meipass.exists()}")
            for base in (meipass / "bin", meipass.parent / "bin"):
                r = _check_base(base)
                _debug_lines.append(f"  _MEIPASS base {base}: exists={base.exists()}, ffmpeg found={r is not None}")
                if r:
                    return r
        # Write debug to /tmp and to user Logs (so we can see lookup result)
        for log_path in (Path("/tmp/bezel_ffmpeg_debug.txt"), Path.home() / "Library" / "Logs" / "Bezel Remover.log"):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n[FFmpeg lookup]\n")
                    for line in _debug_lines:
                        f.write(line + "\n")
                    f.write("-> bundled lookup failed, using find_ffmpeg()\n")
            except Exception:
                pass
    result = find_ffmpeg()
    if getattr(sys, "frozen", False) and result:
        for log_path in (Path("/tmp/bezel_ffmpeg_debug.txt"), Path.home() / "Library" / "Logs" / "Bezel Remover.log"):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"-> found via PATH: {result}\n")
            except Exception:
                pass
    return result


def find_ffprobe() -> Optional[str]:
    """Return path to ffprobe binary, or None if not found."""
    return shutil.which("ffprobe")


def get_duration_seconds(input_path: Union[str, Path], ffprobe_path: Optional[str] = None) -> Optional[float]:
    """Get video duration in seconds via ffprobe. Returns None if unavailable."""
    ffprobe = ffprobe_path or find_ffprobe()
    if not ffprobe:
        return None
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        pass
    return None


def get_video_size(input_path: Union[str, Path], ffprobe_path: Optional[str] = None) -> Optional[tuple[int, int]]:
    """Get (width, height) of first video stream via ffprobe. Returns None if unavailable."""
    ffprobe = ffprobe_path or find_ffprobe()
    if not ffprobe:
        return None
    cmd = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        str(input_path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            parts = out.stdout.strip().split(",")
            if len(parts) >= 2:
                return (int(parts[0]), int(parts[1]))
    except (subprocess.SubprocessError, ValueError):
        pass
    return None


def build_filter_horizontal(top_bezel_px: int, bottom_bezel_px: int) -> str:
    """
    Input is horizontal composite: 8640×3840 (4 panels side-by-side).
    Split into 4 vertical strips (each 2160×3840), crop bezel from left/right of each, hstack.
    Mapping: leftmost strip → Display 1, next → Display 2, next → Display 3, rightmost → Display 4
    (one continuous stream left-to-right across the row). Portrait: top bezel = left edge of strip,
    bottom bezel = right edge.
    """
    strip_w_expr = "iw/4"
    crop_h_expr = "ih"
    x_off = top_bezel_px
    # First crop: take 1/4-width strips from source [0:v] (iw/4 × ih).
    # Second crop: remove bezel from each strip; input is [a1] so its width is already the strip width → use iw - top - bottom
    strip_bezel_w = f"iw-{top_bezel_px}-{bottom_bezel_px}"
    parts = [
        f"[0:v]crop={strip_w_expr}:{crop_h_expr}:0:0[a1]",
        f"[0:v]crop={strip_w_expr}:{crop_h_expr}:iw/4:0[a2]",
        f"[0:v]crop={strip_w_expr}:{crop_h_expr}:iw/2:0[a3]",
        f"[0:v]crop={strip_w_expr}:{crop_h_expr}:3*iw/4:0[a4]",
        f"[a1]crop={strip_bezel_w}:{crop_h_expr}:{x_off}:0[b1]",
        f"[a2]crop={strip_bezel_w}:{crop_h_expr}:{x_off}:0[b2]",
        f"[a3]crop={strip_bezel_w}:{crop_h_expr}:{x_off}:0[b3]",
        f"[a4]crop={strip_bezel_w}:{crop_h_expr}:{x_off}:0[b4]",
        "[b1][b2][b3][b4]hstack=inputs=4[v0]",
        f"[v0]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:flags=lanczos[v]",
    ]
    return ";".join(parts)


def build_filter_vertical(top_bezel_px: int, bottom_bezel_px: int) -> str:
    """
    Input is vertical stack: 3840×8640 (4 panels as horizontal bands top-to-bottom).
    Each band is 3840×2160 (landscape). Rotate each 90° CCW → 2160×3840 (portrait),
    crop bezel from left/right of each, hstack.
    Portrait: top bezel = left edge of strip, bottom bezel = right edge.
    """
    # Band size: full width iw, height ih/4
    band_w_expr = "iw"
    band_h_expr = "ih/4"
    # After transpose=2 (90° CCW), frame is 2160×3840; crop left/right bezel
    crop_w_expr = f"iw-{top_bezel_px}-{bottom_bezel_px}"
    crop_h_expr = "ih"
    x_off = top_bezel_px
    parts = [
        f"[0:v]crop={band_w_expr}:{band_h_expr}:0:0[a1]",
        f"[0:v]crop={band_w_expr}:{band_h_expr}:0:ih/4[a2]",
        f"[0:v]crop={band_w_expr}:{band_h_expr}:0:ih/2[a3]",
        f"[0:v]crop={band_w_expr}:{band_h_expr}:0:3*ih/4[a4]",
        "[a1]transpose=2[a1r]",  # 90° CCW: 3840×2160 → 2160×3840
        "[a2]transpose=2[a2r]",
        "[a3]transpose=2[a3r]",
        "[a4]transpose=2[a4r]",
        f"[a1r]crop={crop_w_expr}:{crop_h_expr}:{x_off}:0[b1]",
        f"[a2r]crop={crop_w_expr}:{crop_h_expr}:{x_off}:0[b2]",
        f"[a3r]crop={crop_w_expr}:{crop_h_expr}:{x_off}:0[b3]",
        f"[a4r]crop={crop_w_expr}:{crop_h_expr}:{x_off}:0[b4]",
        "[b1][b2][b3][b4]hstack=inputs=4[v0]",
        f"[v0]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:flags=lanczos[v]",
    ]
    return ";".join(parts)


def output_path(input_path: Union[str, Path], output_dir: Optional[Union[str, Path]] = None) -> Path:
    """Suggested output path: same dir as input, suffix _bezel_removed."""
    p = Path(input_path).resolve()
    parent = Path(output_dir).resolve() if output_dir else p.parent
    stem = p.stem
    suffix = p.suffix or ".mp4"
    return parent / f"{stem}_bezel_removed{suffix}"


def _run_ffmpeg_pass(
    ffmpeg: str,
    input_path: Path,
    filter_complex: str,
    out_path: Optional[Path],
    pass_num: int,
    duration_sec: Optional[float],
    progress_callback: Optional[callable],
    pass_weight: float = 1.0,
    pass_offset: float = 0.0,
    passlogfile_prefix: Optional[str] = None,
    video_bitrate: Optional[str] = None,
) -> None:
    """Run one FFmpeg pass (1 or 2). video_bitrate overrides ENCODE_BITRATE when set (e.g. from target file size)."""
    b_v = video_bitrate if video_bitrate else ENCODE_BITRATE
    common = [
        ffmpeg,
        "-y",
        "-i", str(input_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-s", f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}",
        "-c:v", "libx264",
        "-pix_fmt", ENCODE_PIX_FMT,
        "-preset", ENCODE_PRESET,
        "-profile:v", ENCODE_PROFILE,
        "-level", ENCODE_LEVEL,
        "-tune", ENCODE_TUNE,
        "-b:v", b_v,
        "-pass", str(pass_num),
        "-progress", "pipe:1",
        "-nostats",
        "-hide_banner",
        "-loglevel", "error",
    ]
    if passlogfile_prefix is not None:
        common.extend(["-passlogfile", passlogfile_prefix])
    if pass_num == 1:
        cmd = common + ["-an", "-f", "null", "-"]
    else:
        cmd = common + [
            "-map", "0:a?",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
            "-ac", str(AUDIO_CHANNELS),
            "-movflags", "+faststart",
            str(out_path),
        ]

    def parse_progress(line: str) -> Optional[float]:
        m = re.search(r"out_time_ms=(\d+)", line)
        if m:
            return int(m.group(1)) / 1_000_000.0
        return None

    last_percent = 0.0
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        line = line.strip()
        if not line:
            continue
        dur = duration_sec
        if dur is None:
            dm = re.search(r"duration=([\d.]+)", line)
            if dm:
                dur = float(dm.group(1))
        out_sec = parse_progress(line)
        if progress_callback and dur and dur > 0 and out_sec is not None:
            p = min(1.0, out_sec / dur)
            percent = pass_offset + p * pass_weight * 100.0
            if percent >= last_percent:
                progress_callback(min(100.0, percent), "Pass 1..." if pass_num == 1 else "Pass 2 (final)...")
                last_percent = percent

    if proc.returncode != 0:
        err = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"FFmpeg pass {pass_num} failed (code {proc.returncode}). {err.strip() or 'No details.'}")


def run(
    input_path: Union[str, Path],
    output_path_arg: Optional[Union[str, Path]] = None,
    top_bezel_px: int = 16,
    bottom_bezel_px: int = 21,
    target_size_mb: Optional[float] = None,
    ffmpeg_path: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> Path:
    """
    Run bezel removal: map input to 4 portrait panels, crop bezels, hstack, scale to 4320×1920 (same aspect as destination 8640×3840), then two-pass H.264 encode.
    If target_size_mb is set (e.g. 200), video bitrate is chosen so the output file stays at or under that size.
    Output fills 8640×3840 desktop correctly. Input layout is auto-detected:
    - Horizontal composite (width ≥ height, e.g. 8640×3840): 4 vertical strips → panels left to right.
    - Vertical stack (height > width, e.g. 3840×8640): 4 horizontal bands → rotate each 90° CCW → panels left to right.
    Portrait: top bezel = left edge of strip, bottom bezel = right edge (px).
    progress_callback(percent: float, message: str) is called with 0.0–100.0 and status.
    Returns path to the output file.
    """
    input_path = Path(input_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    out = Path(output_path_arg).resolve() if output_path_arg else output_path(input_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = ffmpeg_path or get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and add it to your PATH.")

    if top_bezel_px < 0 or bottom_bezel_px < 0:
        raise ValueError("top_bezel_px and bottom_bezel_px must be >= 0")
    if top_bezel_px + bottom_bezel_px >= PANEL_WIDTH:
        raise ValueError(f"top_bezel_px + bottom_bezel_px must be < {PANEL_WIDTH}")

    ffprobe_path = None
    if ffmpeg_path:
        parent = Path(ffmpeg_path).parent
        ffprobe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
        ffprobe_path = str(parent / ffprobe_name)

    # Choose filter by input layout: horizontal composite (8640×3840) vs vertical stack (3840×8640).
    # Panels: portrait 2160×3840 each; horizontal row = 8640×3840.
    size = get_video_size(input_path, ffprobe_path=ffprobe_path)
    if size and size[1] > size[0]:
        # Tall input → vertical stack: 4 bands (3840×2160), rotate each 90° CCW, crop, hstack
        filter_complex = build_filter_vertical(top_bezel_px, bottom_bezel_px)
    else:
        # Wide or square input → horizontal composite: 4 vertical strips, crop, hstack
        filter_complex = build_filter_horizontal(top_bezel_px, bottom_bezel_px)

    duration_sec = get_duration_seconds(input_path, ffprobe_path=ffprobe_path)

    # Video bitrate: from target file size (if set) or default
    video_bitrate: Optional[str] = None
    if target_size_mb is not None and target_size_mb > 0 and duration_sec and duration_sec > 0:
        video_bitrate = video_bitrate_for_target_size_mb(target_size_mb, duration_sec)

    # Two-pass encode: shared passlogfile in output dir (cleaned up after)
    passlog_prefix = str(out.parent / (out.stem + "_2pass"))

    if progress_callback:
        if size:
            progress_callback(0.0, f"Input: {size[0]}×{size[1]} → Output: {OUTPUT_WIDTH}×{OUTPUT_HEIGHT}")
        progress_callback(0.0, "Pass 1 (analysis)...")

    _run_ffmpeg_pass(
        ffmpeg,
        input_path,
        filter_complex,
        out_path=None,
        pass_num=1,
        duration_sec=duration_sec,
        progress_callback=progress_callback,
        pass_weight=0.5,
        pass_offset=0.0,
        passlogfile_prefix=passlog_prefix,
        video_bitrate=video_bitrate,
    )

    if progress_callback:
        progress_callback(50.0, "Pass 2 (final encode)...")

    try:
        _run_ffmpeg_pass(
            ffmpeg,
            input_path,
            filter_complex,
            out_path=out,
            pass_num=2,
            duration_sec=duration_sec,
            progress_callback=progress_callback,
            pass_weight=0.5,
            pass_offset=50.0,
            passlogfile_prefix=passlog_prefix,
            video_bitrate=video_bitrate,
        )
    finally:
        # Remove two-pass log files
        for f in out.parent.glob(out.stem + "_2pass*.log*"):
            try:
                f.unlink()
            except OSError:
                pass

    if progress_callback:
        progress_callback(100.0, "Done.")

    return out
