
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests
import yt_dlp


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

MAX_CLIP_SECONDS = 20 * 60


def parse_time(value: str) -> float:
    value = value.strip()
    if not value:
        raise ValueError("Time cannot be empty.")

    parts = value.split(":")
    try:
        nums = [float(x) for x in parts]
    except ValueError:
        raise ValueError(f"Invalid time: {value}")

    if len(nums) == 1:
        seconds = nums[0]
    elif len(nums) == 2:
        seconds = nums[0] * 60 + nums[1]
    elif len(nums) == 3:
        seconds = nums[0] * 3600 + nums[1] * 60 + nums[2]
    else:
        raise ValueError(f"Invalid time: {value}")

    if seconds < 0:
        raise ValueError("Time cannot be negative.")

    return seconds


def run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed:\n\n" + proc.stderr[-6000:]
        )


def get_info(url: str) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def is_hls_format(fmt: dict) -> bool:
    protocol = (fmt.get("protocol") or "").lower()
    return protocol in {"m3u8", "m3u8_native"}


def video_score(fmt: dict, max_height: int) -> tuple:
    height = fmt.get("height") or 0
    vcodec = (fmt.get("vcodec") or "").lower()
    avc = 1 if vcodec.startswith("avc1") else 0
    h264_bonus = 1 if "avc" in vcodec else 0
    within = 1 if height <= max_height else 0
    return (
        within,
        min(height, max_height),
        avc,
        h264_bonus,
        fmt.get("tbr") or 0,
    )


def choose_video(info: dict, quality: str) -> dict:
    heights = {"1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
    max_height = heights[quality]

    candidates = [
        f for f in info.get("formats", [])
        if is_hls_format(f)
        and (f.get("vcodec") or "none") != "none"
        and (f.get("url") or "")
    ]

    if not candidates:
        raise RuntimeError("No HLS video format was found.")

    under = [f for f in candidates if (f.get("height") or 0) <= max_height]
    pool = under or candidates

    # Prefer H.264/AVC when the requested quality exists.
    avc_pool = [
        f for f in pool
        if (f.get("vcodec") or "").lower().startswith("avc1")
    ]
    if avc_pool:
        pool = avc_pool

    return max(pool, key=lambda f: video_score(f, max_height))


def choose_audio(info: dict) -> dict:
    candidates = [
        f for f in info.get("formats", [])
        if is_hls_format(f)
        and (f.get("vcodec") or "none") == "none"
        and (f.get("acodec") or "none") != "none"
        and (f.get("url") or "")
    ]

    if not candidates:
        raise RuntimeError("No HLS audio-only format was found.")

    # Prefer AAC/MP4 audio when available.
    aac = [
        f for f in candidates
        if "mp4a" in (f.get("acodec") or "").lower()
    ]
    pool = aac or candidates

    return max(pool, key=lambda f: (
        f.get("abr") or 0,
        f.get("tbr") or 0,
    ))


def fetch_text(url: str, headers: dict | None = None) -> str:
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)

    r = requests.get(hdrs=hdrs, url=url, timeout=30)
    r.raise_for_status()
    return r.text


