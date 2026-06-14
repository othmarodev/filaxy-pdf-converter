"""
Coordinate-mapping engine — maximum-fidelity PDF -> DOCX.

Instead of reflowing content (pdf2docx), this recreates the page faithfully:
every text line, image and vector rule is read from the PDF with its exact
geometry and re-emitted into the DOCX anchored at the same coordinates. The
result is pixel-faithful in position because nothing flows — each element sits
where the original puts it.

Trade-off: the document is edited block-by-block (text doesn't reflow between
lines), which is the right model for fixed-layout documents (certificates,
letters, forms).

Prototype: page 1. Multi-page is a straightforward extension (one section per
page); kept single-page here to validate the approach.
"""
from __future__ import annotations
import html
import io
import os
import re
import zipfile

import fitz  # PyMuPDF
from PIL import Image

EMU_PER_PT = 12700
TW_PER_PT = 20
BG_DPI = 200          # resolution of the page-graphics background layer


def _emu(pt: float) -> int: return int(round(pt * EMU_PER_PT))
def _tw(pt: float) -> int: return int(round(pt * TW_PER_PT))


def _tbox(mat, bbox) -> tuple:
    """Transform a native-space bbox to display space via the page rotation
    matrix (identity when the page isn't rotated). Without this, text from a
    page with /Rotate 90 lands rotated/vertical."""
    r = (fitz.Rect(bbox) * mat).normalize()
    return r.x0, r.y0, r.x1, r.y1


# ---- fonts / runs ----------------------------------------------------------

# Some PDFs (notably CR e-invoices) encode the colón ₡ at a bespoke codepoint in
# a custom font; Word substitutes a font without that glyph and shows □. Remap
# the known offenders to their real Unicode so a standard font renders them.
_CHAR_REMAP = {"૿": "₡"}   # Gujarati-range custom colón → ₡


def _basename(name: str) -> str:
    """Strip the 6-letter subset prefix (e.g. 'IFEBGD+AMX-Regular' -> 'AMX-Regular')."""
    return name.split("+", 1)[1] if "+" in name else name


def _clean_font(name: str) -> str:
    low = _basename(name).lower()
    # Fallback when the original font can't be embedded: map to a real installed
    # font. A bespoke name would otherwise be substituted by Word with an
    # unpredictable, often wider font.
    for fam, real in (("arial", "Arial"), ("helvetica", "Arial"),
                      ("times", "Times New Roman"), ("georgia", "Georgia"),
                      ("courier", "Courier New"), ("calibri", "Calibri"),
                      ("verdana", "Verdana")):
        if fam in low:
            return real
    return "Arial"


# ---- font embedding --------------------------------------------------------
# DOCX renders text faithfully only when the ORIGINAL font is available. Rather
# than substitute (which drifts in width/shape and overflows), we extract each
# embedded font from the PDF and embed it in the DOCX as an obfuscated font part
# (ECMA-376 §17.8.1). Word then renders with the exact original glyphs.

def _obfuscate(font_bytes: bytes):
    """Return (fontKey, obfuscated_bytes). The first 32 bytes are XOR'd with the
    GUID-derived key (key bytes used in reverse), per the OOXML embedded-font
    obfuscation scheme. Uses a deterministic GUID base (Date/random are blocked
    in this runtime) seeded off the font content so it stays stable per font."""
    import uuid
    g = uuid.UUID(bytes=__import__("hashlib").md5(font_bytes).digest())
    key = bytes.fromhex(str(g).replace("-", ""))
    data = bytearray(font_bytes)
    for i in range(32):
        data[i] ^= key[15 - (i % 16)]
    return "{%s}" % str(g).upper(), bytes(data)


# Fonts every Word install already has. Embedding a PDF's SUBSET of these is
# pointless and risky: the subset's cmap is often re-encoded (glyphs reachable
# only by index, not Unicode), so Word renders wrong glyphs (e.g. A/O/R/hyphen
# garbled). For these we reference the system font instead — it has every glyph.
_STANDARD_FONTS = ("arial", "helvetica", "times", "calibri", "cambria", "georgia",
                   "verdana", "tahoma", "trebuchet", "courier", "century",
                   "garamond", "candara", "consolas", "segoe", "roboto")


def _is_standard_font(base: str) -> bool:
    low = base.lower()
    return any(k in low for k in _STANDARD_FONTS)


_SYS_FONT_DIR = "/System/Library/Fonts/Supplemental"


