import os
import sys
import urllib.request
import zipfile
import tempfile
import shutil

FFMPEG_DIR = os.path.join(os.path.expanduser("~"), ".ytmp3-app", "ffmpeg")
FFMPEG_URLS = [
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
]

def get_ffmpeg_dir():
    if os.path.isdir(FFMPEG_DIR) and os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg.exe")):
        return FFMPEG_DIR
    if os.path.isfile("ffmpeg.exe") and os.path.isfile("ffprobe.exe"):
        return os.path.abspath(".")
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isfile(os.path.join(p, "ffmpeg.exe")):
            return p
    return None

def get_ffmpeg_path():
    d = get_ffmpeg_dir()
    if d:
        return os.path.join(d, "ffmpeg.exe")
    return None

def is_ffmpeg_available():
    return get_ffmpeg_dir() is not None

def download_ffmpeg(callback=None):
    os.makedirs(FFMPEG_DIR, exist_ok=True)

    for url in FFMPEG_URLS:
        try:
            if callback:
                callback(f"Downloading FFmpeg... (trying {url.split('/')[2]})")

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            tmp.close()

            urllib.request.urlretrieve(url, tmp.name, _make_reporthook(callback))

            extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(tmp.name, "r") as zf:
                zf.extractall(extract_dir)

            for root, _, files in os.walk(extract_dir):
                for f in files:
                    if f.endswith(".exe"):
                        full_path = os.path.join(root, f)
                        shutil.copy2(full_path, os.path.join(FFMPEG_DIR, f))

            shutil.rmtree(extract_dir, ignore_errors=True)
            os.unlink(tmp.name)

            if os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg.exe")):
                if callback:
                    callback("FFmpeg downloaded successfully.")
                return True
        except Exception as e:
            if callback:
                callback(f"Download failed: {e}")
            continue

    if callback:
        callback("All FFmpeg download sources failed.")
    return False

def _make_reporthook(callback):
    class Reporter:
        def __init__(self):
            self.last = 0

        def __call__(self, block, blocksize, totalsize):
            if callback and totalsize > 0:
                pct = int(block * blocksize * 100 / totalsize)
                if pct != self.last and pct % 5 == 0:
                    callback(f"Downloading FFmpeg... {pct}%")
                    self.last = pct
    return Reporter()
