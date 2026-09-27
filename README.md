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

## Installation (no Python needed)

1. Go to the **Releases** page of this repo
2. Download **`YTMP3.exe`**
3. Double-click it

That's it — the .exe bundles Python, PyQt6 and yt-dlp, so it runs on any 64-bit Windows machine.

> Windows SmartScreen may show "Windows protected your PC" because the app isn't
> code-signed. Click **More info** → **Run anyway**.

Your first download will also pull FFmpeg automatically (about 90 MB, saved to
`%USERPROFILE%\.ytmp3-app\ffmpeg`).

## Running from source (developers)

```bash
git clone https://github.com/thecosyplatypus/ytmp3-app.git
cd ytmp3-app
pip install yt-dlp PyQt6
python main.py
```

`run.bat` works too: it launches `YTMP3.exe` if you've built it, otherwise it finds
your Python (via `py`, `python`, or `python3`), installs any missing dependencies
and starts from source.

## Building the .exe yourself

```bash
build.bat
```

Output goes to `dist\YTMP3.exe` (~55 MB, single file, no installer needed).

Every push to `master` is also built by GitHub Actions (`.github/workflows/build.yml`).
Tag a version (`git tag v1.0.0 && git push --tags`) and the exe is attached to the
GitHub Release automatically — that's how the Releases page gets its download.


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
├── build.bat         # Builds the standalone YTMP3.exe (PyInstaller)
├── run.bat           # Launcher: runs YTMP3.exe if built, else Python
├── .github/workflows/build.yml  # CI that builds the exe + attaches to releases
├── config.json       # Saved settings (auto-generated, next to the exe)
└── README.md
```
