#!/usr/bin/env python3
"""Write the release pack SHA-256 manifest in deterministic path order."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    Path("@rtw2_rival_empires_balanced.pack"),
    Path("compatibility/@rtw2_rival_empires_balanced_module_only.pack"),
)


def main() -> int:
    lines = []
    for relative in FILES:
        contents = (ROOT / relative).read_bytes()
        digest = hashlib.sha256(contents).hexdigest()
        lines.append(f"{digest}  {relative.as_posix()}")
    (ROOT / "SHA256SUMS.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="",
    )
    print("updated SHA256SUMS.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
