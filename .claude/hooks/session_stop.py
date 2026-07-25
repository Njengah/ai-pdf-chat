#!/usr/bin/env python3
"""Print a short session summary when Claude stops."""

from __future__ import annotations

import json
import sys
from pathlib import Path

LOG = Path(__file__).resolve().parents[2] / ".claude" / "edit-log.jsonl"


def main() -> None:
    if not LOG.exists():
        sys.exit(0)

    lines = [ln for ln in LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    files = []
    for line in lines[-20:]:
        try:
            files.append(json.loads(line).get("file"))
        except json.JSONDecodeError:
            continue

    unique = [f for f in dict.fromkeys(files) if f]
    if unique:
        print(f"Session touched {len(unique)} file(s): {', '.join(unique[:8])}")
    sys.exit(0)


if __name__ == "__main__":
    main()
