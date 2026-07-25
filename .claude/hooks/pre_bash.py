#!/usr/bin/env python3
"""Block risky shell commands before they run."""

from __future__ import annotations

import json
import re
import sys

BLOCKED = [
    r"\brm\s+-rf\s+/",
    r"\bdel\s+/[fs]\b",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bDrop-Database\b",
    r"\bFORMAT\s+[A-Z]:",
]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    command = (
        payload.get("tool_input", {}).get("command")
        or payload.get("command")
        or ""
    )

    for pattern in BLOCKED:
        if re.search(pattern, command, re.IGNORECASE):
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": f"Blocked risky command matching: {pattern}",
                    }
                )
            )
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
