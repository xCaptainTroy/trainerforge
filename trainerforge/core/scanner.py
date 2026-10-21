"""Value scanner and comparison engine.

The scanner works on snapshots of committed, readable memory obtained through
ReadProcessMemory. It does not inject code, hook APIs, or use a driver.
"""

from __future__ import annotations

import math
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Sequence

from .process import MemoryReadError, Process, Region
from .utils import human_bytes, parse_int

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
DEFAULT_MAX_RESULTS = 250_000
PAGE_SIZE = 0x1000


class ValueType(str, Enum):
    INT32 = "int32"
    INT64 = "int64"
    FLOAT = "float"
    DOUBLE = "double"

    @property
    def size(self) -> int:
        return {
            ValueType.INT32: 4,
            ValueType.INT64: 8,
            ValueType.FLOAT: 4,
            ValueType.DOUBLE: 8,
        }[self]

    @property
    def struct_format(self) -> str:
        return {
            ValueType.INT32: "<i",
            ValueType.INT64: "<q",
            ValueType.FLOAT: "<f",
            ValueType.DOUBLE: "<d",
        }[self]

    @property
    def label(self) -> str:
        return {
            ValueType.INT32: "Int32 (4 bytes)",
            ValueType.INT64: "Int64 (8 bytes)",
            ValueType.FLOAT: "Float (4 bytes)",
            ValueType.DOUBLE: "Double (8 bytes)",
        }[self]


VALUE_TYPE_LABELS = {value_type: value_type.label for value_type in ValueType}
LABEL_TO_VALUE_TYPE = {value_type.label: value_type for value_type in ValueType}


class ScanMode(str, Enum):
    EXACT = "exact"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    INCREASED = "increased"
    DECREASED = "decreased"

    @property
    def label(self) -> str:
        return {
            ScanMode.EXACT: "Exact value",
            ScanMode.CHANGED: "Changed",
            ScanMode.UNCHANGED: "Unchanged",
            ScanMode.INCREASED: "Increased",
            ScanMode.DECREASED: "Decreased",
        }[self]

    @property
    def needs_value(self) -> bool:
        return self in (ScanMode.EXACT, ScanMode.INCREASED, ScanMode.DECREASED)


SCAN_MODE_LABELS = {mode: mode.label for mode in ScanMode}
LABEL_TO_SCAN_MODE = {mode.label: mode for mode in ScanMode}


def encode_value(value: int | float, value_type: ValueType) -> bytes:
    """Encode a Python value using the little-endian target layout."""
    try:
        if value_type is ValueType.INT32:
            number = int(value)
            if not -(2**31) <= number < 2**31:
                raise ValueError("Int32 must be between -2147483648 and 2147483647.")
            return struct.pack("<i", number)
        if value_type is ValueType.INT64:
            number = int(value)
            if not -(2**63) <= number < 2**63:
                raise ValueError("Int64 is out of range.")
            return struct.pack("<q", number)
        if value_type is ValueType.FLOAT:
            return struct.pack("<f", float(value))
        if value_type is ValueType.DOUBLE:
            return struct.pack("<d", float(value))
    except (OverflowError, struct.error) as exc:
        raise ValueError(f"Cannot encode {value!r} as {value_type.label}.") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Cannot encode {value!r} as {value_type.label}: {exc}") from exc
    raise ValueError(f"Unsupported value type: {value_type}")


def decode_value(data: bytes, value_type: ValueType) -> int | float:
    return struct.unpack(value_type.struct_format, data[: value_type.size])[0]


def parse_value(text: str, value_type: ValueType) -> int | float:
    raw = str(text).strip()
    if not raw:
        raise ValueError("Enter a value to scan for.")
    if value_type in (ValueType.INT32, ValueType.INT64):
        # Allow 0x notation, but show results in decimal.
        if raw.lower().startswith(("0x", "+0x", "-0x")):
            return parse_int(raw, "value")
        try:
            return int(raw, 10)
        except ValueError as exc:
            raise ValueError(f"Enter a whole number for {value_type.label}: {text!r}") from exc
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Enter a number for {value_type.label}: {text!r}") from exc


def format_value(value: int | float, value_type: ValueType) -> str:
    if value_type in (ValueType.INT32, ValueType.INT64):
        return str(int(value))
    if math.isnan(float(value)):
        return "NaN"
    if math.isinf(float(value)):
        return "Infinity" if value > 0 else "-Infinity"
    if value_type is ValueType.FLOAT:
        return f"{float(value):.9g}"
    return f"{float(value):.17g}"


@dataclass
class ScanResult:
    address: int
    previous: bytes
    current: bytes
    value_type: ValueType

    @property
    def value(self) -> int | float:
        return decode_value(self.current, self.value_type)

    @property
    def previous_value(self) -> int | float:
        return decode_value(self.previous, self.value_type)

    @property
    def value_text(self) -> str:
        return format_value(self.value, self.value_type)

    @property
    def previous_text(self) -> str:
        return format_value(self.previous_value, self.value_type)


