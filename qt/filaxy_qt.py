#!/usr/bin/env python3
"""
Filaxy PDF Converter — cross-platform desktop UI (PySide6 / Qt).

Runs on Windows, macOS and Linux and reuses the SAME engine as the native macOS
app (engine/coordmap.py + verification). High-fidelity PDF → Word (.docx) with a
fidelity report. The native SwiftUI app stays the premium macOS build; this Qt
app brings the product to Windows (and Linux) from one Python codebase.
"""
from __future__ import annotations
import os
import sys
import subprocess

# Make the project's `engine` package importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point Qt at PySide6's bundled platform plugins (needed when launched from a
# minimal environment / venv; harmless under PyInstaller which sets its own).
import PySide6  # noqa: E402
os.environ.setdefault(
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    os.path.join(os.path.dirname(PySide6.__file__), "Qt", "plugins", "platforms"),
)

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFileDialog, QFrame, QSizePolicy,
)

RED = "#E2231A"
RED_DARK = "#C01810"
PINK = "#FCEAEA"
GREEN = "#2B9A4E"
ORANGE = "#E08A1E"

APP_TITLE = "Filaxy PDF Converter"


# ----------------------------------------------------------------------------- worker
class ConvertWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, src: str, dest: str):
        super().__init__()
        self.src, self.dest = src, dest

    def run(self):
        try:
            from engine.cli import run
            self.finished_ok.emit(run(self.src, self.dest))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


# ----------------------------------------------------------------------------- drop zone
class DropZone(QFrame):
    picked = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("drop")
        self.setMinimumHeight(220)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        icon = QLabel("⬇")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 44px; color: #B9410E;")
        self.title = QLabel("Drag a PDF here")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 18px; color: #222;")
        hint = QLabel("or click to choose")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 12px; color: #888;")
        for w in (icon, self.title, hint):
            lay.addWidget(w)
        self._reset_style()

    def _reset_style(self, active=False):
        color = RED if active else "#C9C9C9"
        self.setStyleSheet(
            f"#drop {{ border: 2px dashed {color}; border-radius: 16px;"
            f" background: {'#FFF4F2' if active else 'transparent'}; }}")

    def mousePressEvent(self, _):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a PDF", "", "PDF files (*.pdf)")
        if path:
            self.picked.emit(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and self._is_pdf(e):
            e.acceptProposedAction()
            self._reset_style(active=True)

    def dragLeaveEvent(self, _):
        self._reset_style(active=False)

    def dropEvent(self, e):
        self._reset_style(active=False)
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".pdf"):
                self.picked.emit(p)
                return

    @staticmethod
    def _is_pdf(e):
        return any(u.toLocalFile().lower().endswith(".pdf") for u in e.mimeData().urls())


