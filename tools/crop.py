"""
Crop the same region from the ORIGINAL pdf and the RESULT pdf (LibreOffice render
of the docx) at high DPI, stacked vertically (original on top, result below) so
fine detail — overflow, corners, borders, shading — is legible.

    python tools/crop.py <orig.pdf> <result.pdf> <page1based> <x0> <y0> <x1> <y1> <out.png> [dpi]

Coordinates are PDF points (same space as the original page).
"""
import sys
import fitz
import numpy as np
from PIL import Image


def crop(pdf, page, clip, dpi):
    d = fitz.open(pdf)
    p = d[page]
    pix = p.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=fitz.Rect(*clip))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()
    d.close()
    return img


def main():
    orig, res = sys.argv[1], sys.argv[2]
    page = int(sys.argv[3]) - 1
    clip = [float(x) for x in sys.argv[4:8]]
    out = sys.argv[8]
    dpi = int(sys.argv[9]) if len(sys.argv) > 9 else 300
    a = crop(orig, page, clip, dpi)
    b = crop(res, page, clip, dpi)
    w = max(a.shape[1], b.shape[1])
    def pad(im):
        if im.shape[1] < w:
            im = np.concatenate([im, np.full((im.shape[0], w - im.shape[1], 3), 200, np.uint8)], axis=1)
        return im
    sep = np.full((6, w, 3), [0, 120, 255], np.uint8)
    combo = np.concatenate([pad(a), sep, pad(b)], axis=0)
    Image.fromarray(combo).save(out)
    print(f"{out}  (top=ORIGINAL, bottom=RESULT)  orig={a.shape[1]}x{a.shape[0]} res={b.shape[1]}x{b.shape[0]}")


if __name__ == "__main__":
    main()
