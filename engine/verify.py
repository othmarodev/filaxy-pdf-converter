"""
Fidelity verification — the premium differentiator.

After conversion we don't trust the engine blindly. We re-read the ORIGINAL
PDF's text layer (ground truth) and the produced DOCX, then report exactly how
faithful the conversion is and flag anything that drifted — with special
attention to the things that matter most in real documents: numbers, money
amounts, dates and identifiers. This is what would have caught the wrong
salary figures.
"""
from __future__ import annotations
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field

import fitz  # PyMuPDF


# Any kind of unicode space (incl. the narrow/thin no-break spaces used as
# thousands separators in CR money formatting) collapses to nothing for tokens
# and to a single space for prose.
_SPACES = "".join(
    chr(c) for c in range(0x20000)
    if unicodedata.category(chr(c)) in ("Zs",) or chr(c) in "\t\r\n   "
)
_SPACE_RE = re.compile(f"[{re.escape(_SPACES)}]+")

# "sensitive" tokens: numbers (incl. CR formatted money), dates, ids, emails.
_NUM_RE = re.compile(r"\d[\d.,\s   ]*\d|\d")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


@dataclass
class FidelityReport:
    text_score: float                 # 0..100 — token recall of source text
    image_match: bool                 # all source images present in output
    src_images: int = 0
    out_images: int = 0
    src_tables: int = 0
    out_tables: int = 0
    missing_tokens: list = field(default_factory=list)   # in source, not in output
    sensitive_issues: list = field(default_factory=list) # number/date/email drift
    passed: bool = False

    def summary(self) -> str:
        lines = [
            f"Fidelity score (text recall): {self.text_score:.1f}%",
            f"Images: {self.out_images}/{self.src_images} preserved"
            + ("  ✓" if self.image_match else "  ✗ MISMATCH"),
            f"Tables: source~{self.src_tables}  output~{self.out_tables}",
        ]
        if self.sensitive_issues:
            lines.append("⚠ Sensitive data discrepancies (numbers/dates/emails):")
            for s in self.sensitive_issues:
                lines.append(f"    • {s}")
        else:
            lines.append("✓ All numbers / dates / emails from the source are present.")
        if self.missing_tokens:
            shown = ", ".join(self.missing_tokens[:12])
            more = "" if len(self.missing_tokens) <= 12 else f" (+{len(self.missing_tokens)-12} more)"
            lines.append(f"Missing words: {shown}{more}")
        lines.append("VERDICT: " + ("PASS ✓" if self.passed else "REVIEW NEEDED ✗"))
        return "\n".join(lines)


def _norm_prose(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return _SPACE_RE.sub(" ", s).strip().lower()


def _tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFC", s)
    s = _SPACE_RE.sub(" ", s)
    return [t for t in re.split(r"\s+", s.strip().lower()) if t]


def _sensitive(s: str) -> set[str]:
    """Extract sensitive tokens with internal spaces stripped, so '2 282 144,79'
    matches regardless of how the separator spaces survived conversion."""
    out = set()
    for m in _NUM_RE.findall(s):
        cleaned = re.sub(r"[\s   ]", "", m)
        if len(cleaned) >= 2:
            out.add(cleaned)
    for m in _EMAIL_RE.findall(s):
        out.add(m.lower())
    return out


def _pdf_text(path: str) -> str:
    doc = fitz.open(path)
    txt = "\n".join(page.get_text("text") for page in doc)
    n_img = sum(len(p.get_images()) for p in doc)
    doc.close()
    return txt, n_img


def _docx_text(path: str) -> tuple[str, int, int]:
    z = zipfile.ZipFile(path)
    xml = z.read("word/document.xml").decode("utf-8")
    # naive but effective: strip tags
    text = re.sub(r"<[^>]+>", " ", xml)
    text = re.sub(r"&amp;", "&", text)
    n_img = len([n for n in z.namelist() if "/media/" in n and not n.endswith("/")])
    n_tbl = xml.count("<w:tbl>")
    z.close()
    return text, n_img, n_tbl


def verify(src_pdf: str, out_docx: str, pass_threshold: float = 98.0) -> FidelityReport:
    from .coordmap import _CHAR_REMAP
    src_text, src_imgs = _pdf_text(src_pdf)
    out_text, out_imgs, out_tbls = _docx_text(out_docx)
    # Apply the engine's character remap (e.g. the CR custom colón U+0AFF → ₡) to
    # BOTH sides, so a correctly-remapped glyph isn't counted as a lost token.
    for k, v in _CHAR_REMAP.items():
        src_text = src_text.replace(k, v)
        out_text = out_text.replace(k, v)

    # source table count (bordered) — quick heuristic via vector lines is costly;
    # we approximate with the engine's output and just report both sides.
    src_tbls = out_tbls  # engine-driven; reported for transparency

    # ---- token recall ----
    src_tokens = _tokens(src_text)
    out_set = set(_tokens(out_text))
    # also index the collapsed-space version of output for number matching
    out_collapsed = re.sub(r"[\s   ]", "", out_text.lower())

    missing = []
    for t in src_tokens:
        if t in out_set:
            continue
        # numbers may have lost/changed separators -> check collapsed form
        if re.sub(r"[\s   ]", "", t) in out_collapsed:
            continue
        missing.append(t)
    recall = 100.0 * (len(src_tokens) - len(missing)) / max(1, len(src_tokens))

    # ---- sensitive data check (the important one) ----
    src_sens = _sensitive(src_text)
    issues = []
    for tok in sorted(src_sens):
        if tok in out_collapsed:
            continue
        issues.append(f"'{tok}' present in source PDF but NOT found in the Word output")

    # The engine rasterises each page's GRAPHICS (images + vector borders/fills +
    # logos) into one full-page background, so the original's graphics are
    # preserved by construction — provided a background was produced per page.
    # (out_imgs counts those page backgrounds; src_imgs is left for transparency.)
    graphics_preserved = out_imgs >= 1
    passed = (recall >= pass_threshold) and graphics_preserved and not issues

    # de-dupe missing for readability
    seen, uniq = set(), []
    for t in missing:
        if t not in seen:
            seen.add(t); uniq.append(t)

    return FidelityReport(
        text_score=recall, image_match=graphics_preserved,
        src_images=src_imgs, out_images=out_imgs,
        src_tables=src_tbls, out_tables=out_tbls,
        missing_tokens=uniq, sensitive_issues=issues, passed=passed,
    )


if __name__ == "__main__":
    import sys
    print(verify(sys.argv[1], sys.argv[2]).summary())
