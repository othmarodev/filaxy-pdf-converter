"""
Engine entrypoint: convert + verify in one shot, emitting a JSON report the
macOS app (Swift) can parse. This is the single contract between the native UI
and the bundled engine.

The conversion engine is the coordinate-mapping engine (engine/coordmap.py):
every element is recreated at its exact PDF coordinates, so position/layout
fidelity is preserved BY CONSTRUCTION. Verification therefore focuses on DATA —
that no text, number, date, email or image was lost in extraction.

Usage:
    python -m engine.cli <input.pdf> <output.docx> [--json]
"""
from __future__ import annotations
import json
import sys
import time

import fitz  # PyMuPDF

from .coordmap import convert as coordmap_convert
from .verify import verify
from .verify_render import analyze as analyze_render


def _probe(src: str) -> tuple[int, bool, list]:
    """Inspect the PDF: page count, whether a usable text layer exists, and
    which pages look scanned (image-only, no extractable text). Kept here so the
    frozen engine doesn't pull in pdf2docx (only the coordmap pipeline ships)."""
    doc = fitz.open(src)
    pages = doc.page_count
    scanned: list[int] = []
    total_chars = 0
    for i, page in enumerate(doc):
        txt = page.get_text("text").strip()
        total_chars += len(txt)
        if len(txt) < 3 and page.get_images():
            scanned.append(i)
    doc.close()
    return pages, total_chars > 0, scanned


def run(src: str, out: str) -> dict:
    t0 = time.perf_counter()
    pages, has_text, scanned = _probe(src)
    warnings = []
    if scanned:
        warnings.append(
            f"{len(scanned)} página(s) parecen escaneadas (sin capa de texto): "
            f"{scanned}. La imagen se conserva, pero el texto no será editable "
            f"sin OCR.")
    elif not has_text:
        warnings.append(
            "No se detectó capa de texto — parece un PDF escaneado. La imagen se "
            "conserva fiel, pero el texto no será editable sin OCR.")

    coordmap_convert(src, out)
    rep = verify(src, out)
    rrep = analyze_render(out)   # re-check the PRODUCED docx: embedded fonts renderable
    elapsed = time.perf_counter() - t0

    # The badge is honest only if data completeness AND font renderability hold.
    overall_passed = rep.passed and rrep.passed
    return {
        "input": src,
        "output": out,
        "pages": pages,
        "elapsed_s": round(elapsed, 3),
        "has_text_layer": has_text,
        "scanned_pages": scanned,
        "warnings": warnings,
        "passed": overall_passed,
        "fidelity": {
            "text_score": round(rep.text_score, 2),
            "images": {"source": rep.src_images, "output": rep.out_images,
                        "match": rep.image_match},
            "tables_output": rep.out_tables,
            "missing_tokens": rep.missing_tokens,
            "sensitive_issues": rep.sensitive_issues,
            "passed": rep.passed,
        },
        # Render-fidelity risk: features that may not reproduce faithfully
        # (custom-font symbols, layered/transparent fills). Reuses the "layout"
        # slot in the JSON contract.
        "layout": {
            "src_tables": 0,
            "out_tables": 0,
            "issues": rrep.issues,
            "score": rrep.score,
            "passed": rrep.passed,
            "overlay_path": None,
        },
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    if len(args) < 2:
        print("usage: python -m engine.cli <input.pdf> <output.docx> [--json]")
        return 2
    result = run(args[0], args[1])
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        f = result["fidelity"]
        print(f"Converted {result['pages']} page(s) in {result['elapsed_s']}s -> {result['output']}")
        print(f"Fidelity (text recall): {f['text_score']}%")
        img = f["images"]
        print(f"Images: {img['output']}/{img['source']} " + ("✓" if img['match'] else "✗"))
        if f["sensitive_issues"]:
            print("⚠ Sensitive data issues:")
            for s in f["sensitive_issues"]:
                print("   •", s)
        else:
            print("✓ All numbers / dates / emails preserved")
        lay = result["layout"]
        if lay["issues"]:
            print(f"Render fidelity: {lay['score']}% — review:")
            for i in lay["issues"]:
                print("   •", i)
        else:
            print("Render fidelity: clean ✓ (position preserved by coordinate mapping)")
        for w in result["warnings"]:
            print("⚠", w)
        print("VERDICT:", "PASS ✓" if result["passed"] else "REVIEW NEEDED ✗")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
