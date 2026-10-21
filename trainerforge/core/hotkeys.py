"""Global hotkeys using a dedicated Win32 message window.

``RegisterHotKey`` must be paired with a window (or a thread message queue).
Tk's main loop owns the UI thread's queue, so a hidden message-only window on a
small worker thread is both simpler and more reliable: the OS posts
``WM_HOTKEY`` to that window, the worker enqueues the event, and the Tk thread
drains the queue from an ``after`` callback. No Tk object is touched off the UI
thread.
"""

from __future__ import annotations

import ctypes
import logging
import queue
import re
import threading
import tkinter as tk
from dataclasses import dataclass
from typing import Callable

from . import winapi

logger = logging.getLogger(__name__)


class HotkeyError(ValueError):
    """A hotkey string is invalid or unavailable."""


@dataclass(frozen=True)
class Hotkey:
    mods: int
    vk: int
    text: str

    @property
    def signature(self) -> tuple[int, int]:
        return self.mods, self.vk


_MODIFIERS = {
    "ctrl": (winapi.MOD_CONTROL, "Ctrl"),
    "control": (winapi.MOD_CONTROL, "Ctrl"),
    "alt": (winapi.MOD_ALT, "Alt"),
    "shift": (winapi.MOD_SHIFT, "Shift"),
    "win": (winapi.MOD_WIN, "Win"),
    "windows": (winapi.MOD_WIN, "Win"),
    "super": (winapi.MOD_WIN, "Win"),
    "meta": (winapi.MOD_WIN, "Win"),
}

_KEY_ALIASES = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "ins": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "scrolllock": 0x91,
    "numlock": 0x90,
    "`": 0xC0,
    "-": 0xBD,
    "=": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    ";": 0xBA,
    "'": 0xDE,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
}

_F_KEY = re.compile(r"^F([1-9]|1[0-9]|2[0-4])$")

_MODIFIER_ORDER = (
    (winapi.MOD_CONTROL, "Ctrl"),
    (winapi.MOD_ALT, "Alt"),
    (winapi.MOD_SHIFT, "Shift"),
    (winapi.MOD_WIN, "Win"),
)


def parse_hotkey(text: str) -> Hotkey:
    raw = (text or "").strip()
    if not raw:
        raise HotkeyError("Hotkey is empty.")
    tokens = [token.strip() for token in raw.split("+") if token.strip()]
    if not tokens:
        raise HotkeyError("Hotkey is empty.")
    key_token = tokens[-1]
    mods = 0
    for token in tokens[:-1]:
        key = token.lower()
        if key not in _MODIFIERS:
            raise HotkeyError(f"Unknown modifier {token!r}.")
        bit, _ = _MODIFIERS[key]
        if mods & bit:
            raise HotkeyError(f"Modifier {token!r} appears twice.")
        mods |= bit

    key_lower = key_token.lower()
    if key_lower in _MODIFIERS:
        raise HotkeyError("A hotkey needs a key, not only a modifier.")
    if key_lower in _KEY_ALIASES:
        vk = _KEY_ALIASES[key_lower]
        display_key = {
            0x0D: "Enter",
            0x1B: "Esc",
            0x20: "Space",
            0x21: "PageUp",
            0x22: "PageDown",
            0x08: "Backspace",
            0x2D: "Insert",
            0x2E: "Delete",
            0x2C: "PrintScreen",
        }.get(vk, key_token.upper())
    elif len(key_token) == 1 and key_token.isalnum():
        vk = ord(key_token.upper())
        display_key = key_token.upper()
    elif _F_KEY.match(key_token.upper()):
        number = int(key_token.upper()[1:])
        vk = 0x70 + number - 1
        display_key = f"F{number}"
    else:
        raise HotkeyError(
            f"Unsupported key {key_token!r}. Try F1-F24, A-Z, 0-9, "
            "Space, Insert, Delete, Home, End, PageUp, or PageDown."
        )

    display_mods = [label for bit, label in _MODIFIER_ORDER if mods & bit]
    display = "+".join(display_mods + [display_key])
    return Hotkey(mods=mods, vk=vk, text=display)