def _system_font_bytes(basefont: str) -> bytes | None:
    """Bytes of the INSTALLED system font matching `basefont` (same family +
    weight/slant). Used to embed a reliable, Unicode-cmap font when the PDF's own
    subset can't be used — so the DOCX renders identically on any Word WITHOUT
    depending on Word's (sometimes corrupt) font cache for system fonts."""
    low = _basename(basefont).lower()
    bold = any(k in low for k in ("bold", "black", "heavy", "semibold"))
    ital = any(k in low for k in ("italic", "oblique"))
    if "times" in low:       fam = "Times New Roman"
    elif "courier" in low:   fam = "Courier New"
    elif "georgia" in low:   fam = "Georgia"
    elif "verdana" in low:   fam = "Verdana"
    elif "tahoma" in low:    fam = "Tahoma"
    else:                    fam = "Arial"   # arial, helvetica, unknown → Arial
    if fam == "Arial" and "black" in low:
        names = ["Arial Black.ttf"]
    else:
        sfx = " Bold Italic" if (bold and ital) else " Bold" if bold else " Italic" if ital else ""
        names = [f"{fam}{sfx}.ttf", f"{fam}.ttf"]
    for n in names:
        p = os.path.join(_SYS_FONT_DIR, n)
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return f.read()
            except OSError:
                pass
    return None


def _has_unicode_cmap(font_bytes: bytes) -> bool:
    """True if the font exposes a UNICODE cmap (Windows BMP/full or Unicode
    platform). Word maps each character by Unicode codepoint; a subset that ships
    only a Mac-Roman (1,0) or symbol cmap can't be looked up, so Word renders the
    wrong glyph (the constancia's Arial subset garbled A/O/R/hyphen this way).
    We only embed fonts that have a real Unicode cmap; the rest fall back to the
    system font, which always maps Unicode correctly."""
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(io.BytesIO(font_bytes), fontNumber=0, lazy=True)
        for t in f["cmap"].tables:
            if t.platformID == 0 or (t.platformID == 3 and t.platEncID in (1, 10)):
                return True
    except Exception:
        return False
    return False


def _build_font_registry(doc):
    """Scan every font in the PDF; for each, decide whether to EMBED it (bespoke
    fonts not installed anywhere) or reference the SYSTEM font (standard fonts
    Word already has). Returns (reg, embedded):
      reg      : basefont-name -> {"family": <DOCX font name>, "embedded": bool}
      embedded : family-name   -> (fontKey, obfuscated_bytes)
    """
    reg: dict[str, dict] = {}
    embedded: dict[str, tuple] = {}
    seen: set[int] = set()
    for pno in range(len(doc)):
        for f in doc.get_page_fonts(pno):
            xref, basefont = f[0], f[3]
            if not xref or xref in seen:
                continue
            seen.add(xref)
            base = _basename(basefont)
            if base in reg:
                continue
            buf = b""
            try:
                info = doc.extract_font(xref)
                if info[1] in ("ttf", "otf"):
                    buf = info[3] or b""
            except Exception:
                buf = b""
            if len(buf) > 200 and _has_unicode_cmap(buf):
                # The PDF's own font is usable → embed it (exact original glyphs).
                family = base
                if family not in embedded:
                    embedded[family] = _obfuscate(buf)
                reg[base] = {"family": family, "embedded": True}
            elif len(buf) > 200:
                # The PDF embeds this font but its subset has NO Unicode cmap, so
                # Word can't map characters to glyphs → the text VANISHES (only
                # bold survived, via the system fallback). Embed the matching
                # SYSTEM font instead (same family, full Unicode cmap) so the docx
                # renders reliably on any Word, independent of its font cache.
                sysbuf = _system_font_bytes(basefont)
                if sysbuf and _has_unicode_cmap(sysbuf):
                    if base not in embedded:
                        embedded[base] = _obfuscate(sysbuf)
                    reg[base] = {"family": base, "embedded": True}
                else:
                    reg[base] = {"family": _clean_font(basefont), "embedded": False}
            else:
                # Base-14 / no embeddable bytes → reference the system font by name
                # + scale-to-fit (substitution).
                reg[base] = {"family": _clean_font(basefont), "embedded": False}
    return reg, embedded


def _span_style(span: dict, font_reg: dict) -> tuple:
    """(family, embedded, bold, ital). When the original font is embedded the
    weight/slant are baked into the font itself (each PDF font is its own family),
    so we don't also emit <w:b>/<w:i> — that would synthesise a fake bold on top."""
    raw = span["font"]
    entry = font_reg.get(_basename(raw)) if font_reg else None
    if entry and entry["embedded"]:
        return entry["family"], True, False, False
    family = entry["family"] if entry else _clean_font(raw)
    flags = span["flags"]
    bold = bool(flags & 16) or "Bold" in raw or "Black" in raw or "Semibold" in raw
    ital = bool(flags & 2) or "Italic" in raw or "Oblique" in raw
    return family, False, bold, ital


