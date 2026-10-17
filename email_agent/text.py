"""Plain-text-only email normalization."""

from __future__ import annotations

import re


QUOTE_START = re.compile(r"^On .+wrote:$|^From: .+<.+>$", re.I)


def newest_customer_text(raw: str) -> str:
    """Remove quoted history and common signatures without interpreting their content."""
    kept: list[str] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip() == "--" or QUOTE_START.match(line.strip()):
            break
        if line.lstrip().startswith(">"):
            break
        kept.append(line.rstrip())
    text = "\n".join(kept).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def safe_summary(text: str, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]
