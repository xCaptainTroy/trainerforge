"""Module-relative pointers and multi-level pointer-chain resolution."""

from __future__ import annotations

from dataclasses import dataclass

from .process import Process, ProcessError
from .utils import format_hex, parse_int


class PointerError(ProcessError):
    """A base expression or pointer chain could not be resolved."""


@dataclass(frozen=True)
class BaseExpression:
    raw: str
    module: str | None = None
    offset: int = 0
    absolute: int | None = None

    def resolve(self, process: Process) -> int:
        if self.absolute is not None:
            address = int(self.absolute)
        elif self.module:
            try:
                module = process.module_by_name(self.module)
            except ProcessError as exc:
                raise PointerError(str(exc)) from exc
            address = module.base + self.offset
        else:
            raise PointerError(f"Invalid base expression: {self.raw!r}")
        if address <= 0:
            raise PointerError(f"Base expression resolved to an invalid address: {self.raw!r}")
        return address

    def describe(self) -> str:
        if self.absolute is not None:
            return format_hex(self.absolute)
        if self.module:
            if self.offset:
                return f"{self.module}+{format_hex(self.offset)}"
            return self.module
        return self.raw


def parse_base_expression(text: str) -> BaseExpression:
    """Parse ``0x7FF...``, ``game.exe+0x1A2B``, or a module name.

    Address arithmetic on an absolute base is accepted as a convenience:
    ``0x1000+0x20`` becomes ``0x1020``.
    """
    raw = (text or "").strip()
    if not raw:
        raise PointerError("Base address is empty.")

    if "+" in raw:
        left, right = raw.rsplit("+", 1)
        left = left.strip()
        right = right.strip()
        if not left or not right:
            raise PointerError(f"Invalid base expression: {text!r}")
        offset = parse_int(right, "base offset")
        try:
            absolute = parse_int(left, "base address")
            return BaseExpression(
                raw=raw,
                offset=offset,
                absolute=absolute + offset,
            )
        except ValueError:
            return BaseExpression(raw=raw, module=left, offset=offset)

    try:
        return BaseExpression(raw=raw, absolute=parse_int(raw, "base address"))
    except ValueError:
        # A bare module name such as "game.exe" is a valid module+0 base.
        return BaseExpression(raw=raw, module=raw, offset=0)


def parse_chain(text: str, offset_text: str = "") -> tuple[BaseExpression, list[int]]:
    """Parse a base expression and comma-separated offset list."""
    base = parse_base_expression(text)
    if offset_text.strip():
        parts = [part.strip() for part in offset_text.replace(";", ",").split(",") if part.strip()]
        offsets = [parse_int(part, "offset") for part in parts]
    else:
        offsets = []
    return base, offsets


def resolve_chain(process: Process, base_text: str, offsets: list[int]) -> int:
    """Resolve ``base -> offset1 -> offset2 ...`` to a final address.

    Each offset means: read a pointer at the current address, then add the
    offset. The final address is *not* dereferenced; it is the address whose
    value TrainerForge will read or write.
    """
    base = parse_base_expression(base_text)
    return resolve_base_chain(process, base, offsets)


def resolve_base_chain(process: Process, base: BaseExpression, offsets: list[int]) -> int:
    address = base.resolve(process)
    limit = process.address_limit
    for index, offset in enumerate(offsets):
        if address <= 0 or address > limit:
            raise PointerError(
                f"Pointer chain went outside the target's address space at level {index} "
                f"({format_hex(address)})."
            )
        try:
            pointer = process.read_pointer(address)
        except ProcessError as exc:
            raise PointerError(
                f"Could not read pointer at {format_hex(address)} (level {index}): {exc}"
            ) from exc
        if pointer == 0:
            raise PointerError(
                f"Null pointer at {format_hex(address)} (level {index}). "
                "The game may not have initialized this structure yet."
            )
        address = pointer + offset
    if address <= 0 or address > limit:
        raise PointerError(f"The pointer chain resolved outside the address space: {format_hex(address)}.")
    return address


def describe_chain(base: BaseExpression, offsets: list[int]) -> str:
    if not offsets:
        return base.describe()
    return f"{base.describe()} -> " + " -> ".join(format_hex(offset) for offset in offsets)