class _HotkeyCommand:
    """A registration request executed on the hidden window's thread."""

    def __init__(self, bindings: dict[str, str]):
        self.bindings = bindings
        self.done = threading.Event()
        self.result: list[tuple[str, str]] = []


class HotkeyManager:
    """Register global hotkeys and dispatch them through a Tk callback.

    The hidden window and its message loop live on a daemon thread. Registration
    and unregistration are marshalled to that thread with ``WM_APP`` messages so
    the Win32 rule "register on the window's thread" is always satisfied.
    """

    POLL_MS = 60
    WM_APP = 0x8000

    def __init__(self, root: tk.Misc, callback: Callable[[str, str], None]):
        self.root = root
        self.callback = callback
        self._bindings: dict[int, tuple[Hotkey, str]] = {}
        self._next_id = 1
        self._active = False
        self._after_id: str | None = None
        self._events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._commands: queue.Queue[_HotkeyCommand] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._hwnd: int | None = None
        self._start_error = ""
        self._class_name = f"TrainerForgeHotkeyWindow-{id(self):x}"

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._ready.clear()
        self._start_error = ""
        self._thread = threading.Thread(
            target=self._window_thread,
            name="trainerforge-hotkeys",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(2.0):
            self._start_error = "Timed out while creating the hotkey message window."
            logger.warning(self._start_error)
        self._schedule()

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        hwnd = self._hwnd
        if hwnd:
            winapi.user32.PostMessageW(hwnd, winapi.WM_CLOSE, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._bindings.clear()
        self._hwnd = None

    # -- registration -----------------------------------------------------
    def replace(self, bindings: dict[str, str]) -> list[tuple[str, str]]:
        """Replace all bindings atomically.

        ``bindings`` maps an opaque token (the table entry ID) to a hotkey
        string. Returns ``(token, error)`` for bindings that could not be
        registered. The old bindings stay in effect if the message window is
        unavailable or the request times out.
        """
        requested = {
            token: text for token, text in bindings.items() if (text or "").strip()
        }
        if not self._active or not self._hwnd:
            reason = self._start_error or "Global hotkeys are unavailable."
            return [(token, reason) for token in requested]
        command = _HotkeyCommand(requested)
        self._commands.put(command)
        if not winapi.user32.PostMessageW(self._hwnd, self.WM_APP, 0, 0):
            reason = f"Could not contact the hotkey window: {winapi.error_text()}"
            return [(token, reason) for token in requested]
        if not command.done.wait(2.0):
            return [
                (token, "Timed out while registering the global hotkey.")
                for token in requested
            ]
        return command.result

    def _apply_bindings(self, bindings: dict[str, str]) -> list[tuple[str, str]]:
        self._unregister_all()
        errors: list[tuple[str, str]] = []
        seen: dict[tuple[int, int], str] = {}
        for token, text in bindings.items():
            try:
                hotkey = parse_hotkey(text)
            except HotkeyError as exc:
                errors.append((token, str(exc)))
                continue
            if hotkey.signature in seen:
                errors.append(
                    (token, f"{hotkey.text} is already assigned to another entry.")
                )
                continue
            hotkey_id = self._next_id
            self._next_id += 1
            if not winapi.user32.RegisterHotKey(
                self._hwnd,
                hotkey_id,
                hotkey.mods | winapi.MOD_NOREPEAT,
                hotkey.vk,
            ):
                code = winapi.last_error()
                errors.append(
                    (
                        token,
                        f"Windows rejected {hotkey.text} ({winapi.error_text(code)}). "
                        "It may be reserved or in use by another app.",
                    )
                )
                continue
            self._bindings[hotkey_id] = (hotkey, token)
            seen[hotkey.signature] = token
        return errors

    def _unregister_all(self) -> None:
        for hotkey_id in list(self._bindings):
            try:
                winapi.user32.UnregisterHotKey(self._hwnd, hotkey_id)
            except Exception:
                pass
        self._bindings.clear()

    # -- hidden window thread --------------------------------------------
    def _window_thread(self) -> None:
        hinstance = winapi.kernel32.GetModuleHandleW(None)
        class_name = self._class_name
        registered_class = False
        window_handle = 0
        try:
            def wndproc(hwnd, message, wparam, lparam):
                try:
                    if message == winapi.WM_HOTKEY:
                        binding = self._bindings.get(int(wparam))
                        if binding is not None:
                            self._events.put((binding[1], binding[0].text))
                        return 0
                    if message == winapi.WM_CLOSE:
                        winapi.user32.DestroyWindow(hwnd)
                        return 0
                    if message == winapi.WM_DESTROY:
                        winapi.user32.PostQuitMessage(0)
                        return 0
                    if message == self.WM_APP:
                        self._drain_commands()
                        return 0
                    return winapi.user32.DefWindowProcW(
                        hwnd, message, wparam, lparam
                    )
                except Exception:
                    logger.exception("Unhandled hotkey window message")
                    return 0

            wndproc_ref = winapi.WNDPROC(wndproc)
            wc = winapi.WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(winapi.WNDCLASSEXW)
            wc.lpfnWndProc = wndproc_ref
            wc.hInstance = hinstance
            wc.lpszClassName = class_name
            if not winapi.user32.RegisterClassExW(ctypes.byref(wc)):
                self._start_error = (
                    f"Could not register the hotkey window: {winapi.error_text()}"
                )
                return
            registered_class = True
            hwnd = winapi.user32.CreateWindowExW(
                0,
                class_name,
                "TrainerForgeHotkeys",
                0,
                0,
                0,
                0,
                0,
                winapi.HWND_MESSAGE,
                None,
                hinstance,
                None,
            )
            if not hwnd:
                self._start_error = (
                    f"Could not create the hotkey window: {winapi.error_text()}"
                )
                return
            window_handle = int(getattr(hwnd, "value", hwnd))
            self._hwnd = window_handle
            self._ready.set()
            message = winapi.MSG()
            while self._active:
                result = winapi.user32.GetMessageW(
                    ctypes.byref(message), None, 0, 0
                )
                if result <= 0:
                    break
                winapi.user32.TranslateMessage(ctypes.byref(message))
                winapi.user32.DispatchMessageW(ctypes.byref(message))
        except Exception as exc:  # pragma: no cover - defensive
            self._start_error = f"Hotkey window failed: {exc}"
            logger.exception("Hotkey window thread failed")
        finally:
            self._hwnd = None
            self._ready.set()
            self._fail_pending("The hotkey window is not available.")
            if window_handle:
                try:
                    winapi.user32.DestroyWindow(window_handle)
                except Exception:
                    pass
            if registered_class:
                try:
                    winapi.user32.UnregisterClassW(class_name, hinstance)
                except Exception:
                    pass

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            try:
                command.result = self._apply_bindings(command.bindings)
            except Exception as exc:  # pragma: no cover - defensive
                command.result = [
                    (token, f"Hotkey registration failed: {exc}")
                    for token in command.bindings
                ]
            finally:
                command.done.set()

    def _fail_pending(self, reason: str) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            command.result = [(token, reason) for token in command.bindings]
            command.done.set()

    # -- UI-side dispatch -------------------------------------------------
    def _schedule(self) -> None:
        if self._active and self._after_id is None:
            self._after_id = self.root.after(self.POLL_MS, self._drain_events)

    def _drain_events(self) -> None:
        self._after_id = None
        if not self._active:
            return
        for _ in range(64):
            try:
                token, text = self._events.get_nowait()
            except queue.Empty:
                break
            try:
                self.callback(token, text)
            except Exception:
                logger.exception("Global hotkey callback failed")
        self._schedule()
