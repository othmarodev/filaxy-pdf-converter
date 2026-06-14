"""
Objective audit of a coordinate-mapped result against its original, focused on
the two failure modes that matter: SHADING (fill colours must match) and
TEXT OVERFLOW (no glyph may spill past its source line box).

    python tools/audit.py <orig.pdf> <result.pdf>   # result = LibreOffice render of the docx

SHADING: for every sizeable filled path in the original, sample the median colour
of its interior in both renders; report when they diverge (wrong colour, missing
fill, black-instead-of-red, etc.).

OVERFLOW: for every original text line, look at the empty margin just past its
right edge and just below its baseline. If the RESULT has dark ink there that the
ORIGINAL does not, the substituted text is spilling out of its container.
"""
import sys
import fitz
import numpy as np

DPI = 200
S = DPI / 72.0


def render(pdf):
    d = fitz.open(pdf)
    out = []
    for p in d:
        px = p.get_pixmap(matrix=fitz.Matrix(S, S))
        out.append(np.frombuffer(px.samples, np.uint8).reshape(px.height, px.width, px.n)[:, :, :3].copy())
    d.close()
    return out


def med_color(img, x0, y0, x1, y1):
    h, w = img.shape[:2]
    a, b = max(0, int(y0 * S)), min(h, int(y1 * S))
    c, e = max(0, int(x0 * S)), min(w, int(x1 * S))
    if b - a < 2 or e - c < 2:
        return None
    reg = img[a:b, c:e].reshape(-1, 3)
    return np.median(reg, axis=0) / 255.0


def dark_frac(img, x0, y0, x1, y1):
    h, w = img.shape[:2]
    a, b = max(0, int(y0 * S)), min(h, int(y1 * S))
    c, e = max(0, int(x0 * S)), min(w, int(x1 * S))
    if b - a < 1 or e - c < 1:
        return 0.0
    reg = img[a:b, c:e].astype(float).mean(axis=2)
    return (reg < 150).mean()


def audit(orig_pdf, res_pdf):
    O, R = render(orig_pdf), render(res_pdf)
    od = fitz.open(orig_pdf)
    issues = 0
    for pi, page in enumerate(od):
        if pi >= len(R):
            print(f"page {pi+1}: MISSING in result"); issues += 1; continue
        oi, ri = O[pi], R[pi]
        mat = page.rotation_matrix
        # ---- SHADING ----
        for dr in page.get_drawings():
            f = dr.get("fill")
            if f is None:
                continue
            r = (fitz.Rect(dr["rect"]) * mat).normalize()
            if min(r.width, r.height) < 5 or r.get_area() < 300:
                continue
            ins = 2.5
            box = (r.x0 + ins, r.y0 + ins, r.x1 - ins, r.y1 - ins)
            co = med_color(oi, *box); cr = med_color(ri, *box)
            if co is None or cr is None:
                continue
            dist = float(np.abs(co - cr).max())
            if dist > 0.22:
                print(f"  p{pi+1} SHADING diff @({r.x0:.0f},{r.y0:.0f}-{r.x1:.0f},{r.y1:.0f}) "
                      f"fill={tuple(round(c,2) for c in f[:3])} "
                      f"orig_shown={tuple(round(c,2) for c in co)} result={tuple(round(c,2) for c in cr)}")
                issues += 1
        # ---- OVERFLOW ----
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                sp = [s for s in line["spans"] if s["text"].strip()]
                if not sp:
                    continue
                r = (fitz.Rect(line["bbox"]) * mat).normalize()
                lh = max(r.height, 4)
                # right margin band
                rb = (r.x1 + 1.5, r.y0 + 0.5, r.x1 + 18, r.y1 - 0.5)
                # below band
                bb = (r.x0 + 1, r.y1 + 1.0, r.x1 - 1, r.y1 + lh * 0.7)
                for tag, band in (("RIGHT", rb), ("BELOW", bb)):
                    o_ink = dark_frac(oi, *band); r_ink = dark_frac(ri, *band)
                    # Only real overflow: the margin must be ~empty in the
                    # original (o_ink low). High o_ink means an adjacent column or
                    # a tightly-stacked next line legitimately occupies that band.
                    if r_ink - o_ink > 0.18 and r_ink > 0.12 and o_ink < 0.08:
                        txt = "".join(s["text"] for s in sp)[:32]
                        print(f"  p{pi+1} OVERFLOW-{tag} @({r.x0:.0f},{r.y0:.0f}) "
                              f"oink={o_ink:.2f} rink={r_ink:.2f}  {txt!r}")
                        issues += 1
    od.close()
    print(f"== {issues} issue(s) ==")
    return issues


if __name__ == "__main__":
    audit(sys.argv[1], sys.argv[2])