def parse_media_playlist(playlist_url: str, text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    segments = []
    current_duration = None
    current_title = ""
    pending_map = None

    media_sequence = 0

    for line in lines:
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            try:
                media_sequence = int(line.split(":", 1)[1])
            except Exception:
                media_sequence = 0

        elif line.startswith("#EXT-X-MAP:"):
            m = re.search(r'URI="([^"]+)"', line)
            if m:
                pending_map = urljoin(playlist_url, m.group(1))

        elif line.startswith("#EXTINF:"):
            raw = line.split(":", 1)[1]
            duration_text = raw.split(",", 1)[0]
            current_duration = float(duration_text)
            current_title = raw.split(",", 1)[1] if "," in raw else ""

        elif not line.startswith("#") and current_duration is not None:
            segments.append({
                "url": urljoin(playlist_url, line),
                "duration": current_duration,
                "title": current_title,
                "map_url": pending_map,
            })
            current_duration = None
            current_title = ""

    if not segments:
        raise RuntimeError("The HLS media playlist contained no media segments.")

    total = sum(s["duration"] for s in segments)

    cursor = 0.0
    for s in segments:
        s["start"] = cursor
        s["end"] = cursor + s["duration"]
        cursor = s["end"]

    return {
        "segments": segments,
        "duration": total,
        "media_sequence": media_sequence,
    }


def select_segments(parsed: dict, start: float, end: float) -> list[dict]:
    selected = [
        s for s in parsed["segments"]
        if s["end"] > start and s["start"] < end
    ]

    if not selected:
        raise RuntimeError(
            f"No HLS segments cover {start:.2f}–{end:.2f} seconds."
        )

    return selected


def download_file(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": USER_AGENT}
    with requests.get(
        url,
        headers=headers,
        stream=True,
        timeout=60,
    ) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def concat_binary(paths: list[Path], output: Path) -> None:
    with open(output, "wb") as out:
        for path in paths:
            with open(path, "rb") as src:
                shutil.copyfileobj(src, out, length=1024 * 1024)


def combine_segments(paths: list[Path], output: Path) -> None:
    if not paths:
        raise RuntimeError("No segment files were downloaded.")

    # MPEG-TS segments can be concatenated directly.
    # For fragmented MP4/fMP4, use FFmpeg concat demuxer.
    first = paths[0].read_bytes()[:16]
    looks_ts = len(first) >= 1 and first[0] == 0x47

    if looks_ts:
        concat_binary(paths, output)
        return

    concat_list = output.with_suffix(".txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for path in paths:
            escaped = str(path).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    try:
        run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output),
        ])
    finally:
        concat_list.unlink(missing_ok=True)


def build_clip(
    video_file: Path,
    audio_file: Path,
    start: float,
    end: float,
    output: Path,
) -> None:
    duration = end - start

    # The downloaded HLS media starts slightly before the requested point.
    # We trim relative to the first selected segment start later.
    # Here we simply normalize each stream from its beginning and then
    # take the requested duration. The caller supplies already-aligned
    # segment groups, so the clip contains the requested range with
    # segment-boundary precision before this final trim.
    run_ffmpeg([
        "-i", str(video_file),
        "-i", str(audio_file),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", f"{duration:.3f}",
        "-c", "copy",
        "-movflags", "+faststart",
        str(output),
    ])


