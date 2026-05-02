#!/usr/bin/env python3
"""Ensure requirements-ci.txt matches requirements.txt with only the Coqui TTS line removed."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ_MAIN = ROOT / "requirements.txt"
REQ_CI = ROOT / "requirements-ci.txt"

# PEP 508 distribution name at line start (before extras or version clauses).
_DIST = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?|[A-Za-z0-9])")


def _non_comment_lines(path: Path) -> list[str]:
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.split("#", 1)[0].strip()
        if s:
            out.append(s)
    return out


def _distribution_name(line: str) -> str:
    m = _DIST.match(line.strip())
    return (m.group(1) if m else "").lower()


def main() -> int:
    main_lines = _non_comment_lines(REQ_MAIN)
    ci_lines = _non_comment_lines(REQ_CI)
    main_without_tts = [ln for ln in main_lines if _distribution_name(ln) != "tts"]

    if main_without_tts != ci_lines:
        sys.stderr.write(
            "requirements-ci.txt must equal requirements.txt with the TTS package line removed.\n"
            "--- expected (requirements minus TTS) ---\n"
            + "\n".join(main_without_tts)
            + "\n--- actual (requirements-ci) ---\n"
            + "\n".join(ci_lines)
            + "\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