def _remap(text: str) -> str:
    for k, v in _CHAR_REMAP.items():
        if k in text:
            text = text.replace(k, v)
    return text


def _measure(text: str, fontsize: float, bold: bool, ital: bool) -> float:
    """Width the text would occupy in the substituted (Helvetica/Arial) font."""
    fn = "hebi" if (bold and ital) else "hebo" if bold else "heit" if ital else "helv"
    try:
        return fitz.get_text_length(_remap(text), fontname=fn, fontsize=fontsize)
    except Exception:
        return 0.5 * fontsize * len(text)


def _run_xml(span: dict, font_reg: dict, scale: float = 1.0, char_space: float = 0.0) -> str:
    text = html.escape(_remap(span["text"]), quote=False)
    if text == "":
        return ""
    size = max(1, round(span["size"] * 2))          # half-points
    hexc = "%06X" % (span["color"] & 0xFFFFFF)
    font, embedded, bold, ital = _span_style(span, font_reg)
    fa = html.escape(font, quote=True)
    # rPr in schema order: rFonts, b, i, color, spacing, w(scale), sz.
    rpr = f'<w:rFonts w:ascii="{fa}" w:hAnsi="{fa}" w:cs="{fa}"/>'
    if bold:
        rpr += "<w:b/><w:bCs/>"
    if ital:
        rpr += "<w:i/><w:iCs/>"
    rpr += f'<w:color w:val="{hexc}"/>'
    if abs(char_space) > 0.01:
        # Inter-character spacing to JUSTIFY a line to its source width (a single
        # framed line can't use jc="both"). Expands the run to fill its footprint.
        rpr += f'<w:spacing w:val="{_tw(char_space)}"/>'
    if abs(scale - 1.0) > 0.02:
        # Horizontal character scaling so the run keeps the original font's
        # footprint despite substitution (a narrow custom font → Arial would
        # otherwise overflow its cell).
        rpr += f'<w:w w:val="{max(33, min(150, round(scale * 100)))}"/>'
    rpr += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>'


def _line_para(line: dict, mat, font_reg: dict, align: str = "center") -> str:
    """`align` reproduces the source paragraph's alignment:
    - "center": standalone line (cell title, label) — centred on its own centre so
      a hair-narrow render doesn't bias it left of its cell.
    - "left": left edge fixed at x0 (a paragraph's last/short line).
    - "justify": a full line of a justified paragraph — expand inter-character
      spacing to fill its footprint (a single framed line can't use jc="both")."""
    x0, y0, x1, y1 = _tbox(mat, line["bbox"])
    spans = [s for s in line["spans"] if s["text"]]
    if not spans:
        return ""
    target = x1 - x0
    all_embedded = all((font_reg.get(_basename(s["font"])) or {}).get("embedded")
                       for s in spans)
    char_space = 0.0
    if align == "justify":
        # fill the footprint by spreading the slack across the characters
        scale = 1.0
        measured = sum(_measure(s["text"], s["size"], *_span_style(s, font_reg)[2:])
                       for s in spans)
        nchars = sum(len(s["text"]) for s in spans) or 1
        if target - measured > 0:
            char_space = (target - measured) / nchars
    elif all_embedded:
        # embedded original font → exact glyphs, no scaling needed
        scale = 1.0
    else:
        measured = sum(_measure(s["text"], s["size"], *_span_style(s, font_reg)[2:])
                       for s in spans)
        scale = max(0.3, min(1.5, (target / measured) * 0.985)) if measured > 1.0 else 1.0
    runs = "".join(_run_xml(s, font_reg, scale, char_space) for s in spans)
    if not runs:
        return ""
    w = max(24.0, target + 30)          # wide enough that a single line never wraps
    sz = max((s["size"] for s in spans), default=10)
    if align == "center":
        fx = max(0.0, (x0 + x1) / 2 - w / 2)   # frame centred on the source centre
        jc = "center"
    else:                                       # left / justify: left edge at x0
        fx = max(0.0, x0)
        jc = "both" if align == "justify" else "left"
    # Absolute x/y from the page edge — NO w:xAlign/w:yAlign (an alignment attribute
    # overrides the absolute offset in some renderers and scrambles the layout).
    frame = (f'<w:framePr w:w="{_tw(w)}" w:hSpace="0" w:vSpace="0" '
             f'w:wrap="none" w:vAnchor="page" w:hAnchor="page" '
             f'w:x="{_tw(fx)}" w:y="{_tw(y0)}"/>')
    spacing = (f'<w:spacing w:before="0" w:after="0" '
               f'w:line="{_tw(sz * 1.18)}" w:lineRule="exact"/>')
    return f'<w:p><w:pPr>{frame}{spacing}<w:jc w:val="{jc}"/></w:pPr>{runs}</w:p>'


