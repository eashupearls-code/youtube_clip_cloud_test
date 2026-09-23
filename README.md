
# YouTube Clip Extractor — Plan C

This is the isolated Streamlit Cloud test project for the segment-based YouTube clip extractor.

## Architecture

The app does not use yt-dlp `download_ranges`.

Instead it:

1. Extracts YouTube metadata with yt-dlp.
2. Selects an HLS video format and HLS audio-only format.
3. Downloads the HLS media playlists.
4. Finds only the segments covering the requested timestamp range.
5. Downloads those segments.
6. Reconstructs the selected media locally.
7. Uses FFmpeg to mux the video and audio into an MP4.
8. Trims the result to the requested duration.

The current application limits individual clips to 20 minutes.

## Streamlit Cloud

Main file:

`app.py`

System package:

`ffmpeg`

Python dependency:

`yt-dlp[default]`

Deno is expected to be available in the Streamlit runtime. yt-dlp's JavaScript support package is installed through `yt-dlp[default]`.

## Important

Use this only for videos you own or are authorized to process, and comply with the applicable platform terms and content rights.
