"""
Dev verification tool: render the ORIGINAL pdf and the RESULT docx (via
LibreOffice) to images and diff them, page by page. Produces a similarity score
and a side-by-side+diff image per page so discrepancies (overflow, wrong colour,
missing/shifted elements) are visible. Used to iterate the engine to fidelity.

    python tools/compare.py <original.pdf> <result.docx> [outdir]
"""
import os
import subprocess
import sys
import tempfile

import fitz
import numpy as np
from PIL import Image

SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def docx_to_pdf(docx: str, outdir: str) -> str:
    subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", outdir, docx],
                   check=True, capture_output=True, timeout=180)
    return os.path.join(outdir, os.path.splitext(os.path.basename(docx))[0] + ".pdf")


def render(pdf: str, dpi: int = 150) -> list:
    d = fitz.open(pdf)
    out = []
    for p in d:
        pix = p.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        out.append(img[:, :, :3].copy())
    d.close()
    return out


def compare(orig_pdf: str, result_docx: str, outdir: str = "/tmp/cmp") -> None:
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp()
    res_pdf = docx_to_pdf(result_docx, tmp)
    A, B = render(orig_pdf), render(res_pdf)
    print(f"pages: original={len(A)} result={len(B)}")
    for i in range(max(len(A), len(B))):
        if i >= len(A) or i >= len(B):
            print(f"  page {i+1}: MISSING in one side"); continue
        h = min(A[i].shape[0], B[i].shape[0]); w = min(A[i].shape[1], B[i].shape[1])
        a = np.array(Image.fromarray(A[i]).resize((w, h)))
        b = np.array(Image.fromarray(B[i]).resize((w, h)))
        d = np.abs(a.astype(int) - b.astype(int)).sum(axis=2)
        mask = d > 60
        score = 100.0 * (1 - mask.mean())
        # locate the worst differing bands (rows) to point at problem areas
        rowdiff = mask.mean(axis=1)
        bad_rows = np.where(rowdiff > 0.04)[0]
        bands = []
        if bad_rows.size:
            start = prev = bad_rows[0]
            for r in bad_rows[1:]:
                if r - prev > 10:
                    bands.append((start, prev)); start = r
                prev = r
            bands.append((start, prev))
        print(f"  page {i+1}: similarity {score:.2f}%  diff {mask.mean()*100:.2f}%  "
              f"problem-bands(y px @150dpi): {[(int(s),int(e)) for s,e in bands][:8]}")
        # side-by-side + diff overlay
        overlay = b.copy(); overlay[mask] = [255, 0, 0]
        combo = np.concatenate([a, b, overlay], axis=1)
        Image.fromarray(combo.astype(np.uint8)).save(os.path.join(outdir, f"p{i+1}.png"))
    print(f"images (orig | result | diff) in {outdir}")


if __name__ == "__main__":
    compare(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "/tmp/cmp")