def extract_clip(
    url: str,
    start_text: str,
    end_text: str,
    quality: str = "1080p",
    log=None,
) -> dict:
    start = parse_time(start_text)
    end = parse_time(end_text)

    if end <= start:
        raise ValueError("End time must be greater than start time.")

    duration = end - start
    if duration > MAX_CLIP_SECONDS:
        raise ValueError("Maximum clip length is 20 minutes.")

    if log:
        log("Extracting YouTube format information...")

    info = get_info(url)
    source_duration = info.get("duration") or 0

    if source_duration and end > source_duration + 1:
        raise ValueError(
            f"End time {end:.2f}s is beyond the source duration "
            f"of {source_duration:.2f}s."
        )

    video_fmt = choose_video(info, quality)
    audio_fmt = choose_audio(info)

    if log:
        log(
            f"Video format: {video_fmt.get('format_id')} | "
            f"{video_fmt.get('width')}x{video_fmt.get('height')} | "
            f"{video_fmt.get('vcodec')}"
        )
        log(
            f"Audio format: {audio_fmt.get('format_id')} | "
            f"{audio_fmt.get('acodec')}"
        )

    with tempfile.TemporaryDirectory(prefix="youtube_plan_c_") as tmp:
        tmp_path = Path(tmp)
        video_dir = tmp_path / "video"
        audio_dir = tmp_path / "audio"
        work_dir = tmp_path / "work"
        video_dir.mkdir()
        audio_dir.mkdir()
        work_dir.mkdir()

        if log:
            log("Downloading video HLS playlist...")

        video_playlist = fetch_text(video_fmt["url"])
        video_parsed = parse_media_playlist(video_fmt["url"], video_playlist)
        video_segments = select_segments(video_parsed, start, end)

        if log:
            log(
                f"Video segments selected: {len(video_segments)} "
                f"({video_segments[0]['start']:.2f}s → "
                f"{video_segments[-1]['end']:.2f}s)"
            )

        if log:
            log("Downloading audio HLS playlist...")

        audio_playlist = fetch_text(audio_fmt["url"])
        audio_parsed = parse_media_playlist(audio_fmt["url"], audio_playlist)
        audio_segments = select_segments(audio_parsed, start, end)

        if log:
            log(
                f"Audio segments selected: {len(audio_segments)} "
                f"({audio_segments[0]['start']:.2f}s → "
                f"{audio_segments[-1]['end']:.2f}s)"
            )

        video_files = []
        audio_files = []

        # If an HLS playlist has an initialization map, download it once
        # before the selected fMP4 segments.
        video_map = video_segments[0].get("map_url")
        if video_map:
            map_path = video_dir / "init.mp4"
            if log:
                log("Downloading video initialization segment...")
            download_file(video_map, map_path)
            video_files.append(map_path)

        audio_map = audio_segments[0].get("map_url")
        if audio_map:
            map_path = audio_dir / "init.mp4"
            if log:
                log("Downloading audio initialization segment...")
            download_file(audio_map, map_path)
            audio_files.append(map_path)

        if log:
            log("Downloading selected video segments...")

        for i, segment in enumerate(video_segments):
            path = video_dir / f"video_{i:04d}.ts"
            download_file(segment["url"], path)
            video_files.append(path)
            if log:
                log(
                    f"Video {i + 1}/{len(video_segments)}: "
                    f"{segment['start']:.2f} → {segment['end']:.2f}"
                )

        if log:
            log("Downloading selected audio segments...")

        for i, segment in enumerate(audio_segments):
            path = audio_dir / f"audio_{i:04d}.ts"
            download_file(segment["url"], path)
            audio_files.append(path)
            if log:
                log(
                    f"Audio {i + 1}/{len(audio_segments)}: "
                    f"{segment['start']:.2f} → {segment['end']:.2f}"
                )

        combined_video = work_dir / "video_combined.ts"
        combined_audio = work_dir / "audio_combined.ts"

        if log:
            log("Combining video segments...")
        combine_segments(video_files, combined_video)

        if log:
            log("Combining audio segments...")
        combine_segments(audio_files, combined_audio)

        # The first selected segment usually begins before the exact requested
        # timestamp. Trim that offset, then take exactly the requested duration.
        video_offset = start - video_segments[0]["start"]
        audio_offset = start - audio_segments[0]["start"]

        output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)

        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", str(info.get("id") or "youtube"))
        output = output_dir / f"clip_{safe_id}_{int(start)}_{int(end)}.mp4"

        run_ffmpeg([
            "-ss", f"{video_offset:.3f}",
            "-i", str(combined_video),
            "-ss", f"{audio_offset:.3f}",
            "-i", str(combined_audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-t", f"{duration:.3f}",
            "-c", "copy",
            "-movflags", "+faststart",
            str(output),
        ])

    # Probe final file.
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-show_entries", "stream=width,height",
            "-of", "default=noprint_wrappers=1",
            str(output),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    duration_out = duration
    width = int(video_fmt.get("width") or 0)
    height = int(video_fmt.get("height") or 0)

    for line in probe.stdout.splitlines():
        if line.startswith("duration="):
            try:
                duration_out = float(line.split("=", 1)[1])
            except Exception:
                pass
        elif line.startswith("width="):
            try:
                width = int(line.split("=", 1)[1])
            except Exception:
                pass
        elif line.startswith("height="):
            try:
                height = int(line.split("=", 1)[1])
            except Exception:
                pass

    downloaded_bytes = 0
    for p in list(video_dir.glob("*")) + list(audio_dir.glob("*")):
        if p.is_file():
            downloaded_bytes += p.stat().st_size

    return {
        "path": str(output),
        "filename": output.name,
        "duration": duration_out,
        "width": width,
        "height": height,
        "downloaded_mb": downloaded_bytes / 1024 / 1024,
        "output_mb": output.stat().st_size / 1024 / 1024,
        "video_format": video_fmt.get("format_id"),
        "audio_format": audio_fmt.get("format_id"),
    }
