from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qa_automation.publication_audit import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["--root", str(PROJECT_ROOT), *sys.argv[1:]]))
