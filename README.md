<div align="center">

# Filaxy PDF Converter

**Convert PDF → Word (.docx) preserving images, box positions, signatures and
every section exactly as the original — then *verify* it.**

A free, open-source, fully-offline macOS app by [Filaxy Labs](https://filaxylabs.co).

</div>

---

## Why it exists

Most PDF→Word tools reflow your document into a soup of text. The ones that keep
the layout still leave you guessing whether a number, a date or a signature
silently drifted. This app does two things that matter:

1. **High-fidelity conversion** — images (with transparency), tables, columns,
   positioned blocks and the exact text layer are reconstructed in the `.docx`.
2. **Fidelity verification** — after converting, it re-reads the *original* PDF's
   text layer (the ground truth) and compares it against the produced Word file,
   reporting a fidelity score and flagging any drift in **numbers, dates and
   emails**. You get a file you can actually trust.

That verification step is the reason the project exists: a salary certificate, an
invoice or a contract is worthless if a single figure converts wrong.

## How it works

```
┌─────────────────────┐     JSON      ┌────────────────────────────┐
│  macOS app (Swift)  │ ───────────▶  │  engine (Python, bundled)  │
│  SwiftUI · MVVM     │ ◀───────────  │  convert → verify          │
│  zero dependencies  │   fidelity    │  pdf2docx + own verifier   │
└─────────────────────┘    report     └────────────────────────────┘
```

- **`Sources/FilaxyPDFConverter/`** — the native macOS shell. Pure Swift, no
  third-party packages.
- **`engine/`** — the offline conversion + verification engine:
  - `convert.py` — high-fidelity conversion (built on the open-source
    [`pdf2docx`](https://github.com/ArtifexSoftware/pdf2docx)), tuned to favour
    source geometry, with scanned-page detection.
  - `verify.py` — the original contribution: a fidelity verifier that diffs the
    source PDF's text layer against the output, with special care for
    money/date/email tokens (handles the narrow no-break spaces used in Costa
    Rican number formatting, e.g. `2 282 144,79`).
  - `cli.py` — the JSON contract consumed by the Swift app.

> **Honest credits:** the raw conversion leans on `pdf2docx` (MIT). The original
> engineering here is the *verification layer*, the native app, the max-fidelity
> tuning and the offline packaging.

## Build from source

Requirements: macOS 13+, Swift 6 toolchain, Python 3.9+.

```bash
# 1. Engine (Python)
cd engine && python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt

# 2. Quick engine test (convert + verify a PDF)
python -m engine.cli input.pdf output.docx

# 3. macOS app
swift build              # compile
./build-app.sh           # assemble Filaxy PDF Converter.app
```

## Roadmap

- [x] Conversion engine tuned for maximum fidelity
- [x] Fidelity verification layer (text + images + sensitive data)
- [x] Native SwiftUI app shell (drag & drop → convert → fidelity report)
- [ ] Free OCR fallback (Tesseract) for scanned PDFs
- [ ] Frozen engine binary (PyInstaller) → 100% self-contained `.app`
- [ ] Signed + notarized DMG
- [ ] Landing + downloads on [filaxy.shop](https://filaxy.shop)

## Support the project

Filaxy PDF Converter is free. If it saved you time, you can tip the work:

- **PayPal:** _(coming soon)_
- **USDT (TRC20):** _(coming soon)_

## License

[MIT](LICENSE) © 2026 Othmaro Fallas Rojas — Filaxy Labs, Inc.
