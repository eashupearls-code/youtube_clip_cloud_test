
from youtube_clip_plan_c import extract_clip

url = input("YouTube URL: ").strip()
start = input("Start time (MM:SS): ").strip()
end = input("End time (MM:SS): ").strip()
quality = input("Quality [1080p]: ").strip() or "1080p"

result = extract_clip(
    url=url,
    start_text=start,
    end_text=end,
    quality=quality,
    log=print,
)

print("\n" + "=" * 70)
print("SUCCESS")
print("=" * 70)
print("Created:", result["path"])
print(f"Duration: {result['duration']:.2f}s")
print(f"Resolution: {result['width']}x{result['height']}")
print(f"Downloaded: {result['downloaded_mb']:.2f} MB")
print(f"Output: {result['output_mb']:.2f} MB")
