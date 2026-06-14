#!/bin/bash
# Freeze the conversion engine into a self-contained binary with PyInstaller,
# so the .app runs fully offline (no Python/venv) and is distributable +
# notarizable. Produces dist/filaxy-engine/ (onedir — notarization-friendly:
# each dylib can be signed individually, unlike --onefile).
#
# Run:  tools/freeze_engine.sh
set -e
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "no .venv — create it first"; exit 1; }

echo "→ ensuring PyInstaller is installed…"
"$PY" -m pip install --quiet --upgrade pyinstaller

echo "→ cleaning previous build…"
rm -rf build dist filaxy-engine.spec

echo "→ freezing engine (onedir)…"
"$PY" -m PyInstaller --noconfirm --clean --onedir --name filaxy-engine \
  --paths . \
  --collect-all fitz \
  --collect-all PIL \
  --collect-all fontTools \
  --exclude-module pdf2docx \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  freeze/filaxy_engine.py

echo "✓ built dist/filaxy-engine/  (binary: dist/filaxy-engine/filaxy-engine)"
