import re

def parse_time(value):
    value=value.strip()
    if re.fullmatch(r"\d+(\.\d+)?", value): return float(value)
    parts=value.split(":")
    if len(parts)==2: return int(parts[0])*60+float(parts[1])
    if len(parts)==3: return int(parts[0])*3600+int(parts[1])*60+float(parts[2])
    raise ValueError("Use SS, MM:SS, or HH:MM:SS.")

def quality_selector(quality):
    if quality=="Best Available": return "bv*+ba/b"
    h=int(quality.replace("p",""))
    return f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]"
