import os
import re
import json
import queue
import threading
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class DownloadItem:
    def __init__(self, url, title="", status="pending", progress=0.0):
        self.url = url
        self.title = title
        self.status = status
        self.progress = progress
        self.error = ""
        self.filepath = ""
        self.format = "mp3"
        self.custom_filename = ""


class DownloadSignals(QObject):
    item_added = pyqtSignal(object)
    item_updated = pyqtSignal(object)
    playlist_discovered = pyqtSignal(object)
    status_message = pyqtSignal(str)
    download_finished = pyqtSignal()
    all_done = pyqtSignal()


class DownloadWorker(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = DownloadSignals()
        self.queue = queue.Queue()
        self._running = False
        self._pause = False
        self._items = {}
        self._lock = threading.Lock()
        self.output_dir = os.path.join(os.path.expanduser("~"), "Music", "YTMP3 Downloads")
        self.quality = "192"
        self.format = "mp3"
        self.cookies_from_browser = None
        self.ffmpeg_dir = None
        self._paused = True
        self._thread = None
        self._done_emitted = False

    @pyqtSlot()
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @pyqtSlot()
    def stop(self):
        self._running = False
        self._pause = False

    @pyqtSlot()
    def pause(self):
        self._pause = True

    @pyqtSlot()
    def resume(self):
        self._pause = False

    def add_url(self, url):
        item = DownloadItem(url)
        with self._lock:
            self._items[url] = item
        self.queue.put(url)
        self.signals.item_added.emit(item)
        return item

    def _run(self):
        import time

        while self._running:
            if self._paused:
                if self.queue.empty() and not self._done_emitted:
                    self._done_emitted = True
                    self.signals.all_done.emit()
                time.sleep(0.3)
                continue

            self._done_emitted = False

            try:
                url = self.queue.get(timeout=0.5)
            except queue.Empty:
                self._done_emitted = True
                self.signals.all_done.emit()
                continue

            if not self._running:
                break

            with self._lock:
                item = self._items.get(url)
                if item:
                    item.status = "analyzing"

            self.signals.status_message.emit(f"Analyzing: {url[:80]}...")
            info, analyze_error = self._analyze_url(url)

            if not info:
                with self._lock:
                    item = self._items.get(url)
                    if item:
                        item.status = "error"
                        item.error = analyze_error or "Could not analyze URL"
                        self.signals.item_updated.emit(item)
                self.signals.status_message.emit(f"Failed to analyze URL: {analyze_error or 'unknown error'}")
                continue

            if info.get("playlist_count", 0) > 1:
                entries = info.get("entries", [])
                playlist_title = info.get("title", "Playlist")
                self.signals.status_message.emit(f"Playlist found: {playlist_title} ({len(entries)} tracks)")

                playlist_items = []
                for entry in entries:
                    vid_url = entry.get("webpage_url") or entry.get("url") or f"https://youtube.com/watch?v={entry.get('id', '')}"
                    if not vid_url:
                        continue
                    child = DownloadItem(vid_url, title=entry.get("title", "Unknown"), status="pending")
                    playlist_items.append(child)

                if playlist_items:
                    self.signals.playlist_discovered.emit({
                        "title": playlist_title,
                        "items": playlist_items,
                        "count": len(playlist_items)
                    })

                with self._lock:
                    orig = self._items.get(url)
                    if orig:
                        orig.status = "done"
                        orig.title = playlist_title
                        self.signals.item_updated.emit(orig)

                for child in playlist_items:
                    with self._lock:
                        self._items[child.url] = child
                    self.queue.put(child.url)
                    self.signals.item_added.emit(child)
            else:
                title = info.get("title", "Unknown Track")
                with self._lock:
                    item = self._items.get(url)
                    if item:
                        item.title = title
                        item.status = "downloading"

                self.signals.item_updated.emit(item)
                self._download_single(url, item)

        self.signals.status_message.emit("Worker stopped")

    def _analyze_url(self, url):
        if not yt_dlp:
            return None, "yt-dlp not installed. Run: pip install yt-dlp"
        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": "in_playlist",
                "skip_download": True,
            }
            if self.cookies_from_browser:
                opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False), None
        except Exception as e:
            return None, str(e)[:300]

    def _download_single(self, url, item):
        if not yt_dlp:
            return

        item.format = self.format

        if item.custom_filename:
            outtmpl = os.path.join(self.output_dir, item.custom_filename + ".%(ext)s")
        else:
            outtmpl = os.path.join(self.output_dir, "%(title)s.%(ext)s")

        opts = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [lambda d: self._progress_hook(d, item)],
            "retries": 10,
            "fragment_retries": 10,
            "continuedl": True,
            "concurrent_fragment_downloads": 4,
        }

        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)

        if self.format == "mp4":
            opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best"
            opts["merge_output_format"] = "mp4"
        else:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": self.quality,
            }]

        if self.ffmpeg_dir:
            opts["ffmpeg_location"] = self.ffmpeg_dir

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            item.status = "done"
            item.progress = 100.0
            self.signals.item_updated.emit(item)
            self.signals.status_message.emit(f"Done: {item.title}")
        except Exception as e:
            item.status = "error"
            item.error = str(e)[:200]
            self.signals.item_updated.emit(item)
            self.signals.status_message.emit(f"Error: {item.title} - {str(e)[:60]}")

    def _progress_hook(self, d, item):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = round(downloaded / total * 100, 1)
                item.progress = pct
                self.signals.item_updated.emit(item)
        elif d.get("status") == "finished":
            item.status = "converting"
            self.signals.item_updated.emit(item)
            self.signals.status_message.emit(f"Converting: {item.title}")

    def remove_item(self, url):
        with self._lock:
            self._items.pop(url, None)
