"""
Visual fidelity verification — the honest half of "verified".

The data verifier (verify.py) proves every number/date/email survived. This
module proves the *layout* survived: it renders the original PDF and the
produced DOCX to images, aligns them, and measures structural similarity
(SSIM). Where they diverge — a table that fragmented, an element that shifted —
it returns the offending regions and paints them onto an overlay image the app
can show. This is what catches the "descuadre" that data checks miss.

DOCX rendering uses macOS QuickLook (`qlmanage`), so no LibreOffice/Word needed.
QuickLook renders the first page only; multi-page visual diff is a follow-up
(data verification already covers every page).
"""
from __future__ import annotations
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

import numpy as np
import cv2
import fitz  # PyMuPDF


@dataclass
class VisualReport:
    available: bool                       # could we render + compare?
    score: float = 0.0                    # 0..100 structural similarity
    diff_regions: list = field(default_factory=list)  # [{x,y,w,h}] on the overlay
    overlay_path: str | None = None       # annotated image for the UI
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "score": round(self.score, 1),
            "diff_regions": self.diff_regions,
            "overlay_path": self.overlay_path,
            "note": self.note,
        }


# ---- rendering -------------------------------------------------------------

def _render_pdf_first_page(pdf: str, target_h: int = 1600) -> np.ndarray | None:
    doc = fitz.open(pdf)
    if doc.page_count == 0:
        doc.close(); return None
    page = doc[0]
    zoom = target_h / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    doc.close()
    return img


def _render_docx_quicklook(docx: str, size_px: int = 1600) -> np.ndarray | None:
    """Render the DOCX first page to grayscale via macOS QuickLook."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                ["qlmanage", "-t", "-s", str(size_px), docx, "-o", tmp],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        pngs = [f for f in os.listdir(tmp) if f.lower().endswith(".png")]
        if not pngs:
            return None
        img = cv2.imread(os.path.join(tmp, pngs[0]), cv2.IMREAD_GRAYSCALE)
        return img


# ---- comparison ------------------------------------------------------------

def _to_common_canvas(a: np.ndarray, b: np.ndarray, w: int = 1000) -> tuple[np.ndarray, np.ndarray]:
    """Normalise both renders to the same WxH so they are comparable. We match
    the original PDF's aspect ratio (a) and resize the DOCX render (b) onto it."""
    h = max(1, round(w * a.shape[0] / a.shape[1]))
    ra = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
    rb = cv2.resize(b, (w, h), interpolation=cv2.INTER_AREA)
    return ra, rb


def _ssim_map(a: np.ndarray, b: np.ndarray) -> tuple[float, np.ndarray]:
    """Mean SSIM and the per-pixel SSIM map (standard Wang et al. formulation)."""
    a = a.astype(np.float64); b = b.astype(np.float64)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    k = (11, 11); s = 1.5
    mu_a = cv2.GaussianBlur(a, k, s); mu_b = cv2.GaussianBlur(b, k, s)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    sa = cv2.GaussianBlur(a * a, k, s) - mu_a2
    sb = cv2.GaussianBlur(b * b, k, s) - mu_b2
    sab = cv2.GaussianBlur(a * b, k, s) - mu_ab
    ssim = ((2 * mu_ab + C1) * (2 * sab + C2)) / ((mu_a2 + mu_b2 + C1) * (sa + sb + C2))
    return float(ssim.mean()), ssim


def _merge_boxes(boxes: list[tuple[int, int, int, int]], pad: int = 12) -> list[tuple[int, int, int, int]]:
    """Recursively merge overlapping/adjacent boxes into clean regions.

    Recursive by design (per the project convention): each pass merges the first
    box that touches another, then recurses on the smaller list. Base case: a
    full pass with no merge → the list is stable. Depth is bounded by the box
    count (tiny), so no stack concern."""
    def overlap(p, q) -> bool:
        ax, ay, aw, ah = p; bx, by, bw, bh = q
        return not (ax > bx + bw + pad or bx > ax + aw + pad or
                    ay > by + bh + pad or by > ay + ah + pad)

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if overlap(boxes[i], boxes[j]):
                ax, ay, aw, ah = boxes[i]; bx, by, bw, bh = boxes[j]
                nx, ny = min(ax, bx), min(ay, by)
                merged = (nx, ny, max(ax + aw, bx + bw) - nx, max(ay + ah, by + bh) - ny)
                rest = [b for k, b in enumerate(boxes) if k not in (i, j)]
                return _merge_boxes([merged] + rest, pad)   # recurse on stabilised-smaller list
    return boxes  # base case: nothing merged


def compare(pdf: str, docx: str, overlay_out: str | None = None) -> VisualReport:
    pdf_img = _render_pdf_first_page(pdf)
    docx_img = _render_docx_quicklook(docx)
    if pdf_img is None or docx_img is None:
        return VisualReport(available=False,
                            note="No se pudo renderizar para comparar visualmente "
                                 "(QuickLook no disponible o PDF vacío).")

    a, b = _to_common_canvas(pdf_img, docx_img)
    score, ssim = _ssim_map(a, b)

    # Dissimilarity → regions. Blur tolerates font antialiasing; we only flag
    # sizeable structural divergence, not pixel-level hinting noise.
    dissim = ((1.0 - ssim) * 255).clip(0, 255).astype(np.uint8)
    dissim = cv2.GaussianBlur(dissim, (15, 15), 0)
    _, mask = cv2.threshold(dissim, 90, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = 0.0008 * a.shape[0] * a.shape[1]
    raw = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) >= min_area]
    boxes = _merge_boxes(raw)

    regions = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for (x, y, w, h) in boxes]

    overlay_path = None
    if overlay_out:
        canvas = cv2.cvtColor(b, cv2.COLOR_GRAY2BGR)
        for (x, y, w, h) in boxes:
            cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 0, 230), 3)
        cv2.imwrite(overlay_out, canvas)
        overlay_path = overlay_out

    return VisualReport(available=True, score=score * 100.0,
                        diff_regions=regions, overlay_path=overlay_path)


if __name__ == "__main__":
    import sys
    r = compare(sys.argv[1], sys.argv[2],
                sys.argv[3] if len(sys.argv) > 3 else None)
    print(f"visual score: {r.score:.1f}%  regions: {len(r.diff_regions)}  {r.note}")
