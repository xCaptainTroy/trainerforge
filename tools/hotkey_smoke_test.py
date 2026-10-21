"""Verify the global hotkey path against a real Windows message queue.

This sends a synthetic Ctrl+Alt+Shift+F24 chord, which is reserved by the
registered hotkey, and waits for the manager's Tk-side callback. It requires an
interactive desktop session (the same requirement as the real application).
"""

from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trainerforge.core.hotkeys import HotkeyManager  # noqa: E402

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_F24 = 0x87
KEYEVENTF_KEYUP = 0x0002


def send_chord() -> None:
    user32 = ctypes.windll.user32
    for key in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_F24):
        user32.keybd_event(key, 0, 0, 0)
    for key in (VK_F24, VK_SHIFT, VK_MENU, VK_CONTROL):
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)


def main() -> int:
    root = tk.Tk()
    root.withdraw()
    fired: list[tuple[str, str]] = []
    manager = HotkeyManager(root, lambda token, text: fired.append((token, text)))
    try:
        manager.start()
        errors = manager.replace({"smoke": "Ctrl+Alt+Shift+F24"})
        if errors:
            print("hotkey registration failed:", errors)
            return 1
        send_chord()
        deadline = time.time() + 3.0
        while time.time() < deadline and not fired:
            root.update()
            time.sleep(0.02)
        if not fired:
            print("hotkey did not fire")
            return 1
        print(f"hotkey ok: {fired[0][1]} -> {fired[0][0]}")
        return 0
    finally:
        manager.stop()
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