# ---- anchored image (the full-page graphics background) --------------------

_ANCHOR = (
    '<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" '
    'simplePos="0" relativeHeight="{z}" behindDoc="{behind}" locked="0" '
    'layoutInCell="1" allowOverlap="1">'
    '<wp:simplePos x="0" y="0"/>'
    '<wp:positionH relativeFrom="page"><wp:posOffset>{x}</wp:posOffset></wp:positionH>'
    '<wp:positionV relativeFrom="page"><wp:posOffset>{y}</wp:posOffset></wp:positionV>'
    '<wp:extent cx="{cx}" cy="{cy}"/>'
    '<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
    '<wp:docPr id="{id}" name="o{id}"/>{body}</wp:anchor></w:drawing></w:r>'
)


def _image_anchor(rid: str, idx: int, x, y, cx, cy, behind: int = 0) -> str:
    body = (
        '<wp:cNvGraphicFramePr/>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{idx}" name="img{idx}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{_emu(cx)}" cy="{_emu(cy)}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        '</a:graphicData></a:graphic>'
    )
    return _ANCHOR.format(z=idx, behind=behind, x=_emu(x), y=_emu(y),
                          cx=_emu(cx), cy=_emu(cy), id=idx, body=body)


# ---- packaging -------------------------------------------------------------

def _page_background_png(doc, page) -> bytes:
    """The page's GRAPHICS + IMAGES with all text removed, rasterised to PNG.
    Reproducing borders/fills/shadows vector-by-vector never matches exactly; the
    original's own rendering does. We strip the text-showing operators (BT…ET)
    from the content streams — leaving every fill, line, rounded box, gradient and
    logo untouched — and rasterise that. The editable text is laid on top."""
    for xref in page.get_contents():
        data = doc.xref_stream(xref)
        if data:
            doc.update_stream(xref, re.sub(rb"BT\b.*?\bET", b"", data, flags=re.S))
    pix = page.get_pixmap(matrix=fitz.Matrix(BG_DPI / 72, BG_DPI / 72), alpha=False)
    return pix.tobytes("png")


def _sectpr(W: float, H: float) -> str:
    """Section properties for one page. Detects orientation from the on-screen
    size: landscape when wider than tall, portrait otherwise — so each page keeps
    the original PDF page's orientation and size (a document can mix both)."""
    orient = ' w:orient="landscape"' if W > H else ''
    return (f'<w:sectPr><w:pgSz w:w="{_tw(W)}" w:h="{_tw(H)}"{orient}/>'
            f'<w:pgMar w:top="0" w:right="0" w:bottom="0" w:left="0" '
            f'w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>')


def _page_content(doc, page, pidx: int, media: dict, rels: list, font_reg: dict) -> tuple:
    """One page → (content_xml, W, H). A full-page graphics background (text
    removed) with the editable text overlaid at its exact coordinates."""
    mat = page.rotation_matrix
    blocks = page.get_text("dict")["blocks"]

    # 1) editable text overlay — collected BEFORE the text is stripped from the page.
    line_paras = []
    for block in blocks:
        lines = [l for l in block.get("lines", [])
                 if any(s["text"].strip() for s in l["spans"])]
        # A vertically-stacked, left-aligned multi-line block is a paragraph; its
        # full-width lines are justified and its short last line is left-aligned.
        # Everything else (titles, labels, side-by-side table cells) is centred.
        ys = sorted(_tbox(mat, l["bbox"])[1] for l in lines)
        stacked = len(lines) >= 2 and all(ys[i + 1] - ys[i] > 3 for i in range(len(ys) - 1))
        boxes = [_tbox(mat, l["bbox"]) for l in lines]
        lmin = min((b[0] for b in boxes), default=0.0)
        rmax = max((b[2] for b in boxes), default=0.0)
        para = stacked and all(abs(b[0] - lmin) < 3 for b in boxes)
        for line, b in zip(lines, boxes):
            if para:
                align = "justify" if abs(b[2] - rmax) < 6 else "left"
            else:
                align = "center"
            p = _line_para(line, mat, font_reg, align)
            if p:
                line_paras.append(p)

    # 2) graphics background (mutates this page's content streams — fine, the doc
    #    is a throwaway open and each page's streams are independent).
    #    page.rect is ALREADY the on-screen (post-rotation) size and get_pixmap
    #    respects /Rotate, so both are in display space — place 1:1, no swap.
    W, H = page.rect.width, page.rect.height
    png = _page_background_png(doc, page)
    idx = len(media) + 1
    name = f"bg{idx}.png"
    media[name] = png
    rid = f"rIdBg{idx}"
    rels.append((rid, f"media/{name}"))
    bg = _image_anchor(rid, 4000 + pidx, 0, 0, W, H, behind=1)

    host = "<w:p>" + bg + "</w:p>"
    return host + "".join(line_paras), W, H


