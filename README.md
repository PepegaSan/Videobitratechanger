# Video Bitrate Changer

Batch tool for **re-encoding videos to a target bitrate by resolution** — without pushing files above their original bitrate.

Scan a folder, review suggested bitrates per file, then run **FFmpeg** (CPU or NVENC). Handy when you want smaller files but do not want to blindly upscale quality.

## How it works

- Reads each file with **ffprobe** (resolution, current bitrate).
- Picks a rule from your preset (e.g. 1080p → 4000 kbps).
- Effective target = **min(original, rule)** so nothing gets a higher bitrate than the source.
- Optional: skip files that are already at or below the target.

## Requirements

- Windows 10/11
- Python 3.10+
- **ffmpeg** and **ffprobe** on your `PATH`

## Install and run

```bat
install.bat
start_tool.bat
```

Settings are stored in `mass_bitrate_gui_config.json` (local only; see `mass_bitrate_gui_config.example.json`).

## License

MIT
