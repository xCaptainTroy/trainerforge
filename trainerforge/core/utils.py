"""Small shared helpers with no Windows dependencies."""

from __future__ import annotations

import re

_INT_RE = re.compile(r"^[+-]?(?:0[xX][0-9a-fA-F]+|[0-9]+)$")


def parse_int(text: str | int, field: str = "value") -> int:
    """Parse a decimal or 0x-prefixed integer.

    Python's ``int(value, 0)`` rejects leading-zero decimals such as ``010``,
    which are common in game guides. This parser accepts both forms.
    """
    if isinstance(text, int):
        return text
    raw = str(text).strip().replace("_", "")
    if not raw:
        raise ValueError(f"{field} is empty")
    if not _INT_RE.match(raw):
        raise ValueError(f"{field} must be a decimal or 0x-prefixed integer: {text!r}")
    sign = 1
    body = raw
    if body[0] in "+-":
        if body[0] == "-":
            sign = -1
        body = body[1:]
    if body.lower().startswith("0x"):
        return sign * int(body, 16)
    return sign * int(body, 10)


def format_hex(value: int) -> str:
    """Format a non-negative address as an uppercase hexadecimal string."""
    return f"0x{int(value):X}"


def parse_offset_list(text: str) -> list[int]:
    """Parse ``0x10, 0x20`` (commas or semicolons) into integers."""
    raw = (text or "").replace(";", ",").strip()
    if not raw:
        return []
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return [parse_int(part, "offset") for part in parts]


def human_bytes(count: int) -> str:
    """Return a short human-readable byte count."""
    value = float(max(0, count))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))
