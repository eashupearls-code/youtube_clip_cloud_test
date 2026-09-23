import os, platform, shutil, subprocess, urllib.request, zipfile
from pathlib import Path
DENO_VERSION="2.9.7"
BASE=Path(__file__).resolve().parent
DENO_DIR=BASE/".runtime"/"deno"
DENO_BIN=DENO_DIR/"deno"

def version(cmd):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
        if p.returncode==0: return (p.stdout or p.stderr).strip().splitlines()[0]
    except Exception: pass
    return "not available"

def ensure_deno():
    existing=shutil.which("deno")
    if existing: return Path(existing)
    if platform.system().lower()!="linux" or platform.machine().lower() not in ("x86_64","amd64"):
        raise RuntimeError("Automatic Deno bootstrap expects Linux x86_64 on Streamlit Cloud.")
    DENO_DIR.mkdir(parents=True,exist_ok=True)
    if not DENO_BIN.exists():
        archive=DENO_DIR/"deno.zip"
        url=f"https://github.com/denoland/deno/releases/download/v{DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip"
        urllib.request.urlretrieve(url,archive)
        with zipfile.ZipFile(archive) as z: z.extractall(DENO_DIR)
        archive.unlink(missing_ok=True)
        DENO_BIN.chmod(0o755)
    return DENO_BIN

def ensure_runtime():
    deno=ensure_deno()
    os.environ["PATH"]=str(deno.parent)+os.pathsep+os.environ.get("PATH","")
    import yt_dlp
    return {"deno_version":version([str(deno),"--version"]),
            "ffmpeg_version":version(["ffmpeg","-version"]),
            "yt_dlp_version":yt_dlp.version.__version__}
