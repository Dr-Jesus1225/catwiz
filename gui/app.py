"""Initial PySide6 desktop shell for CatWiz."""

import os
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget, QCheckBox, QTextEdit
)

from catwiz.system import get_download_dir, set_download_dir, get_auto_update_check, set_auto_update_check


STYLESHEET = """
QWidget { background: #101319; color: #e8ebf2; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; }
QFrame#Sidebar { background: #171c24; border-right: 1px solid #29313d; }
QLabel#Brand { font-size: 23px; font-weight: 800; color: #ffffff; padding: 8px 4px 22px; }
QLabel#Eyebrow { color: #8c9aaf; font-size: 11px; font-weight: 700; }
QLabel#Heading { font-size: 26px; font-weight: 750; color: #ffffff; }
QLabel#Subheading { color: #9aa6b8; font-size: 13px; }
QFrame#Panel { background: #191f29; border: 1px solid #2a3442; border-radius: 13px; }
QPushButton { background: #242d3a; border: 1px solid #344154; border-radius: 8px; padding: 10px 14px; text-align: left; }
QPushButton:hover { background: #303c4d; }
QPushButton#Primary { background: #e34b66; color: white; border: 0; font-weight: 700; padding: 12px 18px; }
QPushButton#Primary:hover { background: #f05b75; }
QPushButton#Nav { background: transparent; border: 0; color: #aeb9c9; padding: 11px 13px; }
QPushButton#Nav:checked { background: #293342; color: #ffffff; font-weight: 700; }
QLineEdit, QComboBox { background: #10151d; border: 1px solid #354153; border-radius: 8px; padding: 11px; selection-background-color: #e34b66; }
QCheckBox { spacing: 9px; }
QLabel#Muted { color: #9aa6b8; }
"""


class CatWizWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CatWiz")
        self.resize(1080, 700)
        self.setMinimumSize(850, 580)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("◈  CatWiz")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        side.addWidget(self._eyebrow("WORKSPACE"))
        self.nav_buttons = []
        self.stack = QStackedWidget()
        for label, page in (("⌂   Home", self._home_page()), ("⇩   Downloads", self._downloads_page()), ("▤   Logs", self._logs_page()), ("⚙   Settings", self._settings_page())):
            button = QPushButton(label)
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, idx=len(self.nav_buttons): self._navigate(idx))
            side.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)
        side.addStretch(1)
        side.addWidget(self._eyebrow("DESKTOP EDITION"))
        side.addWidget(QLabel("GUI preview · CLI preserved"))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 28, 34, 24)
        content_layout.addWidget(self.stack)
        layout.addWidget(sidebar)
        layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self._navigate(0)

    def _eyebrow(self, text):
        label = QLabel(text)
        label.setObjectName("Eyebrow")
        return label

    def _heading(self, title, subtitle):
        box = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("Heading")
        sub = QLabel(subtitle)
        sub.setObjectName("Subheading")
        box.addWidget(title_label)
        box.addWidget(sub)
        return box

    def _panel(self, layout):
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setLayout(layout)
        return frame

    def _home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.addLayout(self._heading("Download media", "Paste a YouTube link and choose what you want CatWiz to save."))

        form = QVBoxLayout()
        form.setContentsMargins(22, 22, 22, 22)
        form.setSpacing(14)
        form.addWidget(self._eyebrow("YOUTUBE URL"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        form.addWidget(self.url_input)
        form.addWidget(self._eyebrow("DOWNLOAD TYPE"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Audio · MP3", "Video · MP4", "Thumbnail · PNG"])
        form.addWidget(self.mode_combo)
        row = QHBoxLayout()
        self.playlist_check = QCheckBox("This is a playlist")
        row.addWidget(self.playlist_check)
        row.addStretch(1)
        form.addLayout(row)
        form.addWidget(self._eyebrow("QUALITY"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Best available", "320 kbps / 1080p", "256 kbps / 720p", "192 kbps / 480p", "128 kbps / 360p"])
        form.addWidget(self.quality_combo)
        self.download_button = QPushButton("Download  →")
        self.download_button.setObjectName("Primary")
        self.download_button.clicked.connect(self._download_placeholder)
        form.addWidget(self.download_button)
        layout.addWidget(self._panel(form))

        info = QHBoxLayout()
        for title, desc in (("Audio", "MP3 quality choices"), ("Video", "Native and custom resolutions"), ("Playlists", "Choose or skip individual items")):
            card = QVBoxLayout()
            h = QLabel(title); h.setStyleSheet("font-size:16px;font-weight:700")
            d = QLabel(desc); d.setObjectName("Muted"); d.setWordWrap(True)
            card.addWidget(h); card.addWidget(d)
            info.addWidget(self._panel(card), 1)
        layout.addLayout(info)
        layout.addStretch(1)
        return page

    def _downloads_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._heading("Downloads", "Your active and completed downloads will appear here."))
        panel = QVBoxLayout()
        panel.setContentsMargins(24, 24, 24, 24)
        title = QLabel("No downloads yet")
        title.setStyleSheet("font-size:18px;font-weight:700")
        note = QLabel("The download queue and live progress will be connected to CatWiz's existing downloader in the next implementation step.")
        note.setObjectName("Muted"); note.setWordWrap(True)
        panel.addStretch(1); panel.addWidget(title, alignment=Qt.AlignHCenter); panel.addWidget(note, alignment=Qt.AlignHCenter); panel.addStretch(1)
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
                archived = sorted(os.listdir(paths["archive"]), reverse=True)
                for name in archived:
                    if name.endswith(".log"):
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
        visible = [
            line.rstrip() for line in lines
            if (not query or query in line.lower())
            and (not level or (" " + level) in line)
        ]
        self.log_view.setPlainText("\n".join(visible) if visible else "No matching log entries.")
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _open_log_folder(self):
        from catwiz.logging_service import get_log_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(get_log_dir()))

    def _export_logs(self, kind):
        try:
            from catwiz.logging_export import export_diagnostics
            path = export_diagnostics(kind)
            QMessageBox.information(self, "Diagnostic export created", f"Saved locally to:\n{path}")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Export failed", "CatWiz could not create the diagnostic export.")

    def _settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self._heading("Settings", "Configure the same CatWiz preferences used by the terminal version."))
        panel = QVBoxLayout()
        panel.setContentsMargins(22, 22, 22, 22)
        panel.setSpacing(16)
        panel.addWidget(self._eyebrow("DOWNLOAD LOCATION"))
        path_row = QHBoxLayout()
        self.path_input = QLineEdit(get_download_dir())
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_folder)
        path_row.addWidget(self.path_input, 1); path_row.addWidget(browse)
        panel.addLayout(path_row)
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

    def _download_placeholder(self):
        QMessageBox.information(self, "Download workflow", "The GUI layout is in place. The next step is connecting URL inspection, playlist selection, quality selection and background downloads to CatWiz's existing engine.")


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = CatWizWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
