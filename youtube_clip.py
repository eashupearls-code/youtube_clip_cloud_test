from pathlib import Path
import time
import yt_dlp
from utils import parse_time, quality_selector

def extract_clip(url, start, end, quality, output_dir):
    start_sec=parse_time(start); end_sec=parse_time(end)
    if end_sec <= start_sec: raise ValueError("End time must be greater than start time.")
    output_dir=Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    progress={"downloaded":0}
    def hook(d):
        if d.get("status")=="downloading":
            progress["downloaded"]=max(progress["downloaded"], d.get("downloaded_bytes",0) or 0)
    opts={
        "format":quality_selector(quality),
        "outtmpl":str(output_dir/"clip_%(id)s_%(title).60s.%(ext)s"),
        "merge_output_format":"mp4","noplaylist":True,"quiet":True,"no_warnings":False,
        "progress_hooks":[hook],
        "download_ranges":yt_dlp.utils.download_range_func(None,[(start_sec,end_sec)]),
        "force_keyframes_at_cuts":False,
        "postprocessor_args":["-movflags","+faststart"],
    }
    started=time.perf_counter()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info=ydl.extract_info(url, download=True)
    elapsed=round(time.perf_counter()-started,2)
    vid=info.get("id","video")
    candidates=sorted(output_dir.glob(f"clip_{vid}_*"),key=lambda p:p.stat().st_mtime,reverse=True)
    if not candidates: raise RuntimeError("yt-dlp completed but no output file was found.")
    output=candidates[0]
    return {
        "title":info.get("title",""),"video_id":vid,
        "resolution":f"{info.get('width','?')}x{info.get('height','?')}",
        "start":start,"end":end,"duration_sec":end_sec-start_sec,
        "output_mb":round(output.stat().st_size/(1024*1024),2),
        "downloaded_bytes":progress["downloaded"],"elapsed_sec":elapsed,"output":str(output)
    }
