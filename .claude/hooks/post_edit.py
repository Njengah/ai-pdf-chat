#!/usr/bin/env python3
"""Log file edits for session visibility."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parents[2] / ".claude" / "edit-log.jsonl"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": payload.get("tool_name"),
        "file": tool_input.get("file_path") or tool_input.get("path"),
    }

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
