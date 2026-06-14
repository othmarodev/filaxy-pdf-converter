"""
Structural fidelity verification — rasterizer-agnostic layout check.

Pixel-diffing a fitz-rendered PDF against a QuickLook-rendered DOCX fails: the
two rasterizers disagree on every glyph, drowning the real layout differences
in font noise (measured: a good and a broken conversion scored within 1.5%).

So we compare STRUCTURE instead. The decisive, reliable signal for the failure
we actually hit — a bordered table fragmenting into disconnected blocks — is the
table grid: count the real (bordered) table regions in the source PDF from its
vector borders, and compare against the tables the engine produced in the DOCX.
1 in the source but 4 in the output ⇒ the table fragmented. No pixels, no noise.
"""
from __future__ import annotations
import os
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field

import numpy as np
import cv2
import fitz  # PyMuPDF


@dataclass
class StructuralReport:
    src_tables: int
    out_tables: int
    issues: list = field(default_factory=list)
    score: float = 100.0
    passed: bool = True
    overlay_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "src_tables": self.src_tables,
            "out_tables": self.out_tables,
            "issues": self.issues,
            "score": round(self.score, 1),
            "passed": self.passed,
            "overlay_path": self.overlay_path,
        }


# ---- PDF side: detect bordered table regions from vector borders -----------

def _h_segments(page) -> list[tuple[float, float, float]]:
    """Horizontal border segments as (y, x0, x1)."""
    segs = []
    for path in page.get_drawings():
        for it in path["items"]:
            if it[0] == "l":
                (x0, y0), (x1, y1) = it[1], it[2]
                if abs(y0 - y1) < 1.5 and abs(x1 - x0) > 20:
                    segs.append(((y0 + y1) / 2, min(x0, x1), max(x0, x1)))
            elif it[0] == "re":
                r = it[1]
                if r.width > 20:
                    segs.append((r.y0, r.x0, r.x1))
                    segs.append((r.y1, r.x0, r.x1))
    return sorted(segs, key=lambda s: s[0])


def _split_bands(segs: list, gap: float) -> list[list]:
    """Recursively split y-sorted segments into bands at the first vertical gap
    larger than `gap`. Base case: no such gap → one contiguous band. Depth is
    bounded by the number of gaps (a handful), so recursion is safe."""
    if len(segs) <= 1:
        return [segs] if segs else []
    for i in range(1, len(segs)):
        if segs[i][0] - segs[i - 1][0] > gap:
            return _split_bands(segs[:i], gap) + _split_bands(segs[i:], gap)
    return [segs]


def pdf_table_regions(page, row_gap: float = 35.0, min_rows: int = 3) -> list[tuple]:
    """Table regions as (x0, y0, x1, y1) in PDF points. A table is a band of
    >= min_rows stacked horizontal borders (isolated rules like a header/footer
    underline have too few lines and are ignored)."""
    bands = _split_bands(_h_segments(page), row_gap)
    regions = []
    for band in bands:
        levels = {round(s[0]) for s in band}
        if len(levels) >= min_rows:
            y0 = min(s[0] for s in band); y1 = max(s[0] for s in band)
            x0 = min(s[1] for s in band); x1 = max(s[2] for s in band)
            regions.append((x0, y0, x1, y1))
    return regions


# ---- DOCX side -------------------------------------------------------------

def _docx_table_count(docx: str) -> int:
    z = zipfile.ZipFile(docx)
    xml = z.read("word/document.xml").decode("utf-8")
    z.close()
    return xml.count("<w:tbl>")


