"""TrainerForge table model and JSON persistence.

The table format is intentionally small, human-readable, and independent from
any commercial trainer format. It is safe to share: no executable content or
remote URLs are stored in it.
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pointers import (
    BaseExpression,
    PointerError,
    describe_chain,
    parse_base_expression,
    resolve_base_chain,
)
from .process import Process
from .scanner import (
    ValueType,
    encode_value,
    format_value,
    parse_value,
)
from .utils import format_hex, parse_int

SCHEMA = "trainerforge.table/1"
TABLE_SUFFIX = ".tforge.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class TableEntry:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    kind: str = "absolute"  # "absolute" or "pointer"
    base: str = "0x0"
    offsets: list[str] = field(default_factory=list)
    value_type: str = "int32"
    value: str = "0"
    frozen: bool = False
    hotkey: str = ""
    notes: str = ""

    # -- validation -------------------------------------------------------
    @property
    def value_enum(self) -> ValueType:
        return ValueType(self.value_type)

    def parsed_base(self) -> BaseExpression:
        return parse_base_expression(self.base)

    def parsed_offsets(self) -> list[int]:
        return [parse_int(offset, "offset") for offset in self.offsets]

    def validate(self) -> None:
        if not self.description.strip():
            raise ValueError("Give the entry a description.")
        if self.kind not in ("absolute", "pointer"):
            raise ValueError("Address kind must be 'absolute' or 'pointer'.")
        base = self.parsed_base()
        if self.kind == "absolute":
            if base.absolute is None:
                raise ValueError("Absolute entries need a numeric address.")
            if base.absolute <= 0:
                raise ValueError("Absolute address must be greater than zero.")
            if self.offsets:
                raise ValueError("Absolute entries must not have pointer offsets.")
        else:
            if not self.offsets:
                raise ValueError("Pointer entries need at least one offset.")
            self.parsed_offsets()
        # Validate the value against the declared type.
        encode_value(parse_value(self.value, self.value_enum), self.value_enum)
        if self.hotkey.strip():
            from .hotkeys import parse_hotkey

            parse_hotkey(self.hotkey)

    # -- runtime ----------------------------------------------------------
    def resolve(self, process: Process) -> int:
        base = self.parsed_base()
        if self.kind == "absolute":
            if base.absolute is None or base.absolute <= 0:
                raise PointerError("Invalid absolute address.")
            return base.absolute
        if not self.offsets:
            raise PointerError("Pointer entry has no offsets.")
        return resolve_base_chain(process, base, self.parsed_offsets())

    def value_bytes(self) -> bytes:
        value = parse_value(self.value, self.value_enum)
        return encode_value(value, self.value_enum)

    def value_number(self) -> int | float:
        return parse_value(self.value, self.value_enum)

    def value_text(self) -> str:
        return format_value(self.value_number(), self.value_enum)

    def display_address(self) -> str:
        try:
            if self.kind == "absolute":
                base = self.parsed_base()
                if base.absolute is not None:
                    return format_hex(base.absolute)
            base = self.parsed_base()
            offsets = self.parsed_offsets() if self.offsets else []
            return describe_chain(base, offsets)
        except (ValueError, PointerError):
            return self.base + (f" -> {', '.join(self.offsets)}" if self.offsets else "")

    def clone(self) -> "TableEntry":
        return copy.deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "kind": self.kind,
            "base": self.base,
            "offsets": list(self.offsets),
            "value_type": self.value_type,
            "value": self.value,
            "frozen": bool(self.frozen),
            "hotkey": self.hotkey,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableEntry":
        if not isinstance(data, dict):
            raise ValueError("Each table entry must be a JSON object.")
        value_type = str(data.get("value_type", "int32"))
        try:
            ValueType(value_type)
        except ValueError as exc:
            raise ValueError(f"Unknown value type: {value_type!r}") from exc
        offsets_raw = data.get("offsets", [])
        if offsets_raw is None:
            offsets_raw = []
        if not isinstance(offsets_raw, list):
            raise ValueError("'offsets' must be a list.")
        offsets = [str(item) for item in offsets_raw]
        entry = cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            description=str(data.get("description", "")),
            kind=str(data.get("kind", "absolute")),
            base=str(data.get("base", "0x0")),
            offsets=offsets,
            value_type=value_type,
            value=str(data.get("value", "0")),
            frozen=bool(data.get("frozen", False)),
            hotkey=str(data.get("hotkey", "")),
            notes=str(data.get("notes", "")),
        )
        return entry


@dataclass
class Table:
    name: str = "Untitled"
    process_name: str = ""
    entries: list[TableEntry] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    path: Path | None = field(default=None, repr=False, compare=False)

    @classmethod
    def new(cls, name: str = "Untitled") -> "Table":
        return cls(name=name or "Untitled")

    def entry(self, entry_id: str) -> TableEntry | None:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def add(self, entry: TableEntry) -> TableEntry:
        if self.entry(entry.id):
            entry.id = uuid.uuid4().hex[:12]
        self.entries.append(entry)
        self.touch()
        return entry

    def remove(self, entry_id: str) -> bool:
        for index, entry in enumerate(self.entries):
            if entry.id == entry_id:
                del self.entries[index]
                self.touch()
                return True
        return False

    def touch(self) -> None:
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "name": self.name,
            "process_name": self.process_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: Path | None = None) -> "Table":
        if not isinstance(data, dict):
            raise ValueError("Table file must contain a JSON object.")
        schema = data.get("schema")
        if schema != SCHEMA:
            raise ValueError(
                f"Unsupported table schema {schema!r}; this build expects {SCHEMA!r}."
            )
        entries_data = data.get("entries", [])
        if not isinstance(entries_data, list):
            raise ValueError("'entries' must be a list.")
        table = cls(
            name=str(data.get("name") or "Untitled"),
            process_name=str(data.get("process_name", "")),
            entries=[TableEntry.from_dict(item) for item in entries_data],
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or _now()),
            path=path,
        )
        # Ensure IDs are unique, even if a hand-edited file contains duplicates.
        seen: set[str] = set()
        for entry in table.entries:
            if entry.id in seen:
                entry.id = uuid.uuid4().hex[:12]
            seen.add(entry.id)
        # Reject unusable entries at load time rather than failing later in the
        # UI or, worse, writing to an unintended address.
        for index, entry in enumerate(table.entries, start=1):
            try:
                entry.validate()
            except ValueError as exc:
                label = entry.description.strip() or f"entry {index}"
                raise ValueError(f"Invalid {label!r}: {exc}") from exc
        return table

    @classmethod
    def load(cls, path: str | Path) -> "Table":
        table_path = Path(path)
        try:
            raw = table_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Could not read {table_path}: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {table_path}: {exc}") from exc
        return cls.from_dict(data, path=table_path)

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("No table path was provided.")
        if target.suffix.lower() != ".json":
            target = target.with_suffix(TABLE_SUFFIX)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        payload = json.dumps(
            self.to_dict(),
            indent=2,
            ensure_ascii=False,
        ) + "\n"
        temporary = target.with_name(target.name + ".tmp")
        try:
            temporary.write_text(payload, encoding="utf-8", newline="\n")
            os.replace(temporary, target)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ValueError(f"Could not save {target}: {exc}") from exc
        self.path = target
        return target
