"""Best-effort guardrails for a single-player-only memory editor.

This is not a security boundary and cannot detect every protected game. It is
a deliberate product decision: TrainerForge refuses obvious anti-cheat and
Windows-critical processes instead of pretending to be safe around them.
"""

from __future__ import annotations

from . import winapi
from .process import Process

CRITICAL_PROCESSES = {
    "system",
    "system idle process",
    "registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "winlogon.exe",
    "fontdrvhost.exe",
    "dwm.exe",
    "svchost.exe",
    "memory compression",
    "secure system",
}

ANTI_CHEAT_MARKERS = (
    "easyanticheat",
    "easy anti-cheat",
    "beclient",
    "beservice",
    "battleye",
    "vgc",
    "vgk",
    "vanguard",
    "faceit",
    "esea",
    "mhyprot",
    "gameguard",
    "xigncode",
    "nprotect",
    "ricochet",
    "equ8",
    "fairfight",
    "safeguard",
    "anti-cheat",
    "anticheat",
)


class UnsafeTargetError(RuntimeError):
    """The selected process is not an acceptable single-player target."""


def _matches_any(value: str, markers: tuple[str, ...]) -> str | None:
    lowered = value.lower()
    for marker in markers:
        if marker in lowered:
            return marker
    return None


def ensure_safe_target(process: Process, *, own_pid: int | None = None) -> list[str]:
    """Raise ``UnsafeTargetError`` for obvious unsafe targets.

    Returns a list of informational warnings for targets that are allowed but
    deserve a note in the UI.
    """
    if own_pid is not None and process.pid == own_pid:
        raise UnsafeTargetError("TrainerForge refuses to attach to itself.")

    if process.name.lower() in CRITICAL_PROCESSES:
        raise UnsafeTargetError(
            f"{process.name} is a Windows-critical process and cannot be a game target."
        )

    name_hit = _matches_any(process.name, ANTI_CHEAT_MARKERS)
    if name_hit:
        raise UnsafeTargetError(
            f"{process.name} looks like an anti-cheat component ({name_hit!r}). "
            "TrainerForge does not attach to anti-cheat or multiplayer processes."
        )

    modules = []
    try:
        modules = process.modules()
    except Exception:
        # Some protected processes deny module enumeration. The name checks
        # above still apply; a failure here is not treated as a bypass.
        modules = []

    hits = []
    for module in modules:
        marker = _matches_any(module.name, ANTI_CHEAT_MARKERS)
        if marker:
            hits.append((module.name, marker))
    if hits:
        names = ", ".join(sorted({name for name, _ in hits})[:4])
        raise UnsafeTargetError(
            f"An anti-cheat module is loaded in this process ({names}). "
            "TrainerForge only supports single-player/offline games and does "
            "not bypass anti-cheat protection."
        )

    warnings: list[str] = []
    if not winapi.is_admin():
        warnings.append(
            "TrainerForge is running without administrator rights; elevated games may be unreadable."
        )
    if process.arch == "x86":
        warnings.append("32-bit target detected; pointer chains use 4-byte pointers.")
    return warnings
