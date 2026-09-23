# YouTube Clip Cloud Test

Minimal Streamlit deployment test for Method A: YouTube URL -> yt-dlp section download -> FFmpeg -> MP4.

`requirements.txt` installs yt-dlp with its EJS package. `packages.txt` installs FFmpeg. The app bootstraps Deno 2.9.7 on Linux x86_64 if Deno is not already available.

Do not upload `.venv`, `outputs`, or `.runtime`; they are ignored by `.gitignore`.

Test locally with the same 24-minute video:
Start `00:15:00`, End `00:15:15`, Quality `1080p`.

Only process videos you own or are authorized to process.
