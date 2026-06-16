#!/usr/bin/env python3
"""
Filaxy PDF Converter — cross-platform desktop UI (PySide6 / Qt).

Runs on Windows, macOS and Linux and reuses the SAME engine as the native macOS
app (engine/coordmap.py + verification). Mirrors the macOS app's chrome: a menu
row (File / How it works / About · Appearance · Language), live ES/EN, light/dark
themes, drag-&-drop, and a fidelity report. The native SwiftUI app stays the
premium macOS build; this Qt app brings the product to Windows (and Linux).
"""
from __future__ import annotations
import os
import sys
import subprocess

# Make the project's `engine` package importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point Qt at PySide6's bundled platform plugins (needed from a minimal env;
# harmless under PyInstaller which sets its own).
import PySide6  # noqa: E402
os.environ.setdefault(
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    os.path.join(os.path.dirname(PySide6.__file__), "Qt", "plugins", "platforms"),
)

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QSettings, QLocale
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QToolButton, QStackedWidget, QFileDialog, QFrame, QMenu,
    QButtonGroup, QDialog, QSizePolicy,
)

USDT_TRC20 = "TBzBitnntNvsnuP5XBwi3FhjDpVf5487sx"
PAYPAL_URL = "https://www.paypal.com/ncp/payment/ALUEC9LDLGZ3L"
GREEN, ORANGE, RED, PINK = "#2B9A4E", "#E08A1E", "#E2231A", "#FF4D4D"

# --------------------------------------------------------------------------- i18n
TR = {
    "en": {
        "subtitle": "PDF → Word, faithful and verified",
        "drop": "Drag a PDF here", "drop_hint": "or click to choose",
        "ready": "Ready to convert", "convert": "Convert to Word",
        "working": "Converting and verifying fidelity…",
        "menu_file": "File", "open": "Open PDF…", "reveal": "Show result in folder",
        "howto": "How it works", "about": "About",
        "appearance": "Appearance", "language": "Language",
        "light": "Light", "auto": "Auto", "dark": "Dark",
        "verdict_ok": "Faithful, verified conversion", "verdict_review": "Review recommended",
        "m_text": "Original text present", "m_text_v": "Complete",
        "m_sens": "Sensitive data (numbers/dates/emails)", "m_sens_v": "All verified", "m_sens_r": "to review",
        "m_font": "Fonts legible in Word", "m_font_v": "Verified", "m_font_r": "Review",
        "m_graph": "Original graphics (layout, logos, stamps)", "m_graph_v": "Preserved", "m_graph_r": "Review",
        "again": "Convert another", "show": "Show in folder", "openw": "Open in Word",
        "save_title": "Save Word document", "close": "Close",
        "about_tag": "A Filaxy Labs product · Free",
        "about_body": "Converts PDF to Word preserving images, positions, fonts and signatures — and verifies fidelity against the original.",
        "howto_body": "1. Drag a PDF onto the window or click to choose one.\n2. Filaxy rebuilds each page: the original graphics (borders, logos, stamps, signatures) are preserved exactly and the text sits editable on top, in its original font and coordinates.\n3. Choose where to save the .docx.\n4. The app verifies the result against the original PDF: text present, sensitive data, legible fonts and preserved graphics.\n\nEverything runs locally and private — nothing leaves your computer.",
        "donate_h": "Support the project",
        "donate_b": "Filaxy PDF Converter is free. If it helped you and you'd like to support more free apps, you can make a voluntary, optional donation.",
        "donate_pp": "Donate with PayPal", "donate_usdt": "USDT (TRC20)",
        "copy": "Copy", "copied": "Copied!",
        "usdt_warn": "⚠ Send only USDT on the TRON network (TRC20). Another network = loss of funds.",
        "fail": "Conversion failed:",
    },
    "es": {
        "subtitle": "PDF → Word, fiel y verificado",
        "drop": "Arrastrá un PDF aquí", "drop_hint": "o hacé clic para elegir",
        "ready": "Listo para convertir", "convert": "Convertir a Word",
        "working": "Convirtiendo y verificando fidelidad…",
        "menu_file": "Archivo", "open": "Abrir PDF…", "reveal": "Mostrar resultado en carpeta",
        "howto": "Cómo funciona", "about": "Acerca de",
        "appearance": "Apariencia", "language": "Idioma",
        "light": "Clara", "auto": "Auto", "dark": "Oscura",
        "verdict_ok": "Conversión fiel y verificada", "verdict_review": "Revisión recomendada",
        "m_text": "Texto del original presente", "m_text_v": "Completo",
        "m_sens": "Datos sensibles (números/fechas/correos)", "m_sens_v": "Todos verificados", "m_sens_r": "por revisar",
        "m_font": "Fuentes legibles en Word", "m_font_v": "Verificadas", "m_font_r": "Revisar",
        "m_graph": "Gráficos del original (diseño, logos, sellos)", "m_graph_v": "Preservados", "m_graph_r": "Revisar",
        "again": "Convertir otro", "show": "Mostrar en carpeta", "openw": "Abrir en Word",
        "save_title": "Guardar documento de Word", "close": "Cerrar",
        "about_tag": "Un producto de Filaxy Labs · Gratis",
        "about_body": "Convierte PDF a Word conservando imágenes, posiciones, fuentes y firmas — y verifica la fidelidad contra el original.",
        "howto_body": "1. Arrastrá un PDF a la ventana o hacé clic para elegirlo.\n2. Filaxy reconstruye cada página: los gráficos del original (bordes, logos, sellos, firmas) se preservan exactos y el texto queda editable encima, en su fuente y coordenadas originales.\n3. Elegí dónde guardar el .docx.\n4. La app verifica el resultado contra el PDF original: texto presente, datos sensibles, fuentes legibles y gráficos preservados.\n\nTodo corre local y privado — nada sale de tu computadora.",
        "donate_h": "Apoyá el proyecto",
        "donate_b": "Filaxy PDF Converter es gratis. Si te sirvió y querés apoyar más apps gratuitas, podés hacer una donación voluntaria y opcional.",
        "donate_pp": "Donar con PayPal", "donate_usdt": "USDT (TRC20)",
        "copy": "Copiar", "copied": "¡Copiado!",
        "usdt_warn": "⚠ Enviá solo USDT por la red TRON (TRC20). Otra red = pérdida de fondos.",
        "fail": "La conversión falló:",
    },
}