def _render_docx(docx: str, size_px: int = 1600) -> np.ndarray | None:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(["qlmanage", "-t", "-s", str(size_px), docx, "-o", tmp],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        pngs = [f for f in os.listdir(tmp) if f.lower().endswith(".png")]
        if not pngs:
            return None
        return cv2.imread(os.path.join(tmp, pngs[0]), cv2.IMREAD_GRAYSCALE)


def _image_table_bands(gray: np.ndarray, min_rows: int = 3, row_gap_px: int = 40):
    """Detect table-grid bands in a rendered page: long horizontal rules
    clustered vertically. Returns [(x0, y0, x1, y1)] in image pixels."""
    inv = 255 - gray
    bw = cv2.threshold(inv, 60, 255, cv2.THRESH_BINARY)[1]
    klen = max(40, gray.shape[1] // 6)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (klen, 1))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    # y positions that contain a long horizontal line, and their x-extent
    rows = []
    for y in range(horiz.shape[0]):
        xs = np.where(horiz[y] > 0)[0]
        if xs.size > klen:
            rows.append((y, int(xs.min()), int(xs.max())))
    bands = _split_bands([(float(y), float(x0), float(x1)) for y, x0, x1 in rows], row_gap_px)
    out = []
    for band in bands:
        if len({round(s[0]) for s in band}) >= min_rows:
            y0 = min(s[0] for s in band); y1 = max(s[0] for s in band)
            x0 = min(s[1] for s in band); x1 = max(s[2] for s in band)
            out.append((int(x0), int(y0), int(x1), int(y1)))
    return out


# ---- alignment -------------------------------------------------------------

# Thresholds as a fraction of page width. Below MINOR: faithful. MINOR..MAJOR:
# noticeable, warn but don't fail. Above MAJOR: a real descuadre, fail.
_ALIGN_MINOR = 0.06
_ALIGN_MAJOR = 0.12


def _alignment_issues(pdf_regions: list, page_w: float,
                      bands: list, img_w: float) -> tuple[list, float, bool]:
    """Compare the horizontal placement of each source table against the matching
    output table (matched by top-to-bottom order). Center fraction is robust to
    any symmetric padding the renderer adds. Returns (issues, penalty, hard_fail)."""
    issues, penalty, hard_fail = [], 0.0, False
    pdf_sorted = sorted(pdf_regions, key=lambda r: r[1])     # by y0
    out_sorted = sorted(bands, key=lambda r: r[1])
    for src_r, out_r in zip(pdf_sorted, out_sorted):
        src_c = ((src_r[0] + src_r[2]) / 2) / page_w
        out_c = ((out_r[0] + out_r[2]) / 2) / img_w
        shift = abs(src_c - out_c)
        if shift < _ALIGN_MINOR:
            continue
        # Describe the direction in plain language.
        src_centered = abs(src_c - 0.5) < 0.06
        if src_centered and out_c < src_c - _ALIGN_MINOR:
            where = "el original la tiene centrada pero quedó pegada a la izquierda"
        elif src_centered and out_c > src_c + _ALIGN_MINOR:
            where = "el original la tiene centrada pero quedó corrida a la derecha"
        else:
            where = f"se movió ~{round(shift * 100)}% del ancho de página"
        sev = "" if shift < _ALIGN_MAJOR else " (descuadre marcado)"
        issues.append(f"La tabla quedó desalineada: {where}{sev}.")
        penalty += min(40.0, shift * 120.0)
        if shift >= _ALIGN_MAJOR:
            hard_fail = True
    return issues, penalty, hard_fail


# ---- compare ---------------------------------------------------------------

def compare(pdf: str, docx: str, overlay_out: str | None = None) -> StructuralReport:
    doc = fitz.open(pdf)
    per_page = [pdf_table_regions(p) for p in doc]
    src = sum(len(r) for r in per_page)
    page_w = doc[0].rect.width if doc.page_count else 1.0
    first_page_regions = per_page[0] if per_page else []
    doc.close()
    out = _docx_table_count(docx)

    issues, score, passed = [], 100.0, True

    # 1) Table integrity — did a single table fragment, or tables vanish/merge?
    if src > 0:
        if out > src:
            issues.append(
                f"La tabla del original ({src}) quedó fragmentada en {out} bloques "
                f"en el Word — revisá el cuadro.")
            score = max(0.0, 100.0 - 22.0 * (out - src))
            passed = False
        elif out < src:
            issues.append(
                f"El original tiene {src} tabla(s) pero el Word quedó con {out} — "
                f"posible fusión o pérdida de estructura.")
            score = max(0.0, 100.0 - 30.0 * (src - out))
            passed = False

    # 2) Alignment — did tables keep their horizontal placement? (needs a render)
    gray = _render_docx(docx) if (overlay_out or first_page_regions) else None
    bands = _image_table_bands(gray) if gray is not None else []
    if first_page_regions and bands:
        a_issues, penalty, hard = _alignment_issues(first_page_regions, page_w, bands, gray.shape[1])
        issues += a_issues
        score = max(0.0, score - penalty)
        if hard:
            passed = False

    # 3) Annotated overlay
    overlay_path = None
    if overlay_out and gray is not None:
        canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        color = (0, 0, 230) if not passed else (40, 170, 40)
        for (x0, y0, x1, y1) in bands:
            cv2.rectangle(canvas, (x0 - 6, y0 - 6), (x1 + 6, y1 + 6), color, 3)
        cv2.imwrite(overlay_out, canvas)
        overlay_path = overlay_out

    return StructuralReport(src_tables=src, out_tables=out, issues=issues,
                            score=score, passed=passed, overlay_path=overlay_path)


if __name__ == "__main__":
    import sys
    r = compare(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    print(f"src_tables={r.src_tables} out_tables={r.out_tables} "
          f"score={r.score:.0f} passed={r.passed}")
    for i in r.issues:
        print("  ⚠", i)
