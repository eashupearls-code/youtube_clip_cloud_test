
import os
import streamlit as st
from youtube_clip_plan_c import extract_clip
from runtime_setup import ensure_runtime

st.set_page_config(page_title="YouTube Clip Extractor", page_icon="🎬", layout="centered")

st.title("🎬 YouTube Clip Extractor")
st.caption("Plan C — HLS segment extraction. Downloads only the HLS segments covering the requested time range.")

with st.expander("Runtime diagnostics", expanded=False):
    try:
        diag = ensure_runtime()
        st.code(
            f"Deno: {diag['deno']}\n"
            f"FFmpeg: {diag['ffmpeg']}\n"
            f"yt-dlp: {diag['yt_dlp']}"
        )
    except Exception as e:
        st.error(f"Runtime check failed: {e}")

url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

c1, c2 = st.columns(2)
with c1:
    start = st.text_input("Start time", value="00:00")
with c2:
    end = st.text_input("End time", value="00:15")

quality = st.selectbox(
    "Quality",
    ["1080p", "720p", "480p", "360p"],
    index=0,
)

extract = st.button("🎬 Extract Clip", type="primary", use_container_width=True)

if extract:
    if not url.strip():
        st.error("Please enter a YouTube URL.")
        st.stop()

    with st.status("Preparing clip...", expanded=True) as status:
        try:
            result = extract_clip(
                url=url.strip(),
                start_text=start.strip(),
                end_text=end.strip(),
                quality=quality,
                log=st.write,
            )

            status.update(label="Clip ready!", state="complete")

            st.success(
                f"Created {result['duration']:.2f}s clip at "
                f"{result['width']}×{result['height']}."
            )

            st.video(result["path"])

            with open(result["path"], "rb") as f:
                data = f.read()

            st.download_button(
                "⬇️ Download MP4",
                data=data,
                file_name=result["filename"],
                mime="video/mp4",
                use_container_width=True,
            )

            st.caption(
                f"Downloaded HLS media: {result['downloaded_mb']:.2f} MB | "
                f"Output: {result['output_mb']:.2f} MB"
            )

        except Exception as e:
            status.update(label="Extraction failed", state="error")
            st.exception(e)