@dataclass
class ScanProgress:
    phase: str
    units_done: int
    units_total: int
    bytes_done: int
    bytes_total: int
    found: int = 0
    message: str = ""

    @property
    def fraction(self) -> float:
        if self.bytes_total <= 0:
            return 0.0
        return max(0.0, min(1.0, self.bytes_done / self.bytes_total))


@dataclass
class ScanSession:
    process: Process
    value_type: ValueType
    results: list[ScanResult]
    mode: str = "first"
    scanned_regions: int = 0
    scanned_bytes: int = 0
    read_errors: int = 0
    truncated: bool = False
    cancelled: bool = False
    started_at: float = field(default_factory=time.time)
    finished_at: float = field(default_factory=time.time)

    @property
    def duration(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    @property
    def count(self) -> int:
        return len(self.results)


ProgressCallback = Callable[[ScanProgress], None]
CancelCallback = Callable[[], bool]


def _should_cancel(callback: CancelCallback | None) -> bool:
    return bool(callback and callback())


def _read_chunk(process: Process, address: int, size: int) -> bytes:
    return process.read(address, size)


def first_scan(
    process: Process,
    value_type: ValueType,
    value: int | float,
    *,
    alignment: int = 4,
    writable_only: bool = True,
    regions: Sequence[Region] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> ScanSession:
    """Scan readable memory for an exact value.

    ``regions`` is primarily useful for tests and advanced callers; by default
    all committed readable regions are considered (writable-only by default).
    """
    if alignment not in (1, 2, 4, 8):
        raise ValueError("Alignment must be 1, 2, 4, or 8 bytes.")
    if max_results <= 0:
        raise ValueError("max_results must be positive.")
    pattern = encode_value(value, value_type)
    pattern_size = len(pattern)
    started = time.time()

    selected: list[Region] = []
    if regions is None:
        selected = [
            region
            for region in process.regions(writable_only=writable_only)
            if region.is_readable and region.size >= pattern_size
        ]
    else:
        selected = [
            region
            for region in regions
            if region.state == 0x1000
            and region.is_readable
            and region.size >= pattern_size
            and (not writable_only or region.is_writable)
        ]

    total_bytes = sum(region.size for region in selected)
    bytes_done = 0
    results: list[ScanResult] = []
    read_errors = 0
    truncated = False
    cancelled = False

    if progress:
        progress(
            ScanProgress(
                phase="first",
                units_done=0,
                units_total=len(selected),
                bytes_done=0,
                bytes_total=total_bytes,
                message=f"Scanning {human_bytes(total_bytes)}",
            )
        )

    for region_index, region in enumerate(selected):
        if _should_cancel(should_cancel):
            cancelled = True
            break
        offset = 0
        while offset < region.size:
            if _should_cancel(should_cancel):
                cancelled = True
                break
            chunk_size = min(DEFAULT_CHUNK_SIZE, region.size - offset)
            read_size = min(chunk_size + pattern_size - 1, region.size - offset)
            try:
                data = _read_chunk(process, region.base + offset, read_size)
            except MemoryReadError:
                read_errors += 1
                bytes_done += chunk_size
                offset += chunk_size
                continue

            limit = min(chunk_size, region.size - offset)
            search_at = 0
            while True:
                found_at = data.find(pattern, search_at)
                if found_at < 0 or found_at >= limit:
                    break
                address = region.base + offset + found_at
                if address % alignment == 0:
                    snapshot = bytes(data[found_at : found_at + pattern_size])
                    results.append(
                        ScanResult(
                            address=address,
                            previous=snapshot,
                            current=snapshot,
                            value_type=value_type,
                        )
                    )
                    if len(results) >= max_results:
                        truncated = True
                        cancelled = True
                        break
                search_at = found_at + 1

            bytes_done += limit
            offset += limit
            if progress:
                progress(
                    ScanProgress(
                        phase="first",
                        units_done=region_index,
                        units_total=len(selected),
                        bytes_done=bytes_done,
                        bytes_total=total_bytes,
                        found=len(results),
                        message=f"{len(results):,} matches",
                    )
                )
            if truncated:
                break
        if progress and not truncated:
            progress(
                ScanProgress(
                    phase="first",
                    units_done=region_index + 1,
                    units_total=len(selected),
                    bytes_done=bytes_done,
                    bytes_total=total_bytes,
                    found=len(results),
                    message=f"{len(results):,} matches",
                )
            )
        if truncated:
            break

    finished = time.time()
    if progress:
        progress(
            ScanProgress(
                phase="first",
                units_done=len(selected),
                units_total=len(selected),
                bytes_done=bytes_done,
                bytes_total=total_bytes,
                found=len(results),
                message="Cancelled" if cancelled else f"{len(results):,} matches",
            )
        )
    return ScanSession(
        process=process,
        value_type=value_type,
        results=results,
        mode="first",
        scanned_regions=len(selected),
        scanned_bytes=bytes_done,
        read_errors=read_errors,
        truncated=truncated,
        cancelled=cancelled,
        started_at=started,
        finished_at=finished,
    )


def snapshot_bytes(
    process: Process,
    addresses: Iterable[int],
    size: int,
    *,
    page_size: int = PAGE_SIZE,
) -> tuple[dict[int, bytes], int]:
    """Read values for many addresses, batching by page.

    Returns ``(values_by_address, read_error_count)``. Inaccessible pages fall
    back to individual reads so one bad page does not discard every result.
    """
    grouped: dict[int, list[int]] = {}
    for address in addresses:
        grouped.setdefault(address & ~(page_size - 1), []).append(address)

    values: dict[int, bytes] = {}
    errors = 0
    for page, page_addresses in grouped.items():
        page_data: bytes | None = None
        try:
            page_data = process.read(page, page_size)
        except MemoryReadError:
            page_data = None
        for address in page_addresses:
            offset = address - page
            if page_data is not None and offset + size <= len(page_data):
                values[address] = page_data[offset : offset + size]
                continue
            try:
                values[address] = process.read(address, size)
            except MemoryReadError:
                errors += 1
    return values, errors


def next_scan(
    session: ScanSession,
    mode: ScanMode | str,
    value: int | float | None = None,
    *,
    progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> ScanSession:
    """Filter an existing result set.

    Exact scanning compares the current bytes to the encoded target. Changed /
    unchanged compare bytes; increased / decreased compare decoded numbers.
    """
    if isinstance(mode, str) and not isinstance(mode, ScanMode):
        mode = ScanMode(mode)
    if not isinstance(mode, ScanMode):
        raise ValueError("Unknown scan mode.")
    value_type = session.value_type
    target_bytes = None
    if mode.needs_value:
        if value is None:
            raise ValueError(f"{mode.label} requires a value.")
        target_bytes = encode_value(value, value_type)

    started = time.time()
    previous_results = session.results
    pages = len({result.address & ~(PAGE_SIZE - 1) for result in previous_results})
    total_bytes = len(previous_results) * value_type.size
    bytes_done = 0
    results: list[ScanResult] = []
    read_errors = 0
    cancelled = False

    if progress:
        progress(
            ScanProgress(
                phase="next",
                units_done=0,
                units_total=pages,
                bytes_done=0,
                bytes_total=total_bytes,
                message=f"Filtering {len(previous_results):,} matches",
            )
        )

    for page_index, (page, page_results) in enumerate(
        _group_results_by_page(previous_results)
    ):
        if _should_cancel(should_cancel):
            cancelled = True
            break
        page_data: bytes | None = None
        try:
            page_data = session.process.read(page, PAGE_SIZE)
        except MemoryReadError:
            page_data = None

        for result in page_results:
            offset = result.address - page
            current: bytes | None = None
            if page_data is not None and offset + value_type.size <= len(page_data):
                current = page_data[offset : offset + value_type.size]
            else:
                try:
                    current = session.process.read(result.address, value_type.size)
                except MemoryReadError:
                    read_errors += 1
                    continue
                    # fall through only after a successful direct read
            bytes_done += value_type.size

            previous = result.current
            matches = False
            if mode is ScanMode.EXACT:
                matches = current == target_bytes
            elif mode is ScanMode.CHANGED:
                matches = current != previous
            elif mode is ScanMode.UNCHANGED:
                matches = current == previous
            elif mode in (ScanMode.INCREASED, ScanMode.DECREASED):
                try:
                    old_number = decode_value(previous, value_type)
                    new_number = decode_value(current, value_type)
                    if isinstance(old_number, float) and (
                        math.isnan(old_number) or math.isnan(new_number)
                    ):
                        matches = False
                    elif mode is ScanMode.INCREASED:
                        matches = new_number > old_number
                    else:
                        matches = new_number < old_number
                except (struct.error, ValueError):
                    matches = False

            if matches:
                results.append(
                    ScanResult(
                        address=result.address,
                        previous=previous,
                        current=current,
                        value_type=value_type,
                    )
                )

        if progress:
            progress(
                ScanProgress(
                    phase="next",
                    units_done=page_index + 1,
                    units_total=pages,
                    bytes_done=bytes_done,
                    bytes_total=total_bytes,
                    found=len(results),
                    message=f"{len(results):,} matches",
                )
            )

    finished = time.time()
    if progress:
        progress(
            ScanProgress(
                phase="next",
                units_done=pages,
                units_total=pages,
                bytes_done=bytes_done,
                bytes_total=total_bytes,
                found=len(results),
                message="Cancelled" if cancelled else f"{len(results):,} matches",
            )
        )
    return ScanSession(
        process=session.process,
        value_type=value_type,
        results=results,
        mode=mode.value,
        scanned_regions=pages,
        scanned_bytes=bytes_done,
        read_errors=read_errors,
        cancelled=cancelled,
        started_at=started,
        finished_at=finished,
    )


def _group_results_by_page(results: Sequence[ScanResult]) -> list[tuple[int, list[ScanResult]]]:
    grouped: dict[int, list[ScanResult]] = {}
    for result in results:
        grouped.setdefault(result.address & ~(PAGE_SIZE - 1), []).append(result)
    return sorted(grouped.items())


def read_value_at(process: Process, address: int, value_type: ValueType) -> int | float:
    return decode_value(process.read(address, value_type.size), value_type)
