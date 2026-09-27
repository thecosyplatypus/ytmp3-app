import sys
import os
import json
import re

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QLabel,
    QComboBox, QFileDialog, QProgressBar, QMessageBox, QSplitter,
    QFrame, QMenu, QCheckBox, QSlider, QStyle, QStyleFactory, QInputDialog,
)
from PyQt6.QtCore import (
    Qt, QThread, QUrl, QTimer, pyqtSignal, pyqtSlot, QObject,
)
from PyQt6.QtGui import (
    QFont, QIcon, QAction, QColor, QPalette, QBrush, QDesktopServices,
)
from PyQt6 import QtGui

from worker import DownloadWorker, DownloadItem
from ffmpeg_helper import (is_ffmpeg_available, download_ffmpeg, get_ffmpeg_dir,
                           get_ffmpeg_path, FFMPEG_DIR, app_dir)

CONFIG_FILE = os.path.join(app_dir(), "config.json")

def load_config():
    default = {
        "output_dir": os.path.join(os.path.expanduser("~"), "Music", "YTMP3 Downloads"),
        "quality": "192",
        "format": "mp3",
        "window_geometry": None,
    }
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                default.update(cfg)
        except Exception:
            pass
    return default

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def _is_url(text):
    return bool(re.match(r'https?://\S+', (text or "").strip()))


DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Arial", sans-serif;
}
QLineEdit {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 13px;
}
QLineEdit:focus {
    border: 1px solid #4a9eff;
}
QPushButton {
    background-color: #3d3d3d;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    color: #e0e0e0;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #555555;
}
QPushButton:disabled {
    background-color: #2a2a2a;
    color: #666666;
}
QPushButton#btnDownload {
    background-color: #4a9eff;
    color: #ffffff;
}
QPushButton#btnDownload:hover {
    background-color: #3a8eef;
}
QPushButton#btnDownload:disabled {
    background-color: #2a4a7a;
    color: #888888;
}
QPushButton#btnStop {
    background-color: #d32f2f;
    color: #ffffff;
}
QPushButton#btnStop:hover {
    background-color: #b71c1c;
}
QListWidget {
    background-color: #252525;
    border: 1px solid #333333;
    border-radius: 4px;
    outline: none;
}
QListWidget::item {
    background-color: #2a2a2a;
    border-bottom: 1px solid #333333;
    padding: 6px 8px;
    color: #e0e0e0;
}
QListWidget::item:hover {
    background-color: #333333;
}
QListWidget::item:selected {
    background-color: #2d4a7a;
}
QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 6px 12px;
    color: #e0e0e0;
    font-size: 13px;
}
QComboBox:hover {
    border: 1px solid #4a9eff;
}
QComboBox::drop-down {
    background-color: #2d2d2d;
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    color: #e0e0e0;
    selection-background-color: #4a9eff;
}
QProgressBar {
    background-color: #333333;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    font-size: 10px;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #4a9eff;
    border-radius: 3px;
}
QLabel#statusLabel {
    color: #888888;
    font-size: 12px;
}
QSplitter::handle {
    background-color: #333333;
    width: 1px;
}
QFrame#headerFrame {
    background-color: #1a1a1a;
    border-bottom: 1px solid #333333;
}
"""


class DownloadListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._items = {}

    def add_item(self, item: DownloadItem):
        row = DownloadRow(item)
        self._layout.addWidget(row)
        self._items[item.url] = row

    def update_item(self, item: DownloadItem):
        row = self._items.get(item.url)
        if row:
            row.update_from(item)

    def remove_item(self, url):
        row = self._items.pop(url, None)
        if row:
            self._layout.removeWidget(row)
            row.deleteLater()

    def clear(self):
        for row in self._items.values():
            self._layout.removeWidget(row)
            row.deleteLater()
        self._items.clear()


class DownloadRow(QFrame):
    def __init__(self, item: DownloadItem):
        super().__init__()
        self._item = item
        self.setFixedHeight(56)
        self.setStyleSheet("""
            DownloadRow {
                background-color: #2a2a2a;
                border-radius: 4px;
                border: 1px solid #333333;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        self._info_layout = QVBoxLayout()
        self._info_layout.setSpacing(2)

        self._title_label = QLabel(item.title or "Analyzing...")
        self._title_label.setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: 500; background: transparent; border: none;")
        self._title_label.setWordWrap(False)

        self._status_label = QLabel(self._status_text(item))
        self._status_label.setStyleSheet("color: #888888; font-size: 11px; background: transparent; border: none;")

        self._info_layout.addWidget(self._title_label)
        self._info_layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setFixedSize(120, 6)
        self._progress.setValue(int(item.progress))
        self._progress.setVisible(item.status in ("downloading", "converting"))

        layout.addLayout(self._info_layout, 1)
        layout.addWidget(self._progress)
        layout.addSpacing(4)

        self._rename_btn = QPushButton("✎")
        self._rename_btn.setFixedSize(26, 26)
        self._rename_btn.setToolTip("Rename file before downloading")
        self._rename_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888888;
                font-size: 14px;
                padding: 0;
            }
            QPushButton:hover { color: #4a9eff; }
        """)
        self._rename_btn.clicked.connect(self._on_rename)
        layout.addWidget(self._rename_btn)

    def _on_rename(self):
        current = self._item.custom_filename or self._item.title or ""
        name, ok = QInputDialog.getText(self, "Rename Download", "File name (no extension):", text=current)
        if ok and name.strip():
            self._item.custom_filename = self._clean_filename(name.strip())
            self._title_label.setText(self._item.custom_filename)
            self._status_label.setText(f"Will be saved as: {self._item.custom_filename}")

    @staticmethod
    def _clean_filename(name):
        cleaned = re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(". ")
        base, ext = os.path.splitext(cleaned)
        if ext.lower() in (".mp3", ".mp4", ".m4a", ".webm", ".mkv"):
            cleaned = base
        return cleaned or "download"

    def _status_text(self, item: DownloadItem):
        status_map = {
            "pending": "Waiting...",
            "analyzing": "Analyzing...",
            "downloading": f"Downloading... {item.progress:.0f}%",
            "converting": f"Converting to {item.format.upper()}...",
            "done": "Completed",
            "error": f"Error: {item.error}",
        }
        return status_map.get(item.status, item.status)

    def update_from(self, item: DownloadItem):
        label = self._item.custom_filename or item.title or "Unknown"
        self._title_label.setText(label)
        self._status_label.setText(self._status_text(item))
        self._progress.setValue(int(item.progress))
        self._progress.setVisible(item.status in ("downloading", "converting"))

        if item.status == "done":
            self.setStyleSheet("""
                DownloadRow {
                    background-color: #1a3a1a;
                    border-radius: 4px;
                    border: 1px solid #2a5a2a;
                }
            """)
        elif item.status == "error":
            self.setStyleSheet("""
                DownloadRow {
                    background-color: #3a1a1a;
                    border-radius: 4px;
                    border: 1px solid #5a2a2a;
                }
            """)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self._init_ui()
        self._init_worker()
        self._check_ffmpeg()
        self._setup_drag_drop()

    def _init_ui(self):
        self.setWindowTitle("YT Downloader (MP3 / MP4)")
        self.setMinimumSize(750, 500)

        if self.config.get("window_geometry"):
            self.restoreGeometry(bytes(self.config["window_geometry"]))
        else:
            self.resize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        self._build_toolbar(main_layout)
        self._build_download_list(main_layout)
        self._build_status_bar(main_layout)

    def _build_toolbar(self, parent):
        toolbar = QFrame()
        toolbar.setObjectName("headerFrame")
        toolbar.setFixedHeight(48)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)

        title = QLabel("YT Downloader (MP3 / MP4)")
        title.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 600; background: transparent;")
        tl.addWidget(title)
        tl.addStretch()

        self._ffmpeg_label = QLabel("FFmpeg: checking...")
        self._ffmpeg_label.setStyleSheet("color: #ffa000; font-size: 11px; background: transparent;")
        tl.addWidget(self._ffmpeg_label)

        parent.addWidget(toolbar)

    def _build_download_list(self, parent):
        url_frame = QWidget()
        url_layout = QHBoxLayout(url_frame)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_layout.setSpacing(8)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Paste a video / episode / playlist link (YouTube, AniKuro, ...)...")
        self._url_input.returnPressed.connect(self._on_add_url)

        self._add_btn = QPushButton("Add")
        self._add_btn.clicked.connect(self._on_add_url)

        self._download_btn = QPushButton("Download All")
        self._download_btn.setObjectName("btnDownload")
        self._download_btn.clicked.connect(self._on_start_all)

        self._stop_btn = QPushButton("■")
        self._stop_btn.setObjectName("btnStop")
        self._stop_btn.setFixedWidth(36)
        self._stop_btn.clicked.connect(self._on_stop_all)
        self._stop_btn.setEnabled(False)

        url_layout.addWidget(self._url_input, 1)
        url_layout.addWidget(self._add_btn)
        url_layout.addWidget(self._download_btn)
        url_layout.addWidget(self._stop_btn)

        quality_frame = QWidget()
        q_layout = QHBoxLayout(quality_frame)
        q_layout.setContentsMargins(0, 0, 0, 0)
        q_layout.setSpacing(8)

        q_layout.addWidget(QLabel("Quality:"))

        self._quality_combo = QComboBox()
        self._quality_combo.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        qidx = ["128", "192", "256", "320"].index(self.config.get("quality", "192"))
        self._quality_combo.setCurrentIndex(qidx)
        q_layout.addWidget(self._quality_combo)

        q_layout.addSpacing(16)
        q_layout.addWidget(QLabel("Format:"))

        self._format_combo = QComboBox()
        self._format_combo.addItem("MP3 (Audio)", "mp3")
        self._format_combo.addItem("MP4 (Video)", "mp4")
        self._format_combo.setCurrentIndex(0 if self.config.get("format", "mp3") == "mp3" else 1)
        q_layout.addWidget(self._format_combo)

        q_layout.addSpacing(16)
        q_layout.addWidget(QLabel("Cookies:"))

        self._cookies_combo = QComboBox()
        self._cookies_combo.addItem("None", None)
        for browser in ("chrome", "edge", "firefox", "brave", "opera", "vivaldi"):
            self._cookies_combo.addItem(browser.title(), browser)
        saved_browser = self.config.get("cookies_from_browser")
        if saved_browser:
            idx = self._cookies_combo.findData(saved_browser)
            if idx >= 0:
                self._cookies_combo.setCurrentIndex(idx)
        q_layout.addWidget(self._cookies_combo)

        q_layout.addSpacing(16)
        q_layout.addWidget(QLabel("Save to:"))

        self._dir_label = QLabel(self.config.get("output_dir", ""))
        self._dir_label.setStyleSheet("color: #888888; font-size: 12px; background: transparent; border: none;")

        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse)
        q_layout.addWidget(self._dir_label, 1)
        q_layout.addWidget(self._browse_btn)

        parent.addWidget(url_frame)
        parent.addWidget(quality_frame)

        self._list_widget = DownloadListWidget()
        parent.addWidget(self._list_widget, 1)

    def _build_status_bar(self, parent):
        status_frame = QFrame()
        status_frame.setFixedHeight(28)
        sl = QHBoxLayout(status_frame)
        sl.setContentsMargins(0, 0, 0, 0)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("statusLabel")
        sl.addWidget(self._status_label)
        sl.addStretch()

        self._count_label = QLabel("0 items")
        self._count_label.setStyleSheet("color: #888888; font-size: 11px;")
        sl.addWidget(self._count_label)

        parent.addWidget(status_frame)

    def _init_worker(self):
        self._worker = DownloadWorker()
        output_dir = self.config.get("output_dir", os.path.join(os.path.expanduser("~"), "Music", "YTMP3 Downloads"))
        self._worker.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        ffmpeg_dir = get_ffmpeg_dir()
        if ffmpeg_dir:
            self._worker.ffmpeg_dir = ffmpeg_dir

        self._worker.signals.item_added.connect(self._on_item_added)
        self._worker.signals.item_updated.connect(self._on_item_updated)
        self._worker.signals.playlist_discovered.connect(self._on_playlist_discovered)
        self._worker.signals.status_message.connect(self._status_label.setText)
        self._worker.signals.all_done.connect(self._on_all_done)

        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._thread.start()

        self._active_downloads = 0

    def _check_ffmpeg(self):
        if is_ffmpeg_available():
            self._ffmpeg_label.setText("FFmpeg: ✓ available")
            self._ffmpeg_label.setStyleSheet("color: #4caf50; font-size: 11px; background: transparent;")
        else:
            self._ffmpeg_label.setText("FFmpeg: not found (click to install)")
            self._ffmpeg_label.setStyleSheet("color: #ffa000; font-size: 11px; background: transparent; text-decoration: underline; cursor: pointer;")
            self._ffmpeg_label.mousePressEvent = lambda e: self._install_ffmpeg()

    def _install_ffmpeg(self):
        self._ffmpeg_label.setText("FFmpeg: downloading...")
        self._ffmpeg_label.setStyleSheet("color: #4a9eff; font-size: 11px; background: transparent;")
        QTimer.singleShot(100, self._do_install_ffmpeg)

    def _do_install_ffmpeg(self):
        def callback(msg):
            self._ffmpeg_label.setText(f"FFmpeg: {msg[:40]}")
            self._status_label.setText(msg)

        success = download_ffmpeg(callback)
        if success:
            self._ffmpeg_label.setText("FFmpeg: ✓ ready")
            self._ffmpeg_label.setStyleSheet("color: #4caf50; font-size: 11px; background: transparent;")
            self._worker.ffmpeg_dir = get_ffmpeg_dir()
            QMessageBox.information(self, "FFmpeg", "FFmpeg has been downloaded and installed successfully.")
        else:
            self._ffmpeg_label.setText("FFmpeg: download failed")
            self._ffmpeg_label.setStyleSheet("color: #f44336; font-size: 11px; background: transparent;")
            QMessageBox.warning(self, "FFmpeg",
                "Could not download FFmpeg automatically.\n\n"
                "Download it manually from: https://ffmpeg.org/download.html\n"
                "and add ffmpeg.exe to your PATH or place it in the app folder.")

    def _setup_drag_drop(self):
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                link = url.toString()
                if _is_url(link):
                    self._add_url(link)
        elif event.mimeData().hasText():
            text = event.mimeData().text()
            for line in text.strip().splitlines():
                line = line.strip()
                if _is_url(line):
                    self._add_url(line)

    def _on_add_url(self):
        text = self._url_input.text().strip()
        if not text:
            return

        urls = re.findall(r'https?://\S+', text)
        if not urls:
            QMessageBox.warning(self, "No link found",
                "That doesn't look like a link.\n\n"
                "Paste a full URL, e.g.\n"
                "  https://www.youtube.com/watch?v=...\n"
                "  https://anikuro.to/watch/16498:1")
            return

        for url in urls:
            self._add_url(url.rstrip('.,;)\'"'))

        self._url_input.clear()

    def _add_url(self, url):
        self._worker.add_url(url)

    def _on_start_all(self):
        self._download_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        quality = self._quality_combo.currentText().split()[0]
        self._worker.quality = quality
        self._worker.format = self._format_combo.currentData()
        self._worker.cookies_from_browser = self._cookies_combo.currentData()
        self._worker._paused = False
        pending = sum(
            1 for item in self._list_widget._items.values()
            if item._status_label.text() in ("Waiting...", "Analyzing...", "Pending")
        )
        self._status_label.setText(f"Downloading {pending} items..." if pending else "No pending items")

    def _on_stop_all(self):
        self._worker._paused = True
        self._download_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("Downloads paused")

    def _on_item_added(self, item: DownloadItem):
        self._list_widget.add_item(item)
        self._update_count()

    def _on_item_updated(self, item: DownloadItem):
        self._list_widget.update_item(item)
        self._update_count()

    def _on_playlist_discovered(self, data):
        self._status_label.setText(f"Playlist loaded: {data['title']} ({data['count']} tracks)")

    def _on_all_done(self):
        self._download_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("All downloads finished")

    def _update_count(self):
        total = len(self._list_widget._items)
        done = sum(1 for item in self._list_widget._items.values()
                   if item._status_label.text() == "Completed")
        self._count_label.setText(f"{done}/{total} completed" if done else f"{total} items")

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self._worker.output_dir)
        if path:
            self._worker.output_dir = path
            self._dir_label.setText(path)
            self.config["output_dir"] = path
            save_config(self.config)

    def closeEvent(self, event):
        self._worker.stop()
        self.config["window_geometry"] = list(self.saveGeometry())
        self.config["quality"] = self._quality_combo.currentText().split()[0]
        self.config["format"] = self._format_combo.currentData()
        self.config["cookies_from_browser"] = self._cookies_combo.currentData()
        save_config(self.config)
        self._thread.quit()
        self._thread.wait(2000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#252525"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2a2a2a"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d2d2d"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#3d3d3d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#4a9eff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#4a9eff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