def convert(pdf_path: str, out_path: str) -> None:
    doc = fitz.open(pdf_path)
    font_reg, embedded_fonts = _build_font_registry(doc)

    media: dict[str, bytes] = {}
    rels: list[tuple[str, str]] = []
    pages = [_page_content(doc, page, i, media, rels, font_reg)
             for i, page in enumerate(doc)]
    doc.close()

    # Each page is its own SECTION carrying that page's size + orientation, so a
    # document with mixed portrait/landscape pages reproduces each correctly. The
    # section break (sectPr in a trailing paragraph) also serves as the page break.
    closer = ('<w:pPr><w:spacing w:before="0" w:after="0" w:line="1" '
              'w:lineRule="exact"/>')
    parts = []
    for i, (content, W, H) in enumerate(pages):
        parts.append(content)
        if i < len(pages) - 1:
            # ends this page's section (its size/orientation) and breaks to the next
            parts.append(f'<w:p><w:pPr>{_sectpr(W, H)}</w:pPr></w:p>')
    last_W, last_H = pages[-1][1], pages[-1][2]
    # A zero-height trailing paragraph keeps the last page's framed content from
    # being culled; the body-level sectPr gives the final (last page's) section.
    body = "".join(parts) + f'<w:p>{closer}</w:pPr></w:p>' + _sectpr(last_W, last_H)

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        f'<w:body>{body}</w:body></w:document>'
    )

    _write_docx(out_path, document_xml, media, rels, embedded_fonts)


def _write_docx(out_path: str, document_xml: str, media: dict, rels: list,
                embedded_fonts: dict) -> None:
    # --- embedded fonts: one obfuscated part + fontTable entry per family ------
    font_files: dict[str, bytes] = {}     # part name -> obfuscated bytes
    font_entries, font_rels = [], []
    for i, (family, (font_key, ob)) in enumerate(sorted(embedded_fonts.items()), 1):
        part = f"fonts/font{i}.odttf"
        rid = f"rIdFont{i}"
        font_files[f"word/{part}"] = ob
        font_rels.append(f'<Relationship Id="{rid}" '
                         f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/font" '
                         f'Target="{part}"/>')
        fa = html.escape(family, quote=True)
        font_entries.append(f'<w:font w:name="{fa}"><w:embedRegular r:id="{rid}" '
                            f'w:fontKey="{font_key}" w:subsetted="1"/></w:font>')
    has_fonts = bool(embedded_fonts)

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        + ('<Default Extension="odttf" ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/>'
           '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
           '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>'
           if has_fonts else '')
        + '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    rel_items = "".join(
        f'<Relationship Id="{rid}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="{tgt}"/>' for rid, tgt in rels)
    if has_fonts:
        rel_items += ('<Relationship Id="rIdFontTable" '
                      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" '
                      'Target="fontTable.xml"/>'
                      '<Relationship Id="rIdSettings" '
                      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" '
                      'Target="settings.xml"/>')
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{rel_items}</Relationships>'
    )
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        for name, data in media.items():
            z.writestr(f"word/media/{name}", data)
        if has_fonts:
            # <w:embedTrueTypeFonts/> tells Word to honour the embedded fonts.
            z.writestr("word/settings.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       '<w:embedTrueTypeFonts/><w:embedSystemFonts/></w:settings>')
            z.writestr("word/fontTable.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<w:fonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                       + "".join(font_entries) + '</w:fonts>')
            z.writestr("word/_rels/fontTable.xml.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       + "".join(font_rels) + '</Relationships>')
            for name, data in font_files.items():
                z.writestr(name, data)


if __name__ == "__main__":
    import sys
    convert(sys.argv[1], sys.argv[2])
    print("wrote", sys.argv[2])
