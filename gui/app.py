"""PySide6 desktop interface for CatWiz's media download workflow."""

import os
import re
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget, QCheckBox, QTextEdit, QScrollArea, QInputDialog
)

from catwiz.system import (
    get_download_dir, set_download_dir, get_auto_update_check,
    set_auto_update_check, get_category_dir,
)

STYLESHEET = """
QWidget { background: #101319; color: #e8ebf2; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; }
QFrame#Sidebar { background: #171c24; border-right: 1px solid #29313d; }
QLabel#Brand { font-size: 23px; font-weight: 800; color: #ffffff; padding: 8px 4px 22px; }
QLabel#Eyebrow { color: #8c9aaf; font-size: 11px; font-weight: 700; }
QLabel#Heading { font-size: 26px; font-weight: 750; color: #ffffff; }
QLabel#Subheading, QLabel#Muted { color: #9aa6b8; font-size: 13px; }
QFrame#Panel { background: #191f29; border: 1px solid #2a3442; border-radius: 13px; }
QPushButton { background: #242d3a; border: 1px solid #344154; border-radius: 8px; padding: 10px 14px; text-align: left; }
QPushButton:hover { background: #303c4d; }
QPushButton#Primary { background: #e34b66; color: white; border: 0; font-weight: 700; padding: 12px 18px; }
QPushButton#Nav { background: transparent; border: 0; color: #aeb9c9; padding: 11px 13px; }
QPushButton#Nav:checked { background: #293342; color: #ffffff; font-weight: 700; }
QLineEdit, QComboBox { background: #10151d; border: 1px solid #354153; border-radius: 8px; padding: 11px; }
QCheckBox { spacing: 9px; }
QScrollArea { border: 0; background: transparent; }
"""

class CatWizWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CatWiz")
        self.resize(1080, 760)
        self.setMinimumSize(850, 620)
        self.media_info = None
        self.playlist_items = []
        self.item_checks = []

        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("◈  CatWiz")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        side.addWidget(self._eyebrow("WORKSPACE"))
        self.stack = QStackedWidget()
        self.nav_buttons = []
        for label, page in (("⌂   Home", self._home_page()), ("⇩   Downloads", self._downloads_page()), ("▤   Logs", self._logs_page()), ("⚙   Settings", self._settings_page())):
            button = QPushButton(label)
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=len(self.nav_buttons): self._navigate(i))
            side.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)
        side.addStretch(1)
        side.addWidget(self._eyebrow("DESKTOP EDITION"))
        outer.addWidget(sidebar)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 28, 34, 24)
        content_layout.addWidget(self.stack)
        outer.addWidget(content, 1)
        self.setCentralWidget(root)
        self._navigate(0)

    def _eyebrow(self, value):
        label = QLabel(value)
        label.setObjectName("Eyebrow")
        return label

    def _heading(self, title, subtitle):
        box = QVBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("Heading")
        sub = QLabel(subtitle)
        sub.setObjectName("Subheading")
        box.addWidget(heading)
        box.addWidget(sub)
        return box

    def _panel(self, layout):
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setLayout(layout)
        return frame

    def _field(self, layout, caption, widget):
        layout.addWidget(self._eyebrow(caption))
        layout.addWidget(widget)

    def _home_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setSpacing(18)
        outer.addLayout(self._heading("Download media", "Choose a media type, then CatWiz will guide you through the next steps."))

        media_form = QVBoxLayout()
        media_form.setContentsMargins(22, 22, 22, 22)
        media_form.setSpacing(12)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Audio", "Video", "Image"])
        self._field(media_form, "WHAT DO YOU WANT TO DOWNLOAD?", self.mode_combo)
        self.media_panel = self._panel(media_form)
        outer.addWidget(self.media_panel)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a YouTube video or playlist URL")
        url_form = QVBoxLayout()
        url_form.setContentsMargins(22, 22, 22, 22)
        url_form.setSpacing(12)
        self._field(url_form, "YOUTUBE LINK", self.url_input)
        self.inspect_button = QPushButton("Continue  →")
        self.inspect_button.setObjectName("Primary")
        self.inspect_button.clicked.connect(self._inspect_url)
        url_form.addWidget(self.inspect_button)
        self.url_panel = self._panel(url_form)
        self.url_panel.hide()
        outer.addWidget(self.url_panel)

        self.options_panel = self._panel(QVBoxLayout())
        self.options_layout = self.options_panel.layout()
        self.options_layout.setContentsMargins(22, 22, 22, 22)
        self.options_layout.setSpacing(12)
        self.options_panel.hide()
        outer.addWidget(self.options_panel)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)
        outer.addStretch(1)
        self.mode_combo.currentIndexChanged.connect(self._reset_options)
        return page
    def _reset_options(self, *_):
        self.url_panel.hide()
        self.options_panel.hide()
        self.url_input.clear()
        self._clear_layout(self.options_layout)
        self.media_info = None
        self.playlist_items = []
        self.item_checks = []
        self.is_playlist = False
        self.status_label.clear()
        self.url_panel.show()
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget:
                widget.deleteLater()
            elif child:
                self._clear_layout(child)

    def _inspect_url(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "CatWiz", "Paste a YouTube URL first.")
            return
        self.inspect_button.setEnabled(False)
        self.status_label.setText("Checking link…")
        QApplication.processEvents()
        try:
            from catwiz.links import fetch_playlist_info, is_valid_yt_url
            if not is_valid_yt_url(url):
                raise ValueError("That does not look like a supported YouTube URL.")
            if not url.startswith("http"):
                url = "https://" + url
            result = fetch_playlist_info(url)
            if not result or not result[2]:
                raise ValueError("This video or playlist is unavailable or could not be inspected.")
            _, _, items, self.media_info = result
            self.is_playlist = self.media_info.get("_type") == "playlist" or "entries" in self.media_info
            self.playlist_items = items if self.is_playlist else []
            self.current_url = url
            self._build_quality_options()
            detected = f"Playlist detected · {len(items)} items" if self.is_playlist else "Single video detected"
            self.status_label.setText(detected + ". Choose what to download below.")
            self.options_panel.show()
        except Exception as error:
            QMessageBox.warning(self, "Could not inspect link", str(error))
            self.status_label.setText("Check the URL and try again.")
        finally:
            self.inspect_button.setEnabled(True)
    def _build_quality_options(self):
        self._clear_layout(self.options_layout)
        mode = self.mode_combo.currentIndex()
        playlist = self.is_playlist

        if playlist:
            self.options_layout.addWidget(self._eyebrow(f"PLAYLIST ITEMS · {len(self.playlist_items)} FOUND"))
            action_row = QHBoxLayout()
            self.select_all_button = QPushButton("Select all")
            self.select_none_button = QPushButton("Select none")
            action_row.addWidget(self.select_all_button)
            action_row.addWidget(self.select_none_button)
            action_row.addStretch(1)
            self.options_layout.addLayout(action_row)
            self.item_checks = []
            entries = (self.media_info or {}).get("entries") or []
            for index, item_url in enumerate(self.playlist_items):
                entry = entries[index] if index < len(entries) else {}
                title = (entry or {}).get("title") or (entry or {}).get("id") or f"Item {index + 1}"
                check = QCheckBox(f"{index + 1}. {title}")
                check.setChecked(True)
                self.item_checks.append((check, item_url))
                self.options_layout.addWidget(check)
            self.select_all_button.clicked.connect(lambda: [c.setChecked(True) for c, _ in self.item_checks])
            self.select_none_button.clicked.connect(lambda: [c.setChecked(False) for c, _ in self.item_checks])

        if mode == 0:
            self.quality_combo = QComboBox()
            self.quality_combo.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps (Best)"])
            self._field(self.options_layout, "AUDIO BITRATE", self.quality_combo)
        elif mode == 1:
            self.audio_check = QCheckBox("Download audio along with the video")
            self.audio_check.setChecked(True)
            self.options_layout.addWidget(self.audio_check)
            self.video_quality = QComboBox()
            self.video_quality.addItems(self._video_quality_labels())
            self._field(self.options_layout, "VIDEO QUALITY", self.video_quality)
            self.video_quality.currentIndexChanged.connect(self._video_custom_changed)
            self.custom_video = QLineEdit()
            self.custom_video.setPlaceholderText("Custom resolution, e.g. 1920x1080")
            self.custom_video.hide()
            self.options_layout.addWidget(self.custom_video)
        else:
            if playlist:
                self.image_playlist_combo = QComboBox()
                self.image_playlist_combo.addItems(["Every item's thumbnail", "Playlist / album cover art"])
                self._field(self.options_layout, "PLAYLIST IMAGE", self.image_playlist_combo)
            self.image_quality = QComboBox()
            self.image_quality.addItems(self._image_quality_labels())
            self._field(self.options_layout, "IMAGE QUALITY", self.image_quality)
            self.image_quality.currentIndexChanged.connect(self._image_custom_changed)
            self.custom_image = QLineEdit()
            self.custom_image.setPlaceholderText("Custom dimensions, e.g. 1000x1000")
            self.custom_image.hide()
            self.options_layout.addWidget(self.custom_image)

        self.download_button = QPushButton("Download  →")
        self.download_button.setObjectName("Primary")
        self.download_button.clicked.connect(self._start_download)
        self.options_layout.addWidget(self.download_button)

    def _video_quality_labels(self):
        heights = {144, 240, 360, 480, 720, 1080}
        infos = [self.media_info] if isinstance(self.media_info, dict) else []
        for info in infos:
            for fmt in info.get("formats", []):
                if fmt.get("vcodec") != "none" and isinstance(fmt.get("height"), int):
                    heights.add(fmt["height"])
        return [f"{h}p" for h in sorted(heights)] + ["Custom resolution…"]

    def _image_quality_labels(self):
        info = self.media_info or {}
        dims = sorted({
            (t.get("width"), t.get("height"))
            for t in info.get("thumbnails", [])
            if t and t.get("width") and t.get("height")
        }, key=lambda d: d[0] * d[1])
        labels = [f"{w}x{h}" for w, h in dims]
        if not labels:
            labels = ["Standard Quality", "High Quality", "Best Available"]
        return labels + ["Custom dimensions…"]

    def _video_custom_changed(self, index):
        self.custom_video.setVisible(index == self.video_quality.count() - 1)

    def _image_custom_changed(self, index):
        self.custom_image.setVisible(index == self.image_quality.count() - 1)

    def _start_download(self):
        mode = str(self.mode_combo.currentIndex() + 1)
        playlist = self.is_playlist
        selected_items = [url for check, url in self.item_checks if check.isChecked()] if playlist else [self.current_url]
        if not selected_items:
            QMessageBox.information(self, "CatWiz", "Select at least one playlist item.")
            return
        try:
            if mode == "1":
                selected_quality = self.quality_combo.currentText().split()[0]
                if selected_quality == "320":
                    selected_quality = "320"
                else:
                    selected_quality = selected_quality
            elif mode == "2":
                label = self.video_quality.currentText()
                if label == "Custom resolution…":
                    selected_quality = self._parse_dimensions(self.custom_video.text(), even=True)
                    quality_label = f"{selected_quality['width']}x{selected_quality['height']} (Custom)"
                else:
                    height = int(label[:-1])
                    selected_quality = {"type": "requested", "height": height}
                    quality_label = label
                with_audio = self.audio_check.isChecked()
            else:
                label = self.image_quality.currentText()
                if label == "Custom dimensions…":
                    selected_quality = self._parse_dimensions(self.custom_image.text(), even=False)
                    selected_quality["type"] = "custom"
                elif "x" in label:
                    width, height = map(int, label.split("x"))
                    # Match the CLI's thumbnail list by dimensions.
                    thumb = next((t for t in self.media_info.get("thumbnails", []) if t.get("width") == width and t.get("height") == height), None)
                    selected_quality = thumb.get("url") if thumb else "best"
                else:
                    selected_quality = {"Standard Quality": "standard", "High Quality": "hq", "Best Available": "best"}[label]
            self._run_downloads(mode, playlist, selected_items, selected_quality, locals().get("with_audio", True), locals().get("quality_label", ""))
        except ValueError as error:
            QMessageBox.warning(self, "Check quality", str(error))

    def _parse_dimensions(self, value, even=False):
        match = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", value)
        if not match:
            raise ValueError("Enter dimensions as WIDTHxHEIGHT, for example 1920x1080.")
        width, height = map(int, match.groups())
        minimum = 2 if even else 1
        if not (minimum <= width <= 16384 and minimum <= height <= 16384):
            raise ValueError("Dimensions must be between 1 and 16384 pixels.")
        if even and (width % 2 or height % 2):
            raise ValueError("Video dimensions must be even numbers.")
        return {"type": "custom", "width": width, "height": height}

    def _run_downloads(self, mode, playlist, items, quality, with_audio, quality_label):
        """Run the existing CatWiz processing functions with the GUI's selections."""
        self.download_button.setEnabled(False)
        self.status_label.setText("Download started. CatWiz is processing your selection…")
        QApplication.processEvents()
        try:
            from catwiz.downloader import process_single_item, process_thumbnail_only
            save_path = get_category_dir({"1": "audio", "2": "video", "3": "thumbnail"}[mode])
            results = []
            total = len(items)
            if mode == "3" and playlist and getattr(self, "image_playlist_combo", None) and self.image_playlist_combo.currentIndex() == 1:
                process_thumbnail_only(self.current_url, False, 1, 1, save_path, quality, pre_info=self.media_info)
                results = [True]
            else:
                for index, item_url in enumerate(items, 1):
                    if mode == "3":
                        result = process_thumbnail_only(item_url, playlist, index, total, save_path, quality, pre_info=self.media_info if not playlist else None)
                    else:
                        result = process_single_item(item_url, mode, playlist, index, total, save_path, quality, pre_info=self.media_info if not playlist else None, with_audio=with_audio, quality_label=quality_label)
                    results.append(bool(result))
            saved = sum(results)
            QMessageBox.information(self, "CatWiz", f"Finished: {saved} of {total if not (mode == '3' and playlist and getattr(self, 'image_playlist_combo', None) and self.image_playlist_combo.currentIndex() == 1) else 1} saved.")
            self.status_label.setText("Download finished.")
        except Exception as error:
            QMessageBox.warning(self, "Download failed", "CatWiz could not complete the selected download. Check Logs for details.")
            try:
                from catwiz.logging_service import component_logger
                component_logger("gui").exception("GUI download workflow failed")
            except Exception:
                pass
            self.status_label.setText("Download failed. See Logs for details.")
        finally:
            self.download_button.setEnabled(True)

    def _downloads_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._heading("Downloads", "Downloads run through CatWiz's existing media engine."))
        panel = QVBoxLayout()
        panel.setContentsMargins(24, 24, 24, 24)
        note = QLabel("Start a download from Home. Completed files are saved in your configured CatWiz folders.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        panel.addWidget(note)
        layout.addWidget(self._panel(panel), 1)
        return page

    def _logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._heading("Logs", "Review CatWiz activity and technical diagnostics stored locally."))
        controls = QHBoxLayout()
        self.log_type = QComboBox()
        self.log_type.addItems(["Activity", "Diagnostics", "Errors", "Archived history"])
        self.log_type.currentIndexChanged.connect(self._refresh_logs)
        self.log_search = QLineEdit()
        self.log_search.setPlaceholderText("Search log messages…")
        self.log_search.textChanged.connect(self._refresh_logs)
        self.log_level = QComboBox()
        self.log_level.addItems(["All levels", "Info", "Warning", "Error", "Debug"])
        self.log_level.currentIndexChanged.connect(self._refresh_logs)
        controls.addWidget(self.log_type)
        controls.addWidget(self.log_level)
        controls.addWidget(self.log_search, 1)
        layout.addLayout(controls)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.log_view, 1)
        actions = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_logs)
        folder = QPushButton("Open Log Folder")
        folder.clicked.connect(self._open_log_folder)
        errors = QPushButton("Export Errors")
        errors.clicked.connect(lambda: self._export_logs("errors"))
        full = QPushButton("Export Full Diagnostics")
        full.setObjectName("Primary")
        full.clicked.connect(lambda: self._export_logs("full"))
        actions.addWidget(refresh)
        actions.addWidget(folder)
        actions.addStretch(1)
        actions.addWidget(errors)
        actions.addWidget(full)
        layout.addLayout(actions)
        self._refresh_logs()
        return page

    def _refresh_logs(self, *_):
        from catwiz.logging_service import get_log_paths, get_logger
        get_logger()
        paths = get_log_paths()
        index = self.log_type.currentIndex()
        if index == 3:
            lines = []
            try:
                for name in sorted(os.listdir(paths["archive"]), reverse=True):
                    if name.startswith(("activity.log.", "diagnostics.log.", "errors.log.")):
                        with open(os.path.join(paths["archive"], name), "r", encoding="utf-8", errors="replace") as stream:
                            lines.extend(stream.readlines())
            except OSError:
                pass
            lines = lines[-3000:]
        else:
            key = ("activity", "diagnostics", "errors")[index]
            try:
                with open(paths[key], "r", encoding="utf-8", errors="replace") as stream:
                    lines = stream.readlines()[-1500:]
            except OSError:
                lines = []
        query = self.log_search.text().strip().lower()
        level = self.log_level.currentText().upper()
        if level == "ALL LEVELS":
            level = ""
        visible = [line.rstrip() for line in lines if (not query or query in line.lower()) and (not level or (" " + level) in line)]
        self.log_view.setPlainText("\n".join(visible) if visible else "No matching log entries.")
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _open_log_folder(self):
        from catwiz.logging_service import get_log_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(get_log_dir()))

    def _export_logs(self, kind):
        try:
            from catwiz.logging_export import export_diagnostics
            path = export_diagnostics(kind)
            QMessageBox.information(self, "Diagnostic export created", f"Saved locally to:\n{path}")
        except (OSError, ValueError):
            QMessageBox.warning(self, "Export failed", "CatWiz could not create the diagnostic export.")

    def _settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._heading("Settings", "Configure the same CatWiz preferences used by the terminal version."))
        panel = QVBoxLayout()
        panel.setContentsMargins(22, 22, 22, 22)
        panel.setSpacing(16)
        panel.addWidget(self._eyebrow("DOWNLOAD LOCATION"))
        row = QHBoxLayout()
        self.path_input = QLineEdit(get_download_dir())
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_folder)
        row.addWidget(self.path_input, 1)
        row.addWidget(browse)
        panel.addLayout(row)
        self.auto_update = QCheckBox("Check for updates when CatWiz starts")
        self.auto_update.setChecked(get_auto_update_check())
        panel.addWidget(self.auto_update)
        save = QPushButton("Save settings")
        save.setObjectName("Primary")
        save.clicked.connect(self._save_settings)
        panel.addWidget(save)
        layout.addWidget(self._panel(panel))
        layout.addStretch(1)
        return page

    def _navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose download folder", self.path_input.text())
        if folder:
            self.path_input.setText(folder)

    def _save_settings(self):
        try:
            folder = os.path.abspath(os.path.expanduser(os.path.expandvars(self.path_input.text().strip())))
            if not folder:
                raise ValueError("Choose a download folder.")
            os.makedirs(folder, exist_ok=True)
            set_download_dir(folder)
            set_auto_update_check(self.auto_update.isChecked())
            QMessageBox.information(self, "CatWiz", "Settings saved.")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Could not save settings", str(error))


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = CatWizWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
