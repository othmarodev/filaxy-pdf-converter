"""PyInstaller entry point for the frozen, self-contained engine binary.

Bundles the coordinate-mapping engine + verification so the .app runs fully
offline with no Python/venv. Invoked exactly like `python -m engine.cli`:
    filaxy-engine <input.pdf> <output.docx> [--json]
"""
import sys
from engine.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