def qss(dark: bool) -> str:
    bg = "#1F1F22" if dark else "#FFFFFF"
    fg = "#ECECEC" if dark else "#1A1A1A"
    sub = "#9A9A9A" if dark else "#888888"
    card = "#2A2A2E" if dark else "#F4F4F5"
    line = "#3A3A3E" if dark else "#E6E6E6"
    seg = "#2A2A2E" if dark else "#EFEFF1"
    return f"""
    QMainWindow, QDialog {{ background: {bg}; }}
    QLabel {{ color: {fg}; }}
    #sub, #brand, #hint, #meta {{ color: {sub}; }}
    #menubar {{ background: {bg}; border-bottom: 1px solid {line}; }}
    #footer {{ color: {sub}; border-top: 1px solid {line}; }}
    QPushButton#menuBtn, QToolButton#menuBtn {{
        color: {fg}; background: transparent; border: none; border-radius: 6px;
        padding: 6px 10px; }}
    QPushButton#menuBtn:hover, QToolButton#menuBtn:hover {{ background: {card}; }}
    QToolButton#seg {{ color: {fg}; background: {seg}; border: none; padding: 5px 9px; }}
    QToolButton#seg:checked {{ background: #3B82F6; color: white; }}
    QToolButton#seg:first {{ border-top-left-radius: 7px; border-bottom-left-radius: 7px; }}
    QToolButton#seg:last  {{ border-top-right-radius: 7px; border-bottom-right-radius: 7px; }}
    QPushButton#primary {{ background: #3B82F6; color: white; border: none; border-radius: 8px;
        padding: 9px 22px; font-weight: 600; }}
    QPushButton#primary:hover {{ background: #2D6FE0; }}
    QPushButton#primary:disabled {{ background: {('#3A4A66' if dark else '#BBD3F7')}; color: #ddd; }}
    QPushButton#ghost {{ background: {card}; color: {fg}; border: 1px solid {line};
        border-radius: 8px; padding: 8px 16px; }}
    QPushButton#ghost:hover {{ background: {seg}; }}
    #metric {{ background: {card}; border-radius: 8px; }}
    #drop[active="false"] {{ border: 2px dashed {('#4A4A4E' if dark else '#C9C9C9')}; border-radius: 16px; }}
    #drop[active="true"]  {{ border: 2px dashed #3B82F6; border-radius: 16px;
        background: {('#22304A' if dark else '#F0F6FF')}; }}
    #addr {{ background: {card}; border-radius: 6px; padding: 6px 8px; color: {fg};
        font-family: Consolas, Menlo, monospace; }}
    """


