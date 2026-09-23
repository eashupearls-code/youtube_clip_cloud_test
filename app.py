import streamlit as st
from pathlib import Path
from runtime_setup import ensure_runtime
from youtube_clip import extract_clip

st.set_page_config(page_title="YouTube Clip Cloud Test", page_icon="🎬", layout="wide")
st.title("🎬 YouTube URL → Exact Clip")
st.caption("Cloud deployment test — Method A (yt-dlp section download)")
st.info("Use only videos you own or are authorized to download/process. This is a separate test project.")

runtime = ensure_runtime()

with st.sidebar:
    st.header("Clip Settings")
    url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
    quality = st.selectbox("Quality", ["Best Available","360p","480p","720p","1080p","1440p","2160p"], index=3)
    start = st.text_input("Start", "00:05:00")
    end = st.text_input("End", "00:05:15")
    st.divider()
    st.caption("Runtime diagnostics")
    st.code(f"Deno: {runtime['deno_version']}\nFFmpeg: {runtime['ffmpeg_version']}\nyt-dlp: {runtime['yt_dlp_version']}")

if st.button("▶ Extract Clip", type="primary", use_container_width=True):
    if not url.strip():
        st.error("Please enter a YouTube URL.")
        st.stop()
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    for old in output_dir.glob("clip_*"):
        try: old.unlink()
        except OSError: pass
    try:
        with st.status("Extracting YouTube section...", expanded=True) as status:
            result = extract_clip(url.strip(), start.strip(), end.strip(), quality, output_dir)
            status.update(label=f"Complete — {result['elapsed_sec']} seconds", state="complete")
        st.success(f"Clip extracted successfully in {result['elapsed_sec']} seconds.")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Source", result["title"][:35] or "Unknown")
        c2.metric("Resolution", result["resolution"])
        c3.metric("Clip", f"{result['duration_sec']:.1f}s")
        c4.metric("Output", f"{result['output_mb']:.2f} MB")
        st.video(result["output"])
        with open(result["output"], "rb") as f:
            st.download_button("⬇ Download MP4", f.read(), Path(result["output"]).name, "video/mp4", use_container_width=True)
        with st.expander("Technical details"):
            st.json(result)
    except Exception as exc:
        st.error("Clip extraction failed.")
        st.exception(exc)