# ----------------------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(780, 580)
        self.pdf_path = None
        self.out_path = None
        self.worker = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.stack.addWidget(self._build_home())     # 0
        self.stack.addWidget(self._build_working())  # 1
        self.stack.addWidget(self._build_result())   # 2
        self.setStyleSheet("QMainWindow { background: #FFFFFF; }")

    # ---- pages
    def _header(self):
        h = QWidget()
        lay = QHBoxLayout(h)
        lay.setContentsMargins(18, 14, 18, 8)
        logo = QLabel("📄")
        logo.setStyleSheet("font-size: 20px;")
        name = QLabel(f"<b>{APP_TITLE}</b>  <span style='color:#999'>1.0</span>")
        brand = QLabel("<span style='color:#bbb'>Filaxy Labs</span>")
        lay.addWidget(logo); lay.addWidget(name); lay.addStretch(); lay.addWidget(brand)
        return h

    def _build_home(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(self._header())
        body = QWidget(); bl = QVBoxLayout(body); bl.setContentsMargins(28, 8, 28, 28)
        self.drop = DropZone()
        self.drop.picked.connect(self._on_picked)
        bl.addWidget(self.drop)
        self.convert_btn = QPushButton("Convert to Word")
        self.convert_btn.setEnabled(False)
        self.convert_btn.setCursor(Qt.PointingHandCursor)
        self.convert_btn.clicked.connect(self._start_convert)
        self.convert_btn.setStyleSheet(self._primary_btn_css())
        bl.addSpacing(10)
        bl.addWidget(self.convert_btn, alignment=Qt.AlignCenter)
        lay.addWidget(body); lay.addStretch()
        lay.addWidget(self._footer())
        return w

    def _build_working(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setAlignment(Qt.AlignCenter)
        self.working_label = QLabel("Converting and verifying fidelity…")
        self.working_label.setAlignment(Qt.AlignCenter)
        self.working_label.setStyleSheet("font-size: 16px; color: #444;")
        lay.addWidget(self.working_label)
        return w

    def _build_result(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(28, 24, 28, 24)
        self.ring = QLabel("100%")
        self.ring.setAlignment(Qt.AlignCenter)
        self.ring.setFixedSize(130, 130)
        self.ring.setStyleSheet(self._ring_css(GREEN))
        ring_row = QHBoxLayout(); ring_row.addStretch(); ring_row.addWidget(self.ring); ring_row.addStretch()
        lay.addLayout(ring_row)
        self.verdict = QLabel("Faithful, verified conversion")
        self.verdict.setAlignment(Qt.AlignCenter)
        self.verdict.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {GREEN}; margin: 6px;")
        lay.addWidget(self.verdict)

        self.metrics_box = QVBoxLayout()
        lay.addLayout(self.metrics_box)
        lay.addStretch()

        btns = QHBoxLayout(); btns.addStretch()
        self.again_btn = QPushButton("Convert another"); self.again_btn.clicked.connect(self._reset)
        self.reveal_btn = QPushButton("Show in folder"); self.reveal_btn.clicked.connect(self._reveal)
        self.open_btn = QPushButton("Open in Word"); self.open_btn.clicked.connect(self._open_out)
        self.open_btn.setStyleSheet(self._primary_btn_css())
        for b in (self.again_btn, self.reveal_btn, self.open_btn):
            b.setCursor(Qt.PointingHandCursor); btns.addWidget(b)
        btns.addStretch()
        lay.addLayout(btns)
        self.meta = QLabel(""); self.meta.setAlignment(Qt.AlignCenter)
        self.meta.setStyleSheet("font-size: 11px; color: #aaa;")
        lay.addWidget(self.meta)
        return w

    def _footer(self):
        f = QLabel("  PDF → Word, faithful and verified")
        f.setStyleSheet("color:#bbb; font-size:11px; padding:6px 14px; border-top:1px solid #eee;")
        return f

    # ---- behavior
    def _on_picked(self, path):
        self.pdf_path = path
        self.drop.title.setText(os.path.basename(path))
        self.convert_btn.setEnabled(True)

    def _start_convert(self):
        if not self.pdf_path:
            return
        suggested = os.path.splitext(os.path.basename(self.pdf_path))[0] + ".docx"
        dest, _ = QFileDialog.getSaveFileName(self, "Save Word document", suggested, "Word document (*.docx)")
        if not dest:
            return
        self.out_path = dest
        self.stack.setCurrentIndex(1)
        self.worker = ConvertWorker(self.pdf_path, dest)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _on_done(self, r: dict):
        passed = r.get("passed", False)
        color = GREEN if passed else ORANGE
        f = r["fidelity"]
        self.ring.setText(f"{int(round(f['text_score']))}%")
        self.ring.setStyleSheet(self._ring_css(color))
        self.verdict.setText("Faithful, verified conversion" if passed else "Review recommended")
        self.verdict.setStyleSheet(f"font-size:16px; font-weight:600; color:{color}; margin:6px;")
        # metrics
        while self.metrics_box.count():
            item = self.metrics_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = [
            ("Original text present", "Complete" if f["text_score"] >= 99.5 else f"{int(f['text_score'])}%", f["text_score"] >= 98),
            ("Sensitive data (numbers/dates/emails)", "All verified" if not f["sensitive_issues"] else f"{len(f['sensitive_issues'])} to review", not f["sensitive_issues"]),
            ("Fonts legible in Word", "Verified" if r["layout"]["passed"] else "Review", r["layout"]["passed"]),
            ("Original graphics (layout, logos, stamps)", "Preserved" if f["images"]["match"] else "Review", f["images"]["match"]),
        ]
        for label, value, ok in rows:
            self.metrics_box.addWidget(self._metric_row(label, value, ok))
        self.meta.setText(f"{r['pages']} page(s) · {r['elapsed_s']}s")
        self.stack.setCurrentIndex(2)

    def _on_fail(self, msg):
        self.working_label.setText(f"Conversion failed:\n{msg}")

    def _metric_row(self, label, value, ok):
        row = QFrame(); row.setStyleSheet("background:#F6F6F6; border-radius:8px;")
        lay = QHBoxLayout(row); lay.setContentsMargins(12, 9, 12, 9)
        tick = QLabel("✓" if ok else "✕")
        tick.setStyleSheet(f"color:{GREEN if ok else ORANGE}; font-weight:bold;")
        name = QLabel(label)
        val = QLabel(value); val.setStyleSheet("color:#888;")
        lay.addWidget(tick); lay.addWidget(name); lay.addStretch(); lay.addWidget(val)
        return row

    def _reset(self):
        self.pdf_path = None; self.out_path = None
        self.drop.title.setText("Drag a PDF here")
        self.convert_btn.setEnabled(False)
        self.stack.setCurrentIndex(0)

    def _open_out(self):
        if self.out_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.out_path))

    def _reveal(self):
        if not self.out_path:
            return
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", self.out_path])
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", "/select,", os.path.normpath(self.out_path)])
        else:
            subprocess.run(["xdg-open", os.path.dirname(self.out_path)])

    # ---- styles
    @staticmethod
    def _primary_btn_css():
        return (f"QPushButton {{ background:{RED}; color:white; border:none; border-radius:8px;"
                f" padding:9px 22px; font-weight:600; }}"
                f" QPushButton:hover {{ background:{RED_DARK}; }}"
                f" QPushButton:disabled {{ background:#E9B8B4; }}")

    @staticmethod
    def _ring_css(color):
        return (f"QLabel {{ border:10px solid {color}; border-radius:65px;"
                f" font-size:30px; font-weight:bold; color:#222; background:white; }}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    QApplication.setFont(QFont("Segoe UI" if sys.platform.startswith("win") else "Helvetica Neue", 13))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
