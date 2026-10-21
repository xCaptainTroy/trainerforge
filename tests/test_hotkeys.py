from __future__ import annotations

import pytest

from trainerforge.core.hotkeys import HotkeyError, parse_hotkey


@pytest.mark.parametrize(
    "text, expected",
    [
        ("F1", "F1"),
        ("ctrl+f2", "Ctrl+F2"),
        ("Alt+Shift+3", "Alt+Shift+3"),
        ("win+space", "Win+Space"),
        ("Ctrl+PageUp", "Ctrl+PageUp"),
    ],
)
def test_parse_hotkey(text, expected):
    hotkey = parse_hotkey(text)
    assert hotkey.text == expected
    assert hotkey.vk > 0


@pytest.mark.parametrize(
    "text",
    ["", "Ctrl", "Ctrl+", "NotAKey", "Ctrl+Ctrl+F1", "Ctrl+NotAKey"],
)
def test_invalid_hotkeys(text):
    with pytest.raises(HotkeyError):
        parse_hotkey(text)
