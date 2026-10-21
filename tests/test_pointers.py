from __future__ import annotations

import pytest

from trainerforge.core.pointers import (
    PointerError,
    parse_base_expression,
    resolve_chain,
)


class FakeProcess:
    pointer_size = 8
    address_limit = 0x7FFFFFFEFFFF

    def __init__(self, pointers):
        self.pointers = pointers

    def read_pointer(self, address):
        if address not in self.pointers:
            raise PointerError(f"no pointer at {address:#x}")
        return self.pointers[address]


def test_parse_base_forms():
    absolute = parse_base_expression("0x1000")
    assert absolute.absolute == 0x1000
    assert absolute.module is None

    arithmetic = parse_base_expression("0x1000+0x20")
    assert arithmetic.absolute == 0x1020

    module = parse_base_expression("Game.exe+0x1A2B")
    assert module.module == "Game.exe"
    assert module.offset == 0x1A2B

    bare_module = parse_base_expression("Game.exe")
    assert bare_module.module == "Game.exe"
    assert bare_module.offset == 0


def test_resolve_chain():
    process = FakeProcess({0x1000: 0x2000, 0x2010: 0x3000})
    assert resolve_chain(process, "0x1000", [0x10]) == 0x2010
    assert resolve_chain(process, "0x1000", [0x10, 0x20]) == 0x3020


def test_null_pointer_is_rejected():
    process = FakeProcess({0x1000: 0})
    with pytest.raises(PointerError, match="Null pointer"):
        resolve_chain(process, "0x1000", [0x10])