# --------------------------------------------------------------------------- worker
class ConvertWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, src, dest):
        super().__init__()
        self.src, self.dest = src, dest

    def run(self):
        try:
            from engine.cli import run
            self.finished_ok.emit(run(self.src, self.dest))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


# --------------------------------------------------------------------------- drop zone
class DropZone(QFrame):
    picked = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("drop")
        self.setProperty("active", "false")
        self.setMinimumHeight(210)
        lay = QVBoxLayout(self); lay.setAlignment(Qt.AlignCenter)
        self.icon = QLabel("⬇"); self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setStyleSheet("font-size: 40px; color: #3B82F6;")
        self.title = QLabel(); self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 18px;")
        self.hint = QLabel(); self.hint.setObjectName("hint"); self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("font-size: 12px;")
        for x in (self.icon, self.title, self.hint):
            lay.addWidget(x)

    def _set_active(self, a):
        self.setProperty("active", "true" if a else "false")
        self.style().unpolish(self); self.style().polish(self)

    def mousePressEvent(self, _):
        p, _ = QFileDialog.getOpenFileName(self, "PDF", "", "PDF files (*.pdf)")
        if p:
            self.picked.emit(p)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".pdf") for u in e.mimeData().urls()):
            e.acceptProposedAction(); self._set_active(True)

    def dragLeaveEvent(self, _):
        self._set_active(False)

    def dropEvent(self, e):
        self._set_active(False)
        for u in e.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.picked.emit(u.toLocalFile()); return


# --------------------------------------------------------------------------- dialogs
class AboutDialog(QDialog):
    def __init__(self, parent, t):
        super().__init__(parent)
        self.setWindowTitle(t["about"]); self.setMinimumWidth(420)
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(28, 24, 28, 20)
        logo = QLabel("📄"); logo.setAlignment(Qt.AlignCenter); logo.setStyleSheet("font-size:40px;")
        title = QLabel("<b style='font-size:18px'>Filaxy PDF Converter</b>"); title.setAlignment(Qt.AlignCenter)
        tag = QLabel(t["about_tag"]); tag.setObjectName("sub"); tag.setAlignment(Qt.AlignCenter)
        body = QLabel(t["about_body"]); body.setWordWrap(True); body.setAlignment(Qt.AlignCenter); body.setObjectName("sub")
        for x in (logo, title, tag, body):
            lay.addWidget(x)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setObjectName("footer"); lay.addWidget(sep)
        dh = QLabel(f"❤  <b>{t['donate_h']}</b>"); dh.setAlignment(Qt.AlignCenter); dh.setStyleSheet(f"color:{PINK};")
        db = QLabel(t["donate_b"]); db.setWordWrap(True); db.setAlignment(Qt.AlignCenter); db.setObjectName("sub")
        lay.addWidget(dh); lay.addWidget(db)
        pp = QPushButton(t["donate_pp"]); pp.setObjectName("primary"); pp.setCursor(Qt.PointingHandCursor)
        pp.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PAYPAL_URL)))
        lay.addWidget(pp)
        usdt_lbl = QLabel(f"<b>{t['donate_usdt']}</b>"); lay.addWidget(usdt_lbl)
        row = QHBoxLayout()
        addr = QLabel(USDT_TRC20); addr.setObjectName("addr"); addr.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._copy = QPushButton(t["copy"]); self._copy.setObjectName("ghost"); self._copy.setCursor(Qt.PointingHandCursor)
        self._copy_label = t
        self._copy.clicked.connect(self._do_copy)
        row.addWidget(addr, 1); row.addWidget(self._copy); lay.addLayout(row)
        warn = QLabel(t["usdt_warn"]); warn.setWordWrap(True); warn.setStyleSheet(f"color:{ORANGE}; font-size:11px;")
        lay.addWidget(warn)
        close = QPushButton(t["close"]); close.setObjectName("ghost"); close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignCenter)

    def _do_copy(self):
        QGuiApplication.clipboard().setText(USDT_TRC20)
        self._copy.setText(self._copy_label["copied"])


