from __future__ import annotations

import pytest

from trainerforge.core.process import ModuleInfo
from trainerforge.core.safety import UnsafeTargetError, ensure_safe_target


class FakeProcess:
    def __init__(self, name, modules=(), arch="x64", pid=1234):
        self.name = name
        self.arch = arch
        self.pid = pid
        self._modules = list(modules)

    def modules(self):
        return self._modules


def test_blocks_critical_processes():
    process = FakeProcess("lsass.exe")
    with pytest.raises(UnsafeTargetError, match="critical"):
        ensure_safe_target(process, own_pid=999)


def test_blocks_anti_cheat_modules():
    process = FakeProcess(
        "game.exe",
        modules=[ModuleInfo(name="EasyAntiCheat_x64.dll", path="", base=0, size=0)],
    )
    with pytest.raises(UnsafeTargetError, match="anti-cheat"):
        ensure_safe_target(process, own_pid=999)


def test_blocks_self_attachment():
    process = FakeProcess("python.exe", pid=1234)
    with pytest.raises(UnsafeTargetError, match="itself"):
        ensure_safe_target(process, own_pid=1234)


def test_allows_normal_target():
    process = FakeProcess("singleplayer.exe")
    assert isinstance(ensure_safe_target(process, own_pid=999), list)
