"""
Regression guard for the coordinate-mapping engine.

The engine reproduces a PDF as an editable DOCX with two layers:
  * a GRAPHICS BACKGROUND — the original page with its text stripped (BT…ET
    removed from the content streams) rasterised to a full-page image, so every
    border / fill / rounded box / shadow / logo is the original's own rendering
    (reconstructing them vector-by-vector never matched);
  * an EDITABLE TEXT overlay — each line placed at its source coordinates, in the
    original font EMBEDDED in the docx (obfuscated, ECMA-376 §17.8.1) so it looks
    exact and the ₡/colón renders, centred on its source centre so cell titles sit
    centred.

This locks those invariants so a future change can't silently regress them.
Runs with plain `python tests/regression.py` (no pytest needed). Uses synthetic
PDFs — no personal data, safe for the public repo.
"""
from __future__ import annotations
import io
import os
import tempfile
import zipfile

import fitz

import sys
sys.path.insert(0, __file__.rsplit("/", 2)[0])
from engine import coordmap  # noqa: E402

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"


def _bespoke_font_file():
    """A system font renamed to a bespoke family — so the engine treats it as a
    NON-standard font and actually embeds it (standard fonts like Arial are now
    referenced from the system, never embedded). Returns a temp path or None."""
    if not os.path.exists(ARIAL):
        return None
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return None
    f = TTFont(ARIAL)
    for rec in f["name"].names:
        if rec.nameID in (1, 3, 4, 6):    # family, unique, full, postscript
            rec.string = "BespokeTestFont"
    path = tempfile.mktemp(suffix=".ttf")
    f.save(path)
    return path


def _make_pdf(pages=1, embed_font=False):
    doc = fitz.open()
    fontfile = _bespoke_font_file() if embed_font else None
    for _ in range(pages):
        page = doc.new_page(width=300, height=200)
        page.draw_rect(fitz.Rect(40, 40, 260, 120), color=(0, 0, 0), width=0.7)
        page.draw_rect(fitz.Rect(40, 40, 260, 60), color=None, fill=(1, 0, 0))
        if fontfile:
            page.insert_text((46, 54), "HEADER", fontsize=9, color=(1, 1, 1),
                             fontfile=fontfile, fontname="BTF")
        else:
            page.insert_text((46, 54), "HEADER", fontsize=9, color=(1, 1, 1))
        page.insert_text((46, 80), "Some cell text", fontsize=9)
    out = io.BytesIO(); doc.save(out); doc.close()
    if fontfile:
        try: os.unlink(fontfile)
        except OSError: pass
    return out.getvalue()


def _make_mixed_orientation_pdf():
    """Two pages: one landscape (wider than tall), one portrait."""
    doc = fitz.open()
    doc.new_page(width=400, height=250)   # landscape
    doc.new_page(width=250, height=400)   # portrait
    for pg in doc:
        pg.insert_text((30, 30), "text", fontsize=10)
    out = io.BytesIO(); doc.save(out); doc.close()
    return out.getvalue()


def _make_justified_pdf():
    """A multi-line, justified paragraph (lines share left AND right edges)."""
    doc = fitz.open()
    page = doc.new_page(width=320, height=400)
    page.insert_textbox(fitz.Rect(40, 40, 280, 160),
                        "Lorem ipsum dolor sit amet consectetur adipiscing elit "
                        "sed do eiusmod tempor incididunt ut labore et dolore magna "
                        "aliqua ut enim ad minim veniam quis nostrud exercitation.",
                        fontsize=10, align=fitz.TEXT_ALIGN_JUSTIFY)
    out = io.BytesIO(); doc.save(out); doc.close()
    return out.getvalue()


def _convert(pdf_bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes); pin = f.name
    pout = pin[:-4] + ".docx"
    try:
        coordmap.convert(pin, pout)
        z = zipfile.ZipFile(pout)
        return z, z.read("word/document.xml").decode()
    finally:
        for p in (pin, pout):
            try: os.unlink(p)
            except OSError: pass


def test_no_xalign():
    _, xml = _convert(_make_pdf())
    assert "w:xAlign" not in xml and "w:yAlign" not in xml, \
        "regressed: framePr emits an alignment attribute (overrides absolute x)"
    assert 'w:hAnchor="page"' in xml and 'w:x=' in xml, "absolute x positioning missing"
    print("PASS  no xAlign/yAlign, absolute x present")


def test_graphics_background_per_page():
    n = 3
    z, xml = _convert(_make_pdf(pages=n))
    bgs = [name for name in z.namelist() if name.startswith("word/media/bg")]
    assert len(bgs) == n, f"regressed: expected {n} page-background images, got {len(bgs)}"
    assert xml.count("<wp:anchor") >= n, "background images not anchored in the body"
    print(f"PASS  graphics background: {len(bgs)} full-page image(s), one per page")


def test_text_is_editable_overlay():
    _, xml = _convert(_make_pdf())
    assert "<w:framePr" in xml and "<w:t" in xml, "regressed: no editable text overlay"
    assert 'w:jc w:val="center"' in xml, "regressed: text no longer centred on its footprint"
    assert "HEADER" in xml and "Some cell text" in xml, "regressed: text content dropped"
    print("PASS  editable text overlay present, centred, complete")


def test_original_fonts_embedded():
    bespoke = _bespoke_font_file()
    if not bespoke:
        print("SKIP  fonts embedded (no fontTools / system TTF to build a test font)")
        return
    os.unlink(bespoke)
    z, _ = _convert(_make_pdf(embed_font=True))
    odttf = [n for n in z.namelist() if n.endswith(".odttf")]
    assert odttf, "regressed: the original embedded font was not carried into the docx"
    ft = z.read("word/fontTable.xml").decode()
    assert "w:embedRegular" in ft and "w:fontKey" in ft, "fontTable missing embed entry"
    print(f"PASS  original fonts embedded ({len(odttf)} obfuscated font part(s))")


def test_per_page_orientation():
    _, xml = _convert(_make_mixed_orientation_pdf())
    assert xml.count('w:orient="landscape"') == 1, \
        "regressed: per-page orientation lost (expected exactly one landscape section)"
    assert xml.count("<w:sectPr") == 2, "expected one section per page"
    print("PASS  per-page orientation: landscape + portrait sections both present")


def test_justified_paragraph():
    _, xml = _convert(_make_justified_pdf())
    assert 'w:jc w:val="both"' in xml, \
        "regressed: a justified multi-line paragraph is no longer justified"
    print("PASS  justified paragraph reproduced (jc=both)")


def main() -> int:
    failures = 0
    for fn in (test_no_xalign, test_graphics_background_per_page,
               test_text_is_editable_overlay, test_original_fonts_embedded,
               test_per_page_orientation, test_justified_paragraph):
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{'ALL PASS' if not failures else str(failures) + ' FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
