
import os
import platform
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path


DENO_VERSION = "2.9.7"


def _first_line(command):
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        lines = result.stdout.strip().splitlines()
        return lines[0] if lines else "unknown"
    except Exception as e:
        return f"unavailable: {e}"


def ensure_deno():
    existing = shutil.which("deno")
    if existing:
        return existing

    # Streamlit Cloud runs Linux. Install a self-contained Deno binary
    # into the application directory if it is not already present.
    if platform.system().lower() != "linux":
        return None

    base = Path(".runtime")
    deno_dir = base / "deno"
    deno_bin = deno_dir / "deno"

    if deno_bin.exists():
        os.environ["PATH"] = str(deno_dir) + os.pathsep + os.environ.get("PATH", "")
        return str(deno_bin)

    base.mkdir(parents=True, exist_ok=True)

    url = (
        f"https://github.com/denoland/deno/releases/download/"
        f"v{DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip"
    )
    zip_path = base / "deno.zip"

    urllib.request.urlretrieve(url, zip_path)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(deno_dir)

    zip_path.unlink(missing_ok=True)
    deno_bin.chmod(0o755)

    os.environ["PATH"] = str(deno_dir) + os.pathsep + os.environ.get("PATH", "")
    return str(deno_bin)


def ensure_runtime():
    deno_path = ensure_deno()

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg was not found. Make sure packages.txt contains: ffmpeg"
        )

    if not ffprobe:
        raise RuntimeError(
            "ffprobe was not found. It should normally be installed with FFmpeg."
        )

    import yt_dlp

    return {
        "deno": _first_line(["deno", "--version"]) if deno_path else "not found",
        "ffmpeg": _first_line(["ffmpeg", "-version"]),
        "yt_dlp": getattr(yt_dlp, "__version__", "unknown"),
    }
