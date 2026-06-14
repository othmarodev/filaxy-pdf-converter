"""
Full-document regression — LOCAL ONLY.

Runs every real sample PDF in tests/fixtures/ through the engine, renders the
DOCX with LibreOffice, and audits it for SHADING mismatches and TEXT OVERFLOW
(tools/audit.py). Fails if any document regresses.

These fixtures are personal documents (salary, ID, address) and are GITIGNORED —
they must never reach the public repo. Drop your own PDFs in tests/fixtures/ to
run this locally:

    python tests/test_samples_local.py

Skips cleanly (exit 0) when there are no fixtures or LibreOffice isn't installed,
so a fresh public clone still passes.
"""
from __future__ import annotations
import glob
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import coordmap          # noqa: E402
import audit                          # noqa: E402  (tools/audit.py)

SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def _render(docx: str, outdir: str) -> str | None:
    if not os.path.exists(SOFFICE):
        return None
    subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", outdir, docx],
                   check=True, capture_output=True, timeout=180)
    return os.path.join(outdir, os.path.splitext(os.path.basename(docx))[0] + ".pdf")


def main() -> int:
    pdfs = sorted(glob.glob(os.path.join(FIXTURES, "*.pdf")))
    if not pdfs:
        print(f"SKIP  no fixtures in {FIXTURES} (drop personal PDFs there to run)")
        return 0
    if not os.path.exists(SOFFICE):
        print("SKIP  LibreOffice not installed — can't render DOCX for audit")
        return 0

    tmp = tempfile.mkdtemp()
    total = 0
    for pdf in pdfs:
        name = os.path.splitext(os.path.basename(pdf))[0]
        docx = os.path.join(tmp, name + ".docx")
        coordmap.convert(pdf, docx)
        res = _render(docx, tmp)
        issues = audit.audit(pdf, res)
        print(f"{'OK ' if issues == 0 else 'BAD'}  {name}: {issues} issue(s)")
        total += issues
    print(f"\n{'ALL PASS' if total == 0 else str(total) + ' TOTAL ISSUE(S)'}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
