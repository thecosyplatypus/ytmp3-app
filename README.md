# YTMP3 Downloader

A desktop application for downloading YouTube videos and playlists as MP3 audio or MP4 video. Built with Python, PyQt6, and yt-dlp.

## Features

- Download single YouTube videos or full playlists as **MP3** or **MP4**
- Dark-themed desktop UI (PyQt6)
- Selectable MP3 quality (128, 192, 256, 320 kbps)
- **Rename files before downloading** — click the ✎ on a row to set a custom file name (great for videos that share the same title)
- Handles videos up to 2 hours (and longer) with resumable, retry-safe downloads
- Cookie-based auth from your browser to bypass YouTube bot checks
- Drag-and-drop URL support
- Download queue with progress tracking
- Auto-detects playlists and expands individual tracks
- Configurable output directory
- FFmpeg auto-install if missing

## Requirements

- Python 3.8+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (auto-installed below)
- [PyQt6](https://pypi.org/project/PyQt6/) (auto-installed below)
- FFmpeg (auto-downloaded from within the app, or install manually)

## Installation

```bash
# 1. Install Python dependencies
pip install yt-dlp PyQt6 mutagen

# 2. Clone or download this repo, then run:
cd ytmp3-app
py main.py
```

Or double-click `run.bat` on Windows.

## Usage

1. **Launch the app** — a dark-themed window opens

2. **Paste a URL** — paste a YouTube video or playlist link into the input field, then click **Add**
   - Supports `youtube.com`, `youtu.be`, `music.youtube.com`
   - Playlists are auto-detected and expanded

3. **Select format & quality** — choose **MP3 (Audio)** or **MP4 (Video)**, and MP3 bitrate: 128, 192, 256, or 320 kbps

4. **Rename (optional)** — click the ✎ button on any row to set a custom file name before it downloads. The name is shown under the row ("Will be saved as: ...")

5. **Choose output folder** — click **Browse...** to change where files are saved (defaults to `~/Music/YTMP3 Downloads`)

6. **Download All** — starts processing the queue. Each track shows:
   - Download progress (%)
   - Conversion status ("Converting to MP3/MP4...")
   - Green highlight on completion, red on error

7. **Stop** — pauses the current queue (resume with **Download All**)

8. **Cookies** — if YouTube says "Sign in to confirm you're not a bot", pick the browser you're signed into YouTube with (Chrome/Edge/Firefox, etc.) from the **Cookies** dropdown. Close the browser first so the app can read its cookie database.

9. **FFmpeg** — if missing, click the "FFmpeg: not found" label at the top to auto-download it

## Project Structure

```
ytmp3-app/
├── main.py           # Application entry point & UI
├── worker.py         # Download queue & yt-dlp integration
├── ffmpeg_helper.py  # FFmpeg detection & download
├── run.bat           # Windows launcher
├── config.json       # Saved settings (auto-generated)
└── README.md
```
