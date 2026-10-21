from __future__ import annotations

import json
from pathlib import Path

import pytest

from trainerforge.core.pointers import parse_base_expression
from trainerforge.core.scanner import ValueType, encode_value, parse_value
from trainerforge.core.table import SCHEMA, Table, TableEntry


def test_entry_validation_and_encoding():
    entry = TableEntry(
        description="Health",
        kind="absolute",
        base="0x1000",
        value_type="int32",
        value="100",
    )
    entry.validate()
    assert entry.value_bytes() == encode_value(100, ValueType.INT32)
    assert entry.value_text() == "100"
    assert entry.display_address() == "0x1000"


def test_pointer_entry_parses_offsets():
    entry = TableEntry(
        description="Ammo",
        kind="pointer",
        base="game.exe+0x1234",
        offsets=["0x10", "0x20"],
        value_type="int32",
        value="42",
        hotkey="Ctrl+F1",
    )
    entry.validate()
    base = parse_base_expression(entry.base)
    assert base.module == "game.exe"
    assert base.offset == 0x1234


@pytest.mark.parametrize(
    "entry, message",
    [
        (TableEntry(description="", base="0x1"), "description"),
        (TableEntry(description="x", kind="absolute", base="game.exe"), "numeric"),
        (TableEntry(description="x", kind="absolute", base="0x1", offsets=["0x4"]), "offsets"),
        (TableEntry(description="x", kind="pointer", base="0x1", offsets=[]), "offset"),
        (TableEntry(description="x", base="0x1", value="not a number"), "whole number"),
        (TableEntry(description="x", base="0x1", hotkey="NotAKey"), "Unsupported"),
    ],
)
def test_invalid_entries(entry, message):
    with pytest.raises(ValueError, match=message):
        entry.validate()


def test_table_roundtrip(tmp_path: Path):
    table = Table.new("Test table")
    table.process_name = "game.exe"
    table.add(
        TableEntry(
            description="Gold",
            kind="absolute",
            base="0xDEADBEEF",
            value_type="int64",
            value="99999",
            frozen=True,
            hotkey="F2",
            notes="A note",
        )
    )
    path = table.save(tmp_path / "test")
    assert path.name == "test.tforge.json"
    loaded = Table.load(path)
    assert loaded.name == "Test table"
    assert loaded.process_name == "game.exe"
    assert len(loaded.entries) == 1
    entry = loaded.entries[0]
    assert entry.description == "Gold"
    assert entry.base == "0xDEADBEEF"
    assert entry.value == "99999"
    assert entry.frozen is True
    assert entry.hotkey == "F2"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema"] == SCHEMA
    assert isinstance(raw["entries"], list)


def test_table_rejects_unknown_schema(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema": "other/1", "entries": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported table schema"):
        Table.load(path)


def test_table_rejects_invalid_entry_on_load(tmp_path: Path):
    path = tmp_path / "bad-entry.json"
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "entries": [
                    {
                        "description": "Broken pointer",
                        "kind": "pointer",
                        "base": "game.exe+0x10",
                        "offsets": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Broken pointer"):
        Table.load(path)


def test_parse_value_accepts_hex():
    assert parse_value("0x10", ValueType.INT32) == 16
    assert parse_value("-5", ValueType.INT32) == -5
    assert parse_value("1234.5", ValueType.FLOAT) == 1234.5