class HowToDialog(QDialog):
    def __init__(self, parent, t):
        super().__init__(parent)
        self.setWindowTitle(t["howto"]); self.setMinimumWidth(480)
        lay = QVBoxLayout(self); lay.setContentsMargins(28, 24, 28, 20); lay.setSpacing(12)
        title = QLabel(f"<b style='font-size:17px'>✦ {t['howto']}</b>"); lay.addWidget(title)
        body = QLabel(t["howto_body"]); body.setWordWrap(True); body.setObjectName("sub"); lay.addWidget(body)
        close = QPushButton(t["close"]); close.setObjectName("ghost"); close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignRight)


# --------------------------------------------------------------------------- main
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("FilaxyLabs", "FilaxyPDFConverter")
        self.lang = self.settings.value("lang") or ("es" if QLocale.system().name().startswith("es") else "en")
        self.theme = self.settings.value("theme") or "light"
        self.pdf_path = self.out_path = self.worker = None

        self.resize(800, 600)
        root = QWidget(); self.setCentralWidget(root)
        self.vmain = QVBoxLayout(root); self.vmain.setContentsMargins(0, 0, 0, 0); self.vmain.setSpacing(0)
        self.vmain.addWidget(self._build_header())
        self.vmain.addWidget(self._build_menubar())
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_home()); self.stack.addWidget(self._build_working()); self.stack.addWidget(self._build_result())
        self.vmain.addWidget(self.stack, 1)
        self.vmain.addWidget(self._build_footer())

        self.retranslate(); self.apply_theme()

    # ---- chrome
    def _build_header(self):
        h = QWidget(); lay = QHBoxLayout(h); lay.setContentsMargins(18, 12, 18, 6)
        logo = QLabel("📄"); logo.setStyleSheet("font-size:18px;")
        self.h_title = QLabel("<b>Filaxy PDF Converter</b> <span style='color:#999'>1.0</span>")
        self.h_brand = QLabel("Filaxy Labs"); self.h_brand.setObjectName("brand")
        lay.addWidget(logo); lay.addWidget(self.h_title); lay.addStretch(); lay.addWidget(self.h_brand)
        return h

    def _build_menubar(self):
        bar = QWidget(); bar.setObjectName("menubar")
        lay = QHBoxLayout(bar); lay.setContentsMargins(12, 6, 12, 6); lay.setSpacing(6)
        # File dropdown
        self.file_btn = QToolButton(); self.file_btn.setObjectName("menuBtn")
        self.file_btn.setPopupMode(QToolButton.InstantPopup)
        self.file_menu = QMenu(self)
        self.act_open = self.file_menu.addAction("", self._pick)
        self.act_reveal = self.file_menu.addAction("", self._reveal); self.act_reveal.setEnabled(False)
        self.file_btn.setMenu(self.file_menu)
        self.howto_btn = QPushButton(); self.howto_btn.setObjectName("menuBtn"); self.howto_btn.clicked.connect(self._show_howto)
        self.about_btn = QPushButton(); self.about_btn.setObjectName("menuBtn"); self.about_btn.clicked.connect(self._show_about)
        lay.addWidget(self.file_btn); lay.addWidget(self.howto_btn); lay.addWidget(self.about_btn)
        lay.addStretch()
        # appearance segmented
        self.app_lbl = QLabel(); self.app_lbl.setObjectName("hint"); self.app_lbl.setStyleSheet("font-size:9px;")
        lay.addWidget(self.app_lbl)
        self.theme_group = QButtonGroup(self)
        for key, sym in (("light", "☀"), ("auto", "◐"), ("dark", "☾")):
            b = QToolButton(); b.setObjectName("seg"); b.setText(sym); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=0, k=key: self._set_theme(k))
            self.theme_group.addButton(b); lay.addWidget(b)
            if key == self.theme: b.setChecked(True)
        lay.addSpacing(8)
        self.lang_lbl = QLabel(); self.lang_lbl.setObjectName("hint"); self.lang_lbl.setStyleSheet("font-size:9px;")
        lay.addWidget(self.lang_lbl)
        self.lang_group = QButtonGroup(self)
        for code in ("es", "en"):
            b = QToolButton(); b.setObjectName("seg"); b.setText(code.upper()); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=0, c=code: self._set_lang(c))
            self.lang_group.addButton(b); lay.addWidget(b)
            if code == self.lang: b.setChecked(True)
        return bar

    def _build_footer(self):
        self.footer = QLabel(); self.footer.setObjectName("footer")
        self.footer.setContentsMargins(14, 6, 14, 6)
        return self.footer

    # ---- pages
    def _build_home(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(28, 16, 28, 24)
        self.drop = DropZone(); self.drop.picked.connect(self._on_picked)
        lay.addWidget(self.drop); lay.addSpacing(12)
        self.convert_btn = QPushButton(); self.convert_btn.setObjectName("primary"); self.convert_btn.setEnabled(False)
        self.convert_btn.setCursor(Qt.PointingHandCursor); self.convert_btn.clicked.connect(self._start)
        lay.addWidget(self.convert_btn, alignment=Qt.AlignCenter); lay.addStretch()
        return w

    def _build_working(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setAlignment(Qt.AlignCenter)
        self.working = QLabel(); self.working.setAlignment(Qt.AlignCenter); self.working.setStyleSheet("font-size:16px;")
        lay.addWidget(self.working)
        return w

    def _build_result(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(28, 20, 28, 20)
        self.ring = QLabel("100%"); self.ring.setAlignment(Qt.AlignCenter); self.ring.setFixedSize(124, 124)
        self.ring.setStyleSheet(self._ring(GREEN))
        rr = QHBoxLayout(); rr.addStretch(); rr.addWidget(self.ring); rr.addStretch(); lay.addLayout(rr)
        self.verdict = QLabel(); self.verdict.setAlignment(Qt.AlignCenter)
        self.verdict.setStyleSheet(f"font-size:16px; font-weight:600; color:{GREEN}; margin:6px;")
        lay.addWidget(self.verdict)
        self.metrics = QVBoxLayout(); lay.addLayout(self.metrics); lay.addStretch()
        br = QHBoxLayout(); br.addStretch()
        self.again_btn = QPushButton(); self.again_btn.setObjectName("ghost"); self.again_btn.clicked.connect(self._reset)
        self.showf_btn = QPushButton(); self.showf_btn.setObjectName("ghost"); self.showf_btn.clicked.connect(self._reveal)
        self.openw_btn = QPushButton(); self.openw_btn.setObjectName("primary"); self.openw_btn.clicked.connect(self._open_out)
        for b in (self.again_btn, self.showf_btn, self.openw_btn):
            b.setCursor(Qt.PointingHandCursor); br.addWidget(b)
        br.addStretch(); lay.addLayout(br)
        self.meta = QLabel(); self.meta.setObjectName("meta"); self.meta.setAlignment(Qt.AlignCenter); lay.addWidget(self.meta)
        return w

    # ---- i18n / theme
    def t(self): return TR[self.lang]

    def retranslate(self):
        t = self.t()
        self.h_brand.setText("Filaxy Labs")
        self.file_btn.setText(t["menu_file"])
        self.act_open.setText(t["open"]); self.act_reveal.setText(t["reveal"])
        self.howto_btn.setText("✦ " + t["howto"]); self.about_btn.setText("ⓘ " + t["about"])
        self.app_lbl.setText(t["appearance"].upper()); self.lang_lbl.setText(t["language"].upper())
        self.drop.title.setText(os.path.basename(self.pdf_path) if self.pdf_path else t["drop"])
        self.drop.hint.setText(t["ready"] if self.pdf_path else t["drop_hint"])
        self.convert_btn.setText(t["convert"]); self.working.setText(t["working"])
        self.footer.setText("  " + t["subtitle"] + "   ·   Filaxy Labs")
        self.again_btn.setText(t["again"]); self.showf_btn.setText(t["show"]); self.openw_btn.setText(t["openw"])

    def _set_lang(self, c):
        self.lang = c; self.settings.setValue("lang", c); self.retranslate()

    def _set_theme(self, k):
        self.theme = k; self.settings.setValue("theme", k); self.apply_theme()

    def apply_theme(self):
        dark = self.theme == "dark" or (self.theme == "auto" and self._system_dark())
        self.setStyleSheet(qss(dark))

    @staticmethod
    def _system_dark():
        h = QGuiApplication.palette().window().color()
        return h.lightness() < 128

    # ---- behavior
    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(self, self.t()["open"], "", "PDF files (*.pdf)")
        if p: self._on_picked(p)

    def _on_picked(self, path):
        self.pdf_path = path
        self.drop.title.setText(os.path.basename(path)); self.drop.hint.setText(self.t()["ready"])
        self.convert_btn.setEnabled(True); self.stack.setCurrentIndex(0)

    def _start(self):
        if not self.pdf_path: return
        suggested = os.path.splitext(os.path.basename(self.pdf_path))[0] + ".docx"
        dest, _ = QFileDialog.getSaveFileName(self, self.t()["save_title"], suggested, "Word document (*.docx)")
        if not dest: return
        self.out_path = dest; self.stack.setCurrentIndex(1)
        self.worker = ConvertWorker(self.pdf_path, dest)
        self.worker.finished_ok.connect(self._done); self.worker.failed.connect(self._fail); self.worker.start()

    def _done(self, r):
        t = self.t(); f = r["fidelity"]; passed = r.get("passed", False)
        color = GREEN if passed else ORANGE
        self.ring.setText(f"{int(round(f['text_score']))}%"); self.ring.setStyleSheet(self._ring(color))
        self.verdict.setText(t["verdict_ok"] if passed else t["verdict_review"])
        self.verdict.setStyleSheet(f"font-size:16px; font-weight:600; color:{color}; margin:6px;")
        while self.metrics.count():
            it = self.metrics.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        rows = [
            (t["m_text"], t["m_text_v"] if f["text_score"] >= 99.5 else f"{int(f['text_score'])}%", f["text_score"] >= 98),
            (t["m_sens"], t["m_sens_v"] if not f["sensitive_issues"] else f"{len(f['sensitive_issues'])} {t['m_sens_r']}", not f["sensitive_issues"]),
            (t["m_font"], t["m_font_v"] if r["layout"]["passed"] else t["m_font_r"], r["layout"]["passed"]),
            (t["m_graph"], t["m_graph_v"] if f["images"]["match"] else t["m_graph_r"], f["images"]["match"]),
        ]
        for lab, val, ok in rows:
            self.metrics.addWidget(self._metric(lab, val, ok))
        self.meta.setText(f"{r['pages']} · {r['elapsed_s']}s")
        self.act_reveal.setEnabled(True)
        self.stack.setCurrentIndex(2)

    def _fail(self, m):
        self.working.setText(self.t()["fail"] + "\n" + m)

    def _metric(self, label, value, ok):
        row = QFrame(); row.setObjectName("metric"); lay = QHBoxLayout(row); lay.setContentsMargins(12, 9, 12, 9)
        tick = QLabel("✓" if ok else "✕"); tick.setStyleSheet(f"color:{GREEN if ok else ORANGE}; font-weight:bold;")
        name = QLabel(label); val = QLabel(value); val.setObjectName("sub")
        lay.addWidget(tick); lay.addWidget(name); lay.addStretch(); lay.addWidget(val)
        return row

    def _reset(self):
        self.pdf_path = self.out_path = None
        self.drop.title.setText(self.t()["drop"]); self.drop.hint.setText(self.t()["drop_hint"])
        self.convert_btn.setEnabled(False); self.act_reveal.setEnabled(False); self.stack.setCurrentIndex(0)

    def _open_out(self):
        if self.out_path: QDesktopServices.openUrl(QUrl.fromLocalFile(self.out_path))

    def _reveal(self):
        if not self.out_path: return
        if sys.platform == "darwin": subprocess.run(["open", "-R", self.out_path])
        elif sys.platform.startswith("win"): subprocess.run(["explorer", "/select,", os.path.normpath(self.out_path)])
        else: subprocess.run(["xdg-open", os.path.dirname(self.out_path)])

    def _show_about(self):
        d = AboutDialog(self, self.t()); d.setStyleSheet(self.styleSheet()); d.exec()

    def _show_howto(self):
        d = HowToDialog(self, self.t()); d.setStyleSheet(self.styleSheet()); d.exec()

    @staticmethod
    def _ring(color):
        return (f"QLabel {{ border:10px solid {color}; border-radius:62px; font-size:30px;"
                f" font-weight:bold; }}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Filaxy PDF Converter")
    QApplication.setFont(QFont("Segoe UI" if sys.platform.startswith("win") else "Helvetica Neue", 12))
    MainWindow().show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
